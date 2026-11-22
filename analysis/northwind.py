from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DATA_PATH = ROOT / "Northwind Database.xlsx"
FIGURES_DIR = ROOT / "docs" / "figures"
OUTPUTS_DIR = ROOT / "outputs"


def load_sheets(path=DATA_PATH):
    return pd.read_excel(path, sheet_name=None)


def line_items(sheets):
    details = sheets["Orders Details"].copy()
    # Discounts are stored as float32-style values (0.0500000007...).
    details["Discount"] = details["Discount"].round(2)
    details["Revenue"] = (
        details["UnitPrice"] * details["Quantity"] * (1 - details["Discount"])
    )
    return details


def orders_with_revenue(sheets):
    details = line_items(sheets)
    revenue = details.groupby("OrderID")["Revenue"].sum().rename("Revenue")
    orders = sheets["Orders"].merge(revenue, left_on="OrderID", right_index=True)
    customers = sheets["Customers"][["CustomerID", "CompanyName", "Country"]]
    orders = orders.merge(customers, on="CustomerID", how="left")
    orders["OrderDate"] = pd.to_datetime(orders["OrderDate"])
    return orders


def ensure_output_dirs():
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
