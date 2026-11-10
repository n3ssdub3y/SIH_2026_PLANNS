"""
NWIS-Sentinel | Module 1 — live DDR ingestion server (FastAPI, internal :15006)

Upload a DDR/WCR PDF -> real OCR (ocr_worker.py) -> hybrid NLP (nlp_worker.py)
-> events in the canonical 15-key events.jsonl schema.

The heavy ML runs in two long-lived worker processes (same interpreter as this
server). OCR and NLP live in separate processes because Paddle and torch cannot
be loaded into one process, and so a long OCR job never blocks the API.

Endpoints (gateway exposes them under /module1/...):
  POST /upload            multipart PDF -> {job_id, pages, ...}
  GET  /jobs/{job_id}     progress + incremental log/tokens/entities + result
  GET  /health            engines, devices, readiness

Outputs (git-ignored):
  data/runtime/module1/uploads/<job>.pdf
  results/module1_outputs/uploads/<job>.jsonl  (+ <job>_meta.json)

Usage:  python module1/server.py --port 15006
"""
import argparse
import json
import os
import queue
import re
import subprocess
import sys
import threading
import time
import uuid
from pathlib import Path

import uvicorn
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import JSONResponse

HERE       = Path(__file__).resolve().parent
BASE_DIR   = HERE.parent                                   # NLP/nlp_task_ddr
UPLOAD_DIR = BASE_DIR / "data" / "runtime" / "module1" / "uploads"
RESULT_DIR = BASE_DIR / "results" / "module1_outputs" / "uploads"
LOGS_DIR   = BASE_DIR / "logs"
MAX_BYTES  = 100 * 1024 * 1024

sys.path.insert(0, str(HERE))
import nlp_rules  # noqa: E402

app = FastAPI(title="NWIS Module 1 — DDR ingestion")


# stdout is a log file under the gateway; on Windows that defaults to cp1252.
for _s in (sys.stdout, sys.stderr):
    try:
        if hasattr(_s, "reconfigure"):
            getattr(_s, "reconfigure")(encoding="utf-8", errors="replace")
    except Exception:                                       # noqa: BLE001
        pass


def log(msg):
    try:
        print(time.strftime("%H:%M:%S"), msg, flush=True)
    except Exception:                                       # noqa: BLE001
        pass


# ─── ML interpreter ────────────────────────────────────────────────────────
def resolve_ml_python():
    """Workers run under the same interpreter as the server (the project venv, which
    has PaddleOCR + sentence-transformers from the single requirements.txt).
    NWIS_ML_PYTHON can point them at another interpreter if ever needed."""
    env = os.environ.get("NWIS_ML_PYTHON")
    if env:
        return env, "NWIS_ML_PYTHON"
    return sys.executable, "project interpreter"


# ─── Worker process wrapper ────────────────────────────────────────────────
class Worker:
    """Long-lived JSON-lines child process; messages are routed to a handler."""

    def __init__(self, name, script, python):
        self.name, self.script, self.python = name, script, python
        self.proc: subprocess.Popen[str] | None = None
        self.ready = threading.Event()
        self.info = {}
        self.handler = None            # callable(msg) for the active job
        self.lock = threading.Lock()

    def start(self):
        LOGS_DIR.mkdir(parents=True, exist_ok=True)
        errf = open(LOGS_DIR / f"module1_{self.name}.log", "w", encoding="utf-8")
        env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUNBUFFERED="1",
                   NWIS_PARENT_PID=str(os.getpid()))
        self.proc = subprocess.Popen(
            [self.python, str(HERE / self.script)], cwd=str(HERE), env=env,
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=errf,
            text=True, encoding="utf-8", bufsize=1)
        threading.Thread(target=self._reader, daemon=True).start()
        log(f"[{self.name}] started pid={self.proc.pid} python={self.python}")

    def _reader(self):
        if self.proc is None or self.proc.stdout is None:
            return
        for line in self.proc.stdout:
            line = line.strip()
            if not line:
                continue
            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                continue
            if msg.get("type") == "ready":
                self.info = msg
                self.ready.set()
                log(f"[{self.name}] ready: {msg}")
                continue
            h = self.handler
            if h:
                try:
                    h(msg)
                except Exception as e:                      # never let one message kill the reader
                    log(f"[{self.name}] handler error: {type(e).__name__}: {e}")
        self.info = dict(self.info, dead=True)
        self.ready.set()
        rc = self.proc.poll() if self.proc is not None else None
        log(f"[{self.name}] exited rc={rc}")
        h = self.handler
        if h:
            h({"type": "error", "error": f"{self.name} process exited"})

    def alive(self):
        return self.proc is not None and self.proc.poll() is None

    def send(self, obj):
        with self.lock:
            if self.proc is None or self.proc.stdin is None:
                raise RuntimeError(f"[{self.name}] worker process not started")
            self.proc.stdin.write(json.dumps(obj) + "\n")
            self.proc.stdin.flush()


