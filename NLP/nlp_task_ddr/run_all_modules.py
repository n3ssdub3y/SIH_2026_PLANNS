"""
NWIS-Sentinel | SIH 2026 | PS SIH26121
Run every module from one command, straight from your IDE terminal.

    python run_all_modules.py                 # from NLP/nlp_task_ddr
    python NLP/nlp_task_ddr/run_all_modules.py   # or from the repo root
    python run_all_modules.py --speed 5.0 --no-browser --port 5000

What it does: starts gateway.py, which launches Modules 1-5 (and Module 1's OCR and
NLP workers) as child processes and serves them all on one port (default 5000).
Output of the gateway is shown live in this terminal; each module also logs to
logs/<module>.log. Press Ctrl+C once to stop everything.

Interpreter: uses the Python you ran this with (e.g. your activated venv). If that
Python is missing the web dependencies and the repo's `.venv` exists, `.venv` is
used instead. Install everything with:  pip install -r requirements.txt  (Python 3.10/3.11).
"""
import subprocess
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent              # NLP/nlp_task_ddr
REPO_DIR = BASE_DIR.parent.parent


def _has_deps(python):
    r = subprocess.run([str(python), "-c", "import fastapi, uvicorn, flask"],
                       capture_output=True, cwd=str(BASE_DIR))
    return r.returncode == 0


def pick_python():
    if _has_deps(sys.executable):
        return sys.executable
    venv_py = REPO_DIR / (".venv/Scripts/python.exe" if sys.platform == "win32" else ".venv/bin/python")
    if venv_py.exists() and _has_deps(venv_py):
        print(f"[run_all_modules] {sys.executable} lacks the dependencies; using {venv_py}")
        return str(venv_py)
    sys.exit("Dependencies are missing. Create a Python 3.10/3.11 venv and run:\n"
             "    pip install -r requirements.txt\n"
             "(or just double-click start_all.bat, which does this for you)")


def main():
    python = pick_python()
    cmd = [python, str(BASE_DIR / "gateway.py"), *sys.argv[1:]]
    proc = subprocess.Popen(cmd, cwd=str(BASE_DIR))
    try:
        sys.exit(proc.wait())
    except KeyboardInterrupt:
        # Ctrl+C is delivered to the whole console group, so the gateway is already
        # shutting its modules down; give it time to finish.
        print("\n[run_all_modules] Ctrl+C - stopping all modules...")
        try:
            proc.wait(timeout=20)
        except (subprocess.TimeoutExpired, KeyboardInterrupt):
            proc.terminate()
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
        sys.exit(0)


if __name__ == "__main__":
    main()
