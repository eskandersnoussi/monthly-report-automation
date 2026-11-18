"""Charts for the PDF, rendered with matplotlib to in-memory PNG images."""
from __future__ import annotations

import io

import matplotlib

matplotlib.use("Agg")  # no screen needed (servers, scheduled tasks)
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.ticker import FuncFormatter  # noqa: E402

PRIMARY = "#0f766e"
PRIMARY_LIGHT = "#99d5cf"
GREY = "#9ca3af"
INK = "#1f2937"
GREEN = "#15803d"
RED = "#b91c1c"

plt.rcParams.update({
    "font.family": "DejaVu Sans",
    "font.size": 9,
    "axes.edgecolor": "#d1d5db",
    "axes.labelcolor": INK,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "xtick.color": INK,
    "ytick.color": INK,
})


def _thousands(x, _pos):
    if abs(x) >= 1_000_000:
        return f"{x / 1_000_000:.1f}M"
    return f"{x / 1000:.0f}k"


def _to_png(fig) -> io.BytesIO:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=200, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf


def daily_revenue(series: pd.Series) -> io.BytesIO:
    fig, ax = plt.subplots(figsize=(7.2, 2.4))
    colors = [GREY if d.dayofweek == 6 else PRIMARY for d in series.index]
    ax.bar(series.index.day, series.values, color=colors, width=0.75)
    ax.yaxis.set_major_formatter(FuncFormatter(_thousands))
    ax.set_xticks(series.index.day[::2])
    ax.set_xlabel("Day of month (grey = Sunday)")
    ax.set_ylabel("Revenue (NOK)")
    ax.grid(axis="y", color="#e5e7eb", linewidth=0.6)
    ax.set_axisbelow(True)
    return _to_png(fig)


def category_revenue(cats: pd.DataFrame, month_label: str, prev_label: str) -> io.BytesIO:
    data = cats.sort_values("revenue")
    fig, ax = plt.subplots(figsize=(7.2, 3.2))
    y = range(len(data))
    ax.barh([i + 0.2 for i in y], data["revenue_prev"], height=0.4,
            color=PRIMARY_LIGHT, label=prev_label)
    ax.barh([i - 0.2 for i in y], data["revenue"], height=0.4, color=PRIMARY, label=month_label)
    ax.set_yticks(list(y))
    ax.set_yticklabels(data["category"])
    ax.xaxis.set_major_formatter(FuncFormatter(_thousands))
    ax.set_xlabel("Revenue (NOK)")
    ax.grid(axis="x", color="#e5e7eb", linewidth=0.6)
    ax.set_axisbelow(True)
    ax.legend(frameon=False, loc="lower right")
    return _to_png(fig)


def monthly_trend(trend: pd.DataFrame) -> io.BytesIO:
    labels = [m.strftime("%b\n%y") for m in trend["month"]]
    x = range(len(trend))
    fig, ax = plt.subplots(figsize=(7.2, 2.8))
    ax.bar([i - 0.2 for i in x], trend["revenue"], width=0.4, color=PRIMARY, label="Revenue")
    ax.bar([i + 0.2 for i in x], trend["operating_costs"], width=0.4,
           color=PRIMARY_LIGHT, label="Operating costs")
    ax.plot(list(x), trend["net_profit"], color=INK, marker="o", markersize=3,
            linewidth=1.5, label="Net profit")
    ax.axhline(0, color="#d1d5db", linewidth=0.8)
    ax.set_xticks(list(x))
    ax.set_xticklabels(labels)
    ax.yaxis.set_major_formatter(FuncFormatter(_thousands))
    ax.set_ylabel("NOK")
    ax.grid(axis="y", color="#e5e7eb", linewidth=0.6)
    ax.set_axisbelow(True)
    ax.legend(frameon=False, ncol=3, loc="upper center", bbox_to_anchor=(0.5, 1.15))
    return _to_png(fig)