ML_PYTHON, ML_PYTHON_SRC = None, None
OCR = None
NLP = None
JOBS = {}
JOB_Q = queue.Queue()
BOOTED = threading.Event()

# token colouring (same classes as the UI's token stream)
TOK_RX = [
    ("tok-date",  re.compile(r"^\d{1,2}-[A-Za-z]{3}-\d{2,4}$|^\d{4}-\d{2}-\d{2}$|^\d{1,2}:\d{2}$")),
    ("tok-depth", re.compile(r"^\d[\d,\.]*(m|ft|mMD|mTVD|')$", re.I)),
    ("tok-num",   re.compile(r"^\d[\d,\.\-/]*(ppg|sg|bbl|psi|hrs?|klbs?|rpm|gpm|lpm|%)?$", re.I)),
    ("tok-event", re.compile(r"^(loss(es)?|lost|stuck|kick|influx|overpull|tight|jar(red)?|fish(ing)?|"
                             r"torque|lcm|cement|woc|gas|packed|drag|shut)$", re.I)),
    ("tok-form",  re.compile(r"^(granite|sandstone|shale|limestone|claystone|basalt|rhyolite|"
                             r"alluvium|volcanics?|hordaland|draupne|utsira|statfjord)$", re.I)),
]


def tokenize_for_stream(text, limit=90):
    out = []
    for w in re.findall(r"\S+", text)[:limit]:
        core = w.strip(".,;:()[]")
        cls = "tok"
        for c, rx in TOK_RX:
            if rx.match(core):
                cls = c
                break
        out.append([cls, w])
    return out


# ─── Job model ─────────────────────────────────────────────────────────────
STAGES = ["upload", "ocr", "extract", "nlp", "structured", "done"]


def new_job(filename, path, pages, size):
    jid = "m1-" + uuid.uuid4().hex[:8]
    JOBS[jid] = {
        "job_id": jid, "filename": filename, "path": str(path), "size": size,
        "status": "queued", "stage": "upload", "pct": 2.0,
        "pages_total": pages, "pages_done": 0, "chars": 0,
        "units_total": 0, "units_done": 0,
        "log": [], "tokens": [], "entities": [], "pages": [],
        "result": None, "error": None, "t0": time.time(),
        "ocr_engine": None, "ocr_device": None,
    }
    return JOBS[jid]


def jlog(job, cls, msg):
    job["log"].append([cls, msg])
    log(f"[{job['job_id']}] {msg}")


def set_pct(job):
    s = job["stage"]
    if s == "upload":
        job["pct"] = 3.0
    elif s == "ocr":
        n = max(job["pages_total"], 1)
        job["pct"] = 5.0 + 75.0 * job["pages_done"] / n
    elif s == "extract":
        job["pct"] = 81.0
    elif s == "nlp":
        n = max(job["units_total"], 1)
        job["pct"] = 82.0 + 15.0 * job["units_done"] / n
    elif s == "structured":
        job["pct"] = 98.0
    elif s == "done":
        job["pct"] = 100.0


# ─── Pipeline steps ────────────────────────────────────────────────────────
def run_ocr(job):
    job["stage"] = "ocr"
    set_pct(job)
    if OCR is None or not OCR.alive() or not OCR.info.get("engine"):
        return text_layer_fallback(job, "OCR engine unavailable")
    job["ocr_engine"], job["ocr_device"] = OCR.info["engine"], OCR.info["device"]
    jlog(job, "ok", f"[OCR]     {job['ocr_engine']} on {job['ocr_device']}")
    finished = threading.Event()

    def on_msg(m):
        t = m.get("type")
        if t == "start":
            job["pages_total"] = m["pages"]
            jlog(job, "info", f"[OCR]     Scanning {m['pages']} pages @200 dpi...")
        elif t == "page":
            job["pages"].append(m["text"])
            job["pages_done"] = m["page"]
            job["chars"] += m["chars"]
            job["tokens"].extend(tokenize_for_stream(m["text"]))
            conf = f"{m['mean_conf']:.3f}" if m.get("mean_conf") is not None else "n/a"
            jlog(job, "ok", f"[OCR]     Page {m['page']:>3}/{m['pages']} ✓ — {m['chars']:,} chars, "
                            f"{m['lines']} lines, conf {conf}, {m['ms']} ms")
            set_pct(job)
        elif t == "done":
            jlog(job, "ok", f"[OCR]     Done: {job['chars']:,} chars in {m['ms']/1000:.1f} s")
            finished.set()
        elif t == "error":
            job["error"] = m.get("error")
            finished.set()

    OCR.handler = on_msg
    try:
        OCR.send({"cmd": "ocr", "job": job["job_id"], "path": job["path"], "dpi": 200})
        finished.wait()
    finally:
        OCR.handler = None
    if job["error"]:
        jlog(job, "warn", f"[OCR]     OCR failed ({job['error']})")
        job["error"] = None
        job["pages"], job["pages_done"], job["chars"] = [], 0, 0
        return text_layer_fallback(job, "OCR failed")
    return True


