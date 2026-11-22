"""Q2: do discounts lead to bigger orders?

Writes charts to ``docs/figures`` and tables to ``outputs``.
"""

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from northwind import FIGURES_DIR, OUTPUTS_DIR, ensure_output_dirs, line_items, load_sheets

STANDARD_LEVELS = [0.0, 0.05, 0.10, 0.15, 0.20, 0.25]
DISCOUNT_COLOR = "#c2410c"
NEUTRAL_COLOR = "#64748b"


def prepare_lines(sheets):
    """Return order lines with customer, gross revenue and discount.

    Args:
        sheets (dict[str, pandas.DataFrame]): Workbook from
            ``load_sheets``.

    Returns:
        pandas.DataFrame: Order lines with ``CustomerID``,
        ``GrossRevenue`` and ``DiscountGiven`` (both USD) and a
        boolean ``Discounted`` column.
    """
    lines = line_items(sheets).merge(
        sheets["Orders"][["OrderID", "CustomerID"]], on="OrderID"
    )
    lines["GrossRevenue"] = lines["UnitPrice"] * lines["Quantity"]
    lines["DiscountGiven"] = lines["GrossRevenue"] - lines["Revenue"]
    lines["Discounted"] = lines["Discount"] > 0
    return lines


def discount_level_summary(lines):
    """Summarize quantity and revenue at each discount rate.

    Args:
        lines (pandas.DataFrame): Order lines from ``prepare_lines``.

    Returns:
        pandas.DataFrame: One row per distinct discount rate with
        line count, mean and median quantity, revenue and discount
        given (USD).
    """
    summary = lines.groupby("Discount").agg(
        Lines=("OrderID", "count"),
        AvgQuantity=("Quantity", "mean"),
        MedianQuantity=("Quantity", "median"),
        Revenue=("Revenue", "sum"),
        DiscountGiven=("DiscountGiven", "sum"),
    )
    return summary.reset_index()


def within_group_lift(lines, keys):
    """Measure extra quantity on discounted lines within groups.

    For each group with both discounted and full-price lines, takes
    the ratio of mean quantities, then averages the ratios
    geometrically.

    Args:
        lines (pandas.DataFrame): Order lines from ``prepare_lines``.
        keys (list[str]): Columns defining a group, e.g.
            ``["CustomerID"]``.

    Returns:
        dict: ``Groups`` (int, groups compared), ``MeanLift`` (float,
        geometric-mean lift; 0.10 means 10% more units),
        ``MedianLift`` (float) and ``GroupsWhereDiscountedHigher``
        (int).
    """
    means = lines.groupby(keys + ["Discounted"])["Quantity"].mean().unstack()
    both = means.dropna()
    ratios = both[True] / both[False]
    # Geometric mean: a plain mean of ratios is dominated by small groups
    # with extreme ratios (e.g. 1 unit vs 40 units).
    return {
        "Groups": len(both),
        "MeanLift": np.exp(np.log(ratios).mean()) - 1,
        "MedianLift": ratios.median() - 1,
        "GroupsWhereDiscountedHigher": int((ratios > 1).sum()),
    }


def comparison_table(lines):
    """Compare discounted vs full-price quantity under four groupings.

    Args:
        lines (pandas.DataFrame): Order lines from ``prepare_lines``.

    Returns:
        pandas.DataFrame: One row per comparison (all lines, same
        product, same customer, same customer and product) with the
        fields of ``within_group_lift``. The all-lines row uses a
        ratio of means and leaves the other fields empty.
    """
    by_flag = lines.groupby("Discounted")["Quantity"].mean()
    rows = [
        {
            "Comparison": "All lines (no adjustment)",
            "Groups": None,
            "MeanLift": by_flag[True] / by_flag[False] - 1,
            "MedianLift": None,
            "GroupsWhereDiscountedHigher": None,
        }
    ]
    for label, keys in [
        ("Same product", ["ProductID"]),
        ("Same customer", ["CustomerID"]),
        ("Same customer and product", ["CustomerID", "ProductID"]),
    ]:
        rows.append({"Comparison": label, **within_group_lift(lines, keys)})
    return pd.DataFrame(rows)


def relative_quantity_by_level(lines, levels=STANDARD_LEVELS):
    """Return quantity relative to each customer's full-price average.

    Args:
        lines (pandas.DataFrame): Order lines from ``prepare_lines``.
        levels (list[float]): Discount rates to keep, as fractions;
            other rates are dropped.

    Returns:
        pandas.DataFrame: One row per discount rate with ``Lines``,
        ``RelativeQuantity`` (mean ratio; 1.0 is the customer's
        usual full-price quantity), ``std`` and ``CI95`` (half-width
        of a normal-approximation 95% interval). Customers with no
        full-price lines are excluded.
    """
    baseline = (
        lines[~lines["Discounted"]].groupby("CustomerID")["Quantity"].mean().rename("Baseline")
    )
    rel = lines.merge(baseline, on="CustomerID")
    rel = rel[rel["Discount"].isin(levels)]
    rel["Relative"] = rel["Quantity"] / rel["Baseline"]
    summary = rel.groupby("Discount")["Relative"].agg(["count", "mean", "std"])
    summary["CI95"] = 1.96 * summary["std"] / np.sqrt(summary["count"])
    return summary.reset_index().rename(columns={"count": "Lines", "mean": "RelativeQuantity"})


