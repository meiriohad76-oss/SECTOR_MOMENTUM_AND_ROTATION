"""Restart the Pi Streamlit dashboard non-interactively by cycling MainPID."""
from __future__ import annotations

import argparse
import os
import signal
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.live_smoke import classify_local_dashboard_response


SIGKILL = getattr(signal, "SIGKILL", signal.SIGTERM)


def _run_text(args: list[str]) -> str:
    result = subprocess.run(args, check=False, capture_output=True, text=True, timeout=10)
    return result.stdout.strip()


def _main_pid(service: str) -> int:
    raw = _run_text(["systemctl", "show", service, "-p", "MainPID", "--value"])
    try:
        return int(raw)
    except ValueError:
        return 0


def _active(service: str) -> str:
    return _run_text(["systemctl", "is-active", service]) or "unknown"


def _http_probe(url: str, timeout: float) -> tuple[int, str]:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            body = response.read(80_000).decode("utf-8", errors="replace")
            return int(response.status), body
    except Exception:
        return 0, ""


def restart_and_wait(service: str, url: str, timeout_seconds: int, poll_seconds: float) -> int:
    old_pid = _main_pid(service)
    if old_pid <= 0:
        print(f"restart_action=no_mainpid service={service}")
        print(f"restart_result=failed_no_mainpid service={service}")
        return 1
    try:
        os.kill(old_pid, signal.SIGTERM)
        print(f"restart_action=sent_sigterm pid={old_pid} service={service}")
    except ProcessLookupError:
        print(f"restart_action=mainpid_already_exited pid={old_pid} service={service}")
    except PermissionError:
        print(f"restart_result=failed_permission pid={old_pid} service={service}")
        return 1

    deadline = time.monotonic() + timeout_seconds
    attempt = 0
    sigkill_sent = False
    while time.monotonic() < deadline:
        attempt += 1
        active = _active(service)
        status, body = _http_probe(url, timeout=min(5.0, poll_seconds))
        smoke = classify_local_dashboard_response(status_code=status, text=body)
        pid = _main_pid(service)
        print(f"poll_{attempt} active={active} http={status} content={smoke.state} pid={pid}")
        if active == "active" and smoke.ok and pid > 0 and pid != old_pid:
            print(f"restart_result=healthy service={service} pid={pid} http={status} content={smoke.state}")
            return 0
        if not sigkill_sent and attempt >= 5 and pid == old_pid and status == 0:
            try:
                os.kill(old_pid, SIGKILL)
                sigkill_sent = True
                print(f"restart_action=sent_sigkill pid={old_pid} service={service}")
            except ProcessLookupError:
                sigkill_sent = True
                print(f"restart_action=mainpid_exited_before_sigkill pid={old_pid} service={service}")
            except PermissionError:
                print(f"restart_result=failed_permission_sigkill pid={old_pid} service={service}")
                return 1
        time.sleep(poll_seconds)

    status, body = _http_probe(url, timeout=5)
    smoke = classify_local_dashboard_response(status_code=status, text=body)
    print(f"restart_result=failed service={service} active={_active(service)} http={status} content={smoke.state}")
    return 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--service", default="sector-dashboard")
    parser.add_argument("--url", default="http://127.0.0.1:8501/?ticker=XLK")
    parser.add_argument("--timeout-seconds", type=int, default=60)
    parser.add_argument("--poll-seconds", type=float, default=2.0)
    args = parser.parse_args()
    return restart_and_wait(args.service, args.url, args.timeout_seconds, args.poll_seconds)


if __name__ == "__main__":
    raise SystemExit(main())
