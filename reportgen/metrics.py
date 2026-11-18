"""All report calculations. Pure pandas, no charts or files, so it is easy to test."""
from __future__ import annotations

import math
from typing import Optional

import numpy as np
import pandas as pd

from .data import DataError, Dataset

EXPIRY_WARNING_DAYS = 90
OVERSTOCK_DAYS = 120


def pct_change(new: float, old: float) -> Optional[float]:
    """Relative change, or None when there is nothing to compare with."""
    if old is None or old == 0 or (isinstance(old, float) and math.isnan(old)):
        return None
    return (new - old) / abs(old)


def check_month(ds: Dataset, month: pd.Period) -> None:
    if month not in set(ds.months):
        first, last = ds.months[0], ds.months[-1]
        raise DataError(f"No sales data for {month}. Data covers {first} to {last}.")


def _month_sales(ds: Dataset, month: pd.Period) -> pd.DataFrame:
    return ds.sales[ds.sales["month"] == month]


def figures(ds: Dataset, month: pd.Period) -> dict:
    s = _month_sales(ds, month)
    revenue = float(s["revenue"].sum())
    gross_profit = revenue - float(s["cost"].sum())
    operating_costs = float(ds.costs.loc[ds.costs["month"] == month, "amount"].sum())
    return {
        "revenue": revenue,
        "gross_profit": gross_profit,
        "gross_margin": gross_profit / revenue if revenue else 0.0,
        "operating_costs": operating_costs,
        "net_profit": gross_profit - operating_costs,
        "units": int(s["quantity"].sum()),
        "has_data": not s.empty,
    }


def summary(ds: Dataset, month: pd.Period) -> dict:
    """Key figures for the month, the previous month and the same month last year."""
    return {
        "current": figures(ds, month),
        "previous": figures(ds, month - 1),
        "last_year": figures(ds, month - 12),
    }


def daily_revenue(ds: Dataset, month: pd.Period) -> pd.Series:
    s = _month_sales(ds, month)
    days = pd.date_range(month.start_time, month.end_time.normalize(), freq="D")
    return s.groupby("date")["revenue"].sum().reindex(days, fill_value=0.0)


def _by(ds: Dataset, month: pd.Period, key: str) -> pd.DataFrame:
    s = _month_sales(ds, month).merge(ds.products[["sku", "product", "category"]], on="sku")
    out = s.groupby(key).agg(revenue=("revenue", "sum"), cost=("cost", "sum"),
                             units=("quantity", "sum"))
    out["gross_profit"] = out["revenue"] - out["cost"]
    return out.drop(columns="cost")


def by_category(ds: Dataset, month: pd.Period) -> pd.DataFrame:
    cur = _by(ds, month, "category")
    prev = _by(ds, month - 1, "category")["revenue"].rename("revenue_prev")
    out = cur.join(prev, how="left").fillna({"revenue_prev": 0.0})
    out["margin"] = out["gross_profit"] / out["revenue"]
    out["share"] = out["revenue"] / out["revenue"].sum()
    out["change"] = [pct_change(n, o) for n, o in zip(out["revenue"], out["revenue_prev"])]
    return out.sort_values("revenue", ascending=False).reset_index()


def top_products(ds: Dataset, month: pd.Period, n: int = 10) -> pd.DataFrame:
    cur = _by(ds, month, "sku")
    prev = _by(ds, month - 1, "sku")["revenue"].rename("revenue_prev")
    out = cur.join(prev, how="left").fillna({"revenue_prev": 0.0})
    out["margin"] = out["gross_profit"] / out["revenue"]
    out["change"] = [pct_change(n_, o) for n_, o in zip(out["revenue"], out["revenue_prev"])]
    out = out.reset_index().merge(ds.products[["sku", "product", "category"]], on="sku")
    return out.sort_values("revenue", ascending=False).head(n).reset_index(drop=True)


def stock_status(ds: Dataset, month: pd.Period) -> pd.DataFrame:
    """Month-end stock per product with days of cover, value and reorder advice."""
    stock = ds.stock[ds.stock["month"] == month]
    if stock.empty:
        raise DataError(f"No stock snapshot for {month} in stock.csv")
    units = _month_sales(ds, month).groupby("sku")["quantity"].sum()
    out = stock.merge(ds.products, on="sku", how="left")
    out["units_sold"] = out["sku"].map(units).fillna(0).astype(int)
    out["avg_daily_units"] = out["units_sold"] / month.days_in_month
    out["days_of_stock"] = np.where(
        out["avg_daily_units"] > 0, out["on_hand"] / out["avg_daily_units"], np.inf
    )
    out["stock_value"] = out["on_hand"] * out["unit_cost"]
    out["below_reorder"] = out["on_hand"] < out["reorder_level"]
    # Order enough for about 30 days of sales, and at least twice the reorder level.
    target = np.maximum(np.ceil(out["avg_daily_units"] * 30), out["reorder_level"] * 2)
    out["suggested_order"] = np.where(
        out["below_reorder"], np.maximum(target - out["on_hand"], 0), 0
    ).astype(int)
    out["order_value"] = out["suggested_order"] * out["unit_cost"]
    month_end = month.end_time.normalize()
    out["days_to_expiry"] = (out["nearest_expiry"] - month_end).dt.days
    return out


