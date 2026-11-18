"""Generate FICTIONAL sample data for a made-up pharmacy ("Nordlys Pharmacy").

    python make_data.py                 # writes data/*.csv (Jan 2025 - Oct 2026)

No real company, customer or sales data is used. Products are generic
(no brand names) and every number is randomly generated with realistic
patterns: seasons (cold & flu in winter, allergy in spring, sunscreen in
summer), quieter weekends, a yearly price increase and slow growth.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent

# name, category, unit cost (NOK), unit price (NOK), average units per weekday
PRODUCTS = [
    ("Paracetamol 500 mg, 20 tablets", "Pain & fever", 22, 39, 30),
    ("Ibuprofen 200 mg, 30 tablets", "Pain & fever", 28, 55, 22),
    ("Ibuprofen gel 5%, 50 g", "Pain & fever", 45, 89, 6),
    ("Acetylsalicylic acid 500 mg, 20 tablets", "Pain & fever", 25, 45, 6),
    ("Paracetamol oral solution for children", "Pain & fever", 48, 89, 5),
    ("Decongestant nasal spray, 10 ml", "Cold & flu", 35, 69, 18),
    ("Throat lozenges, 24 pcs", "Cold & flu", 30, 59, 14),
    ("Cough syrup, 200 ml", "Cold & flu", 55, 109, 8),
    ("Hot lemon cold drink, 10 sachets", "Cold & flu", 40, 79, 7),
    ("Saline nasal drops", "Cold & flu", 25, 49, 6),
    ("Cetirizine 10 mg, 30 tablets", "Allergy", 35, 79, 8),
    ("Loratadine 10 mg, 30 tablets", "Allergy", 38, 85, 6),
    ("Allergy eye drops", "Allergy", 52, 109, 4),
    ("Allergy nasal spray", "Allergy", 70, 139, 4),
    ("Vitamin D 1000 IU, 100 capsules", "Vitamins & supplements", 60, 129, 8),
    ("Omega-3 fish oil, 120 capsules", "Vitamins & supplements", 110, 229, 6),
    ("Multivitamin, 60 tablets", "Vitamins & supplements", 75, 159, 5),
    ("Vitamin C 500 mg, 60 tablets", "Vitamins & supplements", 45, 99, 4),
    ("Iron supplement, 60 tablets", "Vitamins & supplements", 50, 109, 3),
    ("Magnesium, 120 tablets", "Vitamins & supplements", 55, 119, 4),
    ("Moisturising cream, 200 ml", "Skin care", 70, 149, 6),
    ("Sunscreen SPF 50, 200 ml", "Skin care", 95, 199, 4),
    ("Lip balm", "Skin care", 18, 45, 9),
    ("Hydrocortisone cream 1%", "Skin care", 40, 89, 4),
    ("Aftersun lotion, 200 ml", "Skin care", 60, 129, 2),
    ("Hand cream, 100 ml", "Skin care", 35, 79, 6),
    ("Antacid chewable tablets", "Digestive health", 32, 69, 7),
    ("Laxative, 30 tablets", "Digestive health", 45, 95, 4),
    ("Oral rehydration salts", "Digestive health", 40, 85, 3),
    ("Probiotic capsules, 30 pcs", "Digestive health", 95, 199, 3),
    ("Anti-diarrhoea capsules", "Digestive health", 38, 79, 3),
    ("Plasters, assorted 40 pcs", "First aid", 22, 49, 10),
    ("Elastic bandage", "First aid", 30, 69, 3),
    ("Antiseptic solution, 100 ml", "First aid", 35, 75, 4),
    ("Blister plasters", "First aid", 45, 99, 4),
    ("Digital thermometer", "First aid", 90, 199, 1.5),
    ("Nappy cream, 100 ml", "Baby & child", 45, 99, 4),
    ("Teething gel", "Baby & child", 48, 99, 2),
    ("Baby wipes, 3-pack", "Baby & child", 40, 89, 5),
    ("Infant formula, 800 g", "Baby & child", 190, 269, 3),
    ("Sensitive toothpaste", "Personal care", 30, 59, 8),
    ("Deodorant, 50 ml", "Personal care", 35, 69, 6),
    ("Shampoo for dry scalp", "Personal care", 65, 139, 3),
    ("Contact lens solution, 360 ml", "Personal care", 70, 149, 3),
    ("Condoms, 10 pcs", "Personal care", 60, 129, 4),
    ("Prescription medicines (generic)", "Prescription medicines", 160, 185, 60),
    ("Prescription medicines (original brand)", "Prescription medicines", 420, 470, 25),
]

# Monthly demand multipliers, January..December
SEASON = {
    "Cold & flu": [1.6, 1.5, 1.2, 0.9, 0.6, 0.5, 0.45, 0.5, 0.8, 1.2, 1.5, 1.7],
    "Allergy": [0.4, 0.4, 0.7, 1.5, 2.0, 1.8, 1.2, 0.9, 0.7, 0.5, 0.4, 0.4],
    "Vitamins & supplements": [1.3, 1.2, 1.0, 0.9, 0.8, 0.7, 0.7, 0.8, 1.0, 1.2, 1.3, 1.2],
    "Skin care": [0.9, 0.8, 0.9, 1.0, 1.2, 1.4, 1.5, 1.3, 1.0, 0.9, 0.9, 1.0],
}
SUMMER_ONLY = [0.2, 0.2, 0.4, 0.8, 1.8, 2.8, 3.0, 2.0, 0.6, 0.3, 0.2, 0.2]
SUMMER_PRODUCTS = {"Sunscreen SPF 50, 200 ml", "Aftersun lotion, 200 ml"}
WEEKDAY = [1.0, 1.0, 1.0, 1.05, 1.15, 0.8, 0.35]  # Monday..Sunday


def generate(start: str = "2025-01-01", end: str = "2026-10-31", seed: int = 42) -> dict:
    rng = np.random.default_rng(seed)
    days = pd.date_range(start, end, freq="D")
    first_year = days[0].year

    products = pd.DataFrame(
        PRODUCTS, columns=["product", "category", "unit_cost", "unit_price", "base_units"]
    )
    products.insert(0, "sku", [f"P{i + 1:03d}" for i in range(len(products))])
    # Reorder when stock falls below roughly 10 days of normal sales.
    products["reorder_level"] = np.ceil(products["base_units"] * 10).astype(int)

    rows = []
    for _, p in products.iterrows():
        season = SUMMER_ONLY if p["product"] in SUMMER_PRODUCTS else SEASON.get(
            p["category"], [1.0] * 12)
        years = days.year - first_year
        demand = (
            p["base_units"]
            * np.array([season[m - 1] for m in days.month])
            * np.array([WEEKDAY[d] for d in days.dayofweek])
            * (1.05 ** years)                         # slow growth
            * rng.normal(1.0, 0.12, len(days)).clip(0.6, 1.4)
        )
        qty = rng.poisson(demand)
        price_factor = 1.03 ** years                  # yearly price increase
        cost_factor = 1.025 ** years
        for day, q, pf, cf in zip(days, qty, price_factor, cost_factor):
            if q:
                rows.append((day.date(), p["sku"], int(q),
                             round(p["unit_price"] * pf, 2), round(p["unit_cost"] * cf, 2)))

    sales = pd.DataFrame(rows, columns=["date", "sku", "quantity", "unit_price", "unit_cost"])
    sales["revenue"] = (sales["quantity"] * sales["unit_price"]).round(2)
    sales["cost"] = (sales["quantity"] * sales["unit_cost"]).round(2)
    sales = sales.drop(columns=["unit_cost"]).sort_values(["date", "sku"])

    # Current (latest) prices in the product list.
    last_years = days[-1].year - first_year
    products["unit_price"] = (products["unit_price"] * 1.03 ** last_years).round(2)
    products["unit_cost"] = (products["unit_cost"] * 1.025 ** last_years).round(2)

    # Month-end stock snapshot per product, with the nearest expiry date.
    months = pd.period_range(days[0], days[-1], freq="M")
    stock_rows = []
    for month in months:
        month_end = month.to_timestamp(how="end").normalize()
        for _, p in products.iterrows():
            level = p["reorder_level"]
            roll = rng.random()
            if roll < 0.12:
                on_hand = int(level * rng.uniform(0.1, 0.9))      # running low
            elif roll < 0.18:
                on_hand = int(level * rng.uniform(6, 12))         # overstocked
            else:
                on_hand = int(level * rng.uniform(1.1, 3.0))
            soon = rng.random() < 0.10
            expiry_days = int(rng.integers(15, 90) if soon else rng.integers(120, 720))
            stock_rows.append((str(month), p["sku"], on_hand,
                               (month_end + pd.Timedelta(days=expiry_days)).date()))
    stock = pd.DataFrame(stock_rows, columns=["month", "sku", "on_hand", "nearest_expiry"])

    # Monthly operating costs.
    monthly_revenue = sales.groupby(pd.to_datetime(sales["date"]).dt.to_period("M"))["revenue"].sum()
    avg = monthly_revenue.mean()
    cost_rows = []
    for month, revenue in monthly_revenue.items():
        years = month.year - first_year
        salaries = avg * 0.17 * 1.04 ** years
        if month.month == 6:
            salaries *= 1.6  # holiday pay is paid out in June in Norway
        winter = month.month in (11, 12, 1, 2, 3)
        items = {
            "Salaries": salaries,
            "Rent": 68000 * 1.03 ** years,
            "Utilities": rng.uniform(14000, 18000) if winter else rng.uniform(8000, 11000),
            "IT & systems": 9500,
            "Card & bank fees": revenue * 0.011,
            "Marketing": rng.uniform(8000, 20000),
            "Other": rng.uniform(5000, 12000),
        }
        cost_rows += [(str(month), k, round(v, 2)) for k, v in items.items()]
    costs = pd.DataFrame(cost_rows, columns=["month", "cost_type", "amount"])

    products = products.drop(columns=["base_units"])
    return {"products": products, "sales": sales, "stock": stock, "costs": costs}


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate fictional sample data.")
    parser.add_argument("--out", type=Path, default=ROOT / "data")
    parser.add_argument("--start", default="2025-01-01")
    parser.add_argument("--end", default="2026-10-31")
    args = parser.parse_args()

    args.out.mkdir(parents=True, exist_ok=True)
    for name, df in generate(args.start, args.end).items():
        df.to_csv(args.out / f"{name}.csv", index=False)
        print(f"  {name}.csv: {len(df):,} rows")


if __name__ == "__main__":
    main()
