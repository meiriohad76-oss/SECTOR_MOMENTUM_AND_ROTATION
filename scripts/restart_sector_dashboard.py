"""Restart the Pi Streamlit dashboard non-interactively by cycling MainPID."""
from __future__ import annotations

import argparse
import os
import signal
import subprocess
import time
import urllib.request


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


def _http_status(url: str, timeout: float) -> int:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            return int(response.status)
    except Exception:
        return 0


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
    while time.monotonic() < deadline:
        attempt += 1
        active = _active(service)
        status = _http_status(url, timeout=min(5.0, poll_seconds))
        pid = _main_pid(service)
        print(f"poll_{attempt} active={active} http={status} pid={pid}")
        if active == "active" and status == 200 and pid > 0 and pid != old_pid:
            print(f"restart_result=healthy service={service} pid={pid} http={status}")
            return 0
        time.sleep(poll_seconds)

    print(f"restart_result=failed service={service} active={_active(service)} http={_http_status(url, timeout=5)}")
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
