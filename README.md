# MIT 15.561 HW3 – Northwind sales analysis

Python scripts that answer five business questions from the Northwind
sample database. All scripts read the Excel workbook **read-only** and
write their results to `outputs/`.

## Data

- **Source:** `Northwind Database.xlsx`, the Northwind sample database
  (originally a Microsoft Access sample) as provided for this assignment
  in the course spreadsheet:
  <https://docs.google.com/spreadsheets/d/1mD4Hn4NZdJlXMC4EJcSp27vg-_jbxUYJ95vQvMbSpVM/edit>.
  Download it as `.xlsx` and save it under the file name below.
  Eight sheets: Categories, Customers, Employees, Orders Details, Orders,
  Shippers, Product, Suppliers. Orders run from 1996-07-04 to 1998-05-06.
- **Location:** put the workbook in the same folder as the scripts, with
  exactly this file name:

  ```
  HW3/
  ├── Northwind Database.xlsx
  ├── inspect_northwind.py
  ├── q1_country_markets.py
  ├── q2_customer_concentration.py
  ├── q3_shipping_time.py
  ├── q4_category_drivers.py
  ├── q5_discount_levels.py
  ├── build_site.py
  ├── requirements.txt
  ├── README.md
  ├── SKILL.md                          (course docstring skill, copy)
  └── .claude/skills/python-docstrings/SKILL.md
  ```

  Paths are resolved relative to each script (`Path(__file__)`), so the
  folder can live anywhere. The workbook is never modified; `openpyxl` is
  not needed because the scripts parse the xlsx with the standard library.

## Environment

- Tested only with **Python 3.13.1** on Windows 11. No other Python
  version has been tested.
- Third-party packages (pinned in `requirements.txt`): pandas 2.2.3,
  numpy 2.2.2, matplotlib 3.10.9.
- Version compatibility depends on the packages too. Their own metadata
  declares `Requires-Python >=3.9` (pandas 2.2.3) and `>=3.10` (numpy
  2.2.2, matplotlib 3.10.9), so these pins cannot be installed on Python
  3.9 or older. The transitive packages pip chose in the 3.13.1 test (for
  example contourpy 1.4.0, pillow 13.0.0) declare `>=3.11` or `>=3.12`;
  on an older Python pip would pick different versions. None of this has
  been tested.

Create a virtual environment and install them (Windows PowerShell):

```
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
```

macOS / Linux:

```
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

## Run order

Run from the HW3 folder, in this order (each script also runs on its own;
Q2, Q4 and Q5 import helpers from `q1_country_markets.py` and
`inspect_northwind.py`). Replace `python` with `.venv\Scripts\python`
(Windows) or `.venv/bin/python` (macOS / Linux) to use the virtual
environment.

```
python -c "import pathlib; [pathlib.Path('outputs', d).mkdir(parents=True, exist_ok=True) for d in ['q1_country', 'q2_customers', 'q3_shipping', 'q4_categories', 'q5_discounts']]"
python inspect_northwind.py          > outputs/inspect_run_log.txt
python q1_country_markets.py         > outputs/q1_country/q1_run_log.txt
python q2_customer_concentration.py  > outputs/q2_customers/q2_run_log.txt
python q3_shipping_time.py           > outputs/q3_shipping/q3_run_log.txt
python q4_category_drivers.py        > outputs/q4_categories/q4_run_log.txt
python q5_discount_levels.py         > outputs/q5_discounts/q5_run_log.txt
python build_site.py
```

The first line creates the output folders so the logs can be redirected
into them; you can also drop the `> ...` redirections and read the
summary in the terminal (each Q script creates its own folder). Console
output is UTF-8 and contains Chinese labels; the log file encoding then
depends on your shell.

Optional arguments: `inspect_northwind.py --structure-only`;
`q1_country_markets.py <Country>` (spot-check country, default
Switzerland); `q2_customer_concentration.py <CustomerID>` (default RATTC);
`q3_shipping_time.py <OrderID>` (default: the longest late 1997 order).

## Outputs

| Folder | Contents |
|---|---|
| `outputs/inspect_run_log.txt` | Sheet structure, keys, joins, dates, field availability |
| `outputs/q1_country/` | Customer-group bridge (table, per-customer groups, chart), country comparison tables, customer evidence, growth decomposition, background chart, Switzerland spot-check |
| `outputs/q2_customers/` | Customer table, concentration metrics, segments, threshold sensitivity, Pareto chart, RATTC spot-check |
| `outputs/q3_shipping/` | Shipper and ship-country tables, cumulative shares by day, order list, two distribution charts, order 10777 spot-check |
| `outputs/q4_categories/` | Category comparison and decomposition, product detail, price-level check, coverage and exceptions, three charts (decomposition, sales, metrics) |
| `outputs/q5_discounts/` | Discount-band summary, category summary, within-product comparison, order overlap, line list, two charts (within-product ratio, band distributions) |
| `site/` | Static website built by `build_site.py` (pages, `img/` charts, `data/` CSV downloads) |

Every Q folder has a `*_validation.csv` listing each reconciliation check
(expected, actual, difference, pass) and a `*_run_log.txt` if you redirect
the console output. The run logs end with the chart paths, which are
absolute paths on the machine that ran them.

CSV files are UTF-8 with BOM so Excel opens the Chinese headers correctly.
Amounts are discounted sales, `UnitPrice × Quantity × (1 − Discount)` from
order-detail lines, kept at full precision and rounded only for display.
The data has no currency field, so no currency is shown, and no cost
field, so nothing here is profit.

## Analysis website

`build_site.py` turns the results into a static English website in
`site/`: an overview page, one page per question and a downloads page.
Each question page follows the same order: business question and the
decision it supports → short answer and next step → why it matters →
method (formulas in an expandable section) → evidence (main chart and key
table) → findings → business interpretation and next steps → limitations
→ supplementary charts and tables and CSV downloads (expandable). Every
number on the pages is read from the CSV files in `outputs/`.
It uses only HTML and CSS (no JavaScript), reuses the PNG charts and
copies every result CSV and this README, with relative paths throughout.
Each Q script draws every chart twice from the same data: a Chinese
version (`*.png`) and an English version (`*_en.png`); the website shows
the English ones. Pages link to the course spreadsheet and to a
downloadable copy of this README.

Generate it after the six analysis scripts:

```
python build_site.py
```

It prints the number of pages, charts and CSV files and any broken local
links. Preview it locally in either way:

- open `site/index.html` directly in a browser, or
- serve the folder and visit <http://127.0.0.1:8561/>:

  ```
  python -m http.server 8561 --directory site --bind 127.0.0.1
  ```

Every page links to the GitHub repository
<https://github.com/ruxideng/ruxideng-15561-hw3> in the top navigation,
and the overview page links to it again. The scripts do not publish or
upload anything.

## Methods and main limitations

**Q1 – Where did each market's sales change come from?** *Question:* did
each country market's change in sales come mainly from customers who
bought in both windows buying more or less, from customers who bought only
in the 1998 window, or from customers who bought in the 1997 window but not
in the 1998 window — and which customer development or maintenance actions
should the sales team prioritise? *Decision:* which accounts and markets
to develop, review or follow up. Compares Jan–Apr 1997 with Jan–Apr 1998
(OrderDate) by `Customers.Country`. Customers are grouped by whether they
ordered in each window, and every country's change splits exactly into
(both-window sales 1998 − 1997) + 1998-window-only sales − 1997-window-only
sales; checks confirm the groups are mutually exclusive, cover every
customer active in either window and add up to each country's and the
company's change. Orders outside the windows are reported as context.
Country size, growth, AOV and concentration remain as background.
*Limitations:* window presence is not first purchase, retention or churn;
four-month windows and few customers per country; order-detail prices in
early 1997 are about 0.8× the 1998 level (see Q4); descriptive, not causal.

**Q2 – Customer concentration.** *Question:* how much do sales depend on a
few customers, and which customers should be maintained first to manage
revenue risk? *Decision:* which accounts get key-account management and
which head customers need a closer review. Full year 1997. Per customer: sales,
share of company sales, orders, AOV, largest single order. Top-1/5/10
shares, a Pareto chart (cumulative share in its own panel), and a split of
the 33 customers that make up ~80% of sales into those meeting a
repeat-purchase rule (≥6 orders, ≥3 quarters, largest order <50%) and
those that do not, tagged low frequency / few quarters / single-order
dominated.
*Limitations:* one year only, so no statement about stability across
years, lifetime value or churn; segment counts are sensitive to the
thresholds (a sensitivity table is included); no profit data.

**Q3 – Shipping time.** *Question:* which order groups take longer from
order to shipment, and where should operations managers look first?
*Decision:* which shipper assignments and destination countries to
investigate first. Charts: the cumulative share shipped within X days by
shipper, and every order by ship-to country (small samples grouped at the
bottom). 1997 orders from the Orders sheet only (no join to
details, so no double counting). Shipping time = ShippedDate − OrderDate in
calendar days; missing ship dates stay missing. By shipper and ship-to
country: orders, median, P90, orders over 14 days (an analysis threshold,
not a service standard), and share shipped after RequiredDate with its
denominator. Groups under 10 orders are marked as small samples.
*Limitations:* there is no delivery date, so on-time delivery cannot be
measured; shipping time includes internal handling and waiting, so
differences cannot be attributed to the shipper; P90 in small groups
depends on one to three orders; no significance tests.

**Q4 – Category drivers.** *Question:* is each product category's sales
change driven by quantity, realised price or discount, and which
categories deserve promotion or further investigation? *Decision:* which
categories to promote and which to investigate first. The main chart is
the decomposition; the "All categories" row is a separate split of
company totals, so its effects are not column sums. Jan–Apr 1997 vs 1998, details → Product →
Categories, using historical detail `UnitPrice` (never `Product.Price` or
`NewPrice`). Additive LMDI split of the sales change into summed-quantity,
like-for-like price (Fisher index over products sold in both windows),
product-mix residual and discount effects; the parts add up to the actual
change. A price-level check covers 321 of 322 lines in the 1997 window: on
or before 1997-04-04 every comparable line is about 0.8× the product's 1998
price, from 1997-04-07 it equals the 1998 price, with no exceptions.
*Limitations:* summed quantity mixes pack sizes and is not a physical
volume; the mix term is a residual; the effects are descriptive, not
causal; the observed price pattern is not evidence of a documented policy.

**Q5 – Discount levels.** *Question:* how do purchase quantity and
discounted sales differ across discount levels, and which categories merit
further testing of discount strategy? *Decision:* where to run controlled
discount tests. The main chart is the within-product ratio by category;
each category value is exp(median of ln(product ratio)) — the ordinary
median ratio for an odd number of products, the geometric mean of the two
middle ratios for an even number. 1997 order-detail lines grouped as no discount,
(0, 5%], (5, 10%], (10, 15%], >15%, using the discount rounded to 4
decimals for grouping (stored values are single precision) and the stored
value for sales. Per band: lines, unique orders and customers (orders can
appear in several bands, so band counts do not add up), quantity
quartiles, gross and net sales, effective discount rate. Within the same
product, compares median quantity on discounted vs undiscounted lines for
the 56 products with at least 3 lines of each; category intervals use a
product-level percentile bootstrap (5,000 resamples, seed 561).
*Limitations:* association only, not evidence that discounts raise
volume; discounts are not randomly assigned and the comparison does not
control for customer, order size, time or price changes; eight categories
with 4–11 products each are compared at once, so results are exploratory
and meant to design tests; no profit data.

## Fonts

Charts contain Chinese text. `inspect_northwind.CJK_FONTS` lists fonts
tried in order: Microsoft YaHei, SimHei (Windows), PingFang SC, Hiragino
Sans GB, Heiti SC (macOS), Noto Sans CJK SC, Source Han Sans SC,
WenQuanYi Zen Hei (Linux), Arial Unicode MS, then matplotlib's bundled
DejaVu Sans. Numbers and tables never depend on fonts. If no CJK font is
installed, charts still render but Chinese characters show as boxes and
matplotlib prints "Glyph missing" warnings. Fix on Linux, for example:

```
sudo apt install fonts-noto-cjk
rm -rf ~/.cache/matplotlib
```

The reference charts were produced with Microsoft YaHei; other fonts give
identical numbers but slightly different PNG files.

## Docstring skill

The course skill file (called SKILLS.md in the assignment; its name inside
the file is `python-docstrings`) is installed as a project skill for
Claude Code at:

```
.claude/skills/python-docstrings/SKILL.md
```

An identical copy is kept as `SKILL.md` in the HW3 root. Claude Code
discovers the skill when it is started in the HW3 folder. Invoke it by
typing the slash command with the files to document, for example:

```
/python-docstrings inspect_northwind.py q1_country_markets.py q2_customer_concentration.py q3_shipping_time.py q4_category_drivers.py q5_discount_levels.py build_site.py
```

All seven Python files were documented this way.

It edits docstrings only (Google style, one line per argument, a
`Returns:` section, lines ≤72 characters) and reports the docstrings it
wrote and any assumptions.
