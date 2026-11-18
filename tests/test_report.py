"""Tests for the calculations, the PDF/Excel output and the email step."""
import sys
from pathlib import Path

import pandas as pd
import pytest
from openpyxl import load_workbook

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import report  # noqa: E402
from make_data import generate  # noqa: E402
from reportgen import metrics  # noqa: E402
from reportgen.data import DataError, prepare  # noqa: E402
from reportgen.emailer import send_report  # noqa: E402
from reportgen.excel import build_excel  # noqa: E402
from reportgen.pdf import build_pdf  # noqa: E402

OCT, SEP = pd.Period("2026-10", "M"), pd.Period("2026-09", "M")


@pytest.fixture
def small():
    """Two products, two months, numbers easy to check by hand."""
    products = pd.DataFrame({
        "sku": ["A", "B"], "product": ["Tablets", "Cream"], "category": ["Pain", "Skin"],
        "unit_cost": [10.0, 50.0], "unit_price": [20.0, 100.0], "reorder_level": [30, 10],
    })
    sales = pd.DataFrame({
        "date": ["2026-09-10", "2026-09-11", "2026-10-01", "2026-10-15", "2026-10-15"],
        "sku": ["A", "B", "A", "A", "B"],
        "quantity": [10, 1, 20, 10, 2],
        "unit_price": [20.0, 100.0, 20.0, 20.0, 100.0],
    })
    sales["revenue"] = sales["quantity"] * sales["unit_price"]
    sales["cost"] = sales["quantity"] * sales["sku"].map({"A": 10.0, "B": 50.0})
    stock = pd.DataFrame({
        "month": ["2026-10", "2026-10"], "sku": ["A", "B"], "on_hand": [5, 200],
        "nearest_expiry": ["2026-11-20", "2027-06-01"],
    })
    costs = pd.DataFrame({
        "month": ["2026-09", "2026-09", "2026-10", "2026-10"],
        "cost_type": ["Rent", "Salaries", "Rent", "Salaries"],
        "amount": [100.0, 200.0, 100.0, 300.0],
    })
    return prepare(products, sales, stock, costs)


@pytest.fixture(scope="module")
def sample():
    tables = generate("2025-09-01", "2026-10-31", seed=1)
    return prepare(**tables)


# ----------------------------------------------------------- calculations
def test_figures_add_up(small):
    f = metrics.figures(small, OCT)
    assert f["revenue"] == 30 * 20 + 2 * 100          # 800
    assert f["gross_profit"] == 800 - (30 * 10 + 2 * 50)  # 400
    assert f["gross_margin"] == pytest.approx(0.5)
    assert f["operating_costs"] == 400
    assert f["net_profit"] == 0


def test_summary_compares_with_previous_month(small):
    s = metrics.summary(small, OCT)
    assert s["previous"]["revenue"] == 10 * 20 + 100   # 300
    assert s["last_year"]["has_data"] is False


def test_pct_change_handles_missing_base():
    assert metrics.pct_change(110, 100) == pytest.approx(0.10)
    assert metrics.pct_change(5, 0) is None
    assert metrics.pct_change(5, None) is None


def test_daily_revenue_includes_days_without_sales(small):
    daily = metrics.daily_revenue(small, OCT)
    assert len(daily) == 31
    assert daily.loc["2026-10-15"] == 10 * 20 + 2 * 100
    assert daily.loc["2026-10-02"] == 0


def test_category_change(small):
    cats = metrics.by_category(small, OCT).set_index("category")
    assert cats.loc["Pain", "revenue"] == 600
    assert cats.loc["Pain", "change"] == pytest.approx(2.0)   # 200 -> 600
    assert cats["share"].sum() == pytest.approx(1.0)


def test_reorder_suggestion(small):
    status = metrics.stock_status(small, OCT).set_index("sku")
    # A: 30 sold in October (~0.97/day). 5 in stock < reorder level 30.
    assert bool(status.loc["A", "below_reorder"])
    # Order up to max(30 days of sales = 30, 2 x reorder level = 60) -> 60 - 5.
    assert status.loc["A", "suggested_order"] == 55
    assert status.loc["B", "suggested_order"] == 0


