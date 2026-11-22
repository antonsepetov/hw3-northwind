"""Q3: which best sellers are running low on stock?

Writes charts to ``docs/figures`` and tables to ``outputs``.
"""

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from northwind import FIGURES_DIR, OUTPUTS_DIR, ensure_output_dirs, line_items, load_sheets

WEEKS_PER_MONTH = 52 / 12
DAYS_PER_MONTH = 365.25 / 12
LOW_STOCK_WEEKS = 2.0
TOP_SELLER_QUANTILE = 2 / 3
RECENT_WINDOW = ("1997-11-01", "1998-05-01")
RECENT_MONTHS = 6
Y_AXIS_CAP_WEEKS = 12
# Hand-placed number offsets (points) for markers that sit close together.
LABEL_OFFSETS = {
    "Mozzarella di Giovanni": (-7, 7),
    "Outback Lager": (7, 7),
    "Chang": (-6, -14),
    "Tarte au sucre": (6, -14),
}
RISK_COLOR = "#c2410c"
NEUTRAL_COLOR = "#94a3b8"


def dated_lines(sheets):
    """Return order lines with revenue and order date.

    Args:
        sheets (dict[str, pandas.DataFrame]): Workbook from
            ``load_sheets``.

    Returns:
        pandas.DataFrame: Output of ``line_items`` plus
        ``OrderDate`` as datetime.
    """
    lines = line_items(sheets).merge(
        sheets["Orders"][["OrderID", "OrderDate"]], on="OrderID"
    )
    lines["OrderDate"] = pd.to_datetime(lines["OrderDate"])
    return lines


def period_months(lines):
    """Return the length of the sales period in months.

    Args:
        lines (pandas.DataFrame): Order lines with ``OrderDate``.

    Returns:
        float: Days from first to last order, inclusive, divided by
        the average month length (30.44 days).
    """
    span = lines["OrderDate"].max() - lines["OrderDate"].min()
    return (span.days + 1) / DAYS_PER_MONTH


def monthly_sales(lines, months, start=None, end=None):
    """Return average units sold per month for each product.

    Args:
        lines (pandas.DataFrame): Order lines with ``OrderDate``.
        months (float): Months to divide total units by.
        start (str | None): First order date to include; None uses
            all lines.
        end (str | None): Exclusive end date; used only when
            ``start`` is given.

    Returns:
        pandas.Series: Units per month indexed by ``ProductID``.
        Products with no sales in the window are absent.
    """
    if start is not None:
        lines = lines[(lines["OrderDate"] >= start) & (lines["OrderDate"] < end)]
    return lines.groupby("ProductID")["Quantity"].sum() / months


def product_stock_table(sheets, lines):
    """Build the per-product sales pace and stock coverage table.

    Args:
        sheets (dict[str, pandas.DataFrame]): Workbook from
            ``load_sheets``.
        lines (pandas.DataFrame): Output of ``dated_lines``.

    Returns:
        pandas.DataFrame: One row per product with stock fields,
        category name, monthly units (full period and
        ``RECENT_WINDOW``), weeks of stock on hand and including
        units on order, and a boolean ``BelowReorderLevel``.
    """
    products = sheets["Product"][
        [
            "ProductID",
            "ProductName",
            "CategoryID",
            "UnitsInStock",
            "UnitsOnOrder",
            "ReorderLevel",
            "Discontinued",
        ]
    ].merge(sheets["Categories"][["CategoryID", "CategoryName"]], on="CategoryID")
    products["Discontinued"] = products["Discontinued"].astype(bool)

    months = period_months(lines)
    products["MonthlyUnits"] = products["ProductID"].map(monthly_sales(lines, months)).fillna(0)
    products["MonthlyUnitsRecent"] = (
        products["ProductID"]
        .map(monthly_sales(lines, RECENT_MONTHS, *RECENT_WINDOW))
        .fillna(0)
    )
    weekly = products["MonthlyUnits"] / WEEKS_PER_MONTH
    products["WeeksOfStock"] = products["UnitsInStock"] / weekly
    products["WeeksIncludingOnOrder"] = (
        products["UnitsInStock"] + products["UnitsOnOrder"]
    ) / weekly
    products["WeeksOfStockRecent"] = products["UnitsInStock"] / (
        products["MonthlyUnitsRecent"] / WEEKS_PER_MONTH
    )
    products["BelowReorderLevel"] = products["UnitsInStock"] <= products["ReorderLevel"]
    return products


