"""Builds the monthly PDF report with fpdf2."""
from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Optional, Sequence

import pandas as pd
from fpdf import FPDF
from fpdf.enums import XPos, YPos
from PIL import Image

from . import charts, metrics
from .data import Dataset

PRIMARY = (15, 118, 110)
INK = (31, 41, 55)
MUTED = (107, 114, 128)
LINE = (229, 231, 235)
ZEBRA = (243, 244, 246)
GREEN = (21, 128, 61)
RED = (185, 28, 28)
WIDTH = 180  # usable page width in mm (A4 minus margins)
MAX_ROWS = 12


def _change_color(change: Optional[float], higher_is_good: bool = True):
    if change is None or abs(change) < 0.0005:
        return MUTED
    return GREEN if (change > 0) == higher_is_good else RED


class MonthlyReport(FPDF):
    def __init__(self, company: str, month: pd.Period) -> None:
        super().__init__(orientation="P", unit="mm", format="A4")
        self.company, self.month = company, month
        self.set_margins(15, 30, 15)
        self.set_auto_page_break(True, margin=18)
        self.set_title(f"{company} - monthly report {month}")
        self.set_author(company)

    # ------------------------------------------------------------ frame
    def header(self) -> None:
        self.set_fill_color(*PRIMARY)
        self.rect(0, 0, 210, 20, style="F")
        self.set_xy(15, 6)
        self.set_text_color(255, 255, 255)
        self.set_font("Helvetica", "B", 13)
        self.cell(110, 8, self.company)
        self.set_font("Helvetica", "", 10)
        self.cell(70, 8, f"Monthly report | {self.month.strftime('%B %Y')}", align="R")
        self.set_xy(15, 30)

    def footer(self) -> None:
        self.set_y(-12)
        self.set_font("Helvetica", "", 7.5)
        self.set_text_color(*MUTED)
        self.cell(WIDTH / 2, 5, f"Generated automatically on {date.today():%d %B %Y}")
        self.cell(WIDTH / 2, 5, f"Page {self.page_no()} of {{nb}}", align="R")

    # ---------------------------------------------------------- helpers
    def section(self, title: str, note: str = "", keep_mm: float = 30) -> None:
        """Section title. Starts a new page unless title + keep_mm of content fit here."""
        if self.get_y() + 12 + keep_mm > 279:
            self.add_page()
        self.ln(2)
        self.set_text_color(*INK)
        self.set_font("Helvetica", "B", 12)
        self.cell(WIDTH, 7, title, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        if note:
            self.set_font("Helvetica", "", 8.5)
            self.set_text_color(*MUTED)
            self.multi_cell(WIDTH, 4.5, note, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.ln(1.5)

    def chart(self, png) -> None:
        width_px, height_px = Image.open(png).size
        png.seek(0)
        h = WIDTH * height_px / width_px
        if self.get_y() + h > 279:
            self.add_page()
        self.image(png, x=15, y=self.get_y(), w=WIDTH)
        self.set_y(self.get_y() + h + 2)

    def table(self, columns: Sequence[tuple], rows: Sequence[Sequence],
              colors: Optional[Sequence[Sequence]] = None) -> None:
        """columns: (header, width_mm, align). colors: optional RGB per cell or None."""
        self.set_font("Helvetica", "B", 8.5)
        self.set_fill_color(*PRIMARY)
        self.set_text_color(255, 255, 255)
        for header, width, align in columns:
            self.cell(width, 6.5, header, align=align, fill=True)
        self.ln()
        self.set_font("Helvetica", "", 8.5)
        for r, row in enumerate(rows):
            if self.get_y() > 272:
                self.add_page()
            self.set_fill_color(*(ZEBRA if r % 2 else (255, 255, 255)))
            for c, (value, (_, width, align)) in enumerate(zip(row, columns)):
                color = colors[r][c] if colors and colors[r][c] else INK
                self.set_text_color(*color)
                text = str(value)
                while self.get_string_width(text) > width - 2 and len(text) > 4:
                    text = text[:-4] + "..."
                self.cell(width, 6, text, align=align, fill=True)
            self.ln()
        self.set_draw_color(*LINE)
        self.line(15, self.get_y(), 15 + WIDTH, self.get_y())
        self.ln(2)

    def more_rows_note(self, total: int, shown: int) -> None:
        if total > shown:
            self.set_font("Helvetica", "I", 8)
            self.set_text_color(*MUTED)
            self.cell(WIDTH, 5, f"+ {total - shown} more rows in the Excel file.",
                      new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    def kpi_cards(self, cards: list) -> None:
        gap = 3
        w = (WIDTH - gap * (len(cards) - 1)) / len(cards)
        top = self.get_y()
        for i, card in enumerate(cards):
            x = 15 + i * (w + gap)
            self.set_fill_color(*ZEBRA)
            self.rect(x, top, w, 27, style="F")
            self.set_fill_color(*PRIMARY)
            self.rect(x, top, 1.2, 27, style="F")
            self.set_xy(x + 3, top + 2.5)
            self.set_font("Helvetica", "", 7.5)
            self.set_text_color(*MUTED)
            self.cell(w - 4, 4, card["label"].upper())
            self.set_xy(x + 3, top + 7.5)
            self.set_font("Helvetica", "B", 10.5)
            self.set_text_color(*INK)
            self.cell(w - 4, 6, card["value"])
            for j, (label, text, color) in enumerate(card["changes"]):
                self.set_xy(x + 3, top + 15 + j * 5)
                self.set_font("Helvetica", "", 7.5)
                self.set_text_color(*MUTED)
                self.cell(13, 4, label)
                self.set_font("Helvetica", "B", 7.5)
                self.set_text_color(*color)
                self.cell(w - 17, 4, text)
        self.set_y(top + 31)


# ---------------------------------------------------------------- pages
def _summary_cards(s: dict, month: pd.Period) -> list:
    cur, prev, ly = s["current"], s["previous"], s["last_year"]
    prev_label = (month - 1).strftime("vs %b")
    ly_label = (month - 12).strftime("vs %b %y")

    def money_card(label, key, higher_is_good=True):
        changes = []
        for lbl, other in ((prev_label, prev), (ly_label, ly)):
            ch = metrics.pct_change(cur[key], other[key]) if other["has_data"] else None
            changes.append((lbl, metrics.pct(ch), _change_color(ch, higher_is_good)))
        return {"label": label, "value": metrics.nok(cur[key]), "changes": changes}

    margin_changes = []
    for lbl, other in ((prev_label, prev), (ly_label, ly)):
        if other["has_data"]:
            pp = (cur["gross_margin"] - other["gross_margin"]) * 100
            margin_changes.append((lbl, f"{pp:+.1f} pp", _change_color(pp / 100)))
        else:
            margin_changes.append((lbl, "n/a", MUTED))
    return [
        money_card("Revenue", "revenue"),
        money_card("Gross profit", "gross_profit"),
        {"label": "Gross margin", "value": metrics.pct(cur["gross_margin"], signed=False),
         "changes": margin_changes},
        money_card("Operating costs", "operating_costs", higher_is_good=False),
        money_card("Net profit", "net_profit"),
    ]


def _page_summary(pdf: MonthlyReport, ds: Dataset, month: pd.Period) -> None:
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 18)
    pdf.set_text_color(*INK)
    pdf.cell(WIDTH, 9, f"{month.strftime('%B %Y')} at a glance",
             new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(2)
    pdf.kpi_cards(_summary_cards(metrics.summary(ds, month), month))

    pdf.section("Highlights")
    pdf.set_font("Helvetica", "", 9.5)
    pdf.set_text_color(*INK)
    for line in metrics.highlights(ds, month):
        pdf.set_x(17)
        pdf.cell(4, 5.5, "-")
        pdf.multi_cell(WIDTH - 6, 5.5, line, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.section("Daily revenue", keep_mm=65)
    pdf.chart(charts.daily_revenue(metrics.daily_revenue(ds, month)))


def _rows_mm(rows: int) -> float:
    """Space a table with this many rows needs (header + rows + note)."""
    return 6.5 + 6 * rows + 7


def _page_sales(pdf: MonthlyReport, ds: Dataset, month: pd.Period) -> None:
    pdf.add_page()
    cats = metrics.by_category(ds, month)
    prev_name = (month - 1).strftime("%b")
    pdf.section("Revenue by category", f"{month.strftime('%B')} compared with {prev_name}.")
    pdf.chart(charts.category_revenue(cats, month.strftime("%b %Y"),
                                      (month - 1).strftime("%b %Y")))
    pdf.table(
        [("Category", 58, "L"), ("Revenue", 32, "R"), ("Share", 20, "R"),
         (f"vs {prev_name}", 24, "R"), ("Gross profit", 28, "R"), ("Margin", 18, "R")],
        [[r.category, metrics.nok(r.revenue), metrics.pct(r.share, False), metrics.pct(r.change),
          metrics.nok(r.gross_profit), metrics.pct(r.margin, False)] for r in cats.itertuples()],
        [[None, None, None, _change_color(r.change), None, None] for r in cats.itertuples()],
    )


def _page_products_stock(pdf: MonthlyReport, ds: Dataset, month: pd.Period) -> None:
    prev_name = (month - 1).strftime("%b")
    top = metrics.top_products(ds, month, 10)
    pdf.section("Top 10 products by revenue", keep_mm=_rows_mm(len(top)))
    pdf.table(
        [("Product", 70, "L"), ("Units", 16, "R"), ("Revenue", 30, "R"),
         (f"vs {prev_name}", 22, "R"), ("Gross profit", 26, "R"), ("Margin", 16, "R")],
        [[r.product, f"{r.units:,}", metrics.nok(r.revenue), metrics.pct(r.change),
          metrics.nok(r.gross_profit), metrics.pct(r.margin, False)] for r in top.itertuples()],
        [[None, None, None, _change_color(r.change), None, None] for r in top.itertuples()],
    )

    status = metrics.stock_status(ds, month)
    reorder = metrics.reorder_list(status)
    pdf.section(
        "Reorder list",
        f"Month-end stock value: {metrics.nok(status['stock_value'].sum())}. "
        f"Products below their reorder level, most urgent first. Suggested quantity "
        f"covers about 30 days of sales. Total order value: "
        f"{metrics.nok(reorder['order_value'].sum())}.",
        keep_mm=10 + _rows_mm(min(len(reorder), MAX_ROWS)),
    )
    shown = reorder.head(MAX_ROWS)
    pdf.table(
        [("Product", 70, "L"), ("In stock", 18, "R"), ("Reorder at", 20, "R"),
         ("Days left", 18, "R"), ("Order qty", 20, "R"), ("Order value", 34, "R")],
        [[r.product, r.on_hand, r.reorder_level, f"{r.days_of_stock:.0f}", r.suggested_order,
          metrics.nok(r.order_value)] for r in shown.itertuples()],
        [[None, None, None, RED if r.days_of_stock < 3 else None, None, None]
         for r in shown.itertuples()],
    )
    pdf.more_rows_note(len(reorder), len(shown))


def _page_risks_costs(pdf: MonthlyReport, ds: Dataset, month: pd.Period) -> None:
    status = metrics.stock_status(ds, month)
    exp = metrics.expiring(status)
    shown = exp.head(10)
    pdf.section("Expiring soon",
                f"Products whose nearest batch expires within {metrics.EXPIRY_WARNING_DAYS} "
                f"days of month end. Consider a campaign, moving stock or returning it to the supplier.",
                keep_mm=5 + _rows_mm(len(shown)))
    pdf.table(
        [("Product", 76, "L"), ("Expiry date", 26, "R"), ("Days", 16, "R"),
         ("In stock", 22, "R"), ("Stock value", 40, "R")],
        [[r.product, f"{r.nearest_expiry:%d.%m.%Y}", r.days_to_expiry, r.on_hand,
          metrics.nok(r.stock_value)] for r in shown.itertuples()],
        [[None, None, RED if r.days_to_expiry <= 30 else None, None, None]
         for r in shown.itertuples()],
    )
    pdf.more_rows_note(len(exp), len(shown))

    over = metrics.overstock(status)
    shown = over.head(8)
    pdf.section("Overstock",
                f"More than {metrics.OVERSTOCK_DAYS} days of stock at the current sales rate.",
                keep_mm=5 + _rows_mm(len(shown)))
    pdf.table(
        [("Product", 76, "L"), ("In stock", 22, "R"), ("Sold this month", 30, "R"),
         ("Days of stock", 24, "R"), ("Stock value", 28, "R")],
        [[r.product, r.on_hand, r.units_sold,
          "no sales" if r.days_of_stock == float("inf") else f"{r.days_of_stock:.0f}",
          metrics.nok(r.stock_value)] for r in shown.itertuples()],
    )
    pdf.more_rows_note(len(over), len(shown))

    costs = metrics.costs_by_type(ds, month)
    prev_name = (month - 1).strftime("%b")
    pdf.section("Operating costs", keep_mm=_rows_mm(len(costs) + 1))
    lines = [(r.cost_type, r.amount, r.amount_prev) for r in costs.itertuples()]
    lines.append(("Total", costs["amount"].sum(), costs["amount_prev"].sum()))
    changes = [metrics.pct_change(cur, prev) for _, cur, prev in lines]
    pdf.table(
        [("Cost type", 76, "L"), (month.strftime("%b %Y"), 36, "R"),
         ((month - 1).strftime("%b %Y"), 36, "R"), ("Change", 32, "R")],
        [[name, metrics.nok(cur), metrics.nok(prev), metrics.pct(ch)]
         for (name, cur, prev), ch in zip(lines, changes)],
        [[None, None, None, _change_color(ch, higher_is_good=False)] for ch in changes],
    )


def _page_trend(pdf: MonthlyReport, ds: Dataset, month: pd.Period) -> None:
    pdf.add_page()
    tr = metrics.trend(ds, month)
    pdf.section("Last 12 months", "Revenue and operating costs per month, with net profit.")
    pdf.chart(charts.monthly_trend(tr))
    tr = tr.assign(margin=tr["gross_profit"] / tr["revenue"])
    pdf.table(
        [("Month", 30, "L"), ("Revenue", 36, "R"), ("Gross profit", 34, "R"),
         ("Gross margin", 24, "R"), ("Operating costs", 30, "R"), ("Net profit", 26, "R")],
        [[r.month.strftime("%B %Y"), metrics.nok(r.revenue), metrics.nok(r.gross_profit),
          metrics.pct(r.margin, False), metrics.nok(r.operating_costs), metrics.nok(r.net_profit)]
         for r in tr.itertuples()],
        [[None] * 5 + [RED if r.net_profit < 0 else None] for r in tr.itertuples()],
    )


def build_pdf(ds: Dataset, month: pd.Period, path: Path, company: str) -> Path:
    pdf = MonthlyReport(company, month)
    _page_summary(pdf, ds, month)
    _page_sales(pdf, ds, month)
    _page_products_stock(pdf, ds, month)
    _page_risks_costs(pdf, ds, month)
    _page_trend(pdf, ds, month)
    path.parent.mkdir(parents=True, exist_ok=True)
    pdf.output(str(path))
    return path