def test_expiring_and_overstock(small):
    status = metrics.stock_status(small, OCT)
    assert metrics.expiring(status)["sku"].tolist() == ["A"]      # 20 days to expiry
    assert metrics.overstock(status)["sku"].tolist() == ["B"]     # 200 in stock, 2 sold


def test_costs_by_type(small):
    costs = metrics.costs_by_type(small, OCT).set_index("cost_type")
    assert costs.loc["Salaries", "change"] == pytest.approx(0.5)
    assert costs.loc["Rent", "change"] == pytest.approx(0.0)


def test_highlights_mention_key_facts(small):
    text = " ".join(metrics.highlights(small, OCT))
    assert "NOK 800" in text and "below their reorder level" in text
    assert "Salaries costs rose 50.0%" in text


def test_unknown_month_is_rejected(small):
    with pytest.raises(DataError, match="No sales data for 2024-01"):
        metrics.check_month(small, pd.Period("2024-01", "M"))


def test_missing_column_is_reported(small):
    with pytest.raises(DataError, match="missing column"):
        prepare(small.products.drop(columns="reorder_level"), small.sales,
                small.stock, small.costs)


def test_sales_for_unknown_product_is_rejected(small):
    sales = small.sales.copy()
    sales.loc[0, "sku"] = "ZZZ"
    with pytest.raises(DataError, match="not in products"):
        prepare(small.products, sales, small.stock, small.costs)


# ---------------------------------------------------------------- outputs
def test_pdf_and_excel_are_built(sample, tmp_path):
    pdf = build_pdf(sample, OCT, tmp_path / "r.pdf", "Test Pharmacy")
    xlsx = build_excel(sample, OCT, tmp_path / "r.xlsx")
    assert pdf.read_bytes()[:4] == b"%PDF"
    sheets = load_workbook(xlsx).sheetnames
    assert sheets[:3] == ["Summary", "Highlights", "Categories"]
    assert "Reorder list" in sheets and "12-month trend" in sheets


def test_command_line_builds_reports(tmp_path):
    data = tmp_path / "data"
    data.mkdir()
    for name, df in generate("2026-08-01", "2026-10-31", seed=3).items():
        df.to_csv(data / f"{name}.csv", index=False)
    out = tmp_path / "reports"
    assert report.main(["--data", str(data), "--out", str(out), "--month", "2026-10"]) == 0
    assert (out / "2026-10" / "monthly_report_2026-10.pdf").exists()
    assert (out / "2026-10" / "monthly_report_2026-10.xlsx").exists()
    assert report.main(["--data", str(data), "--out", str(out), "--month", "2020-01"]) == 1


def test_latest_complete_month_skips_current_month():
    this_month = pd.Timestamp.today().to_period("M")
    assert report.latest_complete_month([this_month - 2, this_month - 1, this_month]) == this_month - 1


# ------------------------------------------------------------------ email
class FakeSMTP:
    sent = []

    def __init__(self, host, port, timeout):
        self.host, self.port = host, port

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def starttls(self):
        pass

    def login(self, user, password):
        self.user = user

    def send_message(self, msg):
        FakeSMTP.sent.append(msg)


def test_email_has_both_attachments(tmp_path):
    pdf, xlsx = tmp_path / "r.pdf", tmp_path / "r.xlsx"
    pdf.write_bytes(b"%PDF-1.4")
    xlsx.write_bytes(b"PK")
    settings = {"SMTP_HOST": "smtp.example.com", "SMTP_PORT": 587, "SMTP_USER": "me",
                "SMTP_PASSWORD": "x", "REPORT_FROM": "me@example.com",
                "REPORT_TO": "boss@example.com, finance@example.com"}
    send_report("Monthly report", "Attached.", [pdf, xlsx], settings, smtp_class=FakeSMTP)
    msg = FakeSMTP.sent[-1]
    assert msg["To"] == "boss@example.com, finance@example.com"
    assert [a.get_filename() for a in msg.iter_attachments()] == ["r.pdf", "r.xlsx"]