def flag_at_risk(active, sales_col="MonthlyUnits", weeks_col="WeeksOfStock"):
    """Flag top-third sellers with under two weeks of stock.

    Args:
        active (pandas.DataFrame): Active products from
            ``product_stock_table``.
        sales_col (str): Column holding monthly units sold.
        weeks_col (str): Column holding weeks of stock.

    Returns:
        tuple[pandas.Series, float]: Boolean at-risk flag per row,
        and the monthly-units cutoff for the top third of sellers.
    """
    cutoff = active[sales_col].quantile(TOP_SELLER_QUANTILE)
    at_risk = (active[sales_col] >= cutoff) & (active[weeks_col] < LOW_STOCK_WEEKS)
    return at_risk, cutoff


def plot_risk_scatter(active, cutoff, path):
    """Plot sales pace vs weeks of stock, marking at-risk products.

    Args:
        active (pandas.DataFrame): Active products with an
            ``AtRisk`` column.
        cutoff (float): Top-third sales cutoff in units per month.
        path (pathlib.Path): Destination PNG; overwritten if present.

    Returns:
        None. Saves the figure to ``path``.
    """
    fig, ax = plt.subplots(figsize=(10, 6.2))
    y = active["WeeksOfStock"].clip(upper=Y_AXIS_CAP_WEEKS)
    capped = active["WeeksOfStock"] > Y_AXIS_CAP_WEEKS
    risk = active["AtRisk"]

    ax.axvspan(cutoff, active["MonthlyUnits"].max() * 1.08, ymax=LOW_STOCK_WEEKS / (Y_AXIS_CAP_WEEKS + 1), color=RISK_COLOR, alpha=0.08)
    ax.axvline(cutoff, color="black", linestyle=":", linewidth=0.8)
    ax.axhline(LOW_STOCK_WEEKS, color="black", linestyle=":", linewidth=0.8)
    ax.scatter(active.loc[~risk & ~capped, "MonthlyUnits"], y[~risk & ~capped], color=NEUTRAL_COLOR, s=36, label="Other active products")
    ax.scatter(active.loc[capped, "MonthlyUnits"], y[capped], color=NEUTRAL_COLOR, marker="^", s=44, label=f"More than {Y_AXIS_CAP_WEEKS} weeks (capped)")
    ax.scatter(active.loc[risk, "MonthlyUnits"], y[risk], color=RISK_COLOR, s=56, label=f"At risk ({risk.sum()} products)")
    key_lines = []
    ranked = active[risk].sort_values("WeeksOfStock").reset_index(drop=True)
    for number, row in ranked.iterrows():
        offset = LABEL_OFFSETS.get(row["ProductName"], (0, 7))
        ax.annotate(
            str(number + 1),
            (row["MonthlyUnits"], row["WeeksOfStock"]),
            xytext=offset,
            textcoords="offset points",
            ha="center",
            fontsize=9,
            fontweight="bold",
            color=RISK_COLOR,
        )
        key_lines.append(f"{number + 1}  {row['ProductName']} ({row['WeeksOfStock']:.1f} wk)")
    ax.text(
        0.99,
        0.97,
        "At-risk products\n" + "\n".join(key_lines),
        transform=ax.transAxes,
        ha="right",
        va="top",
        fontsize=8.5,
        linespacing=1.4,
        bbox={"boxstyle": "round,pad=0.5", "facecolor": "white", "edgecolor": "#cbd5e1"},
    )

    ax.text(cutoff + 0.5, Y_AXIS_CAP_WEEKS + 0.3, f"Top third of sellers (≥ {cutoff:.0f} units/month)", fontsize=9)
    ax.text(active["MonthlyUnits"].max() * 1.07, LOW_STOCK_WEEKS + 0.3, f"{LOW_STOCK_WEEKS:.0f} weeks of stock", fontsize=9, ha="right")
    ax.set_xlim(0, active["MonthlyUnits"].max() * 1.08)
    ax.set_ylim(0, Y_AXIS_CAP_WEEKS + 1)
    ax.set_xlabel("Average units sold per month (Jul 1996 – May 1998)")
    ax.set_ylabel("Weeks of stock on hand at that sales pace")
    ax.set_title("Best sellers with the least stock: 69 active products")
    ax.legend(frameon=True, facecolor="white", edgecolor="#cbd5e1", loc="center left", bbox_to_anchor=(0.01, 0.47))
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def plot_reorder_vs_sales(active, path):
    """Plot reorder level against sales pace for active products.

    Args:
        active (pandas.DataFrame): Active products with ``AtRisk``
            and ``BelowReorderLevel`` columns.
        path (pathlib.Path): Destination PNG; overwritten if present.

    Returns:
        None. Saves the figure to ``path``.
    """
    fig, ax = plt.subplots(figsize=(9, 5))
    risk = active["AtRisk"]
    flagged = active["BelowReorderLevel"]
    ax.scatter(active.loc[~risk, "MonthlyUnits"], active.loc[~risk, "ReorderLevel"], color=NEUTRAL_COLOR, s=36, label="Other active products")
    ax.scatter(active.loc[risk & flagged, "MonthlyUnits"], active.loc[risk & flagged, "ReorderLevel"], color=RISK_COLOR, s=56, label="At risk, flagged by reorder level")
    ax.scatter(active.loc[risk & ~flagged, "MonthlyUnits"], active.loc[risk & ~flagged, "ReorderLevel"], facecolors="white", edgecolors=RISK_COLOR, linewidths=1.8, s=56, label="At risk, NOT flagged by reorder level")
    corr = active["ReorderLevel"].corr(active["MonthlyUnits"])
    ax.set_xlabel("Average units sold per month (Jul 1996 – May 1998)")
    ax.set_ylabel("Reorder level set by Northwind (units)")
    ax.set_title(f"Reorder levels are unrelated to how fast products sell (correlation {corr:.2f})")
    ax.legend(frameon=False, loc="upper left")
    ax.set_ylim(-1, active["ReorderLevel"].max() * 1.35)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def main():
    """Run the Q3 analysis and write its tables and charts.

    Args:
        None.

    Returns:
        None. Writes CSVs to ``outputs`` and PNGs to
        ``docs/figures``, and prints a summary.
    """
    ensure_output_dirs()
    sheets = load_sheets()
    lines = dated_lines(sheets)
    products = product_stock_table(sheets, lines)
    active = products[~products["Discontinued"]].copy()
    active["AtRisk"], cutoff = flag_at_risk(active)
    recent_risk, recent_cutoff = flag_at_risk(active, "MonthlyUnitsRecent", "WeeksOfStockRecent")

    report_cols = [
        "ProductName",
        "CategoryName",
        "MonthlyUnits",
        "UnitsInStock",
        "WeeksOfStock",
        "UnitsOnOrder",
        "WeeksIncludingOnOrder",
        "ReorderLevel",
        "BelowReorderLevel",
    ]
    at_risk = active[active["AtRisk"]].sort_values("WeeksOfStock")[report_cols]
    at_risk.to_csv(OUTPUTS_DIR / "q3_at_risk_products.csv", index=False)
    active.sort_values("MonthlyUnits", ascending=False).to_csv(OUTPUTS_DIR / "q3_all_active_products.csv", index=False)
    discontinued = products[products["Discontinued"]].sort_values("MonthlyUnits", ascending=False)
    discontinued[["ProductName", "MonthlyUnits", "UnitsInStock"]].to_csv(OUTPUTS_DIR / "q3_discontinued_products.csv", index=False)

    plot_risk_scatter(active, cutoff, FIGURES_DIR / "q3_stock_risk.png")
    plot_reorder_vs_sales(active, FIGURES_DIR / "q3_reorder_vs_sales.png")

    print(f"Sales period: {period_months(lines):.1f} months; active products: {len(active)}")
    print(f"Median weeks of stock (active): {active['WeeksOfStock'].median():.1f}; "
          f"including on order: {active['WeeksIncludingOnOrder'].median():.1f}")
    print(f"Top-third seller cutoff: {cutoff:.1f} units/month")
    print(f"At risk (top third, < {LOW_STOCK_WEEKS:.0f} weeks): {len(at_risk)}; "
          f"flagged by reorder level: {at_risk['BelowReorderLevel'].sum()}; "
          f"with stock on order: {(at_risk['UnitsOnOrder'] > 0).sum()}")
    print(f"Correlation of reorder level with monthly sales: {active['ReorderLevel'].corr(active['MonthlyUnits']):.2f}")
    slow = active["MonthlyUnits"] < active["MonthlyUnits"].quantile(1 / 3)
    print(f"Slow sellers (bottom third) flagged by reorder level: {(slow & active['BelowReorderLevel']).sum()}")
    overlap = (active["AtRisk"] & recent_risk).sum()
    print(f"\nCheck with last 6 months' sales pace: {recent_risk.sum()} at risk, {overlap} also on the full-period list")
    print("\nAt-risk products:")
    print(at_risk.round(1).to_string(index=False))
    print("\nDiscontinued products still selling:")
    print(discontinued[["ProductName", "MonthlyUnits", "UnitsInStock"]].round(1).to_string(index=False))


if __name__ == "__main__":
    main()
