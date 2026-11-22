# Northwind: Big Orders, Discounts and Stock Risk

Reproducible Python analysis of the Northwind Traders database for
15.561 HW 3 (AI-Assisted Business Data Analysis). It answers three
business questions:

1. **Big orders:** how many big orders are there, and do they come
   from one or two "whale" customers or many?
2. **Discounts:** do discounts lead to bigger orders, or should
   Northwind stop discounting?
3. **Stock risk:** which products sell a lot but are low on stock?

Webpage with the findings: https://antonsepetov.github.io/hw3-northwind/

## Repository layout

| Path | What it is |
|---|---|
| `Northwind Database.xlsx` | Input data (8 sheets: Orders, Orders Details, Customers, Product, Categories, Employees, Shippers, Suppliers) |
| `analysis/northwind.py` | Shared loader and revenue calculation used by every script |
| `analysis/q1_big_orders.py` | Question 1 |
| `analysis/q2_discounts.py` | Question 2 |
| `analysis/q3_inventory.py` | Question 3 |
| `outputs/` | Tables (CSV) written by the scripts |
| `docs/figures/` | Charts (PNG) written by the scripts and used on the webpage |
| `docs/` | The webpage (served by GitHub Pages) |
| `requirements.txt` | Pinned Python packages |
| `.claude/skills/python-docstrings/` | The course docstring skill used to document the code |

## Reproduce the results

Tested with Python 3.9 on macOS. Run these from the repository root.

1. Create and activate a virtual environment:

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```

   On Windows, activate with `.venv\Scripts\activate` instead.

2. Install the pinned packages (pandas, openpyxl, matplotlib):

   ```bash
   pip install -r requirements.txt
   ```

3. Run the three analyses. Each one reads `Northwind Database.xlsx`,
   prints its key numbers, and overwrites its files in `outputs/` and
   `docs/figures/`:

   ```bash
   python analysis/q1_big_orders.py
   python analysis/q2_discounts.py
   python analysis/q3_inventory.py
   ```

Each script takes a few seconds. The outputs are deterministic: running
them again produces identical tables and charts.

## Where each webpage number comes from

### Question 1: big orders (`q1_big_orders.py`)

| Webpage item | Source |
|---|---|
| Order value histogram | `docs/figures/q1_order_distribution.png` |
| Big-order revenue by customer chart | `docs/figures/q1_big_order_customers.png` |
| Cutoff ($3,161), 83 big orders, 38.1% of revenue, 30 customers | Printed by the script |
| Big three's 46.7% share of big-order revenue | `outputs/q1_big_order_customers.csv` (`CumulativeShare`, row 3) |
| Same result at five cutoffs | `outputs/q1_cutoff_sensitivity.csv` |

### Question 2: discounts (`q2_discounts.py`)

| Webpage item | Source |
|---|---|
| Quantity lift chart with break-even line | `docs/figures/q2_quantity_lift.png` |
| Quantity by discount level chart | `docs/figures/q2_relative_quantity_by_level.png` |
| $88,666 given away, 6.5% of gross, +17.2% break-even | Printed by the script |
| +25% / +21% / −1% / +10% lifts | `outputs/q2_quantity_lift.csv` (`MeanLift`) |
| Relative quantity and 95% intervals by level | `outputs/q2_relative_quantity_by_level.csv` |
| Revenue and discount given by level | `outputs/q2_discount_levels.csv` |

### Question 3: stock risk (`q3_inventory.py`)

| Webpage item | Source |
|---|---|
| Sales pace vs weeks of stock chart | `docs/figures/q3_stock_risk.png` |
| Reorder level vs sales chart | `docs/figures/q3_reorder_vs_sales.png` |
| Table of 9 at-risk products | `outputs/q3_at_risk_products.csv` |
| Every active product's pace and stock | `outputs/q3_all_active_products.csv` |
| Discontinued products still selling | `outputs/q3_discontinued_products.csv` |
| Reorder-level correlation (−0.11) and recent-pace check | Printed by the script |

## Definitions and analytical choices

- **Revenue** = `UnitPrice × Quantity × (1 − Discount)` from Orders
  Details, in USD. Discounts are rounded to two decimals because the
  workbook stores them as values like 0.0500000007. Total revenue is
  $1,265,793 across 830 orders (4 Jul 1996 – 6 May 1998).
- **Big order (Q1):** an order at or above the 90th percentile of order
  revenue, i.e. the top 10% of orders. Four other cutoffs are reported
  as a check.
- **Discount effect (Q2):** quantities on discounted vs full-price lines
  are compared within the same customer (and within the same customer
  and product), because discounts go mostly to customers who already
  buy in bulk. Group ratios are averaged geometrically so small groups
  with extreme ratios do not dominate. Break-even is the extra quantity
  needed to offset the average discount on discounted lines.
- **Stock risk (Q3):** sales pace is average units per month over the
  whole period (22.1 months). Weeks of stock = units in stock ÷ weekly
  sales. At risk = active (not discontinued) products in the top third
  by sales pace with under 2 weeks of stock. The script also reports
  the list using only the last six full months (Nov 1997 – Apr 1998) as
  a check.
- The stock snapshot in the Product sheet is undated; it is treated as
  the stock position at the end of the order data.
- The Product sheet contains extra columns that are not part of the
  standard Northwind schema (`Cheap`, `NewPrice`, `IsCheap`, an unnamed
  column and duplicates). They are not used.

## Limitations

- The data is observational. Q2 cannot show whether customers would
  have left without discounts, and there is no cost data, so results
  are about revenue, not profit.
- Q3 uses the long-run sales pace, which is slow to reflect products
  whose sales have recently jumped (for example Konbu).

## Documentation

All Python code was documented with the course `python-docstrings`
skill (installed in `.claude/skills/python-docstrings/SKILL.md`),
invoked in Claude Code as `/python-docstrings` on the four files in
`analysis/`.
