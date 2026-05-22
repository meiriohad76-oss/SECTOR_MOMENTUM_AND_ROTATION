from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
import sys

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.evidence_gates import evaluate_promotion_gate, format_evidence_gate_report


FRED_VALIDATION_SUMMARY_PATH = ROOT / "docs" / "fred_macro_validation_summary.csv"
MASSIVE_VALIDATION_SUMMARY_PATH = ROOT / "docs" / "massive_provider_validation_summary.csv"
FRED_VALIDATION_REPORT_PATH = ROOT / "docs" / "fred_macro_validation_report.md"
MASSIVE_VALIDATION_REPORT_PATH = ROOT / "docs" / "massive_provider_validation_report.md"
EVIDENCE_GATE_REPORT_PATH = ROOT / "docs" / "evidence_gate_report.md"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Evaluate fail-closed B-158/B-160 evidence gates.")
    parser.add_argument(
        "--output",
        default=str(EVIDENCE_GATE_REPORT_PATH),
        help=f"Output Markdown report path (default: {EVIDENCE_GATE_REPORT_PATH}).",
    )
    return parser


def _read_validation_summary(path: str | Path) -> pd.DataFrame:
    source = Path(path)
    if not source.exists():
        return pd.DataFrame()
    return pd.read_csv(source)


def _path_label(path: str | Path) -> str:
    source = Path(path)
    try:
        return source.relative_to(ROOT).as_posix()
    except ValueError:
        return source.as_posix()


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv or [])
    fred = evaluate_promotion_gate(
        ticket="B-158",
        source="FRED macro",
        summary=_read_validation_summary(FRED_VALIDATION_SUMMARY_PATH),
        validation_report_path=_path_label(FRED_VALIDATION_REPORT_PATH),
    )
    massive = evaluate_promotion_gate(
        ticket="B-160",
        source="Massive provider data",
        summary=_read_validation_summary(MASSIVE_VALIDATION_SUMMARY_PATH),
        validation_report_path=_path_label(MASSIVE_VALIDATION_REPORT_PATH),
    )
    report = format_evidence_gate_report(
        [fred, massive],
        generated_at_utc=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    )
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(report, encoding="utf-8")
    print(f"Wrote {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