def break_even_lift(lines):
    """Return the quantity lift that offsets the average discount.

    Args:
        lines (pandas.DataFrame): Order lines from ``prepare_lines``.

    Returns:
        float: Required lift (0.172 means 17.2% more units), using
        the gross-revenue-weighted discount rate of discounted lines.
    """
    discounted = lines[lines["Discounted"]]
    rate = discounted["DiscountGiven"].sum() / discounted["GrossRevenue"].sum()
    return 1 / (1 - rate) - 1


def plot_comparison(table, break_even, path):
    """Plot quantity lift by comparison with a break-even line.

    Args:
        table (pandas.DataFrame): Output of ``comparison_table``.
        break_even (float): Break-even lift as a fraction, from
            ``break_even_lift``.
        path (pathlib.Path): Destination PNG; overwritten if present.

    Returns:
        None. Saves the figure to ``path``.
    """
    fig, ax = plt.subplots(figsize=(9, 4.8))
    labels = table["Comparison"]
    values = table["MeanLift"] * 100
    colors = [NEUTRAL_COLOR if "customer" not in c else DISCOUNT_COLOR for c in labels]
    y = np.arange(len(values))[::-1]
    ax.barh(y, values, color=colors)
    for yi, v in zip(y, values):
        ax.text(max(v, 0) + 0.6, yi, f"{v:+.0f}%", va="center", fontsize=11)
    ax.axvline(0, color="black", linewidth=0.8)
    ax.axvline(break_even * 100, color="black", linestyle="--", linewidth=1)
    ax.text(
        break_even * 100 + 0.4,
        1,
        f"Break-even: +{break_even:.0%} more units\nneeded to offset the average discount",
        fontsize=9,
        va="center",
    )
    ax.set_yticks(y)
    ax.set_yticklabels(labels)
    ax.set_xlim(-3, max(values) * 1.3)
    ax.set_ylim(-0.6, y.max() + 0.7)
    ax.set_xlabel("Extra units per order line when discounted vs full price (%)")
    ax.set_title("Like-for-like, discounted lines are not big enough to pay for the discount")
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def plot_relative_quantity(rel, path):
    """Plot relative quantity by discount rate with 95% intervals.

    Args:
        rel (pandas.DataFrame): Output of
            ``relative_quantity_by_level``.
        path (pathlib.Path): Destination PNG; overwritten if present.

    Returns:
        None. Saves the figure to ``path``.
    """
    fig, ax = plt.subplots(figsize=(9, 4.5))
    labels = ["Full price" if d == 0 else f"{d:.0%} off" for d in rel["Discount"]]
    colors = [NEUTRAL_COLOR if d == 0 else DISCOUNT_COLOR for d in rel["Discount"]]
    x = np.arange(len(rel))
    ax.bar(x, rel["RelativeQuantity"], yerr=rel["CI95"], color=colors, capsize=4)
    ax.axhline(1.0, color="black", linestyle="--", linewidth=0.8)
    for xi, v, n in zip(x, rel["RelativeQuantity"], rel["Lines"]):
        ax.text(xi, 0.05, f"{v:.2f}×\n{n} lines", ha="center", color="white", fontsize=9)
    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.set_ylabel("Units vs the customer's own full-price average")
    ax.set_title("Bigger discounts do not buy bigger orders (95% confidence intervals)")
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def main():
    """Run the Q2 analysis and write its tables and charts.

    Args:
        None.

    Returns:
        None. Writes CSVs to ``outputs`` and PNGs to
        ``docs/figures``, and prints a summary.
    """
    ensure_output_dirs()
    lines = prepare_lines(load_sheets())
    levels = discount_level_summary(lines)
    table = comparison_table(lines)
    rel = relative_quantity_by_level(lines)

    levels.to_csv(OUTPUTS_DIR / "q2_discount_levels.csv", index=False)
    table.to_csv(OUTPUTS_DIR / "q2_quantity_lift.csv", index=False)
    rel.to_csv(OUTPUTS_DIR / "q2_relative_quantity_by_level.csv", index=False)
    break_even = break_even_lift(lines)
    plot_comparison(table, break_even, FIGURES_DIR / "q2_quantity_lift.png")
    plot_relative_quantity(rel, FIGURES_DIR / "q2_relative_quantity_by_level.png")

    gross = lines["GrossRevenue"].sum()
    given = lines["DiscountGiven"].sum()
    print(f"Lines: {len(lines)}, discounted: {lines['Discounted'].sum()} ({lines['Discounted'].mean():.1%})")
    print(f"Discount given: ${given:,.0f} ({given / gross:.1%} of gross ${gross:,.0f})")
    print(f"Break-even quantity lift for the average discount: {break_even:+.1%}")
    customers = lines.groupby("CustomerID")["Discounted"].any()
    print(f"Customers never discounted: {(~customers).sum()} of {len(customers)}")
    print("\nQuantity lift on discounted lines:")
    print(table.round(3).to_string(index=False))
    print("\nRelative quantity by discount level (same customer):")
    print(rel.round(3).to_string(index=False))
    print("\nBy discount level:")
    print(levels.round({"AvgQuantity": 1, "Revenue": 0, "DiscountGiven": 0}).to_string(index=False))


if __name__ == "__main__":
    main()
