"""
Module 1 — NLP worker (long-lived, JSON-lines over stdin/stdout).

Keeps the hybrid engine's models warm (nlp_engine.HybridEngine) under the ML
interpreter, in a process separate from Paddle (ocr_worker.py).

Protocol
  stdin : {"cmd":"extract","job":..,"pages":[str,...],"default_well":..,"source":..}
  stdout: {"type":"ready","mode":..,"semantic_model":..,"field_extraction":..,"device":..}
          {"type":"log","cls":"info|ok|warn","msg":..}
          {"type":"units","job":..,"n":N}
          {"type":"unit","job":..,"i":i,"n":N,"entities":[{tag,cls,val,conf},...]}
          {"type":"result","job":..,"result":{records,evidence,well,n_units,model_info}}
          {"type":"error","job":..,"error":..}
"""
import json
import os
import sys
import traceback

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from worker_common import protocol_channel, start_parent_watchdog  # noqa: E402

emit = protocol_channel()
start_parent_watchdog()


def main():
    from nlp_engine import HybridEngine
    eng = HybridEngine(load_models=True, log=lambda m: print(m, file=sys.stderr))
    emit(dict(type="ready", **eng.model_info()))
    for raw in sys.stdin:
        raw = raw.strip()
        if not raw:
            continue
        try:
            msg = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if msg.get("cmd") == "quit":
            break
        if msg.get("cmd") != "extract":
            continue
        job = msg.get("job")

        def progress(kind, **kw):
            if kind == "log":
                emit({"type": "log", "job": job, "cls": kw.get("cls", "info"), "msg": kw["msg"]})
            elif kind == "units":
                emit({"type": "units", "job": job, "n": kw["n"]})
            elif kind == "unit":
                emit({"type": "unit", "job": job, "i": kw["i"], "n": kw["n"],
                      "entities": kw.get("entities", [])})

        try:
            res = eng.extract_document(msg["pages"], default_well=msg.get("default_well", "UPLOAD"),
                                       source=msg.get("source", "uploaded_pdf_ocr"), progress=progress)
            emit({"type": "result", "job": job, "result": res})
        except Exception as e:                       # noqa: BLE001
            traceback.print_exc()
            emit({"type": "error", "job": job, "error": f"{type(e).__name__}: {e}"})


if __name__ == "__main__":
    main()
