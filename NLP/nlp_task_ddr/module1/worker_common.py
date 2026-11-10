"""
Shared plumbing for the Module 1 JSON-lines workers (stdlib only).

- protocol_channel(): keep the real stdout for JSON only; native library
  chatter on fd 1 is redirected to stderr (the worker's log file).
- start_parent_watchdog(): exit when the server that spawned us dies, so a
  killed server never leaves a worker holding the GPU. (On Windows,
  os.kill(pid, 0) would *terminate* the process, so Win32 APIs are used.)
"""
import json
import os
import sys
import threading
import time


def protocol_channel():
    proto_fd = os.dup(1)
    os.dup2(2, 1)
    sys.stdout = sys.stderr
    proto = os.fdopen(proto_fd, "w", encoding="utf-8", buffering=1)

    def emit(obj):
        try:
            proto.write(json.dumps(obj, ensure_ascii=False) + "\n")
            proto.flush()
        except (OSError, ValueError):            # server gone (broken pipe)
            os._exit(0)
    return emit


def _alive(pid):
    if os.name == "nt":
        import ctypes
        k32 = ctypes.windll.kernel32
        h = k32.OpenProcess(0x1000, False, pid)          # PROCESS_QUERY_LIMITED_INFORMATION
        if not h:
            return False
        code = ctypes.c_ulong()
        ok = k32.GetExitCodeProcess(h, ctypes.byref(code))
        k32.CloseHandle(h)
        return bool(ok) and code.value == 259            # STILL_ACTIVE
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def start_parent_watchdog(interval=2.0):
    pid = int(os.environ.get("NWIS_PARENT_PID", "0") or 0)
    if not pid:
        return

    def watch():
        while True:
            time.sleep(interval)
            if not _alive(pid):
                print(f"[worker] parent {pid} gone - exiting", file=sys.stderr)
                os._exit(0)
    threading.Thread(target=watch, daemon=True).start()
