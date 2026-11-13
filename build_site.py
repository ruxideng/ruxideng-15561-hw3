"""Build the static English analysis site in site/ from outputs/.

Run after the six analysis scripts; open site/index.html to preview.
"""

import html
import re
import shutil
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).parent
OUTPUTS = ROOT / "outputs"
SITE = ROOT / "site"
QDIRS = ["q1_country", "q2_customers", "q3_shipping", "q4_categories", "q5_discounts"]
DATA_URL = "https://docs.google.com/spreadsheets/d/1mD4Hn4NZdJlXMC4EJcSp27vg-_jbxUYJ95vQvMbSpVM/edit"
REPO_URL = "https://github.com/ruxideng/ruxideng-15561-hw3"
PAGES = [("index.html", "Overview"), ("q1.html", "Q1 Markets"), ("q2.html", "Q2 Customers"),
         ("q3.html", "Q3 Shipping"), ("q4.html", "Q4 Categories"), ("q5.html", "Q5 Discounts"),
         ("downloads.html", "Downloads")]

Q1_FLAGS = {
    "基期窗口无销售、本期窗口有销售": "no sales in 1997 window, sales in 1998 window",
    "低基数": "low base (<2% of 1997 total)",
    "本期窗口无销售": "no sales in 1998 window",
    "某期客户≤2": "≤2 customers in a window",
    "某期最大客户销售占比>50%": "one customer >50% of a window's sales",
}
Q2_SEGMENTS = {
    "头部·持续多次购买": "Head · meets repeat rule",
    "未满足持续购买规则的头部客户": "Head · misses repeat rule",
    "其余客户·满足持续购买规则": "Rest · meets repeat rule",
    "其余客户·未满足持续购买规则": "Rest · misses repeat rule",
    "1997年无订单": "No 1997 orders",
}
Q2_TAGS = {"低频": "low frequency", "季度覆盖不足": "few quarters", "单笔主导": "single-order dominated"}
Q5_BANDS = {"无折扣": "No discount", "0–5%": "(0, 5%]", ">5–10%": "(5, 10%]",
            ">10–15%": "(10, 15%]", ">15%": "> 15%", "全部": "All lines"}

CSV_NOTES = {
    "q1_country_comparison.csv": "Country table, rounded, Chinese headers",
    "q1_country_raw_precision.csv": "Country table, full precision",
    "q1_customer_evidence.csv": "Customer evidence for USA, Germany and declining countries",
    "q1_customer_sales_by_country.csv": "Sales per customer per window",
    "q1_growth_decomposition.csv": "Log split of growth into orders and AOV",
    "q1_customer_group_bridge.csv": "Change by country split into the three customer buying groups",
    "q1_customer_groups.csv": "Every customer's window sales, orders, group and out-of-window orders",
    "q2_customer_table.csv": "All 91 customers, rounded, Chinese headers",
    "q2_customer_raw_precision.csv": "All 91 customers, full precision",
    "q2_concentration_summary.csv": "Top-N shares, HHI and other concentration measures",
    "q2_segment_summary.csv": "Segment totals",
    "q2_unmet_rule_breakdown.csv": "Head customers missing the repeat rule, by rule",
    "q2_threshold_sensitivity.csv": "Repeat-rule threshold sensitivity",
    "q2_order_sales_1997.csv": "1997 order-level sales",
    "q3_by_shipper.csv": "Shipper table with denominators",
    "q3_by_shipper_raw.csv": "Shipper table, full precision",
    "q3_by_country.csv": "Ship-country table with denominators",
    "q3_by_country_raw.csv": "Ship-country table, full precision",
    "q3_required_window_vs_late.csv": "Required window vs shipped after RequiredDate",
    "q3_shipper_cumulative_share_by_day.csv": "Share shipped within X days, by shipper",
    "q3_orders_1997.csv": "All 408 orders of 1997 with shipping days",
    "q4_category_comparison.csv": "Category table and decomposition, rounded",
    "q4_category_raw_precision.csv": "Category table and decomposition, full precision",
    "q4_product_detail.csv": "Per-product quantities, prices and sales",
    "q4_price_level_check.csv": "Share of lines below the 1998 price level",
    "q4_price_level_coverage.csv": "Coverage of the price-level comparison",
    "q4_price_level_exceptions.csv": "Lines not matching the price pattern (empty)",
    "q5_discount_band_summary.csv": "Discount-band table",
    "q5_category_discount_summary.csv": "Category discount use and within-product ratios",
    "q5_within_product_comparison.csv": "Per-product discounted vs undiscounted quantity",
    "q5_relative_quantity_by_band.csv": "Relative quantity by band",
    "q5_order_overlap.csv": "Orders and customers across bands",
    "q5_lines_1997.csv": "All 1,059 order lines of 1997 with bands",
}

CSS = """
:root { color-scheme: light dark;
  --bg: #f9f9f7; --surface: #fcfcfb; --ink: #0b0b0b; --ink2: #52514e;
  --muted: #6b6a66; --line: #e1e0d9; --accent: #2a78d6; --accent-soft: #e8f1fc;
  --warn: #b25b00; }
@media (prefers-color-scheme: dark) { :root {
  --bg: #0d0d0d; --surface: #1a1a19; --ink: #f0efec; --ink2: #c3c2b7;
  --muted: #9a998f; --line: #2c2c2a; --accent: #6aa5ef; --accent-soft: #17283d;
  --warn: #f0a24a; } }
* { box-sizing: border-box; }
body { margin: 0; background: var(--bg); color: var(--ink);
  font: 16px/1.6 system-ui, -apple-system, "Segoe UI", "Microsoft YaHei", sans-serif; }
a { color: var(--accent); }
header.top { background: var(--surface); border-bottom: 1px solid var(--line); }
header.top .wrap { display: flex; flex-wrap: wrap; gap: 4px 16px; align-items: baseline;
  padding-top: 12px; padding-bottom: 12px; }
header.top .brand { font-weight: 600; margin-right: auto; }
nav a { text-decoration: none; color: var(--ink2); padding: 2px 0; }
nav a[aria-current] { color: var(--accent); font-weight: 600; }
nav { display: flex; flex-wrap: wrap; gap: 4px 14px; font-size: 15px; }
.wrap { max-width: 980px; margin: 0 auto; padding-left: 16px; padding-right: 16px; }
main { padding-bottom: 48px; }
h1 { font-size: 1.9rem; line-height: 1.25; margin: 28px 0 8px; }
h2 { font-size: 1.3rem; margin: 36px 0 10px; padding-top: 8px; border-top: 1px solid var(--line); }
h3 { font-size: 1.05rem; margin: 22px 0 6px; }
.lede { color: var(--ink2); font-size: 1.05rem; margin-top: 0; }
.question { background: var(--accent-soft); border-left: 4px solid var(--accent);
  padding: 12px 16px; border-radius: 6px; margin: 16px 0; }
.question .label { display: block; font-size: .8rem; letter-spacing: .04em;
  text-transform: uppercase; color: var(--ink2); font-weight: 600; }
.question .decision { margin-top: 10px; }
.answer { background: var(--surface); border: 1px solid var(--line); border-left: 4px solid #1baf7a;
  border-radius: 6px; padding: 4px 16px; }
strong { font-weight: 700; }
/* Charts may extend past the 980px text column on wide screens so their labels stay readable. */
figure { width: min(1240px, calc(100vw - 48px)); position: relative; left: 50%; transform: translateX(-50%); }
@media (max-width: 1020px) { figure { width: auto; left: auto; transform: none; } }
.cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 14px; }
.card { background: var(--surface); border: 1px solid var(--line); border-radius: 8px; padding: 14px 16px; }
.card h3 { margin-top: 0; }
.card p { margin: 6px 0; }
.stat { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 10px; margin: 14px 0; }
.stat div { background: var(--surface); border: 1px solid var(--line); border-radius: 8px; padding: 10px 12px; }
.stat b { display: block; font-size: 1.35rem; font-variant-numeric: tabular-nums; }
.stat span { color: var(--ink2); font-size: .85rem; }
figure { margin: 18px 0; }
figure img { width: 100%; height: auto; display: block; border: 1px solid var(--line);
  border-radius: 6px; background: #fcfcfb; }
figcaption { color: var(--ink2); font-size: .9rem; margin-top: 6px; }
.table-wrap { overflow-x: auto; margin: 12px 0; border: 1px solid var(--line); border-radius: 6px;
  background: var(--surface); }
table { border-collapse: collapse; width: 100%; font-size: .88rem; }
th, td { padding: 6px 10px; border-bottom: 1px solid var(--line); text-align: right;
  white-space: nowrap; font-variant-numeric: tabular-nums; }
th:first-child, td:first-child, th.l, td.l { text-align: left; }
td.wrap-cell { white-space: normal; min-width: 180px; text-align: left; }
thead th { background: var(--bg); position: sticky; top: 0; }
tr.total td { font-weight: 600; }
.note { color: var(--muted); font-size: .88rem; }
details { background: var(--surface); border: 1px solid var(--line); border-radius: 6px;
  padding: 8px 14px; margin: 12px 0; }
summary { cursor: pointer; font-weight: 600; }
code, .formula { font-family: ui-monospace, Consolas, monospace; font-size: .9em; }
.formula { display: block; overflow-x: auto; padding: 8px 10px; background: var(--bg);
  border-radius: 4px; margin: 8px 0; white-space: pre-wrap; }
ul.tight li { margin: 4px 0; }
.limits li { color: var(--ink2); }
.pass { color: #0c7a0c; font-weight: 600; }
@media (prefers-color-scheme: dark) { .pass { color: #4ccf4c; } }
footer { border-top: 1px solid var(--line); color: var(--muted); font-size: .85rem; padding: 18px 0 30px; }
@media (max-width: 600px) { h1 { font-size: 1.5rem; } body { font-size: 15px; } }
"""


def esc(x):
    """Escape a value for HTML text.

    Args:
        x (object): Value to show; converted with ``str``.

    Returns:
        str: HTML-escaped text.
    """
    return html.escape(str(x))


def money(x, d=2):
    """Format an amount with thousands separators.

    Args:
        x (float): Amount; NaN allowed.
        d (int): Decimal places.

    Returns:
        str: e.g. "191,321.88", or "n/a" for NaN.
    """
    return "n/a" if pd.isna(x) else f"{x:,.{d}f}"


def signed(x, d=2):
    """Format an amount with an explicit sign.

    Args:
        x (float): Amount; NaN allowed.
        d (int): Decimal places.

    Returns:
        str: e.g. "+53,190.05", or "n/a" for NaN.
    """
    return "n/a" if pd.isna(x) else f"{x:+,.{d}f}"


def pct(x, d=1, sign=False):
    """Format a ratio as a percentage.

    Args:
        x (float): Ratio, e.g. 0.207 for 20.7%; NaN allowed.
        d (int): Decimal places.
        sign (bool): Prefix positive values with "+".

    Returns:
        str: e.g. "20.7%", or "n/a" for NaN.
    """
    if pd.isna(x):
        return "n/a"
    return f"{x * 100:+.{d}f}%" if sign else f"{x * 100:.{d}f}%"


def read(qdir, name, **kw):
    """Read one result CSV from ``outputs``.

    Args:
        qdir (str): Sub-folder of ``outputs``, e.g. "q1_country".
        name (str): CSV file name.
        **kw (Any): Extra keyword arguments for ``pandas.read_csv``.

    Returns:
        pandas.DataFrame: The table as read (UTF-8 with BOM).
    """
    return pd.read_csv(OUTPUTS / qdir / name, encoding="utf-8-sig", **kw)


