import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from northwind import (
    FIGURES_DIR,
    OUTPUTS_DIR,
    ensure_output_dirs,
    load_sheets,
    orders_with_revenue,
)

BIG_ORDER_QUANTILE = 0.90
TOP_N_CUSTOMERS = 12
BIG_THREE_COLOR = "#c2410c"
OTHER_COLOR = "#64748b"


def big_order_cutoff(orders, quantile=BIG_ORDER_QUANTILE):
    return orders["Revenue"].quantile(quantile)


def customer_summary(orders, cutoff):
    orders = orders.assign(IsBig=orders["Revenue"] >= cutoff)
    summary = orders.groupby(["CompanyName", "Country"]).agg(
        TotalOrders=("OrderID", "count"),
        TotalRevenue=("Revenue", "sum"),
        BigOrders=("IsBig", "sum"),
    )
    big_revenue = (
        orders[orders["IsBig"]].groupby(["CompanyName", "Country"])["Revenue"].sum()
    )
    summary["BigOrderRevenue"] = big_revenue.reindex(summary.index).fillna(0)
    summary = summary[summary["BigOrders"] > 0].sort_values(
        "BigOrderRevenue", ascending=False
    )
    total_big = summary["BigOrderRevenue"].sum()
    summary["ShareOfBigOrderRevenue"] = summary["BigOrderRevenue"] / total_big
    summary["CumulativeShare"] = summary["ShareOfBigOrderRevenue"].cumsum()
    summary["ShareOfOwnOrdersBig"] = summary["BigOrders"] / summary["TotalOrders"]
    return summary.reset_index()


def cutoff_sensitivity(orders):
    q1, q3 = orders["Revenue"].quantile([0.25, 0.75])
    cutoffs = [
        ("$2,500 and up", 2500.0),
        ("Top 10% of orders", orders["Revenue"].quantile(0.90)),
        ("Outlier rule (Q3 + 1.5 IQR)", q3 + 1.5 * (q3 - q1)),
        ("Top 5% of orders", orders["Revenue"].quantile(0.95)),
        ("$5,000 and up", 5000.0),
    ]
    rows = []
    for label, cutoff in cutoffs:
        summary = customer_summary(orders, cutoff)
        rows.append(
            {
                "Definition": label,
                "Cutoff": round(cutoff, 2),
                "BigOrders": int(summary["BigOrders"].sum()),
                "CustomersWithBigOrders": len(summary),
                "Top3Customers": ", ".join(summary["CompanyName"].head(3)),
                "Top3Share": round(summary["ShareOfBigOrderRevenue"].head(3).sum(), 4),
            }
        )
    return pd.DataFrame(rows)


def plot_order_distribution(orders, cutoff, path):
    fig, ax = plt.subplots(figsize=(9, 4.8))
    low, high = np.log10(orders["Revenue"].min()), np.log10(orders["Revenue"].max())
    step = (high - low) / 40
    # Anchor the bin edges on the cutoff so no bar straddles it.
    anchor = np.log10(cutoff)
    edges = np.arange(anchor - np.ceil((anchor - low) / step) * step, high + step, step)
    bins = 10 ** edges
    is_big = orders["Revenue"] >= cutoff
    ax.hist(
        [orders.loc[~is_big, "Revenue"], orders.loc[is_big, "Revenue"]],
        bins=bins,
        stacked=True,
        color=[OTHER_COLOR, BIG_THREE_COLOR],
        label=[f"Other orders ({(~is_big).sum()})", f"Big orders, top 10% ({is_big.sum()})"],
    )
    ax.axvline(cutoff, color="black", linestyle="--", linewidth=1)
    ax.annotate(
        f"Cutoff ${cutoff:,.0f}",
        xy=(cutoff, ax.get_ylim()[1] * 0.9),
        xytext=(8, 0),
        textcoords="offset points",
    )
    ax.set_xscale("log")
    ax.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"${v:,.0f}"))
    ax.set_xlabel("Order value (USD, after discounts; log scale)")
    ax.set_ylabel("Number of orders")
    ax.set_title("Order values, Jul 1996 – May 1998 (830 orders)")
    ax.legend(frameon=False)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def plot_big_order_customers(summary, path, top_n=TOP_N_CUSTOMERS, highlight=3):
    top = summary.head(top_n)
    rest = summary.iloc[top_n:]
    labels = [f"{n} ({c})" for n, c in zip(top["CompanyName"], top["Country"])]
    values = list(top["BigOrderRevenue"])
    counts = list(top["BigOrders"])
    if len(rest):
        labels.append(f"{len(rest)} other customers")
        values.append(rest["BigOrderRevenue"].sum())
        counts.append(int(rest["BigOrders"].sum()))
    colors = [BIG_THREE_COLOR if i < highlight else OTHER_COLOR for i in range(len(values))]

    fig, ax = plt.subplots(figsize=(9, 6))
    y = np.arange(len(values))[::-1]
    ax.barh(y, values, color=colors)
    total = summary["BigOrderRevenue"].sum()
    for yi, v, n in zip(y, values, counts):
        ax.text(v + total * 0.004, yi, f"${v / 1000:,.0f}K · {n} order{'s' if n != 1 else ''} · {v / total:.0%}", va="center", fontsize=9)
    ax.set_yticks(y)
    ax.set_yticklabels(labels)
    ax.set_xlabel("Revenue from big orders (USD)")
    ax.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"${v / 1000:,.0f}K"))
    ax.set_xlim(0, max(values) * 1.35)
    ax.set_title("Who places the big orders? Revenue from top-10% orders by customer")
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def main():
    ensure_output_dirs()
    orders = orders_with_revenue(load_sheets())
    cutoff = big_order_cutoff(orders)
    summary = customer_summary(orders, cutoff)
    sensitivity = cutoff_sensitivity(orders)

    summary.to_csv(OUTPUTS_DIR / "q1_big_order_customers.csv", index=False)
    sensitivity.to_csv(OUTPUTS_DIR / "q1_cutoff_sensitivity.csv", index=False)
    plot_order_distribution(orders, cutoff, FIGURES_DIR / "q1_order_distribution.png")
    plot_big_order_customers(summary, FIGURES_DIR / "q1_big_order_customers.png")

    big = orders[orders["Revenue"] >= cutoff]
    print(f"Orders: {len(orders)}, total revenue ${orders['Revenue'].sum():,.0f}")
    print(f"Big-order cutoff (p90): ${cutoff:,.2f}")
    print(
        f"Big orders: {len(big)} ({big['Revenue'].sum() / orders['Revenue'].sum():.1%} of revenue) "
        f"from {len(summary)} of {orders['CustomerID'].nunique()} customers"
    )
    print("\nTop customers by big-order revenue:")
    print(summary.head(8).round(3).to_string(index=False))
    print("\nCutoff sensitivity:")
    print(sensitivity.to_string(index=False))


if __name__ == "__main__":
    main()