def reorder_list(status: pd.DataFrame) -> pd.DataFrame:
    out = status[status["below_reorder"]].copy()
    return out.sort_values("days_of_stock").reset_index(drop=True)


def expiring(status: pd.DataFrame, days: int = EXPIRY_WARNING_DAYS) -> pd.DataFrame:
    out = status[status["days_to_expiry"] <= days].copy()
    return out.sort_values("days_to_expiry").reset_index(drop=True)


def overstock(status: pd.DataFrame, days: int = OVERSTOCK_DAYS) -> pd.DataFrame:
    out = status[status["days_of_stock"] > days].copy()
    return out.sort_values("stock_value", ascending=False).reset_index(drop=True)


def costs_by_type(ds: Dataset, month: pd.Period) -> pd.DataFrame:
    def per_type(m):
        return ds.costs[ds.costs["month"] == m].groupby("cost_type")["amount"].sum()

    out = pd.DataFrame({"amount": per_type(month)})
    out["amount_prev"] = per_type(month - 1).reindex(out.index).fillna(0.0)
    out["change"] = [pct_change(n, o) for n, o in zip(out["amount"], out["amount_prev"])]
    return out.sort_values("amount", ascending=False).reset_index()


def trend(ds: Dataset, month: pd.Period, months: int = 12) -> pd.DataFrame:
    rows = []
    for m in pd.period_range(month - (months - 1), month, freq="M"):
        f = figures(ds, m)
        if f["has_data"]:
            rows.append({"month": m, **{k: f[k] for k in
                         ("revenue", "gross_profit", "operating_costs", "net_profit")}})
    return pd.DataFrame(rows)


# --------------------------------------------------------------- text helpers
def nok(value: float) -> str:
    return f"NOK {value:,.0f}"


def pct(value: Optional[float], signed: bool = True) -> str:
    if value is None:
        return "n/a"
    return f"{value:+.1%}" if signed else f"{value:.1%}"


def _direction(change: Optional[float]) -> str:
    if change is None:
        return "with no comparison available"
    return f"{'up' if change >= 0 else 'down'} {abs(change):.1%}"


def highlights(ds: Dataset, month: pd.Period) -> list:
    """Short plain-language findings shown at the top of the report."""
    s = summary(ds, month)
    cur, prev, ly = s["current"], s["previous"], s["last_year"]
    prev_name = (month - 1).strftime("%B")
    lines = [
        f"Revenue was {nok(cur['revenue'])}, {_direction(pct_change(cur['revenue'], prev['revenue']))} "
        f"on {prev_name} and {_direction(pct_change(cur['revenue'], ly['revenue']))} "
        f"on {(month - 12).strftime('%B %Y')}."
        if ly["has_data"] else
        f"Revenue was {nok(cur['revenue'])}, "
        f"{_direction(pct_change(cur['revenue'], prev['revenue']))} on {prev_name}.",
        f"Gross margin was {pct(cur['gross_margin'], signed=False)} and net profit "
        f"{nok(cur['net_profit'])} after {nok(cur['operating_costs'])} in operating costs.",
    ]

    cats = by_category(ds, month)
    cats["abs_change"] = cats["revenue"] - cats["revenue_prev"]
    if prev["has_data"] and len(cats) > 1:
        up, down = cats.loc[cats["abs_change"].idxmax()], cats.loc[cats["abs_change"].idxmin()]
        if up["abs_change"] > 0:
            lines.append(f"Biggest growth: {up['category']} ({pct(up['change'])}, "
                         f"{nok(up['abs_change'])} more than {prev_name}).")
        if down["abs_change"] < 0:
            lines.append(f"Biggest drop: {down['category']} ({pct(down['change'])}, "
                         f"{nok(-down['abs_change'])} less than {prev_name}).")

    status = stock_status(ds, month)
    reorder, exp = reorder_list(status), expiring(status)
    if not reorder.empty:
        lines.append(f"{len(reorder)} products are below their reorder level. "
                     f"Suggested order value: {nok(reorder['order_value'].sum())}.")
    if not exp.empty:
        lines.append(f"{len(exp)} products have batches expiring within "
                     f"{EXPIRY_WARNING_DAYS} days (stock value {nok(exp['stock_value'].sum())}).")

    costs = costs_by_type(ds, month)
    rising = costs[costs["change"].apply(lambda c: c is not None and c > 0.15)]
    if not rising.empty:
        top = rising.iloc[0]
        lines.append(f"{top['cost_type']} costs rose {pct(top['change'], signed=False)} on {prev_name}.")
    return lines
