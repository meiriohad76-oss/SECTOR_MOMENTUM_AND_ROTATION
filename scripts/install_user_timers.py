"""Install and verify non-sudo user timers for Pi operations."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
USER_UNIT_SOURCE_DIR = ROOT / "systemd" / "user"
DEFAULT_USER_UNIT_DIR = Path.home() / ".config" / "systemd" / "user"
DEFAULT_TIMERS = (
    "sector-transition-feeds.timer",
    "sector-massive-provider-snapshots.timer",
    "sector-provider-flow-cache.timer",
    "sector-dashboard-state-refresh.timer",
    "sector-rendered-dashboard-smoke.timer",
)


def _run_systemctl(args: list[str]) -> tuple[int, str]:
    completed = subprocess.run(
        ["systemctl", "--user", *args],
        capture_output=True,
        text=True,
        check=False,
    )
    output = (completed.stdout or completed.stderr or "").strip()
    return int(completed.returncode), output


def _service_for_timer(timer: str) -> str:
    if not timer.endswith(".timer"):
        raise ValueError(f"timer must end with .timer: {timer}")
    return timer.removesuffix(".timer") + ".service"


def _rewrite_unit_paths(text: str, repo_root: Path) -> str:
    return text.replace("%h/SECTOR_MOMENTUM_AND_ROTATION", str(repo_root))


def _copy_unit(name: str, *, repo_root: Path, user_unit_dir: Path, dry_run: bool) -> dict[str, object]:
    source = USER_UNIT_SOURCE_DIR / name
    target = user_unit_dir / name
    if not source.exists():
        return {"unit": name, "copied": False, "error": "source_missing"}
    if dry_run:
        return {"unit": name, "copied": False, "target": str(target), "dry_run": True}
    user_unit_dir.mkdir(parents=True, exist_ok=True)
    text = _rewrite_unit_paths(source.read_text(encoding="utf-8"), repo_root)
    target.write_text(text, encoding="utf-8")
    return {"unit": name, "copied": True, "target": str(target)}


def _timer_status(timer: str) -> dict[str, object]:
    enabled_code, enabled = _run_systemctl(["is-enabled", timer])
    active_code, active = _run_systemctl(["is-active", timer])
    result_code, result = _run_systemctl(["show", _service_for_timer(timer), "-p", "Result", "--value"])
    exit_code, exit_status = _run_systemctl(
        ["show", _service_for_timer(timer), "-p", "ExecMainStatus", "--value"]
    )
    return {
        "timer": timer,
        "enabled": enabled,
        "active": active,
        "last_service_result": result if result_code == 0 else "unknown",
        "last_service_exit_status": exit_status if exit_code == 0 else "unknown",
        "ok": enabled_code == 0 and enabled in {"enabled", "enabled-runtime"} and active_code == 0 and active == "active",
    }


def _install_timer(timer: str, *, repo_root: Path, user_unit_dir: Path, dry_run: bool) -> dict[str, object]:
    service = _service_for_timer(timer)
    copy_results = [
        _copy_unit(service, repo_root=repo_root, user_unit_dir=user_unit_dir, dry_run=dry_run),
        _copy_unit(timer, repo_root=repo_root, user_unit_dir=user_unit_dir, dry_run=dry_run),
    ]
    if dry_run:
        return {
            "timer": timer,
            "service": service,
            "units": copy_results,
            "enabled": "dry_run",
            "active": "dry_run",
            "ok": True,
        }
    missing = [row for row in copy_results if row.get("error")]
    if missing:
        return {"timer": timer, "service": service, "units": copy_results, "ok": False}
    reload_code, reload_output = _run_systemctl(["daemon-reload"])
    enable_code, enable_output = _run_systemctl(["enable", "--now", timer])
    status = _timer_status(timer)
    return {
        "timer": timer,
        "service": service,
        "units": copy_results,
        "daemon_reload": {"exit_code": reload_code, "output": reload_output},
        "enable_now": {"exit_code": enable_code, "output": enable_output},
        **status,
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--timer",
        action="append",
        default=[],
        help="User timer to install. Repeatable. Defaults to operational non-secret timers.",
    )
    parser.add_argument("--repo-root", default=str(ROOT), help="Repo checkout path to bake into copied unit files.")
    parser.add_argument("--user-systemd-dir", default=str(DEFAULT_USER_UNIT_DIR))
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    timers = tuple(dict.fromkeys(args.timer or DEFAULT_TIMERS))
    repo_root = Path(args.repo_root).resolve()
    user_unit_dir = Path(args.user_systemd_dir)
    results = [
        _install_timer(timer, repo_root=repo_root, user_unit_dir=user_unit_dir, dry_run=args.dry_run)
        for timer in timers
    ]
    payload = {
        "repo_root": str(repo_root),
        "user_systemd_dir": str(user_unit_dir),
        "dry_run": bool(args.dry_run),
        "timers": results,
    }
    print(json.dumps(payload, sort_keys=True))
    return 0 if all(row.get("ok") for row in results) else 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