def text_layer_fallback(job, why):
    import pymupdf
    job["ocr_engine"], job["ocr_device"] = "PDF text layer (no OCR)", "cpu"
    jlog(job, "warn", f"[OCR]     {why} — falling back to the PDF text layer. This is NOT OCR.")
    doc = pymupdf.open(job["path"])
    job["pages_total"] = doc.page_count
    for i, page in enumerate(doc):
        t = page.get_text()
        job["pages"].append(t)
        job["pages_done"] = i + 1
        job["chars"] += len(t)
        job["tokens"].extend(tokenize_for_stream(t))
        set_pct(job)
    if job["chars"] == 0:
        job["error"] = "No OCR engine and the PDF has no text layer"
        return False
    return True


def run_nlp(job):
    job["stage"] = "extract"
    set_pct(job)
    stem = Path(job["filename"]).stem
    if NLP is None or not NLP.alive():
        jlog(job, "warn", "[NLP]     NLP worker unavailable — keyword/regex rules only")
        from nlp_engine import HybridEngine
        eng = HybridEngine(load_models=False)
        return eng.extract_document(job["pages"], default_well=stem, source="uploaded_pdf_ocr")
    done = threading.Event()
    box = {}

    def on_msg(m):
        t = m.get("type")
        if t == "log":
            jlog(job, m.get("cls", "info"), m["msg"])
        elif t == "units":
            job["units_total"] = m["n"]
            job["stage"] = "nlp"
            set_pct(job)
        elif t == "unit":
            job["units_done"] = m["i"]
            job["entities"].extend(m.get("entities", []))
            set_pct(job)
        elif t == "result":
            box["result"] = m["result"]
            done.set()
        elif t == "error":
            box["error"] = m.get("error")
            done.set()

    NLP.handler = on_msg
    try:
        NLP.send({"cmd": "extract", "job": job["job_id"], "pages": job["pages"],
                  "default_well": stem, "source": "uploaded_pdf_ocr"})
        done.wait()
    finally:
        NLP.handler = None
    if "error" in box:
        raise RuntimeError(f"NLP worker: {box['error']}")
    return box["result"]