def table(df, left=(), wrap=(), total_last=False):
    """Render a DataFrame of display strings as an HTML table.

    Args:
        df (pandas.DataFrame): Cells already formatted as text; the
            index is not shown.
        left (tuple[str, ...]): Columns to left-align.
        wrap (tuple[str, ...]): Columns allowed to wrap lines.
        total_last (bool): Style the last row as a total row.

    Returns:
        str: A ``<table>`` inside a horizontally scrollable wrapper.
    """
    def cls(c):
        """Return the class attribute for column ``c``.

        Args:
            c (str): Column name.

        Returns:
            str: ``' class="..."'`` or an empty string.
        """
        if c in wrap:
            return ' class="wrap-cell"'
        return ' class="l"' if c in left else ""

    head = "".join(f"<th{cls(c)}>{esc(c)}</th>" for c in df.columns)
    rows = []
    for i, (_, r) in enumerate(df.iterrows()):
        tr = ' class="total"' if total_last and i == len(df) - 1 else ""
        rows.append(f"<tr{tr}>" + "".join(f"<td{cls(c)}>{esc(r[c])}</td>" for c in df.columns) + "</tr>")
    return (f'<div class="table-wrap"><table><thead><tr>{head}</tr></thead>'
            f'<tbody>{"".join(rows)}</tbody></table></div>')


def figure(img, alt, caption):
    """Render a figure that points at the English version of a PNG.

    Args:
        img (str): Chart file name as written by the analysis scripts;
            its ``_en`` counterpart inside ``site/img`` is shown.
        alt (str): Alternative text.
        caption (str): Caption HTML (not escaped).

    Returns:
        str: ``<figure>`` markup.
    """
    img = img.replace(".png", "_en.png")
    return (f'<figure><a href="img/{img}"><img src="img/{img}" alt="{esc(alt)}" loading="lazy"></a>'
            f"<figcaption>{caption}</figcaption></figure>")


def checks_line(qdir, prefix):
    """Summarise a question's validation file as one sentence.

    Args:
        qdir (str): Sub-folder of ``outputs``.
        prefix (str): Validation file prefix, e.g. "q1".

    Returns:
        str: HTML sentence with the pass count and a link to the CSV.
    """
    v = read(qdir, f"{prefix}_validation.csv")
    passed = int(v["通过"].astype(str).eq("True").sum())
    status = ('<span class="pass">all passed</span>' if passed == len(v)
              else f"<strong>{len(v) - passed} failed</strong>")
    return (f"{len(v)} reconciliation checks, {status} "
            f'(<a href="data/{qdir}/{prefix}_validation.csv">{prefix}_validation.csv</a>).')


def section(title, body):
    """Wrap content in an ``<h2>`` section.

    Args:
        title (str): Section heading text.
        body (str): Section HTML.

    Returns:
        str: Section markup.
    """
    return f"<section><h2>{esc(title)}</h2>{body}</section>"


def bullets(items, cls="tight"):
    """Render a bullet list.

    Args:
        items (list[str]): Item HTML (not escaped).
        cls (str): Class for the ``<ul>``.

    Returns:
        str: ``<ul>`` markup.
    """
    return f'<ul class="{cls}">' + "".join(f"<li>{i}</li>" for i in items) + "</ul>"


def downloads_for(qdir):
    """List links to every CSV of one question.

    Args:
        qdir (str): Sub-folder of ``outputs``.

    Returns:
        str: Bullet list of CSV links with short descriptions.
    """
    items = []
    for p in sorted((OUTPUTS / qdir).glob("*.csv")):
        note = CSV_NOTES.get(p.name, "Reconciliation checks (expected, actual, pass)"
                             if p.name.endswith("_validation.csv") else "Spot-check detail")
        items.append(f'<a href="data/{qdir}/{p.name}">{esc(p.name)}</a> — {esc(note)}')
    return bullets(items)


