"""Load and validate the input CSV files."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

REQUIRED_COLUMNS = {
    "products": ["sku", "product", "category", "unit_cost", "unit_price", "reorder_level"],
    "sales": ["date", "sku", "quantity", "unit_price", "revenue", "cost"],
    "stock": ["month", "sku", "on_hand", "nearest_expiry"],
    "costs": ["month", "cost_type", "amount"],
}


class DataError(ValueError):
    """The input data is missing, incomplete or inconsistent."""


@dataclass
class Dataset:
    products: pd.DataFrame
    sales: pd.DataFrame
    stock: pd.DataFrame
    costs: pd.DataFrame

    @property
    def months(self) -> list:
        return sorted(self.sales["month"].unique())


def _check_columns(name: str, df: pd.DataFrame) -> None:
    missing = [c for c in REQUIRED_COLUMNS[name] if c not in df.columns]
    if missing:
        raise DataError(f"{name}.csv is missing column(s): {', '.join(missing)}")


def prepare(products: pd.DataFrame, sales: pd.DataFrame, stock: pd.DataFrame,
            costs: pd.DataFrame) -> Dataset:
    """Validate raw tables and add the parsed columns the report needs."""
    tables = {"products": products, "sales": sales, "stock": stock, "costs": costs}
    for name, df in tables.items():
        _check_columns(name, df)

    sales = sales.copy()
    sales["date"] = pd.to_datetime(sales["date"])
    sales["month"] = sales["date"].dt.to_period("M")
    if (sales["quantity"] < 0).any():
        raise DataError("sales.csv contains negative quantities")

    unknown = set(sales["sku"]) - set(products["sku"])
    if unknown:
        raise DataError(f"sales.csv has SKUs that are not in products.csv: {sorted(unknown)[:5]}")

    stock = stock.copy()
    stock["month"] = pd.PeriodIndex(stock["month"].astype(str), freq="M")
    stock["nearest_expiry"] = pd.to_datetime(stock["nearest_expiry"])

    costs = costs.copy()
    costs["month"] = pd.PeriodIndex(costs["month"].astype(str), freq="M")

    return Dataset(products.copy(), sales, stock, costs)


def load(data_dir: Path) -> Dataset:
    data_dir = Path(data_dir)
    tables = {}
    for name in REQUIRED_COLUMNS:
        path = data_dir / f"{name}.csv"
        if not path.exists():
            raise DataError(f"Missing file: {path}. Run 'python make_data.py' for sample data.")
        tables[name] = pd.read_csv(path)
    return prepare(**tables)
