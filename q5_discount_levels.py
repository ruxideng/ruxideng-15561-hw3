"""Q5: 1997 line quantity and sales by discount band, within products.

Writes tables, checks and charts to outputs/q5_discounts/.
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from inspect_northwind import CJK_FONTS, XLSX, load_workbook
from q1_country_markets import load

OUT = Path(__file__).with_name("outputs") / "q5_discounts"
YEAR = 1997
START, END = pd.Timestamp(f"{YEAR}-01-01"), pd.Timestamp(f"{YEAR}-12-31")
# Right-closed bands on the rounded discount: 0 | (0, .05] | (.05, .10] | (.10, .15] | > .15
BANDS = ["无折扣", "0–5%", ">5–10%", ">10–15%", ">15%"]
EDGES = [0.05, 0.10, 0.15]
ROUND = 4
MIN_LINES = 3          # per arm, for a product to enter the within-product comparison
MIN_PRODUCTS = 3       # per category, for a category-level summary to be read
N_BOOT = 5000
BOOT_SEED = 561
BOOT_METHOD = ("按产品有放回重抽样，每次取各产品对数比值的中位数，"
               "取 2.5% 与 97.5% 分位数后取指数（百分位法）")

# Chart text per language; "en" charts are written with an "_en" suffix.
CHART_TEXT = {
    "zh": {"suffix": "", "bands": {b: b for b in BANDS}, "median": "中位",
           "lab1": "{b}\n明细 {n}", "lab2": "{b}\n明细 {n} / 产品 {p}",
           "raw": "各折扣组明细数量（原始单位，跨产品包装不同）", "ylabel": "Quantity（每行明细）",
           "rel": "产品内相对数量（数量 ÷ 本产品无折扣数量中位数，对数轴；虚线 = 1）",
           "d_title": "{} 年订单明细：折扣水平与购买数量",
           "d_note": "注：框为四分位距，粗线为中位数，每点一行明细。右图仅含有折扣与无折扣明细各 ≥{} 行的产品。"
                     "关联描述，不能证明折扣提高销量，也不能判断利润。",
           "all": "全部类别 {:.2f}",
           "row": "{r:.2f} [{lo:.2f}, {hi:.2f}]   可比产品 {n}：更高 {up} / 更低 {down} / 相等 {eq}",
           "ref_only": "  仅参考", "c_axis": "比值（有折扣 ÷ 无折扣），虚线 = 1",
           "c_title": "同一产品内：有折扣明细数量中位数 ÷ 无折扣明细数量中位数（1997 年，按类别）\n"
                      "（类别值 = 各产品比值在对数尺度上的中位数再取指数；线段为按产品重抽样的 95% 自助区间）",
           "c_note": "注：>1 表示有折扣明细的数量通常更大；关联描述，不能证明因果；8 个类别同时比较、产品样本少，仅供探索。"
                     "自助区间：按产品有放回重抽样 {} 次，随机种子 {}，百分位法。"},
    "en": {"suffix": "_en", "median": "",
           "bands": dict(zip(BANDS, ["No discount", "(0, 5%]", "(5, 10%]", "(10, 15%]", "> 15%"])),
           "lab1": "{b}\n{n} lines", "lab2": "{b}\n{n} lines\n{p} products",
           "raw": "Quantity per order line by discount band (raw units; pack sizes differ)",
           "ylabel": "Quantity per order line",
           "rel": "Relative quantity (÷ same product's median undiscounted qty; log scale; dashed = 1)",
           "d_title": "{} order lines: discount level and quantity",
           "d_note": "Note: box = interquartile range, thick bar = median (value at right), one dot per line. "
                     "Right panel: products with ≥{0} lines of each kind. Association only; nothing about profit.",
           "all": "All categories {:.2f}",
           "row": "{r:.2f} [{lo:.2f}, {hi:.2f}]   {n} products: {up} higher / {down} lower / {eq} equal",
           "ref_only": "  reference only", "c_axis": "Ratio (discounted ÷ undiscounted); dashed = 1",
           "c_title": "Do discounted order lines buy more of the same product? 1997, by category\n"
                      "(each product: median discounted qty ÷ median undiscounted qty; category value = median "
                      "of these ratios on the log scale; bars = 95% bootstrap interval)",
           "c_note": "Note: 1 = same quantity with and without discount; >1 = discounted lines usually larger. "
                     "Association only, not causal and not profit. Eight categories,\nfew products each: exploratory. "
                     "Bootstrap: products resampled with replacement {} times, seed {}, percentile method."},
}

CHECKS = []


def check(name, expected, actual, tol=1e-6):
    """Record a validation result in the module-level ``CHECKS`` list.

    Args:
        name (str): What is being compared.
        expected (float): Reference value; any number castable to float.
        actual (float): Value produced by the pipeline.
        tol (float): Absolute tolerance for a pass.

    Returns:
        None. Appends one row to ``CHECKS``.
    """
    ok = abs(float(expected) - float(actual)) <= tol
    CHECKS.append({"检查项": name, "期望": expected, "实际": actual,
                   "差额": float(actual) - float(expected), "通过": ok})


def band_of(d):
    """Assign right-closed discount bands to discount rates.

    Args:
        d (pandas.Series): Discount rates as fractions; the caller
            rounds them to ``ROUND`` decimals first.

    Returns:
        pandas.Categorical: Band per value, ordered as ``BANDS``; NaN
            for values fitting no band (e.g. negative).
    """
    conds = [d == 0, (d > 0) & (d <= EDGES[0]), (d > EDGES[0]) & (d <= EDGES[1]),
             (d > EDGES[1]) & (d <= EDGES[2]), d > EDGES[2]]
    return pd.Categorical(np.select(conds, BANDS, default="未分组"), categories=BANDS, ordered=True)


def build_lines():
    """Return 1997 detail lines with order, product and band columns.

    Join checks are appended to ``CHECKS``. The number of lines whose
    band would change without rounding is stored in
    ``attrs["shifted_by_rounding"]`` of the returned lines.

    Args:
        None.

    Returns:
        tuple[pandas.DataFrame, pandas.DataFrame]: One row per 1997
            detail line with CustomerID, product, category,
            ``DiscRounded``, ``Band``, ``Gross``, ``DiscountAmt`` and
            ``HasDiscount``; and the 1997 orders.
    """
    det, ords, _ = load()
    sheets = load_workbook(XLSX)
    prod = sheets["Product"].iloc[:, [0, 1, 3]].copy()
    prod.columns = ["ProductID", "ProductName", "CategoryID"]
    prod = prod.astype({"ProductID": "int64", "CategoryID": "int64"})
    cat = sheets["Categories"][["CategoryID", "CategoryName"]].astype({"CategoryID": "int64"})

    o = ords[(ords["OrderDate"] >= START) & (ords["OrderDate"] <= END)]
    raw = det[det["OrderID"].isin(o["OrderID"])]
    l = (raw.merge(o[["OrderID", "CustomerID", "OrderDate"]], on="OrderID", how="left", validate="many_to_one")
         .merge(prod, on="ProductID", how="left", validate="many_to_one")
         .merge(cat, on="CategoryID", how="left", validate="many_to_one"))
    check(f"{YEAR} 明细关联订单/产品/类别后行数不变", len(raw), len(l))
    check(f"{YEAR} 明细关联后折后销售额不变", raw["Sales"].sum(), l["Sales"].sum())
    check("关联后 CategoryName 为空的行数", 0, l["CategoryName"].isna().sum())
    check(f"{YEAR} 订单数（Orders 表）= 明细中唯一 OrderID", len(o), l["OrderID"].nunique())

    l["DiscRounded"] = l["Discount"].round(ROUND)
    l["Band"] = band_of(l["DiscRounded"])
    l["Gross"] = l["UnitPrice"] * l["Quantity"]
    l["DiscountAmt"] = l["Gross"] * l["Discount"]
    l["HasDiscount"] = l["DiscRounded"] > 0
    raw_bands = band_of(l["Discount"])
    l.attrs["shifted_by_rounding"] = int((raw_bands != l["Band"]).sum())
    return l, o


def band_table(l, o):
    """Summarise lines per discount band.

    Coverage and total checks are appended to ``CHECKS``.

    Args:
        l (pandas.DataFrame): First output of ``build_lines``.
        o (pandas.DataFrame): 1997 orders.

    Returns:
        pandas.DataFrame: One row per band plus a "全部" row, with
            counts, quantity quartiles, sales, effective discount rate
            and shares of lines and sales.
    """
    def stats(g):
        """Compute line, order, quantity and sales figures for lines.

        Args:
            g (pandas.DataFrame): Lines of one band, or all lines.

        Returns:
            pandas.Series: Chinese-labelled statistics.
        """
        q = g["Quantity"]
        return pd.Series({
            "明细数": len(g), "唯一订单数": g["OrderID"].nunique(),
            "客户数": g["CustomerID"].nunique(), "产品数": g["ProductID"].nunique(),
            "数量P25": q.quantile(0.25), "数量中位数": q.median(), "数量P75": q.quantile(0.75),
            "折前销售额": g["Gross"].sum(), "折扣金额": g["DiscountAmt"].sum(),
            "折后销售额": g["Sales"].sum(),
            "有效折扣率": g["DiscountAmt"].sum() / g["Gross"].sum(),
            "原始折扣值": "、".join(f"{v:g}" for v in sorted(g["DiscRounded"].unique())),
        })

    t = l.groupby("Band", observed=False).apply(stats, include_groups=False)
    t.loc["全部"] = stats(l)
    t["明细占比"] = t["明细数"] / len(l)
    t["折后销售额占比"] = t["折后销售额"] / l["Sales"].sum()

    body = t.drop("全部")
    check("各组明细数之和 = 1997 明细数", len(l), body["明细数"].sum())
    check("未分组明细数", 0, (l["Band"].astype(str) == "未分组").sum() + l["Band"].isna().sum())
    check("每行明细恰好属于一个组", len(l), l.groupby("Band", observed=False).size().sum())
    check("各组折后销售额之和 = 1997 总额", l["Sales"].sum(), body["折后销售额"].sum())
    check("各组折前销售额之和 = 1997 折前总额", l["Gross"].sum(), body["折前销售额"].sum())
    check("1997 折后总额 = 第二题总额 617,085.20（两位小数）", 617085.20, round(l["Sales"].sum(), 2), tol=0.005)
    check("全部行唯一订单数 = Orders 表 1997 订单数", len(o), t.loc["全部", "唯一订单数"])
    return t


def order_overlap(l):
    """Count orders spanning bands and customers' discount exposure.

    Args:
        l (pandas.DataFrame): First output of ``build_lines``.

    Returns:
        dict[str, int]: Orders, orders in more than one band, sum of
            per-band order counts, customers with and without any
            discount, and orders with a single discount value.
    """
    per_order = l.groupby("OrderID")["Band"].nunique()
    per_cust = l.groupby("CustomerID")["HasDiscount"].agg(["any", "all"])
    return {
        "orders": len(per_order),
        "orders_multi_band": int((per_order > 1).sum()),
        "sum_band_orders": int(l.groupby("Band", observed=False)["OrderID"].nunique().sum()),
        "customers": len(per_cust),
        "customers_any_discount": int(per_cust["any"].sum()),
        "customers_never_discount": int((~per_cust["any"]).sum()),
        "orders_uniform_discount": int((l.groupby("OrderID")["DiscRounded"].nunique() == 1).sum()),
    }


def within_product(l):
    """Compare discounted and undiscounted quantity within each product.

    Each eligible line's quantity is divided by the median undiscounted
    quantity of its own product, so pack size cancels out. Products
    need ``MIN_LINES`` lines in each arm to be eligible.

    Args:
        l (pandas.DataFrame): First output of ``build_lines``.

    Returns:
        tuple[pandas.DataFrame, pandas.DataFrame]: One row per product
            with arm line counts, median quantities, ``Eligible``,
            ``MedianRatio`` and ``LogRatio``; and the lines of eligible
            products with ``RelQty``.
    """
    rows = []
    for (pid, name, catname), g in l.groupby(["ProductID", "ProductName", "CategoryName"]):
        nd, d = g[~g["HasDiscount"]], g[g["HasDiscount"]]
        rows.append({"ProductID": pid, "ProductName": name, "CategoryName": catname,
                     "NoDiscLines": len(nd), "DiscLines": len(d),
                     "NoDiscMedianQty": nd["Quantity"].median() if len(nd) else np.nan,
                     "DiscMedianQty": d["Quantity"].median() if len(d) else np.nan,
                     "DiscSalesShare": d["Sales"].sum() / g["Sales"].sum()})
    p = pd.DataFrame(rows)
    p["Eligible"] = (p["NoDiscLines"] >= MIN_LINES) & (p["DiscLines"] >= MIN_LINES)
    p["MedianRatio"] = p["DiscMedianQty"] / p["NoDiscMedianQty"]
    p["LogRatio"] = np.log(p["MedianRatio"])
    el = l[l["ProductID"].isin(p.loc[p["Eligible"], "ProductID"])].copy()
    base = el[~el["HasDiscount"]].groupby("ProductID")["Quantity"].median()
    el["RelQty"] = el["Quantity"] / el["ProductID"].map(base)
    check("可比产品的无折扣明细相对数量中位数 = 1（按定义）", 1.0,
          el[~el["HasDiscount"]].groupby("ProductID")["RelQty"].median().median())
    return p, el


def boot_ci(x, rng):
    """Bootstrap a percentile 95% interval for the median of ``x``.

    Draws ``N_BOOT`` resamples of ``x`` with replacement.

    Args:
        x (numpy.ndarray): Per-product log ratios.
        rng (numpy.random.Generator): Random generator; advanced by
            the call.

    Returns:
        tuple[float, float]: 2.5th and 97.5th percentiles of the
            resampled medians, or (NaN, NaN) if ``x`` has < 2 values.
    """
    if len(x) < 2:
        return np.nan, np.nan
    meds = np.median(rng.choice(x, size=(N_BOOT, len(x)), replace=True), axis=1)
    return tuple(np.percentile(meds, [2.5, 97.5]))


def category_summary(l, p, el):
    """Summarise discount use and within-product ratios by category.

    One generator seeded with ``BOOT_SEED`` is shared across categories
    in alphabetical order, then "全部类别", so intervals are
    reproducible for this order. Checks that the eight categories'
    counts add up to the comparable-product total go to ``CHECKS``.

    Args:
        l (pandas.DataFrame): All 1997 lines.
        p (pandas.DataFrame): First output of ``within_product``.
        el (pandas.DataFrame): Second output of ``within_product``.

    Returns:
        pandas.DataFrame: One row per category plus "全部类别", with
            discount use, comparable-product counts, the median ratio
            and its bootstrap interval.
    """
    rng = np.random.default_rng(BOOT_SEED)
    rows = []
    for cat_name, g in list(l.groupby("CategoryName")) + [("全部类别", l)]:
        pc = p[p["Eligible"]] if cat_name == "全部类别" else p[p["Eligible"] & (p["CategoryName"] == cat_name)]
        ec = el if cat_name == "全部类别" else el[el["CategoryName"] == cat_name]
        lo, hi = boot_ci(pc["LogRatio"].to_numpy(), rng)
        med = pc["LogRatio"].median() if len(pc) else np.nan
        rows.append({
            "类别": cat_name, "明细数": len(g), "有折扣明细数": int(g["HasDiscount"].sum()),
            "有折扣明细占比": g["HasDiscount"].mean(),
            "有效折扣率": g["DiscountAmt"].sum() / g["Gross"].sum(),
            "折扣金额": g["DiscountAmt"].sum(), "折后销售额": g["Sales"].sum(),
            "可比产品数": len(pc), "可比产品无折扣明细数": int((~ec["HasDiscount"]).sum()),
            "可比产品有折扣明细数": int(ec["HasDiscount"].sum()),
            "有折扣数量中位数更高的产品数": int((pc["MedianRatio"] > 1).sum()),
            "有折扣数量中位数更低的产品数": int((pc["MedianRatio"] < 1).sum()),
            "比值等于1的产品数": int((pc["MedianRatio"] == 1).sum()),
            "产品内数量比中位数（有折扣/无折扣）": np.exp(med) if pd.notna(med) else np.nan,
            "95%区间下限（按产品自助法）": np.exp(lo) if pd.notna(lo) else np.nan,
            "95%区间上限（按产品自助法）": np.exp(hi) if pd.notna(hi) else np.nan,
            "有折扣明细相对数量中位数": ec.loc[ec["HasDiscount"], "RelQty"].median() if len(ec) else np.nan,
            "样本提示": "" if len(pc) >= MIN_PRODUCTS else f"可比产品<{MIN_PRODUCTS}，仅参考",
            "自助法": f"{BOOT_METHOD}；重抽样 {N_BOOT} 次；随机种子 {BOOT_SEED}",
        })
    c = pd.DataFrame(rows).set_index("类别")
    cats = c.drop("全部类别")
    check("八个类别可比产品数之和 = 可比产品总数", int(p["Eligible"].sum()), cats["可比产品数"].sum())
    check("八个类别更高+更低+等于1的产品数之和 = 可比产品总数", int(p["Eligible"].sum()),
          cats[["有折扣数量中位数更高的产品数", "有折扣数量中位数更低的产品数", "比值等于1的产品数"]].sum().sum())
    check("各类别明细数之和 = 1997 明细数", len(l), c.drop("全部类别")["明细数"].sum())
    check("各类别折后销售额之和 = 1997 总额", l["Sales"].sum(), c.drop("全部类别")["折后销售额"].sum())
    return c


def band_relative(el):
    """Summarise relative quantity per discount band.

    Args:
        el (pandas.DataFrame): Second output of ``within_product``.

    Returns:
        pandas.DataFrame: Lines, products and ``RelQty`` quartiles per
            band.
    """
    return el.groupby("Band", observed=False).agg(
        明细数=("RelQty", "size"), 产品数=("ProductID", "nunique"),
        相对数量P25=("RelQty", lambda s: s.quantile(0.25)),
        相对数量中位数=("RelQty", "median"),
        相对数量P75=("RelQty", lambda s: s.quantile(0.75)))


def setup_style():
    """Set fonts from ``CJK_FONTS`` and return the chart colours.

    Args:
        None.

    Returns:
        dict[str, str]: Named hex colours.
    """
    plt.rcParams["font.sans-serif"] = CJK_FONTS
    plt.rcParams["axes.unicode_minus"] = False
    return {"ink": "#0b0b0b", "ink2": "#52514e", "muted": "#898781", "grid": "#e1e0d9",
            "base": "#c3c2b7", "surf": "#fcfcfb", "dot": "#2a78d6", "box": "#0b0b0b",
            "ref": "#eb6834"}


def style_axes(ax, c, axis="y"):
    """Apply the recessive grid and spine style.

    Args:
        ax (matplotlib.axes.Axes): Axes to style.
        c (dict): Colours from ``setup_style``.
        axis (str): Axis that carries gridlines.

    Returns:
        None.
    """
    ax.set_facecolor(c["surf"])
    ax.grid(axis=axis, color=c["grid"], lw=0.6)
    ax.set_axisbelow(True)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.spines["left"].set_color(c["base"])
    ax.spines["bottom"].set_color(c["base"])
    ax.tick_params(colors=c["muted"], labelsize=9, length=0)


def strip_box(ax, groups, labels, c, log=False, median_word="中位"):
    """Draw jittered points with quartile boxes and median ticks.

    Jitter uses a fresh generator seeded with 0, so it is the same on
    every call. Empty groups are skipped.

    Args:
        ax (matplotlib.axes.Axes): Target axes.
        groups (list[numpy.ndarray]): Values per group, in x order.
        labels (list[str]): Tick label per group.
        c (dict): Colours from ``setup_style``.
        log (bool): Use a log y-scale.
        median_word (str): Word printed before each median value;
            "" prints the value alone.

    Returns:
        None.
    """
    rng = np.random.default_rng(0)
    for i, v in enumerate(groups):
        if len(v) == 0:
            continue
        ax.scatter(i + rng.uniform(-0.28, 0.28, len(v)), v, s=9, color=c["dot"], alpha=0.35, linewidths=0)
        q1, med, q3 = np.percentile(v, [25, 50, 75])
        ax.add_patch(matplotlib.patches.Rectangle((i - 0.32, q1), 0.64, q3 - q1, fill=False,
                                                  edgecolor=c["box"], lw=1.2))
        ax.plot([i - 0.36, i + 0.36], [med, med], color=c["box"], lw=2.4)
        ax.text(i + 0.4, med, f"{median_word} {med:.2f}".rstrip("0").rstrip("."), va="center",
                fontsize=8.5, color=c["ink2"])
    ax.set_xticks(range(len(labels)), labels, color=c["ink2"])
    ax.set_xlim(-0.6, len(labels) - 0.1)
    if log:
        ax.set_yscale("log")


def plot_distributions(l, el, bands, rel, lang="zh"):
    """Draw raw and within-product relative quantity by discount band.

    Args:
        l (pandas.DataFrame): All 1997 lines.
        el (pandas.DataFrame): Second output of ``within_product``.
        bands (pandas.DataFrame): Output of ``band_table``.
        rel (pandas.DataFrame): Output of ``band_relative``.
        lang (str): Chart language, a key of ``CHART_TEXT``; "en"
            adds an "_en" suffix to the file name.

    Returns:
        pathlib.Path: The PNG written to ``OUT``.
    """
    c = setup_style()
    tx = CHART_TEXT[lang]
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(15, 6.4))
    fig.patch.set_facecolor(c["surf"])
    lab1 = [tx["lab1"].format(b=tx["bands"][b], n=int(bands.loc[b, "明细数"])) for b in BANDS]
    strip_box(a1, [l.loc[l["Band"] == b, "Quantity"].to_numpy() for b in BANDS], lab1, c,
              median_word=tx["median"])
    a1.set_title(tx["raw"], loc="left", color=c["ink"], fontsize=12)
    a1.set_ylabel(tx["ylabel"], color=c["muted"])
    lab2 = [tx["lab2"].format(b=tx["bands"][b], n=int(rel.loc[b, "明细数"]), p=int(rel.loc[b, "产品数"]))
            for b in BANDS]
    strip_box(a2, [el.loc[el["Band"] == b, "RelQty"].to_numpy() for b in BANDS], lab2, c, log=True,
              median_word=tx["median"])
    a2.axhline(1, color=c["ref"], lw=1.2, ls="--")
    a2.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:g}"))
    a2.set_title(tx["rel"], loc="left", color=c["ink"], fontsize=12)
    for ax in (a1, a2):
        style_axes(ax, c)
    fig.suptitle(tx["d_title"].format(YEAR), x=0.01, ha="left", fontsize=14, color=c["ink"])
    fig.text(0.01, 0.01, tx["d_note"].format(MIN_LINES), fontsize=9, color=c["muted"])
    fig.tight_layout(rect=(0, 0.03, 1, 0.95))
    path = OUT / f"q5_quantity_by_discount_band{tx['suffix']}.png"
    fig.savefig(path, dpi=150, facecolor=c["surf"])
    plt.close(fig)
    return path


def plot_categories(cats, lang="zh"):
    """Plot each category's within-product ratio with its interval.

    Args:
        cats (pandas.DataFrame): Output of ``category_summary``.
        lang (str): Chart language, a key of ``CHART_TEXT``; "en"
            adds an "_en" suffix to the file name.

    Returns:
        pathlib.Path: The PNG written to ``OUT``.
    """
    c = setup_style()
    tx = CHART_TEXT[lang]
    k = "产品内数量比中位数（有折扣/无折扣）"
    b = cats.drop("全部类别").sort_values(k)
    allr = cats.loc["全部类别"]
    y = np.arange(len(b))
    fig, ax = plt.subplots(figsize=(15, 6.2))
    fig.patch.set_facecolor(c["surf"])
    small = b["样本提示"] != ""
    ax.hlines(y, b["95%区间下限（按产品自助法）"], b["95%区间上限（按产品自助法）"],
              color=np.where(small, c["base"], c["dot"]), lw=2)
    ax.scatter(b[k], y, s=60, zorder=3, color=np.where(small, c["base"], c["dot"]),
               edgecolors=c["surf"], linewidths=1.5)
    ax.axvline(1, color=c["ref"], lw=1.2, ls="--")
    ax.axvline(allr[k], color=c["muted"], lw=1, ls=":")
    # Start the label just right of the dotted all-categories line so neither
    # reference line crosses it.
    ax.text(allr[k] + 0.04, -0.75, tx["all"].format(allr[k]), ha="left", va="center",
            fontsize=8.5, color=c["muted"])
    tr = ax.get_yaxis_transform()
    for yi, (_, r) in zip(y, b.iterrows()):
        ax.text(1.03, yi, tx["row"].format(
                    r=r[k], lo=r["95%区间下限（按产品自助法）"], hi=r["95%区间上限（按产品自助法）"],
                    n=int(r["可比产品数"]), nd=int(r["可比产品无折扣明细数"]), d=int(r["可比产品有折扣明细数"]),
                    up=int(r["有折扣数量中位数更高的产品数"]), down=int(r["有折扣数量中位数更低的产品数"]),
                    eq=int(r["比值等于1的产品数"]))
                + (tx["ref_only"] if r["样本提示"] else ""),
                transform=tr, va="center", fontsize=8.5, color=c["muted"] if r["样本提示"] else c["ink2"])
    ax.set_xlim(0.3, 3.5)
    ax.set_ylim(-1.1, len(b) - 0.5)
    ax.set_xticks([0.5, 1, 1.5, 2, 2.5, 3])
    ax.set_yticks(y, b.index, color=c["ink2"])
    style_axes(ax, c, "x")
    ax.set_title(tx["c_axis"], loc="left", color=c["ink"], fontsize=11)
    fig.suptitle(tx["c_title"], x=0.01, ha="left", fontsize=13, color=c["ink"])
    fig.text(0.01, 0.01, tx["c_note"].format(N_BOOT, BOOT_SEED), fontsize=9, color=c["muted"])
    fig.tight_layout(rect=(0, 0.06, 0.74, 0.9))
    path = OUT / f"q5_within_product_ratio_by_category{tx['suffix']}.png"
    fig.savefig(path, dpi=150, facecolor=c["surf"])
    plt.close(fig)
    return path


def display_bands(t):
    """Format the band table for CSV.

    Args:
        t (pandas.DataFrame): Output of ``band_table``; not modified.

    Returns:
        pandas.DataFrame: Copy with integer counts, sales rounded to 2
            decimals and rates as percentage strings.
    """
    d = t.copy()
    for col in ["明细数", "唯一订单数", "客户数", "产品数"]:
        d[col] = d[col].astype(int)
    for col in ["折前销售额", "折扣金额", "折后销售额"]:
        d[col] = d[col].astype(float).round(2)
    for col in ["有效折扣率", "明细占比", "折后销售额占比"]:
        d[col] = d[col].map(lambda x: f"{x * 100:.2f}%")
    d.index.name = "折扣组"
    return d


def main():
    """Run Q5, write all outputs to ``OUT`` and print a summary.

    Args:
        None.

    Returns:
        None.
    """
    sys.stdout.reconfigure(encoding="utf-8")
    pd.set_option("display.width", 260)
    pd.set_option("display.max_columns", 40)
    pd.set_option("display.max_rows", 120)
    OUT.mkdir(parents=True, exist_ok=True)

    l, o = build_lines()
    bands = band_table(l, o)
    ov = order_overlap(l)
    p, el = within_product(l)
    cats = category_summary(l, p, el)
    rel = band_relative(el)
    f1 = plot_distributions(l, el, bands, rel)
    f2 = plot_categories(cats)
    plot_distributions(l, el, bands, rel, "en")
    plot_categories(cats, "en")

    display_bands(bands).to_csv(OUT / "q5_discount_band_summary.csv", encoding="utf-8-sig")
    cats.to_csv(OUT / "q5_category_discount_summary.csv", encoding="utf-8-sig")
    p.sort_values(["CategoryName", "ProductName"]).to_csv(
        OUT / "q5_within_product_comparison.csv", index=False, encoding="utf-8-sig")
    rel.to_csv(OUT / "q5_relative_quantity_by_band.csv", encoding="utf-8-sig")
    pd.Series(ov, name="value").to_csv(OUT / "q5_order_overlap.csv", index_label="item",
                                       encoding="utf-8-sig")
    l[["OrderID", "OrderDate", "CustomerID", "ProductID", "ProductName", "CategoryName", "UnitPrice",
       "Quantity", "Discount", "DiscRounded", "Band", "Gross", "DiscountAmt", "Sales"]].to_csv(
        OUT / "q5_lines_1997.csv", index=False, encoding="utf-8-sig")
    checks = pd.DataFrame(CHECKS)
    checks.to_csv(OUT / "q5_validation.csv", index=False, encoding="utf-8-sig")

    print("== 折扣分组 ==")
    print(display_bands(bands).T.to_string())
    print(f"\n浮点边界：按 {ROUND} 位小数四舍五入后分组；若直接用存储值分组会改变组别的明细数 = "
          f"{l.attrs['shifted_by_rounding']}")
    print("\n== 订单与客户跨组情况 ==")
    print(ov)
    print("\n== 可比产品：相对数量按折扣组 ==")
    print(rel.round(3).to_string())
    print("\n== 类别汇总 ==")
    print(cats.round(3).T.to_string())
    print(f"\n自助区间：{BOOT_METHOD}；重抽样 {N_BOOT} 次；随机种子 {BOOT_SEED}")
    print(f"可比产品总数: {int(p['Eligible'].sum())} / {len(p)}；"
          f"至少有一行有折扣和一行无折扣的产品: {int(((p['DiscLines'] > 0) & (p['NoDiscLines'] > 0)).sum())}")
    print("\n== 验证 ==")
    print(checks.to_string(index=False))
    print(f"\n全部通过: {checks['通过'].all()}")
    print(f"\n图表: {f1}\n      {f2}")


if __name__ == "__main__":
    main()