def page(fname, title, body):
    """Wrap page content with the shared head, navigation and footer.

    The navigation lists ``PAGES`` and ends with a "GitHub Repository"
    link to ``REPO_URL``.

    Args:
        fname (str): Output file name, used to mark the current tab.
        title (str): Page title.
        body (str): Main content HTML.

    Returns:
        str: Complete HTML document.
    """
    nav = "".join(f'<a href="{f}"{" aria-current=\"page\"" if f == fname else ""}>{esc(t)}</a>'
                  for f, t in PAGES)
    nav += f'<a href="{REPO_URL}" rel="noopener">GitHub Repository</a>'
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)} · Northwind Analysis</title>
<link rel="stylesheet" href="style.css"></head>
<body><header class="top"><div class="wrap"><span class="brand">Northwind Analysis</span>
<nav>{nav}</nav></div></header>
<main class="wrap">{body}</main>
<footer><div class="wrap">MIT 15.561 HW3. Data: <a href="{DATA_URL}">course spreadsheet</a>.
Generated by <code>build_site.py</code> from the CSV and PNG files in <code>outputs/</code>;
<a href="README.md" download>README (download)</a>. Amounts are discounted sales without freight; the
data has no currency field and no cost field, so no currency is shown and nothing here is profit.</div></footer>
</body></html>"""


def qpage(fname, title, question, decision, answer, why, method, details, evidence, findings,
          implications, limits, supplement, qdir, prefix):
    """Assemble a question page in the fixed reading order.

    Order: question and decision, short answer, why it matters, method
    (core visible, formulas expandable), evidence, findings, business
    interpretation, limitations, then supplementary material and
    downloads inside expandable blocks.

    Args:
        fname (str): Output file name.
        title (str): Page heading.
        question (str): Full business question text.
        decision (str): Management decision the question supports.
        answer (str): Short answer and recommendation HTML.
        why (str): Why-it-matters HTML.
        method (str): Plain-language method HTML (always visible).
        details (str): HTML inside the expandable formula block.
        evidence (str): Main chart(s) and key table HTML.
        findings (list[str]): Findings, one HTML item each.
        implications (list[str]): Interpretation and next steps, HTML.
        limits (list[str]): Limitations, HTML items.
        supplement (str): Supplementary charts and tables HTML; may be
            empty.
        qdir (str): Sub-folder of ``outputs`` for downloads.
        prefix (str): Validation file prefix.

    Returns:
        str: Complete HTML document.
    """
    supp = (f"<details><summary>Supplementary charts and tables</summary>{supplement}</details>"
            if supplement else "")
    body = (f"<h1>{esc(title)}</h1>"
            f'<div class="question"><span class="label">Business question</span>{esc(question)}'
            f'<span class="label decision">Decision it supports</span>{esc(decision)}</div>'
            + section("Short answer", f'<div class="answer">{answer}</div>')
            + section("Why it matters", why)
            + section("Method", method + f"<details><summary>Formulas, definitions and analysis choices"
                                         f"</summary>{details}</details>"
                      + f'<p class="note">{checks_line(qdir, prefix)}</p>')
            + section("Evidence", evidence)
            + section("Findings", bullets(findings))
            + section("Business interpretation and next steps", bullets(implications)
                      + '<p class="note">These are candidate directions for further evaluation, not decisions '
                        "the data can settle on its own.</p>")
            + section("Limitations and boundaries", bullets(limits, "tight limits"))
            + section("Supplementary material and downloads", supp
                      + "<details><summary>Download the full result tables (CSV)</summary>"
                      + downloads_for(qdir)
                      + '<p class="note">CSV files are UTF-8 with BOM; some headers are in Chinese.</p>'
                      + "</details>"))
    return page(fname, title, body)


def build_q1():
    """Build the Q1 page and return its overview summary.

    Args:
        None.

    Returns:
        tuple[str, str]: Page HTML and a one-line overview finding
            (HTML with <strong> on its key figures).
    """
    raw = read("q1_country", "q1_country_raw_precision.csv", index_col="Country")
    br = read("q1_country", "q1_customer_group_bridge.csv", index_col=0)
    cg = read("q1_country", "q1_customer_groups.csv")
    ev = read("q1_country", "q1_customer_evidence.csv")
    t0, t1 = raw["Sales_1997"].sum(), raw["Sales_1998"].sum()
    o0, o1 = raw["Orders_1997"].sum(), raw["Orders_1998"].sum()
    c0, c1 = int(raw["Customers_1997"].sum()), int(raw["Customers_1998"].sum())
    g = t1 / t0 - 1
    T = br.loc["Total"]
    b = br.drop("Total").sort_values("NetChange", ascending=False)

    def grp(country, group):
        """Return one country's customers in one buying group.

        Args:
            country (str): Country name.
            group (str): "both", "only_cur" or "only_base".

        Returns:
            pandas.DataFrame: Rows of ``q1_customer_groups.csv``.
        """
        return cg[(cg["Country"] == country) & (cg["Group"] == group)]

    def biggest(country, group, col):
        """Return the group's customer with the largest ``abs(col)``.

        Args:
            country (str): Country name.
            group (str): "both", "only_cur" or "only_base".
            col (str): Column to rank by, e.g. "Sales_1997".

        Returns:
            pandas.Series: That customer's row.
        """
        d = grp(country, group)
        return d.loc[d[col].abs().idxmax()]

    def cell(v, n):
        """Format a contribution with its customer count.

        Args:
            v (float): Contribution amount.
            n (float): Customers in the group.

        Returns:
            str: e.g. "+39,776 (5)", or "—" when the group is empty.
        """
        return "—" if int(n) == 0 else f"{signed(v, 0)} ({int(n)})"

    btab = pd.DataFrame({
        "Country": list(b.index) + ["Total"],
        "Net change": [signed(v, 0) for v in list(b["NetChange"]) + [T["NetChange"]]],
        "Bought in both windows: change (customers)": [
            cell(v, n) for v, n in zip(list(b["BothChange"]) + [T["BothChange"]],
                                      list(b["CustBoth"]) + [T["CustBoth"]])],
        "1998 window only: + sales (customers)": [
            cell(v, n) for v, n in zip(list(b["OnlyCurContribution"]) + [T["OnlyCurContribution"]],
                                      list(b["CustOnlyCur"]) + [T["CustOnlyCur"]])],
        "1997 window only: − sales (customers)": [
            cell(v, n) for v, n in zip(list(b["OnlyBaseContribution"]) + [T["OnlyBaseContribution"]],
                                      list(b["CustOnlyBase"]) + [T["CustOnlyBase"]])],
    })

    r = raw.sort_values("Sales_1998", ascending=False)
    share_pp = (r["Sales_1998"] / t1 - r["Sales_1997"] / t0) * 100
    flags = r["Flags"].fillna("").map(
        lambda s: "; ".join(Q1_FLAGS.get(f, f) for f in s.split("；") if f))
    tab = pd.DataFrame({
        "Country": r.index,
        "Sales 1997": r["Sales_1997"].map(money), "Sales 1998": r["Sales_1998"].map(money),
        "Change": r["SalesChange"].map(signed),
        "Growth": r["SalesGrowth"].map(lambda x: "not applicable" if pd.isna(x) else pct(x, 1, True)),
        "Orders": [f"{int(a)} → {int(b)}" for a, b in zip(r["Orders_1997"], r["Orders_1998"])],
        "Customers": [f"{int(a)} → {int(b)}" for a, b in zip(r["Customers_1997"], r["Customers_1998"])],
        "AOV": [f"{money(a, 0)} → {money(b, 0)}" for a, b in zip(r["AOV_1997"], r["AOV_1998"])],
        "Share Δ (pp)": share_pp.map(lambda x: f"{x:+.1f}"),
        "Flags": flags,
    })
    # Each customer has one country, so country counts add up to unique totals
    # (checked in q1_validation.csv).
    tab.loc[len(tab)] = ["Total", money(t0), money(t1), signed(t1 - t0), pct(g, 1, True),
                         f"{int(o0)} → {int(o1)}", f"{c0} → {c1}",
                         f"{money(t0 / o0, 0)} → {money(t1 / o1, 0)}", "", ""]
    conc = raw.loc[["USA", "Germany", "Brazil"]]
    ctab = pd.DataFrame({
        "Country": conc.index,
        "Largest customer 1997": [f"{a} {pct(v, 1)}" for a, v in zip(conc["TopCust_1997"], conc["TopCustShare_1997"])],
        "Largest customer 1998": [f"{a} {pct(v, 1)}" for a, v in zip(conc["TopCust_1998"], conc["TopCustShare_1998"])],
        "Top contributor to the increase": [f"{a} {signed(v)}" for a, v in zip(conc["TopIncCustomer"],
                                                                              conc["TopIncChange"])],
        "Its share of the net increase": conc["TopIncShareOfNet"].map(lambda x: pct(x, 1)),
        "Top two share": conc["Top2IncShareOfNet"].map(lambda x: pct(x, 1)),
    })
    gl = cg.copy()
    gl["Group"] = gl["Group"].map({"both": "Both windows", "only_cur": "1998 window only",
                                   "only_base": "1997 window only"})
    sel = gl[gl["Country"].isin(["Brazil", "France", "Canada", "Denmark", "Finland", "Mexico"])]
    gtab = pd.DataFrame({
        "Country": sel["Country"], "Customer": sel["CustomerID"], "Group": sel["Group"],
        "Sales 1997": sel["Sales_1997"].map(money), "Sales 1998": sel["Sales_1998"].map(money),
        "Orders outside both windows": [int(a) if g_ == "1998 window only" else int(b_) if g_ == "1997 window only"
                                        else "—" for g_, a, b_ in zip(sel["Group"],
                                                                     sel["OrdersBefore1998OutsideWindows"],
                                                                     sel["OrdersAfter1997Window"])],
    })

    us, de, fr = br.loc["USA"], br.loc["Germany"], br.loc["France"]
    bz, ca, dk, fi, mx = br.loc["Brazil"], br.loc["Canada"], br.loc["Denmark"], br.loc["Finland"], br.loc["Mexico"]
    bz_new = biggest("Brazil", "only_cur", "Sales_1998")
    ca_lost, dk_lost = biggest("Canada", "only_base", "Sales_1997"), biggest("Denmark", "only_base", "Sales_1997")
    fi_both = biggest("Finland", "both", "Sales_1997")
    mx_rows = ev[ev["Country"] == "Mexico"]
    mx_down = int((mx_rows["Change"] < 0).sum())
    mx_top = mx_rows.loc[mx_rows["Change"].idxmin()]
    merep_last = ev.loc[ev["CustomerID"] == "MEREP", "LastOrderOverall"].iloc[0]
    simob_after = ev.loc[ev["CustomerID"] == "SIMOB", "OrdersAfter1998Window"].iloc[0]
    fr_g = raw.loc["France", "SalesGrowth"]
    low = [c for c, f in raw["Flags"].fillna("").items() if "低基数" in f]

    answer = (
        f"<p>Company sales in January–April rose by <strong>{signed(T['NetChange'], 0)} "
        f"({pct(g, 1, True)})</strong>. Exactly: <strong>{signed(T['BothChange'], 0)}</strong> is the net change "
        f"from the {int(T['CustBoth'])} customers who bought in <strong>both windows</strong>, "
        f"<strong>{signed(T['OnlyCurContribution'], 0)}</strong> from {int(T['CustOnlyCur'])} customers who bought "
        f"<strong>only in the 1998 window</strong>, and <strong>{signed(T['OnlyBaseContribution'], 0)}</strong> "
        f"from {int(T['CustOnlyBase'])} customers who bought <strong>only in the 1997 window</strong>.</p>"
        "<p><strong>Window presence alone does not identify acquisition or loss</strong>; out-of-window orders "
        "show that these are window-based buying groups: "
        f"{int(T['OnlyCurWithEarlierOrders'])} of the {int(T['CustOnlyCur'])} 1998-window-only customers had ordered "
        f"before, outside the windows, and all {int(T['OnlyBaseWithLaterOrders'])} 1997-window-only customers "
        f"ordered again after April 1997. <strong>Next step:</strong> work with account managers on the "
        "largest both-window customers (what drove their increase, and is it repeatable), review the few "
        "1997-window-only accounts behind the Canada and Denmark declines, and find out why the "
        "1998-window-only customers ordered in this window and whether their orders continue.</p>")
    evidence = (
        figure("q1_customer_group_bridge.png",
               "Stacked bars per country splitting the change in sales into three customer groups",
               "Each bar splits a country's change in discounted sales (Jan–Apr 1998 minus Jan–Apr 1997) into "
               "<strong>blue</strong> = change from customers who bought in both windows, <strong>green, hatched "
               "/</strong> = sales of customers who bought only in the 1998 window, <strong>orange, hatched \\"
               "</strong> = sales of customers who bought only in the 1997 window (subtracted). The black diamond "
               "and number show the net change. Read amounts, not shares: for countries with a small net change, "
               "shares of it would be huge or meaningless.")
        + "<h3>The three contributions by country (amount, with customers in brackets)</h3>"
        + table(btab, left=("Country",), total_last=True)
        + '<p class="note">Net change = both-window change + 1998-window-only sales − 1997-window-only sales, '
          "exactly, for every country and for the company.</p>")
    findings = [
        f"<strong>Customers who bought in both windows drove most of the growth</strong>: "
        f"{signed(T['BothChange'], 0)} of the {signed(T['NetChange'], 0)} company increase "
        f"({int(T['CustBoth'])} of {int(T['CustUnion'])} customers active in either window).",
        f"<strong>USA</strong> ({signed(us['NetChange'], 0)}) and <strong>Germany</strong> "
        f"({signed(de['NetChange'], 0)}) grew mainly through both-window customers buying more "
        f"({signed(us['BothChange'], 0)} from {int(us['CustBoth'])} customers in the USA, "
        f"{signed(de['BothChange'], 0)} from {int(de['CustBoth'])} in Germany). The USA also added "
        f"{signed(us['OnlyCurContribution'], 0)} from {int(us['CustOnlyCur'])} 1998-window-only customers. "
        f"Germany's increase is concentrated: QUICK and KOENE explain "
        f"{pct(raw.loc['Germany', 'Top2IncShareOfNet'], 0)} of it.",
        f"<strong>Brazil</strong> ({signed(bz['NetChange'], 0)}) depends on one 1998-window-only customer: "
        f"{bz_new['CustomerID']} added {signed(bz_new['Sales_1998'], 0)}, more than the "
        f"{signed(bz['BothChange'], 0)} from its {int(bz['CustBoth'])} both-window customers.",
        f"<strong>France grew {pct(fr_g, 1, True)}</strong> ({signed(fr['NetChange'], 0)}): its "
        f"{int(fr['CustBoth'])} both-window customers bought less ({signed(fr['BothChange'], 0)}), offset by "
        f"{int(fr['CustOnlyCur'])} 1998-window-only customers ({signed(fr['OnlyCurContribution'], 0)}), with one "
        f"1997-window-only customer ({signed(fr['OnlyBaseContribution'], 0)}).",
        f"<strong>Canada</strong> ({signed(ca['NetChange'], 0)}) and <strong>Denmark</strong> "
        f"({signed(dk['NetChange'], 0)}) declined mainly through one 1997-window-only customer each "
        f"({ca_lost['CustomerID']} {signed(-ca_lost['Sales_1997'], 0)}, {dk_lost['CustomerID']} "
        f"{signed(-dk_lost['Sales_1997'], 0)}) outweighed growth from both-window customers. "
        f"{dk_lost['CustomerID']} ordered again on {simob_after}, just after the window; "
        f"{ca_lost['CustomerID']} placed no order between {merep_last} and the end of the data.",
        f"<strong>Finland</strong> ({signed(fi['NetChange'], 0)}) and <strong>Mexico</strong> "
        f"({signed(mx['NetChange'], 0)}) declined through both-window customers buying less. In Finland that is "
        f"{fi_both['CustomerID']} ({signed(fi_both['Sales_1998'] - fi_both['Sales_1997'], 0)}). In Mexico "
        f"{mx_down} of its {len(mx_rows)} customers bought less, and the largest single drop "
        f"({mx_top['CustomerID']}, {signed(mx_top['Change'], 0)}) is "
        f"{pct(mx_top['Change'] / mx['NetChange'], 0)} of the net decline — both are true at once.",
        f"Countries flagged as low base ({', '.join(low)}) can show extreme growth rates; Spain's increase, for "
        f"example, comes from {int(br.loc['Spain', 'CustOnlyCur'])} 1998-window-only customers. Poland had no "
        "sales in the 1997 window, so its growth rate is not applicable.",
    ]
    implications = [
        "<strong>Both-window customers (main source of growth):</strong> ask account managers what drove the "
        "largest increases (for example SAVEA and WHITC in the USA, QUICK and KOENE in Germany) and whether it "
        "can repeat. In Germany, weigh the dependence on two accounts before adding effort.",
        "<strong>1997-window-only customers:</strong> review these accounts one by one; MEREP (Canada) is the "
        "case with no orders from late October 1997 to the end of the data. The others did order again after "
        "April 1997; check what their absence from the 1998 window reflects before treating it as a loss.",
        "<strong>1998-window-only customers:</strong> almost all had bought before; find out why they ordered "
        "in this window (for example HANAR in Brazil) and whether orders continue. This is not evidence that "
        "an acquisition effort worked.",
        "<strong>France</strong> needs an account-level look at why its both-window customers bought less while "
        "others returned. Small markets with extreme growth rates should be watched, not prioritised, on this "
        "evidence alone.",
    ]
    limits = [
        "<strong>Window presence is not first purchase, retention or churn</strong>: a customer can be absent "
        "from a four-month window and still be active; no retention or repurchase rate is computed.",
        "The split is <strong>descriptive arithmetic</strong>; it does not explain why customers bought more or "
        "less.",
        "<strong>Price level differs</strong>: most 1997-window order lines were priced at about 0.8× the 1998 "
        "level (see Q4), so part of every group's change reflects that difference.",
        "<strong>Small samples and concentration</strong>: many countries have one to three customers or fewer "
        "than 15 orders, so one order or one account can swing the result.",
        "Country = the customer's master-data country, not the ship-to country. Orders not yet shipped at the "
        "data cut-off are included. Sales are not profit.",
    ]
    method = (
        "<p><strong>Data and period:</strong> January–April 1997 vs January–April 1998 by order date. Comparing "
        "the same months <strong>reduces differences caused by seasonality</strong> (the data stops in early May "
        "1998), but does not remove them entirely.</p>"
        "<p><strong>Grain and joins:</strong> order lines (Orders Details) are joined to Orders by OrderID and to "
        "Customers by CustomerID; discounted sales = UnitPrice × Quantity × (1 − Discount), summed per customer "
        "and window. The market is <code>Customers.Country</code>.</p>"
        "<p><strong>Customer groups</strong> (by whether a customer has any order in each window): bought in "
        "<strong>both windows</strong>; bought in the <strong>1998 window only</strong>; bought in the <strong>"
        "1997 window only</strong>. Every country's change then splits exactly into:</p>"
        '<span class="formula">Change = (both-window sales 1998 − both-window sales 1997)\n'
        "       + sales 1998 of 1998-window-only customers\n"
        "       − sales 1997 of 1997-window-only customers</span>")
    details = (
        '<span class="formula">Growth = (S1998 − S1997) / S1997   (not applicable when S1997 = 0)\n'
        "AOV = Sales / unique OrderID\n"
        "ln(S1/S0) = ln(O1/O0) + ln(AOV1/AOV0)   where O = orders</span>"
        "<p>Windows: OrderDate 1997-01-01 to 1997-04-30 and 1998-01-01 to 1998-04-30. Context columns: orders "
        "placed outside both windows (before 1998 for 1998-window-only customers; after April 1997 for "
        "1997-window-only customers). They describe purchase timing and do not turn the groups into new or lost "
        "customers. Flags: low base = 1997 sales below 2% of the 1997 total; ≤2 customers in either window; one "
        "customer above 50% of a window's sales. Checks: the three groups are mutually exclusive, cover every "
        "customer active in either window, and their contributions add up to each country's and the company's "
        "change.</p>")
    why = ("<p>Change among customers who bought in both windows points to <strong>account development</strong>; "
           "customers missing from the later window point to <strong>account review</strong>; customers present "
           "only in the later window point to <strong>follow-up</strong>. Knowing which group moved each market "
           "tells the sales team what kind of action to consider, not just where — the groups describe buying in "
           "two windows, not the reasons behind it.</p>")
    supplement = (
        figure("q1_country_sales_chart.png", "Bar charts of sales by country in both windows and the change",
               "Background: discounted sales by customer country, Jan–Apr 1997 (light) vs 1998 (dark), and the "
               "change with growth in brackets (\"n/a\" = no 1997 sales).")
        + "<h3>Country size and growth (background)</h3>"
        + table(tab, left=("Country",), wrap=("Flags",), total_last=True)
        + '<p class="note">Share Δ = change in the country\'s share of company sales (internal share, not market '
          "share), in percentage points. AOV = average order value.</p>"
        + "<h3>Concentration inside the largest markets</h3>" + table(ctab, left=("Country",))
        + "<h3>Customers behind selected countries</h3>"
        + table(gtab, left=("Country", "Customer", "Group")))
    summary = (f"Company sales <strong>{pct(g, 1, True)}</strong> (Jan–Apr): <strong>{signed(T['BothChange'], 0)}"
               f"</strong> from customers buying in both windows, {signed(T['OnlyCurContribution'], 0)} from "
               f"1998-window-only and {signed(T['OnlyBaseContribution'], 0)} from 1997-window-only buyers; Canada's "
               "and Denmark's declines trace to <strong>one 1997-window-only account each</strong>.")
    return qpage("q1.html", "Q1 · Where did each market's sales change come from?",
                 "Did each country market's change in sales come mainly from customers who bought in both "
                 "windows buying more or less, from customers who bought only in the 1998 window, or from "
                 "customers who bought in the 1997 window but not in the 1998 window — and which customer "
                 "development or maintenance actions should the sales team prioritise?",
                 "Which accounts and markets to develop, review or follow up, and with what kind of action.",
                 answer, why, method, details, evidence, findings, implications, limits, supplement,
                 "q1_country", "q1"), summary


def build_q2():
    """Build the Q2 page and return its overview summary.

    Args:
        None.

    Returns:
        tuple[str, str]: Page HTML and a one-line overview finding
            (HTML with <strong> on its key figures).
    """
    c = read("q2_customers", "q2_customer_raw_precision.csv", index_col="CustomerID")
    sens = read("q2_customers", "q2_threshold_sensitivity.csv")
    act = c[c["Sales"] > 0]
    total = act["Sales"].sum()
    top = {n: act["CumShare"].iloc[n - 1] for n in (1, 3, 5, 10)}
    n50 = int((act["CumShare"].shift(fill_value=0) < 0.5).sum())
    core = c[c["Core"]]
    n80, cum80 = len(core), core["CumShare"].iloc[-1]
    hhi = (act["Share"] ** 2).sum()

    def tags(s):
        """Translate unmet-rule tags to English.

        Args:
            s (str): Tags joined by "、"; NaN allowed.

        Returns:
            str: English tags joined by ", ", or "".
        """
        return "" if pd.isna(s) else ", ".join(Q2_TAGS.get(t, t) for t in s.split("、"))

    t12 = act.head(12)
    tab = pd.DataFrame({
        "Rank": t12["Rank"].astype(int), "Customer": t12.index, "Company": t12["CompanyName"],
        "Country": t12["Country"], "Sales 1997": t12["Sales"].map(money),
        "Share": t12["Share"].map(pct), "Cumulative": t12["CumShare"].map(pct),
        "Orders": t12["Orders"].astype(int), "AOV": t12["AOV"].map(lambda x: money(x, 0)),
        "Largest order share": t12["MaxOrderShare"].map(lambda x: pct(x, 0)),
        "Quarters": t12["ActiveQuarters"].astype(int),
        "Group": t12["Segment"].map(Q2_SEGMENTS), "Unmet rules": t12["RuleTags"].map(tags),
    })
    ktab = pd.DataFrame({"Measure": ["Top 1 customer (QUICK)", "Top 5 customers", "Top 10 customers",
                                     "Customers needed for 50% of sales", "Customers making up ~80% of sales",
                                     "Equivalent number of equal-size customers (1/HHI)"],
                         "Value": [pct(top[1]), pct(top[5]), pct(top[10]), f"{n50}",
                                   f"{n80} ({pct(cum80)})", f"{1 / hhi:.1f}"]})

    seg = c.groupby("Segment").agg(n=("Sales", "size"), s=("Sales", "sum"), o=("Orders", "sum"),
                                   mo=("Orders", "median"), mx=("MaxOrderShare", "median"))
    order = list(Q2_SEGMENTS)
    seg = seg.reindex([x for x in order if x in seg.index])
    head_sales = core["Sales"].sum()
    stab = pd.DataFrame({
        "Group": seg.index.map(Q2_SEGMENTS), "Customers": seg["n"].astype(int),
        "Sales": seg["s"].map(money), "Share of company sales": (seg["s"] / total).map(pct),
        f"Share of top-{n80} sales": [pct(s / head_sales) if i in order[:2] else "—"
                                       for i, s in seg["s"].items()],
        "Median orders": seg["mo"].map(lambda x: f"{x:g}"),
        "Median largest-order share": seg["mx"].map(lambda x: "—" if pd.isna(x) else pct(x, 0)),
    })
    miss = c[c["Segment"] == order[1]].copy()
    miss["Tags"] = miss["RuleTags"].map(tags)
    mt = miss.groupby("Tags").agg(n=("Sales", "size"), s=("Sales", "sum"),
                                  who=("Sales", lambda s: ", ".join(s.index)))
    mtab = pd.DataFrame({"Unmet rules (exact combination)": mt.index, "Customers": mt["n"],
                         "Who": mt["who"], "Share of company sales": (mt["s"] / total).map(pct)})
    sens.columns = ["Min orders", "Min quarters", "Customers meeting rule", "Share of company sales",
                    f"Share of top-{n80} sales"]
    sens["Share of company sales"] = sens["Share of company sales"].map(pct)
    sens[f"Share of top-{n80} sales"] = sens[f"Share of top-{n80} sales"].map(pct)

    rep, mis = seg.loc[order[0]], seg.loc[order[1]]
    evidence = (figure("q2_customer_pareto.png", "Pareto chart of 1997 customer sales with cumulative share",
                       f"Top: each customer's 1997 discounted sales, largest first (<strong>blue</strong> = among the "
                       f"top {n80} and meets the repeat rule; <strong>orange, hatched</strong> = among the top {n80} "
                       "but misses it; grey = the rest). Bottom: cumulative share of company sales, with the top 1, "
                       "5, 10, 12 and 33 marked. The x-axis is the customer rank; names are in the tables.")
                + "<h3>Concentration measures</h3>" + table(ktab, left=("Measure",))
                + f"<h3>Buying patterns of the top {n80} customers</h3>"
                + table(stab, left=("Group",)))
    supplement = ("<h3>Top 12 customers (together just over 50% of 1997 sales)</h3>"
                  + table(tab, left=("Customer", "Company", "Country", "Group", "Unmet rules"))
                  + "<h3>Which rule each head customer misses</h3>"
                  + table(mtab, left=("Unmet rules (exact combination)", "Who"), wrap=("Who",))
                  + "<h3>Sensitivity to the repeat-rule thresholds</h3>" + table(sens))
    answer = (f"<p>The top 1, 5 and 10 customers hold "
              f"<strong>{pct(top[1])}</strong>, <strong>{pct(top[5])}</strong> and <strong>{pct(top[10])}</strong> of "
              f"1997 sales, and <strong>{n80} customers</strong> make up {pct(cum80)}. The three largest (QUICK, "
              f"SAVEA, ERNSH, {pct(top[3])} together) bought steadily all year.</p>"
              "<p><strong>Next step:</strong> manage QUICK, SAVEA and ERNSH as key accounts, and review the "
              f"{int(mis['n'])} head customers whose 1997 sales came from few orders, few quarters or one large "
              "order before treating their sales as a recurring baseline.</p>")
    findings = [
        f"The top 1, 5 and 10 customers account for <strong>{pct(top[1])}</strong>, <strong>{pct(top[5])}"
        f"</strong> and <strong>{pct(top[10])}</strong> of 1997 sales. {n50} customers make up half of sales and "
        f"{n80} make up {pct(cum80)}.",
        f"<strong>The three largest customers (QUICK, SAVEA, ERNSH) hold {pct(top[3])}</strong>. In 1997 each "
        "placed 14–17 orders in all four quarters, and no single order exceeded 18% of its annual sales.",
        f"Of the top {n80}, {int(rep['n'])} meet the repeat rule ({pct(rep['s'] / total)} of company sales) and "
        f"<strong>{int(mis['n'])} do not ({pct(mis['s'] / total)} of company sales</strong>, or "
        f"{pct(mis['s'] / head_sales)} of the top-{n80} sales).",
        "Those 11 differ: six only have fewer than six orders; RATTC is dominated by one order (54%); SIMOB, GREAL, "
        "CHOPS and SUPRD miss two or three rules.",
    ]
    implications = [
        "<strong>Key accounts:</strong> treat QUICK, SAVEA and ERNSH as key accounts — they carry the largest "
        "share of revenue — and learn their buying cycle and product mix.",
        "<strong>Head customers that miss the rule:</strong> handle each tag differently: learn the buying cycle "
        "of low-frequency customers, the nature of single large orders, and when few-quarter customers buy. Do "
        "not treat their 1997 amounts as a recurring baseline.",
        f"The remaining {int((c['Orders'] > 0).sum()) - n80} customers with 1997 orders hold "
        f"{pct(1 - head_sales / total)} of sales; standardised, "
        "lower-cost account care is a reasonable starting point.",
    ]
    limits = [
        "One year of data: nothing here says whether these patterns hold across years; 1997 sales are not lifetime "
        "value, and no churn is inferred.",
        "The repeat rule uses analysis thresholds; the sensitivity table shows how much the groups move.",
        "No cost or margin data, freight is excluded, and related accounts of one group are not merged.",
    ]
    method = (
        "<p><strong>Data and period:</strong> full year 1997 by order date (the only complete year), 408 orders. "
        "<strong>Grain and joins:</strong> order lines joined to Orders by OrderID; discounted sales summed per "
        "CustomerID; orders counted as unique OrderIDs; all 91 customers kept (5 without 1997 orders).</p>"
        "<p>Sorting customers from largest to smallest gives the <strong>Pareto curve</strong>: how quickly sales "
        f"accumulate. For the top {n80} customers (about 80% of sales) we then check whether their 1997 buying was "
        "spread out — the <strong>repeat rule</strong>: at least 6 orders, orders in at least 3 quarters, and no "
        "single order of 50% or more of the customer's sales — or concentrated.</p>")
    details = (
        '<span class="formula">Share_i = Sales_i / Σ Sales\n'
        "HHI = Σ Share_i²     equivalent customers = 1 / HHI\n"
        "Repeat rule: Orders ≥ 6  and  quarters with orders ≥ 3  and  largest order / Sales_i < 50%</span>"
        f"<p>Six orders is the 75th percentile of 1997 order counts. The top {n80} are the customers needed to "
        "reach 80% of cumulative sales, including the one that crosses it. Tags: low frequency (fewer than 6 "
        "orders), few quarters (fewer than 3), single-order dominated (largest order ≥ 50%).</p>")
    why = ("<p>If a few customers carry most of the revenue, losing or shrinking one of them is a real risk. "
           "Knowing who they are, and how steadily they bought, tells account managers where attention matters "
           "most.</p>")
    summary = (f"Top 1/5/10 customers hold <strong>{pct(top[1])}/{pct(top[5])}/{pct(top[10])}</strong> of 1997 "
               f"sales; <strong>{n80} customers</strong> make up {pct(cum80)}.")
    return qpage("q2.html", "Q2 · How much do sales depend on a few customers?",
                 "How much do sales depend on a few customers, and which customers should be maintained first "
                 "to manage revenue risk?",
                 "Which accounts get key-account management and which head customers need a closer review of "
                 "how they buy.",
                 answer, why, method, details, evidence, findings, implications, limits, supplement,
                 "q2_customers", "q2"), summary


def build_q3():
    """Build the Q3 page and return its overview summary.

    Args:
        None.

    Returns:
        tuple[str, str]: Page HTML and a one-line overview finding
            (HTML with <strong> on its key figures).
    """
    s = read("q3_shipping", "q3_by_shipper_raw.csv", index_col=0)
    c = read("q3_shipping", "q3_by_country_raw.csv", index_col=0)
    w = read("q3_shipping", "q3_required_window_vs_late.csv", index_col=0)
    cum = read("q3_shipping", "q3_shipper_cumulative_share_by_day.csv", index_col=0)

    def rows(t):
        """Format shipping statistics with explicit denominators.

        Args:
            t (pandas.DataFrame): Raw shipper or country table.

        Returns:
            pandas.DataFrame: Display table.
        """
        return pd.DataFrame({
            "Group": t.index, "Orders": t["Orders"].astype(int),
            "Missing ship date": t["MissingShipped"].astype(int),
            "Median days": t["Median"].map(lambda x: f"{x:g}"), "P90 days": t["P90"].map(lambda x: f"{x:.1f}"),
            "Over 14 days": [f"{int(a)}/{int(b)}" for a, b in zip(t["OverReview"], t["Shipped"])],
            "Shipped after RequiredDate": [f"{pct(r, 1)} ({int(a)}/{int(b)})"
                                           for r, a, b in zip(t["LateRate"], t["LateCount"], t["Shipped"])],
            "14-day windows": [f"{int(a)}/{int(b)}" for a, b in zip(t["Window14Count"], t["Orders"])],
            "Sample": t["SmallSample"].fillna("").map(lambda x: "small (<10)" if x else ""),
        })

    body = s.drop("全部").sort_values(["Median", "P90"], ascending=False)
    stab = rows(pd.concat([body, s.loc[["全部"]]])).replace({"Group": {"全部": "All"}})
    # Same order as the country chart: countries with ≥10 orders by orders over
    # 14 days, then small samples, so table position does not imply priority.
    rest = c.drop("全部")
    cb = pd.concat([rest[rest["SmallSample"].isna()].sort_values(["OverReview", "P90"], ascending=False),
                    rest[rest["SmallSample"].notna()].sort_values("Orders", ascending=False)])
    ctab = rows(pd.concat([cb, c.loc[["全部"]]])).replace({"Group": {"全部": "All"}})
    w.index.name = None
    wtab = pd.DataFrame({"Required window (days)": w.index.astype(str).str.replace("合计", "All"),
                         "Orders": w["合计"].astype(int),
                         "Shipped after RequiredDate": [f"{pct(b / a, 1)} ({int(b)}/{int(a)})"
                                                        for a, b in zip(w["合计"], w["晚于要求日期"])]})
    win = cum.loc[7:25]
    others = win.iloc[:, [0, 2]]
    gap_best = win.iloc[:, 1] - others.max(axis=1)
    gap_low = win.iloc[:, 1] - others.min(axis=1)
    tot = s.loc["全部"]
    up = s.loc[[i for i in s.index if "United" in i][0]]
    big = c.drop("全部")
    big = big[big["Orders"] >= 10]
    us, de, uk = c.loc["USA"], c.loc["Germany"], c.loc["UK"]
    med_lo, med_hi = big["Median"].min(), big["Median"].max()

    w14 = w.loc[[i for i in w.index if str(i) == "14"][0]]
    w28 = w.loc[[i for i in w.index if str(i) == "28"][0]]
    evidence = (figure("q3_shipping_by_shipper.png", "Cumulative share of orders shipped within X days, by shipper",
                       "Share of each shipper's 1997 orders already shipped X calendar days after the order date "
                       "(solid blue Speedy Express, <strong>dashed orange United Package</strong>, dotted green "
                       "Federal Shipping); the vertical line marks the 14-day review threshold. A lower line means "
                       "more orders still waiting to ship.")
                + "<h3>By shipper (ShipVia)</h3>" + table(stab, left=("Group", "Sample"))
                + figure("q3_shipping_by_country.png", "Dot plot of every 1997 order's shipping days by ship-to country",
                         "Each dot is one order; black bar = median, dashed bar = P90, red dots = shipped after "
                         "RequiredDate. Countries with 10+ orders are sorted by orders over 14 days; "
                         "<strong>small samples (&lt;10 orders, grey) are grouped at the bottom</strong> and are "
                         "reference only.")
                + "<h3>Required window and late shipment</h3>" + table(wtab))
    supplement = "<h3>All ship-to countries (same order as the chart)</h3>" + table(ctab, left=("Group", "Sample"))
    sh_lo, sh_hi = body["Median"].min(), body["Median"].max()
    answer = (f"<p>Median order-to-shipment time is <strong>{med_lo:g}–{med_hi:g} days</strong> in every country "
              f"with at least 10 orders, and {sh_lo:g}–{sh_hi:g} days for the three shippers; the difference is in "
              "the <strong>slow tail</strong>. Orders assigned to <strong>United Package</strong> "
              f"have the longest tail (P90 {up['P90']:.0f} days; {int(up['OverReview'])}/{int(up['Shipped'])} over 14 "
              f"days), and <strong>USA and Germany</strong> hold {pct((us['OverReview'] + de['OverReview']) / tot['OverReview'], 0)} "
              "of all orders over 14 days.</p>"
              "<p><strong>Next step:</strong> trace the over-14-day orders assigned to United Package and those for "
              "the USA, Germany, UK and Austria, to see whether the time goes into stock, internal handling or "
              "waiting for pick-up. This measures order-to-shipment time, not carrier transit or delivery.</p>")
    findings = [
        f"All {int(tot['Orders'])} orders of 1997 have a ship date; none ship before the order date. "
        f"<strong>Typical shipping time is similar across shippers and countries with 10+ orders</strong>: "
        f"medians are {med_lo:g}–{med_hi:g} days "
        "for every country with 10+ orders and 6–7 days for the shippers.",
        f"<strong>Differences are in the tail.</strong> United Package has the highest P90 ({up['P90']:.0f} days), "
        f"the most orders over 14 days ({int(up['OverReview'])}/{int(up['Shipped'])}) and the highest share shipped "
        f"after RequiredDate ({pct(up['LateRate'])}). Between day 7 and day 25 its share of orders already shipped "
        f"is {abs(gap_best.max()):.1f}–{abs(gap_best.min()):.1f} points below the better of the other two shippers "
        f"and {abs(gap_low.max()):.1f}–{abs(gap_low.min()):.1f} points below the weaker one.",
        f"<strong>USA ({int(us['OverReview'])}) and Germany ({int(de['OverReview'])})</strong> have the most orders "
        f"over 14 days, {pct((us['OverReview'] + de['OverReview']) / tot['OverReview'], 0)} of all long orders. UK "
        f"has the highest P90 among countries with 10+ orders ({uk['P90']:.0f} days) and "
        f"{int(uk['LateCount'])}/{int(uk['Shipped'])} shipped late.",
        f"Orders with a 14-day required window were shipped late {pct(w14['晚于要求日期'] / w14['合计'], 1)} of the "
        f"time vs {pct(w28['晚于要求日期'] / w28['合计'], 1)} for 28-day windows, so late shares also reflect the "
        "required window.",
    ]
    implications = [
        "<strong>Start with the long-tail orders assigned to United Package</strong>: check where the time goes "
        "(stock, internal handling, pick-up). This is not evidence that the carrier is slower.",
        "<strong>Review the over-14-day orders for the USA, Germany, UK and Austria</strong> order by order; "
        "small-sample countries are not a priority on this evidence.",
        "Consider tracking 14-day-window orders separately, since they are the ones most often shipped late.",
    ]
    limits = [
        "<strong>No delivery date</strong>: on-time delivery cannot be measured; \"shipped after RequiredDate\" is "
        "about dispatch.",
        "<strong>Shipping time is not carrier transit time</strong>: it includes internal processing and waiting, "
        "so differences cannot be attributed to the shipper or the country.",
        "P90 in groups of 10–30 orders depends on the slowest one to three orders; small groups (<10) are "
        "reference only; no significance tests.",
        "The 14-day review threshold is an analysis choice, not a service standard. Orders are grouped by order "
        "date, so December orders shipped in January count in 1997.",
    ]
    method = (
        "<p><strong>Data and period:</strong> the 408 orders placed in 1997. <strong>Grain:</strong> one row per "
        "order from the Orders sheet only (no join to order lines, so nothing is double counted); shipper via "
        "ShipVia → Shippers, country = ShipCountry.</p>"
        "<p><strong>Shipping time</strong> = calendar days from OrderDate to ShippedDate — order-to-shipment time, "
        "including internal handling and waiting. Because averages hide long delays, we report the "
        "<strong>median</strong> (a typical order), the <strong>90th percentile</strong> (the slow tail), orders "
        "over <strong>14 days</strong> (a review threshold chosen for this analysis, not a service standard) and "
        "the share shipped after the RequiredDate, each with its denominator.</p>")
    details = (
        '<span class="formula">ShipDays = ShippedDate − OrderDate   (calendar days; missing ship date stays missing)\n'
        "Late = ShippedDate > RequiredDate   (denominator: shipped orders)\n"
        "P90 = numpy linear-interpolation 90th percentile of ShipDays</span>"
        "<p>Orders with OrderDate in 1997 (408). Groups with fewer than 10 orders are marked as small samples. "
        "\"Over 14 days\" is the review threshold chosen for this analysis.</p>")
    why = ("<p>Slow dispatch ties up working capital and frustrates customers. Finding where the slow orders "
           "<strong>cluster</strong> tells operations managers where an investigation is most likely to pay "
           "off.</p>")
    summary = (f"Median order-to-shipment time is <strong>{med_lo:g}–{med_hi:g} days</strong> in every country "
               f"with 10+ orders ({sh_lo:g}–{sh_hi:g} days by shipper); <strong>orders assigned to United Package"
               "</strong> and those for the USA and Germany make up most of the slow tail.")
    return qpage("q3.html", "Q3 · Which order groups take longer to ship?",
                 "Which order groups take longer from order to shipment, and where should operations managers "
                 "look first?",
                 "Which shipper assignments and destination countries to investigate first for dispatch delays.",
                 answer, why, method, details, evidence, findings, implications, limits, supplement,
                 "q3_shipping", "q3"), summary


def build_q4():
    """Build the Q4 page and return its overview summary.

    Args:
        None.

    Returns:
        tuple[str, str]: Page HTML and a one-line overview finding
            (HTML with <strong> on its key figures).
    """
    g = read("q4_categories", "q4_category_raw_precision.csv", index_col="CategoryName")
    cov = read("q4_categories", "q4_price_level_coverage.csv", index_col="item")["value"]
    prod = read("q4_categories", "q4_product_detail.csv")
    allc = g.loc["全部类别"]
    b = g.drop("全部类别").sort_values("SalesChange", ascending=False)

    tab = pd.DataFrame({
        "Category": b.index, "Sales 1997": b["Sales_1997"].map(money), "Sales 1998": b["Sales_1998"].map(money),
        "Change": b["SalesChange"].map(signed), "Growth": b["SalesGrowth"].map(lambda x: pct(x, 1, True)),
        "Quantity (mixed units)": [f"{int(a):,} → {int(c):,}" for a, c in zip(b["Qty_1997"], b["Qty_1998"])],
        "Avg realised price": [f"{a:.2f} → {c:.2f}" for a, c in zip(b["Price_1997"], b["Price_1998"])],
        "Effective discount": [f"{pct(a, 2)} → {pct(c, 2)}" for a, c in zip(b["DiscRate_1997"], b["DiscRate_1998"])],
    })
    tab.loc[len(tab)] = ["All", money(allc["Sales_1997"]), money(allc["Sales_1998"]), signed(allc["SalesChange"]),
                         pct(allc["SalesGrowth"], 1, True), f"{int(allc['Qty_1997']):,} → {int(allc['Qty_1998']):,}",
                         f"{allc['Price_1997']:.2f} → {allc['Price_1998']:.2f}",
                         f"{pct(allc['DiscRate_1997'], 2)} → {pct(allc['DiscRate_1998'], 2)}"]
    full = pd.concat([b, g.loc[["全部类别"]]])
    etab = pd.DataFrame({
        "Category": list(b.index) + ["All categories (separate company-level split)"],
        "Quantity effect": full["QtyEffect"].map(lambda x: signed(x, 0)),
        "Like-for-like price": full["LikePriceEffect"].map(lambda x: signed(x, 0)),
        "Product mix (residual)": full["MixEffect"].map(lambda x: signed(x, 0)),
        "Discount": full["DiscountEffect"].map(lambda x: signed(x, 0)),
        "Actual change": full["SalesChange"].map(lambda x: signed(x, 0)),
    })
    spread = pd.DataFrame({
        "Category": b.index,
        "Products up / down": [f"{int(u)} / {int(dn)}" for u, dn in zip(b["ProductsUp"], b["ProductsDown"])],
        "Largest mover (share of change)": [f"{p} ({pct(s, 0)})"
                                            for p, s in zip(b["TopProduct"], b["TopProductShareOfChange"])],
    })
    # The "All" row decomposes the company totals directly, so its effects
    # differ from column sums of the category rows (only Actual change adds up).
    col_sum_qty = b["QtyEffect"].sum()
    one = prod[prod["SoldIn"] != "两期均有"]
    otab = pd.DataFrame({"Category": one["CategoryName"], "Product": one["ProductName"],
                         "Sold in": one["SoldIn"].map(lambda s: "1997 window only" if "1997" in s
                                                      else "1998 window only"),
                         "Sales change": one["SalesChange"].map(signed)})
    ctab = pd.DataFrame({"Check": ["Lines / products in the 1997 window",
                                   "Comparable with a 1998 price",
                                   f"Ordered on or before {cov['last_low']}",
                                   "…of which at 0.78–0.82 × the 1998 price",
                                   f"Ordered from {cov['first_full']}",
                                   "…of which at 0.99–1.01 × the 1998 price",
                                   "Products with more than one price in 1998"],
                         "Result": [f"{cov['lines_window']} / {cov['products_window']}",
                                    f"{cov['lines_comparable']} / {cov['products_comparable']}",
                                    f"{cov['pre_lines']} lines / {cov['pre_products']} products",
                                    f"{cov['pre_near08']} lines (no exceptions)",
                                    f"{cov['post_lines']} lines / {cov['post_products']} products",
                                    f"{cov['post_near10']} lines (no exceptions)",
                                    f"{cov['products_multi_price_1998']}"]})
    d = allc["SalesChange"]
    meat, bev, grain = g.loc["Meat/Poultry"], g.loc["Beverages"], g.loc["Grains/Cereals"]
    dairy, sea, conf = g.loc["Dairy Products"], g.loc["Seafood"], g.loc["Confections"]
    evidence = (figure("q4_category_decomposition.png", "Stacked bars splitting each category's change in sales into four effects",
                       "<strong>How to read:</strong> each bar is one category's change in discounted sales "
                       "(Jan–Apr 1998 minus Jan–Apr 1997). Segments right of 0 add to sales, segments left of 0 "
                       "subtract; the black diamond and number are the actual net change. Blue = quantity effect, "
                       "orange / = like-for-like price, green dotted = product mix (residual), yellow \\ = discount.")
                + "<h3>The four effects by category</h3>"
                + table(etab, left=("Category",), total_last=True)
                + f'<p class="note"><strong>The last row is a separate split of company totals</strong>, not the '
                  f"sum of the rows above: only “Actual change” adds up down the column (for example, the category "
                  f"quantity effects sum to {signed(col_sum_qty, 0)}, not {signed(allc['QtyEffect'], 0)}).</p>"
                + "<h3>Price-level check behind the like-for-like price effect</h3>" + table(ctab, left=("Check",)))
    supplement = (figure("q4_category_sales.png", "Grouped bars of category sales in both windows",
                         "Discounted sales by category, Jan–Apr 1997 (light) vs 1998 (dark), labelled with growth.")
                  + "<h3>Sales, quantity, price and discount by category</h3>"
                  + table(tab, left=("Category",), total_last=True)
                  + figure("q4_category_metrics.png", "Dumbbell charts of quantity, average price and discount rate",
                           "Summed quantity (mixed pack sizes), average realised price and effective discount "
                           "rate, Jan–Apr 1997 (light) vs 1998 (dark).")
                  + "<h3>How widely each category's change is spread across products</h3>"
                  + table(spread, left=("Category", "Largest mover (share of change)"))
                  + "<h3>Products sold in only one window</h3>"
                  + table(otab, left=("Category", "Product", "Sold in")))
    lp = b["LikePriceEffect"]
    answer = (f"<p>Across categories, most of the {signed(d, 0)} change goes with the <strong>quantity effect "
              f"({signed(allc['QtyEffect'], 0)})</strong>. <strong>Every category shows a positive like-for-like "
              f"price term, of different sizes</strong> ({signed(lp.min(), 0)} to {signed(lp.max(), 0)}; "
              f"{signed(allc['LikePriceEffect'], 0)} for the company split). This is a descriptive result, alongside "
              "an observed price-level step in early April 1997 — not a proven policy or causal contribution. "
              "<strong>Dairy Products and Seafood</strong> grew broadly across products without deeper "
              "discounts; <strong>Meat/Poultry</strong>'s higher average price is mainly product mix.</p>"
              "<p><strong>Next step:</strong> treat Dairy Products and Seafood as candidates to promote; look "
              "into Meat/Poultry, Confections and Grains/Cereals before acting, because their changes rest on one "
              "or two products or on rising discounts.</p>")
    findings = [
        f"Of the {signed(d, 0)} increase, the quantity effect is <strong>{signed(allc['QtyEffect'], 0)}</strong> "
        f"({pct(allc['QtyEffect'] / d, 1)} of the increase) and the like-for-like price effect "
        f"<strong>{signed(allc['LikePriceEffect'], 0)}</strong> ({pct(allc['LikePriceEffect'] / d, 1)}); mix and "
        "discount are small overall. These are shares of the sales increase, not percentage points of growth.",
        f"The like-for-like price index is {g['FisherPriceIndex'].drop('全部类别').min():.2f}–"
        f"{g['FisherPriceIndex'].drop('全部类别').max():.2f} in every category. In the data, every comparable line "
        f"ordered up to {cov['last_low']} was priced at about 0.8× the product's 1998 price and every later one at "
        "the 1998 price. That is <strong>an observed pattern, not a documented price policy</strong>, and it is "
        "not specific to any category.",
        f"<strong>Meat/Poultry</strong>'s average price jump ({meat['Price_1997']:.0f} → {meat['Price_1998']:.0f}) is mainly "
        f"associated with a shift in product mix (mix effect {signed(meat['MixEffect'], 0)}, "
        f"{pct(meat['MixEffect'] / meat['SalesChange'], 0)} of its change), with like-for-like price changes also "
        f"contributing ({signed(meat['LikePriceEffect'], 0)}, {pct(meat['LikePriceEffect'] / meat['SalesChange'], 0)}). "
        f"One product (Thüringer Rostbratwurst) explains {pct(meat['TopProductShareOfChange'], 0)} of the change; "
        f"its effective discount "
        f"rose {(meat['DiscRate_1998'] - meat['DiscRate_1997']) * 100:.1f} pp.",
        f"<strong>Dairy Products</strong> and <strong>Seafood</strong> grew broadly "
        f"({int(dairy['ProductsUp'])}/{int(dairy['ProductsDown'])} and {int(sea['ProductsUp'])}/"
        f"{int(sea['ProductsDown'])} products up/down), mainly through the quantity effect, and their discount "
        "rates did not rise.",
        f"<strong>Beverages</strong> had the largest increase ({signed(bev['SalesChange'], 0)}); quantity grew "
        f"mostly in cheaper drinks (mix {signed(bev['MixEffect'], 0)}), while Côte de Blaye explains "
        f"{pct(bev['TopProductShareOfChange'], 0)} of the change. <strong>Grains/Cereals</strong> grew least "
        f"({pct(grain['SalesGrowth'], 1, True)}).",
        f"<strong>Confections</strong>' effective discount rose "
        f"{(conf['DiscRate_1998'] - conf['DiscRate_1997']) * 100:.1f} pp and about half its change comes from one "
        "product.",
    ]
    implications = [
        "<strong>Candidates to promote:</strong> Dairy Products and Seafood (broad growth across products, mainly "
        "through quantity, without deeper discounts). Beverages too, looking separately at cheap-drink volume and "
        "Côte de Blaye.",
        "<strong>Investigate before acting:</strong> Meat/Poultry (one high-price product and rising discount), "
        "Grains/Cereals (Gnocchi decline), Confections (rising discount, one product), Produce and Condiments "
        "(several products declining). Pack-size data would help turn the quantity effect into real volume.",
    ]
    limits = [
        "<strong>Summed quantity adds different pack sizes</strong>; the quantity effect is not a physical volume "
        "or a measure of real demand growth.",
        "The <strong>mix effect is a residual</strong> that also contains products sold in only one window.",
        "LMDI splits describe the arithmetic; other split methods give somewhat different numbers; "
        "<strong>nothing here is causal</strong>.",
        "Four-month windows; some categories depend on one or two products. Sales are not profit.",
    ]
    method = (
        "<p><strong>Data and period:</strong> January–April 1997 vs January–April 1998 by order date. "
        "<strong>Grain and joins:</strong> order lines joined to Orders (OrderID), Product (ProductID) and "
        "Categories (CategoryID), using the price actually charged on each line (Orders Details.UnitPrice).</p>"
        "<p>A category's sales equal <strong>quantity × average price × (1 − discount)</strong>, so the change can "
        "be split into four parts: more or fewer units (<strong>quantity</strong>), the same products costing more "
        "or less (<strong>like-for-like price</strong>), a shift toward cheaper or dearer products (<strong>product "
        "mix</strong>, the residual), and deeper or shallower <strong>discounts</strong>. The four parts add up "
        "exactly to the actual change of each category.</p>")
    details = (
        '<span class="formula">S = Q × P × (1 − d)\n'
        "  Q = Σ Quantity (mixed units),  P = Σ UnitPrice×Quantity / Q,  d = discount amount / gross sales\n"
        "w = (S1 − S0) / (ln S1 − ln S0)                      (log-mean weight, LMDI-I)\n"
        "ΔS = w·ln(Q1/Q0) + w·ln(P1/P0) + w·ln((1−d1)/(1−d0))\n"
        "w·ln(P1/P0) = w·ln(Fisher) + w·[ln(P1/P0) − ln(Fisher)]   (like-for-like + mix residual)\n"
        "Fisher = √(Laspeyres × Paasche) over products sold in both windows</span>"
        "<p>Prices come from Orders Details.UnitPrice, never Product.Price or NewPrice. The largest absolute "
        f"residual of the four-part split is {g['Residual'].abs().max():.1e}.</p>")
    why = ("<p>Growth that goes with more units sold calls for a different response than growth that goes with "
           "price or with selling more expensive items. Separating them shows which categories grew <strong>"
           "broadly</strong> and which rest on <strong>one product, a price step or discounts</strong> and need a "
           "closer look before more promotion money goes in.</p>")
    summary = (f"Most category growth goes with the <strong>quantity effect ({signed(allc['QtyEffect'], 0)} of "
               f"{signed(d, 0)})</strong>; <strong>Dairy Products and Seafood</strong> grew broadly; Meat/Poultry's "
               "average price jump is mainly associated with product-mix change, with like-for-like price "
               "changes also contributing.")
    return qpage("q4.html", "Q4 · What drives each category's sales change?",
                 "Is each product category's sales change driven by quantity, realised price or discount, and "
                 "which categories deserve promotion or further investigation?",
                 "Which product categories to promote and which to investigate before spending on them.",
                 answer, why, method, details, evidence, findings, implications, limits, supplement,
                 "q4_categories", "q4"), summary


def build_q5():
    """Build the Q5 page and return its overview summary.

    Args:
        None.

    Returns:
        tuple[str, str]: Page HTML and a one-line overview finding
            (HTML with <strong> on its key figures).
    """
    bands = read("q5_discounts", "q5_discount_band_summary.csv", index_col=0)
    cats = read("q5_discounts", "q5_category_discount_summary.csv", index_col=0)
    rel = read("q5_discounts", "q5_relative_quantity_by_band.csv", index_col=0)
    ov = read("q5_discounts", "q5_order_overlap.csv", index_col="item")["value"]
    bands.columns = ["Lines", "Orders", "Customers", "Products", "Qty P25", "Qty median", "Qty P75",
                     "Gross sales", "Discount", "Net sales", "Effective discount", "Discount values",
                     "Line share", "Net sales share"]
    btab = pd.DataFrame({
        "Band": bands.index.map(Q5_BANDS), "Lines": bands["Lines"], "Unique orders*": bands["Orders"],
        "Customers*": bands["Customers"],
        "Quantity P25 / median / P75": [f"{a:g} / {b:g} / {c:g}" for a, b, c in
                                        zip(bands["Qty P25"], bands["Qty median"], bands["Qty P75"])],
        "Gross sales": bands["Gross sales"].map(money), "Net sales": bands["Net sales"].map(money),
        "Effective discount": bands["Effective discount"],
        "Values in data": bands["Discount values"].str.replace("、", ", "),
    })
    rtab = pd.DataFrame({"Band": rel.index.map(Q5_BANDS), "Lines": rel["明细数"], "Products": rel["产品数"],
                         "Relative quantity P25 / median / P75": [f"{a:.2f} / {b:.2f} / {c:.2f}" for a, b, c in
                                                                  zip(rel["相对数量P25"], rel["相对数量中位数"],
                                                                      rel["相对数量P75"])]})
    k = "产品内数量比中位数（有折扣/无折扣）"
    lo, hi = "95%区间下限（按产品自助法）", "95%区间上限（按产品自助法）"
    cb = cats.drop("全部类别").sort_values(k, ascending=False)
    full = pd.concat([cb, cats.loc[["全部类别"]]])
    ctab = pd.DataFrame({
        "Category": list(cb.index) + ["All categories"],
        "Discounted lines": [f"{int(a)}/{int(b)}" for a, b in zip(full["有折扣明细数"], full["明细数"])],
        "Effective discount": full["有效折扣率"].map(lambda x: pct(x, 1)),
        "Comparable products": full["可比产品数"].astype(int),
        "Lines (no discount / discount)": [f"{int(a)} / {int(b)}" for a, b in
                                           zip(full["可比产品无折扣明细数"], full["可比产品有折扣明细数"])],
        "Higher / lower / equal": [f"{int(a)} / {int(b)} / {int(c)}" for a, b, c in
                                   zip(full["有折扣数量中位数更高的产品数"], full["有折扣数量中位数更低的产品数"],
                                       full["比值等于1的产品数"])],
        "Median ratio [95% interval]": [f"{r:.2f} [{a:.2f}, {b:.2f}]" for r, a, b in zip(full[k], full[lo], full[hi])],
    })
    allr = cats.loc["全部类别"]
    conf = cats.loc["Confections"]
    n_cmp = int(cb["可比产品数"].sum())
    evidence = (figure("q5_within_product_ratio_by_category.png",
                       "Within-product quantity ratio by category with 95% intervals",
                       "<strong>How to read:</strong> for each product, the typical (median) quantity on discounted "
                       "lines is divided by the typical quantity on undiscounted lines of the same product. "
                       "<strong>1 = the same quantity; above 1 = discounted lines are usually larger.</strong> Each "
                       "dot is a category's median of these product ratios, taken on the log scale; the bar is a 95% "
                       "bootstrap interval over products. Dashed line = 1; dotted line = all categories.")
                + "<h3>By category</h3>" + table(ctab, left=("Category",), total_last=True)
                + '<p class="note">Category value = exp(median of ln(product ratio)). With an odd number of products '
                  "this equals the ordinary median ratio; with an even number it is the geometric mean of the two "
                  "middle ratios.</p>")
    supplement = (figure("q5_quantity_by_discount_band.png", "Quantity per order line by discount band",
                         "Background. Left: quantity on each 1997 order line by discount band (raw units; pack sizes "
                         "differ, so this cannot compare demand across products). Right: quantity relative to the "
                         "same product's median undiscounted quantity (log scale; dashed line = 1), for products with "
                         "at least 3 lines of each kind. Boxes show the interquartile range, thick bars the median.")
                  + "<h3>Discount bands (1997 order lines)</h3>" + table(btab, left=("Band", "Values in data"))
                  + f'<p class="note">* Orders and customers can appear in several bands ({int(ov["orders_multi_band"])} '
                    f'of {int(ov["orders"])} orders do), so band counts add up to {int(ov["sum_band_orders"])}, not '
                    f'{int(ov["orders"])}. {int(ov["customers_any_discount"])} of {int(ov["customers"])} customers '
                    f'received a discount at least once; {int(ov["customers_never_discount"])} never did.</p>'
                  + "<h3>Relative quantity by band (same product)</h3>" + table(rtab, left=("Band",)))
    dairy = cats.loc["Dairy Products"]
    answer = (f"<p>Within the same product, discounted order lines are <strong>usually somewhat larger</strong>: "
              f"across {n_cmp} comparable products the summary ratio is <strong>{allr[k]:.2f}</strong> (95% interval "
              f"{allr[lo]:.2f}–{allr[hi]:.2f}). This summarises products; it does <strong>not</strong> mean every "
              f"discounted line bought {(allr[k] - 1) * 100:.0f}% more, and it does not show that discounts caused "
              "larger orders or improved profit.</p>"
              "<p><strong>Next step:</strong> treat <strong>Confections</strong> (the only category whose interval "
              f"excludes 1) and <strong>Dairy Products</strong> (lower bound exactly {dairy[lo]:.2f}) as candidates for "
              "a controlled discount test; the data does not support ranking one above the other.</p>")
    findings = [
        "Across discount bands, raw quantity per line looks similar (medians 18–24 units), with heavily "
        "overlapping quartiles; across products this mixes pack sizes, so it is background only.",
        f"<strong>Within the same product, discounted lines are usually somewhat larger</strong>: across {n_cmp} "
        f"comparable products the summary ratio is <strong>{allr[k]:.2f}</strong> (95% interval "
        f"{allr[lo]:.2f}–{allr[hi]:.2f}); {int(allr['有折扣数量中位数更高的产品数'])} products are higher, "
        f"{int(allr['有折扣数量中位数更低的产品数'])} lower and {int(allr['比值等于1的产品数'])} equal. The pattern does "
        "not rise steadily with discount depth (see the supplementary band table).",
        f"<strong>Confections</strong> is the only category whose interval excludes 1 ({conf[k]:.2f} "
        f"[{conf[lo]:.2f}, {conf[hi]:.2f}]). <strong>Dairy Products</strong> is borderline ({dairy[k]:.2f} "
        f"[{dairy[lo]:.2f}, {dairy[hi]:.2f}]). With eight categories compared at once and few products each, "
        "neither is proof that discounts work.",
        "Produce and Grains/Cereals show lower quantities on discounted lines, with very wide intervals.",
    ]
    implications = [
        "<strong>Candidates for a controlled test</strong> (for example, randomise a discount among similar "
        "customers): Confections and Dairy Products. The current evidence does not justify an order of priority "
        "between them; a test would need comparable customers and enough orders per arm.",
        "<strong>Meat/Poultry</strong> has the highest effective discount rate but an inconclusive ratio: a "
        "candidate for testing whether smaller discounts change volume.",
        "<strong>Before testing</strong>, document how discounts were granted in 1997 (by customer?) and add "
        "cost data so margin can be judged.",
    ]
    limits = [
        "<strong>Association only</strong>: discounts were not assigned at random, so this does not show that "
        "discounts raise quantity, and it says nothing about profit.",
        "The within-product comparison removes pack-size differences but <strong>does not control for customer, "
        "order size, timing or price changes</strong>, which may move together with discounts.",
        "Eight categories with 4–11 comparable products each are compared at once; intervals are rough and the "
        "results are <strong>exploratory, for designing tests</strong>.",
        "The eligibility rule (at least 3 lines of each kind) is an analysis choice.",
    ]
    method = (
        "<p><strong>Data and period:</strong> all 1,059 order lines of 1997 (by order date), joined to Orders, "
        "Product and Categories. Each line is put into a discount band: none, (0, 5%], (5, 10%], (10, 15%], above "
        "15%.</p>"
        "<p>Because pack sizes differ between products, comparing raw quantities across products says little about "
        "demand. So the <strong>main comparison is within the same product</strong>: for each product with at "
        "least 3 discounted and 3 undiscounted lines, the median discounted quantity divided by the median "
        "undiscounted quantity. Each category is summarised by the median of these ratios on the log scale, with "
        "a 95% bootstrap interval over products.</p>")
    details = (
        '<span class="formula">Band (on the discount rounded to 4 decimals):\n'
        "  0 | (0, 0.05] | (0.05, 0.10] | (0.10, 0.15] | > 0.15\n"
        "Effective discount = Σ UnitPrice×Quantity×Discount / Σ UnitPrice×Quantity\n"
        "Relative quantity = Quantity / median undiscounted Quantity of the same product\n"
        "Product ratio = median discounted Quantity / median undiscounted Quantity\n"
        "Category value = exp(median over products of ln(product ratio))</span>"
        "<p>Rounding fixes single-precision storage (0.05 is stored as 0.0500000007); sales use the stored value. "
        "Intervals: resample products with replacement 5,000 times, take the median log ratio each time, use the "
        "2.5th and 97.5th percentiles (percentile method), random seed 561.</p>")
    why = ("<p>Discounts cost money on every unit sold. If they do not go with larger purchases, they may be "
           "giving away revenue; where they do, those categories are the places to <strong>test discount policy "
           "properly</strong> before changing it.</p>")
    summary = (f"Across {n_cmp} comparable products, the median of each product's ratio (median discounted "
               f"quantity ÷ median undiscounted quantity) is <strong>{allr[k]:.2f}</strong>. This summarises "
               f"products; it does not mean every discounted line bought {(allr[k] - 1) * 100:.0f}% more. "
               "<strong>Only Confections' interval excludes 1</strong> — a lead for testing, not proof.")
    return qpage("q5.html", "Q5 · How do quantity and sales differ by discount level?",
                 "How do purchase quantity and discounted sales differ across discount levels, and which "
                 "categories merit further testing of discount strategy?",
                 "Where to run controlled discount tests, and what to document before changing discount policy.",
                 answer, why, method, details, evidence, findings, implications, limits, supplement,
                 "q5_discounts", "q5"), summary


def build_index(summaries):
    """Build the overview page, including links to the repository.

    Args:
        summaries (list[str]): One-line HTML finding per question,
            Q1-Q5; shown with <strong> in Main findings, plain in cards.

    Returns:
        str: Complete HTML document.
    """
    titles = ["Where did each market's sales change come from — which customers?",
              "How much do sales depend on a few customers?",
              "Which order groups take longer to ship?",
              "What drives each category's sales change?",
              "How do quantity and sales differ by discount level?"]
    # Summaries carry <strong> for the Main findings list; cards show them plain.
    cards = "".join(f'<div class="card"><h3><a href="q{i}.html">Q{i} · {esc(t)}</a></h3>'
                    f'<p>{re.sub(r"</?strong>", "", s)}</p></div>'
                    for i, (t, s) in enumerate(zip(titles, summaries), 1))
    extra = [
        'Spot-check: Switzerland traced to its raw orders and order lines '
        '(<a href="data/q1_country/spotcheck_Switzerland_lines.csv">lines</a>).',
        'Spot-check: customer RATTC traced to its raw order lines '
        '(<a href="data/q2_customers/spotcheck_RATTC_lines.csv">lines</a>).',
        "Spot-check: order 10777's shipping days recomputed from the Excel date serials.",
        "No single-record spot-check. Totals and join counts are reconciled, and every comparable order line in "
        "the 1997 window is compared with its product's 1998 price.",
        "No single-record spot-check. Totals are reconciled and every 1997 line is checked to fall in exactly "
        "one discount band.",
    ]
    checks = "".join(f"<li>Q{i}: {checks_line(d, f'q{i}')} {x}</li>"
                     for i, (d, x) in enumerate(zip(QDIRS, extra), 1))
    body = (
        "<h1>Northwind sales analysis</h1>"
        f'<p class="note">Code, data instructions and this site: <a href="{REPO_URL}">GitHub Repository</a></p>'
        '<p class="lede">Five business questions answered from the Northwind sample database (orders from '
        "1996-07-04 to 1998-05-06), for a manager who wants to understand the business. Each page gives the "
        "question and the decision it supports, a short answer, why it matters, the method, the evidence, "
        "findings, next steps and limitations.</p>"
        + section("Main findings", bullets([f"<strong>Q{i}.</strong> {s}" for i, s in enumerate(summaries, 1)])
                  + '<p class="note">All implications are directions for further evaluation. The analysis is '
                    "descriptive: it shows associations, not causes.</p>")
        + section("Questions", f'<div class="cards">{cards}</div>')
        + section("How the analysis was done", bullets([
            f'<strong>Data.</strong> <code>Northwind Database.xlsx</code> from the <a href="{DATA_URL}">course '
            "spreadsheet</a> (Google Sheets), read-only. Eight sheets; "
            "orders join to order lines by OrderID, to customers by CustomerID, to shippers by ShipVia, and lines "
            "join to products and categories. All joins were checked for lost or duplicated rows.",
            "<strong>Sales.</strong> Discounted sales of each order line, UnitPrice × Quantity × (1 − Discount), at "
            "full precision and rounded only for display. Freight is excluded. There is no currency field and no "
            "cost field, so amounts carry no currency and are <strong>never called profit</strong>.",
            "<strong>Grain.</strong> Orders are counted as unique OrderIDs and freight is taken at order level, so "
            "joining to order lines never inflates order counts.",
            "<strong>Periods.</strong> Only 1997 is a complete year. Q1 and Q4 compare January–April of 1997 and "
            "1998, which reduces seasonal differences; Q2, Q3 and Q5 use the full year 1997, by order date.",
            "<strong>Checks.</strong> Every question reconciles its totals with independently computed totals. Q1–Q3 also "
            "trace one example back to the raw rows; Q4 and Q5 do not:" + f'<ul class="tight">{checks}</ul>',
        ]))
        + section("Data source, reproduce and download",
                  f'<p>Data: <a href="{DATA_URL}">course spreadsheet (Google Sheets)</a>, downloaded as '
                  "<code>Northwind Database.xlsx</code>.</p>"
                  f'<p>Code: <a href="{REPO_URL}">GitHub Repository</a> '
                  f"(<code>{esc(REPO_URL)}</code>).</p>"
                  "<p>Run <code>inspect_northwind.py</code> and the five <code>q*.py</code> scripts, then "
                  '<code>build_site.py</code>; the steps are in the <a href="README.md" download>README '
                  "(download)</a>. All result tables can be downloaded from "
                  '<a href="downloads.html">Downloads</a>.</p>'))
    return page("index.html", "Overview", body)


def build_downloads():
    """Build the downloads page listing every result CSV.

    Args:
        None.

    Returns:
        str: Complete HTML document.
    """
    names = ["Q1 · Customer-country markets", "Q2 · Customer concentration", "Q3 · Shipping time",
             "Q4 · Category drivers", "Q5 · Discount levels"]
    body = ("<h1>Downloads</h1>"
            '<p class="lede">Every result table produced by the analysis scripts. Files are UTF-8 CSV with BOM, '
            "so Excel shows Chinese headers correctly; the \"raw precision\" files keep full precision.</p>"
            f'<p>Source data: <a href="{DATA_URL}">course spreadsheet (Google Sheets)</a>. Reproduction steps: '
            '<a href="README.md" download>README.md</a>.</p>'
            + "".join(section(n, downloads_for(d)) for n, d in zip(names, QDIRS)))
    return page("downloads.html", "Downloads", body)


def copy_assets():
    """Copy charts, CSVs and the README into ``site``.

    Removes and recreates ``site/img`` and ``site/data`` first; copies
    both Chinese and ``_en`` charts, and ``README.md`` to the site root.

    Args:
        None.

    Returns:
        tuple[int, int]: Number of PNG and CSV files copied.
    """
    shutil.copy2(ROOT / "README.md", SITE / "README.md")
    for sub in ("img", "data"):
        if (SITE / sub).exists():
            shutil.rmtree(SITE / sub)
    (SITE / "img").mkdir(parents=True)
    n_png = n_csv = 0
    for q in QDIRS:
        for p in (OUTPUTS / q).glob("*.png"):
            shutil.copy2(p, SITE / "img" / p.name)
            n_png += 1
        (SITE / "data" / q).mkdir(parents=True)
        for p in (OUTPUTS / q).glob("*.csv"):
            shutil.copy2(p, SITE / "data" / q / p.name)
            n_csv += 1
    return n_png, n_csv


def check_links():
    """Verify that every local href/src in the generated pages exists.

    Args:
        None.

    Returns:
        list[str]: "page -> target" for each missing target; empty if
            all links resolve.
    """
    import re
    missing = []
    for f in SITE.glob("*.html"):
        for target in re.findall(r'(?:href|src)="([^"#:]+)"', f.read_text(encoding="utf-8")):
            if not (SITE / target).exists():
                missing.append(f"{f.name} -> {target}")
    return missing


def main():
    """Build every page into ``SITE`` and print a short report.

    Args:
        None.

    Returns:
        None.

    Raises:
        SystemExit: If a chart has no ``_en`` version in ``outputs``.
    """
    SITE.mkdir(exist_ok=True)
    n_png, n_csv = copy_assets()
    missing_en = [p.name for p in (SITE / "img").glob("*.png")
                  if not p.stem.endswith("_en") and not (SITE / "img" / f"{p.stem}_en.png").exists()]
    if missing_en:
        raise SystemExit(f"English charts missing for {missing_en}; rerun the q*.py scripts first.")
    (SITE / "style.css").write_text(CSS.strip() + "\n", encoding="utf-8")
    summaries = []
    for name, build in [("q1.html", build_q1), ("q2.html", build_q2), ("q3.html", build_q3),
                        ("q4.html", build_q4), ("q5.html", build_q5)]:
        doc, summary = build()
        (SITE / name).write_text(doc, encoding="utf-8")
        summaries.append(summary)
    (SITE / "index.html").write_text(build_index(summaries), encoding="utf-8")
    (SITE / "downloads.html").write_text(build_downloads(), encoding="utf-8")
    missing = check_links()
    print(f"site/: {len(PAGES)} pages, {n_png} charts, {n_csv} CSV files")
    print("missing links:", missing or "none")


if __name__ == "__main__":
    main()
