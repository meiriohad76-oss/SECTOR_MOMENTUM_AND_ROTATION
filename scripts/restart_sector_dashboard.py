"""Restart the Pi dashboard service non-interactively by cycling MainPID.

Supports both Streamlit (system service, Streamlit content check) and
Next.js (user service, HTTP-200-only check) via --user-service flag.
"""
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


def _systemctl(user_service: bool) -> list[str]:
    """Return base systemctl command, with --user if this is a user service."""
    return ["systemctl", "--user"] if user_service else ["systemctl"]


def _main_pid(service: str, user_service: bool = False) -> int:
    raw = _run_text(_systemctl(user_service) + ["show", service, "-p", "MainPID", "--value"])
    try:
        return int(raw)
    except ValueError:
        return 0


def _active(service: str, user_service: bool = False) -> str:
    return _run_text(_systemctl(user_service) + ["is-active", service]) or "unknown"


def _http_probe(url: str, timeout: float) -> tuple[int, str]:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            body = response.read(80_000).decode("utf-8", errors="replace")
            return int(response.status), body
    except Exception:
        return 0, ""


def _classify(status: int, body: str, require_content: bool) -> tuple[bool, str]:
    """Return (ok, state_label). For Next.js (require_content=False), HTTP 200 is sufficient."""
    if not require_content:
        if status == 200:
            return True, "http_200_ok"
        return False, f"http_{status}"
    smoke = classify_local_dashboard_response(status_code=status, text=body)
    return smoke.ok, smoke.state


def restart_and_wait(
    service: str,
    url: str,
    timeout_seconds: int,
    poll_seconds: float,
    user_service: bool = False,
    require_content: bool = True,
) -> int:
    old_pid = _main_pid(service, user_service)
    if old_pid <= 0:
        if user_service:
            # User services can be started directly (no privilege escalation needed).
            print(f"restart_action=starting_stopped_service service={service}")
            _run_text(_systemctl(user_service) + ["start", service])
        else:
            # System service with no running PID — it was likely just killed (e.g.
            # by fuser) and systemd is about to restart it via Restart=always.
            # We cannot call `sudo systemctl restart` without NOPASSWD sudo, so we
            # rely on systemd's automatic restart and just poll until the new PID
            # and HTTP 200 appear.
            print(f"restart_action=waiting_for_system_service_restart service={service}")
            # Fall through to the HTTP wait loop below.
    else:
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
        active = _active(service, user_service)
        status, body = _http_probe(url, timeout=min(5.0, poll_seconds))
        ok, content_state = _classify(status, body, require_content)
        pid = _main_pid(service, user_service)
        print(f"poll_{attempt} active={active} http={status} content={content_state} pid={pid}")
        # Primary success: new process is serving HTTP and has a new PID.
        # active=="active" is ideal but not required — a freshly started service
        # may briefly report "activating" or "inactive" while its PID is already
        # serving.  The HTTP + new-PID check is sufficient proof of liveness.
        if ok and pid > 0 and pid != old_pid:
            print(f"restart_result=healthy service={service} pid={pid} active={active} http={status} content={content_state}")
            return 0
        if not sigkill_sent and attempt >= 5 and old_pid > 0 and pid == old_pid and status == 0:
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
    ok, content_state = _classify(status, body, require_content)
    print(f"restart_result=failed service={service} active={_active(service, user_service)} http={status} content={content_state}")
    return 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--service", default="sector-dashboard")
    parser.add_argument("--url", default="http://127.0.0.1:8501/?ticker=XLK")
    parser.add_argument("--timeout-seconds", type=int, default=60)
    parser.add_argument("--poll-seconds", type=float, default=2.0)
    parser.add_argument(
        "--user-service",
        action="store_true",
        default=False,
        help="Use 'systemctl --user' (for user-scoped services). "
             "Implies --no-content-check.",
    )
    parser.add_argument(
        "--no-content-check",
        action="store_true",
        default=False,
        help="Accept HTTP 200 as healthy without checking for Streamlit page markers. "
             "Use for Next.js or any non-Streamlit service.",
    )
    args = parser.parse_args()
    return restart_and_wait(
        args.service,
        args.url,
        args.timeout_seconds,
        args.poll_seconds,
        user_service=args.user_service,
        require_content=not args.user_service and not args.no_content_check,
    )


if __name__ == "__main__":
    raise SystemExit(main())
