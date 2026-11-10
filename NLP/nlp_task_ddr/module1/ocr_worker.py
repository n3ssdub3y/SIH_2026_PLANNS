"""
Module 1 — OCR worker (long-lived, JSON-lines over stdin/stdout).

Kept in its own process because Paddle and torch (nlp_worker.py) cannot be
loaded into the same process.

Engine: PaddleOCR 2.7.x (PP-OCRv4 det/rec + angle classifier) on the GPU when
Paddle is CUDA-built and a GPU is visible, otherwise on the CPU. If PaddleOCR
cannot load, the worker reports engine=None and the server falls back to the
PDF text layer (clearly labelled "NOT OCR" in the UI).

Protocol
  stdin : {"cmd":"ocr","job":"<id>","path":"<pdf>","dpi":200}
          {"cmd":"ping"}
  stdout: {"type":"ready","engine":...,"device":...}
          {"type":"start","job":..,"pages":N}
          {"type":"page","job":..,"page":i,"pages":N,"text":..,"chars":..,
           "lines":..,"mean_conf":..,"text_layer_chars":..,"ms":..}
          {"type":"done","job":..,"ms":..}
          {"type":"error","job":..,"error":..}
Only JSON is ever written to the real stdout: fd 1 is redirected to stderr at
start-up so native library chatter cannot corrupt the protocol.
"""
import json
import os
import sys
import time
import traceback

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from worker_common import protocol_channel, start_parent_watchdog  # noqa: E402

# ── protect the protocol channel; die with the server ─────────────────────
emit = protocol_channel()
start_parent_watchdog()


def _register_nvidia_dlls():
    """paddlepaddle-gpu on Windows loads cuDNN 8 / cuBLAS 11 at the first GPU call.
    requirements.txt installs them as pip wheels (nvidia-cudnn-cu11, nvidia-cublas-cu11,
    nvidia-cuda-nvrtc-cu11) under site-packages/nvidia/*/bin, which is not on the DLL
    search path, so add those folders (no system CUDA install needed)."""
    if os.name != "nt":
        return
    for base in sys.path:
        nv = os.path.join(base, "nvidia")
        if not os.path.isdir(nv):
            continue
        for pkg in os.listdir(nv):
            b = os.path.join(nv, pkg, "bin")
            if os.path.isdir(b):
                os.environ["PATH"] = b + os.pathsep + os.environ.get("PATH", "")
                try:
                    os.add_dll_directory(b)
                except (OSError, AttributeError):
                    pass


def load_engine():
    """Return (callable(img)->[(box, text, conf)], engine_name, device)."""
    _register_nvidia_dlls()
    try:
        import paddle  # type: ignore[import-not-found]
        from paddleocr import PaddleOCR  # type: ignore[import-not-found]
        import paddleocr  # type: ignore[import-not-found]
        gpu = paddle.device.is_compiled_with_cuda() and paddle.device.cuda.device_count() > 0
        ocr = PaddleOCR(use_angle_cls=True, lang="en", use_gpu=gpu, show_log=False)
        device = f"gpu:{paddle.device.cuda.get_device_name(0)}" if gpu else "cpu"

        def run(img):
            res = ocr.ocr(img, cls=True)
            page = res[0] if res and res[0] else []
            return [(b, t, float(c)) for b, (t, c) in page]
        return run, f"PaddleOCR {paddleocr.__version__} (PP-OCRv4)", device
    except Exception as e:                          # noqa: BLE001
        print(f"[ocr_worker] PaddleOCR unavailable: {e}", file=sys.stderr)
    return None, None, None


def reading_order(items):
    """Group OCR boxes into text lines (top-to-bottom, left-to-right)."""
    if not items:
        return []
    boxes = []
    for box, text, conf in items:
        ys = [p[1] for p in box]
        xs = [p[0] for p in box]
        boxes.append({"y": (min(ys) + max(ys)) / 2, "h": max(ys) - min(ys),
                      "x": min(xs), "text": text, "conf": conf})
    boxes.sort(key=lambda b: (b["y"], b["x"]))
    heights = sorted(b["h"] for b in boxes)
    tol = max(4.0, 0.5 * heights[len(heights) // 2])
    lines, cur = [], [boxes[0]]
    for b in boxes[1:]:
        if abs(b["y"] - cur[-1]["y"]) <= tol:
            cur.append(b)
        else:
            lines.append(cur)
            cur = [b]
    lines.append(cur)
    return [" ".join(b["text"] for b in sorted(line, key=lambda b: b["x"])) for line in lines]


def ocr_pdf(run, job, path, dpi):
    try:
        import pymupdf as fitz
    except ImportError:                              # PyMuPDF < 1.24
        import fitz
    import numpy as np
    t_job = time.time()
    doc = fitz.open(path)
    n = doc.page_count
    emit({"type": "start", "job": job, "pages": n})
    for i, page in enumerate(doc):
        t0 = time.time()
        pix = page.get_pixmap(dpi=dpi, alpha=False)
        img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
        if pix.n == 1:
            img = np.repeat(img, 3, axis=2)
        img = np.ascontiguousarray(img[:, :, :3][:, :, ::-1])     # RGB -> BGR
        items = run(img)
        lines = reading_order(items)
        text = "\n".join(lines)
        confs = [c for *_, c in items]
        emit({"type": "page", "job": job, "page": i + 1, "pages": n,
              "text": text, "chars": len(text), "lines": len(lines),
              "mean_conf": round(sum(confs) / len(confs), 4) if confs else None,
              "text_layer_chars": len(str(page.get_text()).strip()),
              "ms": int((time.time() - t0) * 1000)})
    emit({"type": "done", "job": job, "ms": int((time.time() - t_job) * 1000)})


def main():
    run, engine, device = load_engine()
    emit({"type": "ready", "engine": engine, "device": device, "python": sys.version.split()[0]})
    for raw in sys.stdin:
        raw = raw.strip()
        if not raw:
            continue
        try:
            msg = json.loads(raw)
        except json.JSONDecodeError:
            continue
        cmd = msg.get("cmd")
        if cmd == "ping":
            emit({"type": "pong", "engine": engine, "device": device})
        elif cmd == "ocr":
            job = msg.get("job")
            if run is None:
                emit({"type": "error", "job": job, "error": "no OCR engine available"})
                continue
            try:
                ocr_pdf(run, job, msg["path"], int(msg.get("dpi", 200)))
            except Exception as e:                  # noqa: BLE001
                traceback.print_exc()
                emit({"type": "error", "job": job, "error": f"{type(e).__name__}: {e}"})
        elif cmd == "quit":
            break


if __name__ == "__main__":
    main()
