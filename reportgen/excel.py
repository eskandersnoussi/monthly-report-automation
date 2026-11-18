"""Excel workbook with the full detail behind the PDF."""
from __future__ import annotations

from pathlib import Path

import pandas as pd
from openpyxl.styles import Font, PatternFill
from openpyxl.utils import get_column_letter

from . import metrics
from .data import Dataset

HEADER_FILL = PatternFill("solid", fgColor="0F766E")
HEADER_FONT = Font(bold=True, color="FFFFFF")
MONEY = '#,##0" kr"'
PERCENT = "0.0%"


def _sheets(ds: Dataset, month: pd.Period) -> dict:
    s = metrics.summary(ds, month)
    labels = {"revenue": "Revenue", "gross_profit": "Gross profit",
              "gross_margin": "Gross margin", "operating_costs": "Operating costs",
              "net_profit": "Net profit", "units": "Units sold"}
    summary = pd.DataFrame({
        "Figure": list(labels.values()),
        str(month): [s["current"][k] for k in labels],
        str(month - 1): [s["previous"][k] for k in labels],
        str(month - 12): [s["last_year"][k] if s["last_year"]["has_data"] else None
                          for k in labels],
    })

    status = metrics.stock_status(ds, month)
    stock_cols = {"sku": "SKU", "product": "Product", "category": "Category",
                  "on_hand": "In stock", "reorder_level": "Reorder level",
                  "units_sold": "Sold this month", "days_of_stock": "Days of stock",
                  "stock_value": "Stock value", "suggested_order": "Suggested order",
                  "order_value": "Order value", "nearest_expiry": "Nearest expiry",
                  "days_to_expiry": "Days to expiry"}

    def stock_view(df):
        out = df[list(stock_cols)].rename(columns=stock_cols)
        out["Days of stock"] = out["Days of stock"].replace(float("inf"), None).round(1)
        out["Nearest expiry"] = out["Nearest expiry"].dt.date
        return out

    products = metrics.top_products(ds, month, n=len(ds.products))
    return {
        "Summary": summary,
        "Highlights": pd.DataFrame({"Highlight": metrics.highlights(ds, month)}),
        "Categories": metrics.by_category(ds, month).rename(columns={
            "category": "Category", "revenue": "Revenue", "units": "Units",
            "gross_profit": "Gross profit", "revenue_prev": "Revenue previous month",
            "margin": "Gross margin", "share": "Share", "change": "Change"}),
        "Products": products[["sku", "product", "category", "units", "revenue",
                              "gross_profit", "margin", "revenue_prev", "change"]].rename(columns={
            "sku": "SKU", "product": "Product", "category": "Category", "units": "Units",
            "revenue": "Revenue", "gross_profit": "Gross profit", "margin": "Gross margin",
            "revenue_prev": "Revenue previous month", "change": "Change"}),
        "Reorder list": stock_view(metrics.reorder_list(status)),
        "Expiring": stock_view(metrics.expiring(status)),
        "Stock": stock_view(status.sort_values("product")),
        "Costs": metrics.costs_by_type(ds, month).rename(columns={
            "cost_type": "Cost type", "amount": str(month),
            "amount_prev": str(month - 1), "change": "Change"}),
        "12-month trend": metrics.trend(ds, month).assign(
            month=lambda d: d["month"].astype(str)).rename(columns={
                "month": "Month", "revenue": "Revenue", "gross_profit": "Gross profit",
                "operating_costs": "Operating costs", "net_profit": "Net profit"}),
    }


def _style(ws, df: pd.DataFrame) -> None:
    for cell in ws[1]:
        cell.fill, cell.font = HEADER_FILL, HEADER_FONT
    ws.freeze_panes = "A2"
    for i, column in enumerate(df.columns, start=1):
        name = str(column)
        values = df[column].astype(str).tolist()
        width = min(max([len(name)] + [len(v) for v in values]) + 2, 60)
        ws.column_dimensions[get_column_letter(i)].width = width
        if name in ("Gross margin", "Share", "Change"):
            fmt = PERCENT
        elif any(word in name for word in ("Revenue", "profit", "value", "costs")) or \
                name[:4].isdigit():
            fmt = MONEY
        else:
            continue
        for row in ws.iter_rows(min_row=2, min_col=i, max_col=i):
            row[0].number_format = fmt


def build_excel(ds: Dataset, month: pd.Period, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    sheets = _sheets(ds, month)
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        for name, df in sheets.items():
            df.to_excel(writer, sheet_name=name, index=False)
            _style(writer.sheets[name], df)
        # The summary mixes money, a percentage and a count in one column.
        ws = writer.sheets["Summary"]
        for row in ws.iter_rows(min_row=2, min_col=2):
            label = ws.cell(row=row[0].row, column=1).value
            for cell in row:
                cell.number_format = (PERCENT if label == "Gross margin"
                                      else "#,##0" if label == "Units sold" else MONEY)
    return path