def finalize(job, res):
    job["stage"] = "structured"
    set_pct(job)
    recs = res["records"]
    for r in recs:                                   # schema guard
        assert tuple(r.keys()) == nlp_rules.EVENT_RECORD_KEYS, r.keys()
    haz = [r for r in recs if r["hazard"] != "none"]
    depths = [r["depth_m"] for r in recs if r["depth_m"]]
    confs = [r["confidence"] for r in recs]
    stats = {
        "pages": job["pages_total"], "chars": job["chars"],
        "tokens": len(re.findall(r"\S+", "\n".join(job["pages"]))),
        "reports": res.get("n_units", 0), "events": len(recs), "hazard_events": len(haz),
        "max_depth_m": round(max(depths), 1) if depths else None,
        "avg_confidence": round(sum(confs) / len(confs), 3) if confs else None,
        "total_npt_h": round(sum(r["npt_hours"] for r in recs), 1),
        "elapsed_s": round(time.time() - job["t0"], 1),
    }
    meta = {
        "job_id": job["job_id"], "filename": job["filename"],
        "ocr_engine": job["ocr_engine"], "ocr_device": job["ocr_device"],
        "nlp": res.get("model_info", {}), "well": res.get("well", {}), "stats": stats,
        "evidence": res.get("evidence", []),
    }
    RESULT_DIR.mkdir(parents=True, exist_ok=True)
    with open(RESULT_DIR / f"{job['job_id']}.jsonl", "w", encoding="utf-8") as f:
        for r in recs:
            f.write(json.dumps(r) + "\n")
    with open(RESULT_DIR / f"{job['job_id']}_meta.json", "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)
    jlog(job, "ok", f"[STRUCT]  events.jsonl schema: {len(recs)} records "
                    f"({len(haz)} hazard) -> results/module1_outputs/uploads/{job['job_id']}.jsonl")
    jlog(job, "ok", f"[DONE]    Pipeline complete in {stats['elapsed_s']} s.")
    job["result"] = dict(meta, records=recs)
    job["stage"], job["status"] = "done", "done"
    set_pct(job)


def job_loop():
    while True:
        jid = JOB_Q.get()
        job = JOBS[jid]
        job["status"] = "running"
        job["t0"] = time.time()
        try:
            if not BOOTED.is_set():
                jlog(job, "info", "[INIT]    Starting ML workers...")
                BOOTED.wait(timeout=180)
            if OCR is not None and not OCR.ready.is_set():
                jlog(job, "info", "[INIT]    Waiting for OCR engine to warm up...")
                OCR.ready.wait(timeout=300)
            if not run_ocr(job):
                raise RuntimeError(job["error"] or "OCR failed")
            if NLP is not None and not NLP.ready.is_set():
                jlog(job, "info", "[INIT]    Waiting for NLP models to warm up...")
                NLP.ready.wait(timeout=300)
            res = run_nlp(job)
            finalize(job, res)
        except Exception as e:                        # noqa: BLE001
            job["status"], job["stage"] = "error", "error"
            job["error"] = f"{type(e).__name__}: {e}"
            jlog(job, "warn", f"[ERROR]   {job['error']}")


# ─── HTTP API ──────────────────────────────────────────────────────────────
@app.post("/upload")
async def upload(file: UploadFile = File(...)):
    name = os.path.basename(file.filename or "upload.pdf")
    data = await file.read()
    if not data:
        raise HTTPException(400, "empty file")
    if len(data) > MAX_BYTES:
        raise HTTPException(413, "file larger than 100 MB")
    if not data[:5] == b"%PDF-":
        raise HTTPException(415, "not a PDF")
    import pymupdf
    try:
        pages = pymupdf.open(stream=data, filetype="pdf").page_count
    except Exception as e:                            # noqa: BLE001
        raise HTTPException(422, f"unreadable PDF: {e}")
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    job = new_job(name, "", pages, len(data))
    path = UPLOAD_DIR / f"{job['job_id']}.pdf"
    path.write_bytes(data)
    job["path"] = str(path)
    jlog(job, "info", f"[INIT]    PDF received: {name} ({len(data)/1024/1024:.2f} MB, {pages} pages)")
    import hashlib
    jlog(job, "ok", f"[HASH]    SHA-256: {hashlib.sha256(data).hexdigest()[:16]}...")
    JOB_Q.put(job["job_id"])
    return {"status": "accepted", "job_id": job["job_id"], "filename": name, "pages": pages,
            "queue_position": JOB_Q.qsize(),
            "ocr_engine": OCR.info.get("engine") if OCR else None,
            "ocr_device": OCR.info.get("device") if OCR else None}


@app.get("/jobs/{job_id}")
async def job_status(job_id: str, log_since: int = 0, tok_since: int = 0, ent_since: int = 0):
    job = JOBS.get(job_id)
    if not job:
        raise HTTPException(404, "unknown job")
    return JSONResponse({
        "job_id": job_id, "filename": job["filename"], "status": job["status"],
        "stage": job["stage"], "stage_index": STAGES.index(job["stage"]) if job["stage"] in STAGES else -1,
        "pct": round(job["pct"], 1), "pages_done": job["pages_done"], "pages_total": job["pages_total"],
        "chars": job["chars"], "units_done": job["units_done"], "units_total": job["units_total"],
        "ocr_engine": job["ocr_engine"], "ocr_device": job["ocr_device"],
        "elapsed_s": round(time.time() - job["t0"], 1),
        "log": job["log"][log_since:], "log_total": len(job["log"]),
        "tokens": job["tokens"][tok_since:tok_since + 400], "tok_total": len(job["tokens"]),
        "entities": job["entities"][ent_since:], "ent_total": len(job["entities"]),
        "error": job["error"], "result": job["result"] if job["status"] == "done" else None,
    })


@app.get("/health")
async def health():
    def w(x):
        if x is None:
            return {"running": False}
        return {"running": x.alive(), "ready": x.ready.is_set(), **{k: v for k, v in x.info.items() if k != "type"}}
    return {"status": "ok", "ml_python": ML_PYTHON, "ml_python_source": ML_PYTHON_SRC,
            "ocr": w(OCR), "nlp": w(NLP), "queued": JOB_Q.qsize(),
            "ready": bool(OCR and OCR.ready.is_set() and NLP and NLP.ready.is_set())}


def boot_workers():
    global ML_PYTHON, ML_PYTHON_SRC, OCR, NLP
    ML_PYTHON, ML_PYTHON_SRC = resolve_ml_python()
    log(f"ML interpreter: {ML_PYTHON} ({ML_PYTHON_SRC})")
    OCR = Worker("ocr_worker", "ocr_worker.py", ML_PYTHON)
    NLP = Worker("nlp_worker", "nlp_worker.py", ML_PYTHON)
    OCR.start()
    NLP.start()
    BOOTED.set()


@app.on_event("startup")
def _startup():
    threading.Thread(target=boot_workers, daemon=True).start()
    threading.Thread(target=job_loop, daemon=True).start()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=15006)
    a = ap.parse_args()
    uvicorn.run(app, host="127.0.0.1", port=a.port, log_level="warning")
