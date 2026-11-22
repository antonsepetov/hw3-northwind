"""Load the Northwind workbook and compute order revenue.

Shared paths and helpers used by the Q1-Q3 analysis scripts.
"""

from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DATA_PATH = ROOT / "Northwind Database.xlsx"
FIGURES_DIR = ROOT / "docs" / "figures"
OUTPUTS_DIR = ROOT / "outputs"


def load_sheets(path=DATA_PATH):
    """Read every sheet of the Northwind workbook.

    Args:
        path (pathlib.Path): Workbook to read; defaults to the
            repository copy of ``Northwind Database.xlsx``.

    Returns:
        dict[str, pandas.DataFrame]: One DataFrame per sheet, keyed by
        sheet name.
    """
    return pd.read_excel(path, sheet_name=None)


def line_items(sheets):
    """Return order lines with discount-adjusted revenue.

    Args:
        sheets (dict[str, pandas.DataFrame]): Workbook from
            ``load_sheets``.

    Returns:
        pandas.DataFrame: Copy of ``Orders Details`` with ``Discount``
        rounded to two decimals and a ``Revenue`` column equal to
        unit price x quantity x (1 - discount), in USD.
    """
    details = sheets["Orders Details"].copy()
    # Discounts are stored as float32-style values (0.0500000007...).
    details["Discount"] = details["Discount"].round(2)
    details["Revenue"] = (
        details["UnitPrice"] * details["Quantity"] * (1 - details["Discount"])
    )
    return details


def orders_with_revenue(sheets):
    """Return one row per order with its revenue and customer.

    Args:
        sheets (dict[str, pandas.DataFrame]): Workbook from
            ``load_sheets``.

    Returns:
        pandas.DataFrame: ``Orders`` plus ``Revenue`` (USD, after
        discounts), ``CompanyName`` and ``Country``, with
        ``OrderDate`` parsed to datetime. Orders without line items
        are dropped.
    """
    details = line_items(sheets)
    revenue = details.groupby("OrderID")["Revenue"].sum().rename("Revenue")
    orders = sheets["Orders"].merge(revenue, left_on="OrderID", right_index=True)
    customers = sheets["Customers"][["CustomerID", "CompanyName", "Country"]]
    orders = orders.merge(customers, on="CustomerID", how="left")
    orders["OrderDate"] = pd.to_datetime(orders["OrderDate"])
    return orders


def ensure_output_dirs():
    """Create the figures and outputs directories if missing.

    Args:
        None.

    Returns:
        None.
    """
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
