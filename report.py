"""Build the monthly report: a PDF for reading and an Excel file with all the detail.

    python report.py                      # last complete month in the data
    python report.py --month 2026-10      # a specific month
    python report.py --email              # also email it (settings in .env)
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import pandas as pd

from reportgen import metrics
from reportgen.data import DataError, load
from reportgen.excel import build_excel
from reportgen.pdf import build_pdf

ROOT = Path(__file__).resolve().parent


def load_env(path: Path) -> None:
    """Minimal .env reader, so no extra package is needed."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip())


def latest_complete_month(months: list) -> pd.Period:
    """The newest month in the data that has ended (today's month is skipped)."""
    this_month = pd.Timestamp.today().to_period("M")
    complete = [m for m in months if m < this_month]
    return complete[-1] if complete else months[-1]


def main(argv=None) -> int:
    load_env(ROOT / ".env")
    parser = argparse.ArgumentParser(description="Build the monthly PDF and Excel report.")
    parser.add_argument("--month", help="YYYY-MM (default: last complete month)")
    parser.add_argument("--data", type=Path, default=ROOT / "data", help="folder with the CSV files")
    parser.add_argument("--out", type=Path, default=ROOT / "reports", help="output folder")
    parser.add_argument("--company", default=os.environ.get(
        "COMPANY_NAME", "Nordlys Pharmacy (fictional demo)"))
    parser.add_argument("--email", action="store_true", help="email the report when done")
    args = parser.parse_args(argv)

    try:
        ds = load(args.data)
        month = pd.Period(args.month, freq="M") if args.month else latest_complete_month(ds.months)
        metrics.check_month(ds, month)
        folder = args.out / str(month)
        pdf = build_pdf(ds, month, folder / f"monthly_report_{month}.pdf", args.company)
        xlsx = build_excel(ds, month, folder / f"monthly_report_{month}.xlsx")
    except (DataError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print(f"Report for {month.strftime('%B %Y')}:")
    for line in metrics.highlights(ds, month):
        print("  -", line)
    print(f"\nSaved:\n  {pdf}\n  {xlsx}")

    if args.email:
        from reportgen.emailer import send_report, settings_from_env

        try:
            settings = settings_from_env()
        except ValueError as exc:
            print(f"Email not sent: {exc}", file=sys.stderr)
            return 1
        send_report(
            subject=f"{args.company} - monthly report {month.strftime('%B %Y')}",
            body="Hi,\n\nThe monthly report is attached.\n\n" +
                 "\n".join(f"- {line}" for line in metrics.highlights(ds, month)),
            attachments=[pdf, xlsx],
            settings=settings,
        )
        print(f"Emailed to {settings['REPORT_TO']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
