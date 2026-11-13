"""Q4: LMDI split of Jan-Apr 1997 vs 1998 category sales changes.

Writes tables, price checks and charts to outputs/q4_categories/.
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from inspect_northwind import CJK_FONTS, XLSX, load_workbook
from q1_country_markets import load, period_of

OUT = Path(__file__).with_name("outputs") / "q4_categories"
BASE, CUR = "1997", "1998"
NA = "不适用"
EFFECTS = ["QtyEffect", "LikePriceEffect", "MixEffect", "DiscountEffect"]
EFFECT_ZH = {
    "QtyEffect": "数量合计效应",
    "LikePriceEffect": "同产品成交单价效应",
    "MixEffect": "产品组合效应（剩余项，含仅在一个窗口有销售的产品）",
    "DiscountEffect": "折扣效应",
}
# Chart text per language; "en" charts are written with an "_en" suffix.
CHART_TEXT = {
    "zh": {"suffix": "", "window": "{} 年 1–4 月", "effects": EFFECT_ZH,
           "sales": "折后销售额（未标注币种），标注为增长率",
           "actual": "实际变化（四项之和）",
           "decomp": "读图：右侧为增加、左侧为减少；菱形为实际净变化（四项之和）",
           "title": "产品类别折后销售额：{} vs {} 年 1–4 月",
           "sales_x": "折后销售额（未标注币种）",
           "decomp_title": "各类别销售额变化由哪些部分构成：{} → {} 年 1–4 月（LMDI 描述性分解）",
           "decomp_x": "对销售额变化的贡献（未标注币种）",
           "note": "注：数量合计跨产品相加，包装单位不同，不是标准化实物销量；组合效应是剩余项，反映类别内\n"
                   "产品结构及仅在一个窗口有销售的产品，不是涨价；同产品成交单价效应是描述性分解项，观察到"
                   "可比明细在 1997-04-04 及以前约为 1998 年单价的 0.8 倍。",
           "qty": "数量合计（混合包装单位）", "price": "加权平均成交单价",
           "disc": "有效折扣率（折扣金额 ÷ 折前销售额）",
           "m_title": "类别指标：两期对比（按销售额变化金额排序）",
           "m_note": "注：加权平均成交单价受类别内产品组合影响，变化不等于涨价；数量合计不可跨产品直接比较需求。"},
    "en": {"suffix": "_en", "window": "Jan–Apr {}",
           "effects": {"QtyEffect": "Quantity effect", "LikePriceEffect": "Like-for-like price effect",
                       "MixEffect": "Product-mix effect (residual)", "DiscountEffect": "Discount effect"},
           "sales": "Discounted sales (no currency field), labelled with growth",
           "actual": "Actual change (sum of the four)",
           "decomp": "How to read: bars right of 0 add to sales, bars left of 0 subtract; "
                     "the diamond is the actual net change (sum of the four)",
           "title": "Discounted sales by product category: Jan–Apr {} vs Jan–Apr {}",
           "sales_x": "Discounted sales (no currency field)",
           "decomp_title": "What each category's change in sales is made of: Jan–Apr {} → Jan–Apr {} "
                           "(descriptive LMDI split)",
           "decomp_x": "Contribution to the change in sales (no currency field)",
           "note": "Note: summed quantity mixes pack sizes, so the quantity effect is not a measure of real demand; "
                   "the mix effect is a residual,\nnot a price rise; the like-for-like price effect is descriptive "
                   "(see the price-level check on the page).",
           "qty": "Summed quantity (mixed pack sizes)", "price": "Average realised price",
           "disc": "Effective discount rate (discount ÷ gross sales)",
           "m_title": "Category metrics, both windows (sorted by change in sales)",
           "m_note": "Note: average realised price also moves with product mix, so its change is not only a "
                     "price change; summed quantity cannot compare demand across products."},
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


def logmean(a, b):
    """Return the logarithmic mean L(a, b) used as the LMDI weight.

    Args:
        a (float): Current-period value, > 0.
        b (float): Base-period value, > 0.

    Returns:
        float: (a - b) / (ln a - ln b), or ``a`` when
            ``numpy.isclose(a, b)``.
    """
    return a if np.isclose(a, b) else (a - b) / (np.log(a) - np.log(b))


def build_lines():
    """Join window detail lines to products and categories.

    Key, join and total checks are appended to ``CHECKS``.

    Args:
        None.

    Returns:
        pandas.DataFrame: One row per detail line in either Jan-Apr
            window, with ``Period``, ``ProductName``, ``CategoryID``,
            ``CategoryName``, ``Gross``, ``DiscountAmt`` and ``Sales``.
    """
    det, ords, _ = load()
    sheets = load_workbook(XLSX)
    prod = sheets["Product"].iloc[:, [0, 1, 3]].copy()
    prod.columns = ["ProductID", "ProductName", "CategoryID"]
    prod = prod.astype({"ProductID": "int64", "CategoryID": "int64"})
    cat = sheets["Categories"][["CategoryID", "CategoryName"]].astype({"CategoryID": "int64"})
    check("Product.ProductID 唯一", len(prod), prod["ProductID"].nunique())
    check("Categories.CategoryID 唯一", len(cat), cat["CategoryID"].nunique())

    ords = ords.assign(Period=period_of(ords["OrderDate"]))
    ids = ords.loc[ords["Period"].notna(), ["OrderID", "Period"]]
    raw = det[det["OrderID"].isin(ids["OrderID"])]
    l1 = raw.merge(ids, on="OrderID", how="left", validate="many_to_one")
    l2 = l1.merge(prod, on="ProductID", how="left", validate="many_to_one")
    l3 = l2.merge(cat, on="CategoryID", how="left", validate="many_to_one")
    for name, df in [("关联订单期间后", l1), ("关联产品后", l2), ("关联类别后", l3)]:
        check(f"{name}明细行数不变", len(raw), len(df))
        check(f"{name}折后销售额不变", raw["Sales"].sum(), df["Sales"].sum())
    check("关联后 CategoryID 为空的行数", 0, l3["CategoryID"].isna().sum())
    check("关联后 CategoryName 为空的行数", 0, l3["CategoryName"].isna().sum())
    check("（OrderID, ProductID）在期间明细中无重复", 0,
          l3.duplicated(["OrderID", "ProductID"]).sum())

    l3["Gross"] = l3["UnitPrice"] * l3["Quantity"]
    l3["DiscountAmt"] = l3["Gross"] * l3["Discount"]
    check("折前 − 折扣金额 = 折后（全部期间明细）", l3["Sales"].sum(),
          (l3["Gross"] - l3["DiscountAmt"]).sum())
    for p in [BASE, CUR]:
        ref = det[det["OrderID"].isin(ids.loc[ids["Period"] == p, "OrderID"])]
        got = l3[l3["Period"] == p]
        check(f"{p} 期明细行数：原始明细 vs 关联后", len(ref), len(got))
        check(f"{p} 期折后销售额：原始明细 vs 关联后", ref["Sales"].sum(), got["Sales"].sum())
    return l3


def price_regime():
    """Compare detail UnitPrice with each product's 1998 UnitPrice.

    Only products sold in 1998 can be compared. One coverage check is
    appended to ``CHECKS``.

    Args:
        None.

    Returns:
        tuple[pandas.DataFrame, dict]: Share of lines below 95% of the
            1998 price per window and per 1997 month; and a dict with
            the switch dates, window coverage counts, lines near 0.8
            and 1.0 of the 1998 price, and an ``exceptions`` DataFrame.
    """
    det, ords, _ = load()
    l = det.merge(ords[["OrderID", "OrderDate"]], on="OrderID", validate="many_to_one")
    p98 = l[l["OrderDate"].dt.year == 1998].groupby("ProductID")["UnitPrice"].max().rename("P98")
    l = l.merge(p98, on="ProductID", how="inner")
    l["Ratio"] = l["UnitPrice"] / l["P98"]
    l["Below"] = l["Ratio"] < 0.95
    l["Period"] = period_of(l["OrderDate"])
    rows = [{"范围": f"{p} 年 1–4 月", "明细行": int((l["Period"] == p).sum()),
             "低于1998价格水平的行占比": l.loc[l["Period"] == p, "Below"].mean(),
             "低价行的单价/1998单价中位数": l.loc[(l["Period"] == p) & l["Below"], "Ratio"].median()}
            for p in [BASE, CUR]]
    y97 = l[l["OrderDate"].dt.year == 1997]
    for m, g in y97.groupby(y97["OrderDate"].dt.to_period("M")):
        rows.append({"范围": f"{m}", "明细行": len(g), "低于1998价格水平的行占比": g["Below"].mean(),
                     "低价行的单价/1998单价中位数": g.loc[g["Below"], "Ratio"].median()})
    info = {"last_low": l.loc[l["Below"], "OrderDate"].max().date(),
            "first_full": l.loc[~l["Below"] & (l["OrderDate"].dt.year == 1997), "OrderDate"].min().date()}

    # Coverage of the observed pattern within the 1997 Jan-Apr window.
    all97 = det.merge(ords[["OrderID", "OrderDate"]], on="OrderID")
    all97 = all97[period_of(all97["OrderDate"]) == BASE]
    win = l[l["Period"] == BASE]
    pre = win[win["OrderDate"] <= pd.Timestamp(info["last_low"])]
    post = win[win["OrderDate"] > pd.Timestamp(info["last_low"])]
    near08 = pre["Ratio"].between(0.78, 0.82)
    near10 = post["Ratio"].between(0.99, 1.01)
    p98_n = l[l["OrderDate"].dt.year == 1998].groupby("ProductID")["UnitPrice"].nunique()
    no98 = sorted(set(all97["ProductID"]) - set(p98.index))
    exc = pd.concat([pre.loc[~near08].assign(Rule=f"≤{info['last_low']} 但单价/1998单价不在 0.78–0.82"),
                     post.loc[~near10].assign(Rule=f">{info['last_low']} 但单价/1998单价不在 0.99–1.01")])
    info.update({
        "products_window": all97["ProductID"].nunique(),
        "lines_window": len(all97),
        "products_comparable": win["ProductID"].nunique(),
        "lines_comparable": len(win),
        "products_no_1998_price": no98,
        "lines_no_1998_price": int(all97["ProductID"].isin(no98).sum()),
        "pre_lines": len(pre), "pre_products": pre["ProductID"].nunique(),
        "pre_near08": int(near08.sum()),
        "post_lines": len(post), "post_products": post["ProductID"].nunique(),
        "post_near10": int(near10.sum()),
        "products_multi_price_1998": int((p98_n > 1).sum()),
        "exceptions": exc[["OrderID", "OrderDate", "ProductID", "UnitPrice", "P98", "Ratio", "Rule"]],
    })
    check(f"{BASE} 窗口：可比明细 + 无 1998 单价的明细 = 窗口明细", info["lines_window"],
          info["lines_comparable"] + info["lines_no_1998_price"])
    return pd.DataFrame(rows), info


def product_table(lines):
    """Aggregate lines to one row per product with both windows.

    Args:
        lines (pandas.DataFrame): Output of ``build_lines``.

    Returns:
        pandas.DataFrame: Per product: quantity, gross, net sales and
            lines per window (0 if unsold), unit value gross / quantity
            (NaN if unsold), change columns and ``SoldIn``.
    """
    g = lines.groupby(["CategoryName", "ProductID", "ProductName", "Period"]).agg(
        Qty=("Quantity", "sum"), Gross=("Gross", "sum"), Sales=("Sales", "sum"),
        Lines=("OrderID", "size")).unstack("Period")
    g.columns = [f"{m}_{p}" for m, p in g.columns]
    for m in ["Qty", "Gross", "Sales", "Lines"]:
        for p in [BASE, CUR]:
            g[f"{m}_{p}"] = g.get(f"{m}_{p}", 0).fillna(0)
    for p in [BASE, CUR]:
        g[f"Price_{p}"] = g[f"Gross_{p}"] / g[f"Qty_{p}"].replace(0, np.nan)
    g["SalesChange"] = g[f"Sales_{CUR}"] - g[f"Sales_{BASE}"]
    g["PriceChange"] = g[f"Price_{CUR}"] / g[f"Price_{BASE}"] - 1
    # Describes sales in the two windows only; says nothing about launch
    # or discontinuation.
    g["SoldIn"] = np.select(
        [(g[f"Qty_{BASE}"] > 0) & (g[f"Qty_{CUR}"] > 0), g[f"Qty_{BASE}"] > 0],
        ["两期均有", f"仅{BASE}年窗口有销售"], f"仅{CUR}年窗口有销售")
    return g.reset_index()


def fisher_index(prods):
    """Compute a Fisher price index over products sold in both windows.

    Args:
        prods (pandas.DataFrame): Rows of ``product_table`` for one
            category (or all products).

    Returns:
        float: sqrt(Laspeyres * Paasche) of product unit values, or NaN
            if no product sold in both windows.
    """
    c = prods[prods["SoldIn"] == "两期均有"]
    if c.empty:
        return np.nan
    q0, q1, p0, p1 = c[f"Qty_{BASE}"], c[f"Qty_{CUR}"], c[f"Price_{BASE}"], c[f"Price_{CUR}"]
    lasp = (q0 * p1).sum() / (q0 * p0).sum()
    paas = (q1 * p1).sum() / (q1 * p0).sum()
    return np.sqrt(lasp * paas)


def category_table(lines, prods):
    """Aggregate per category and window and decompose the change.

    Net sales S = Q * P * (1 - d): Q summed quantity, P gross / Q, d
    discount / gross. LMDI-I gives dS = w ln(Q1/Q0) + w ln(P1/P0)
    + w ln((1-d1)/(1-d0)) with w = L(S1, S0). The price term is split
    into a Fisher index over products sold in both windows and a
    residual mix term. Total and identity checks go to ``CHECKS``.

    Args:
        lines (pandas.DataFrame): Output of ``build_lines``.
        prods (pandas.DataFrame): Output of ``product_table``.

    Returns:
        tuple[pandas.DataFrame, pandas.DataFrame]: Category table with
            measures, effects and ``Residual`` (plus a "全部类别" row),
            and per-window totals.
    """
    g = lines.groupby(["CategoryName", "Period"]).agg(
        Sales=("Sales", "sum"), Gross=("Gross", "sum"), DiscountAmt=("DiscountAmt", "sum"),
        Qty=("Quantity", "sum"), Lines=("OrderID", "size"), Orders=("OrderID", "nunique"),
        Products=("ProductID", "nunique")).unstack("Period")
    g.columns = [f"{m}_{p}" for m, p in g.columns]
    tot = lines.groupby("Period").agg(
        Sales=("Sales", "sum"), Gross=("Gross", "sum"), DiscountAmt=("DiscountAmt", "sum"),
        Qty=("Quantity", "sum"), Lines=("OrderID", "size"), Orders=("OrderID", "nunique"),
        Products=("ProductID", "nunique"))
    for p in [BASE, CUR]:
        check(f"{p} 各类别折后销售额之和 = 期间总额", tot.loc[p, "Sales"], g[f"Sales_{p}"].sum())
        check(f"{p} 各类别明细行之和 = 期间明细行", tot.loc[p, "Lines"], g[f"Lines_{p}"].sum())
        check(f"{p} 各类别数量之和 = 期间数量", tot.loc[p, "Qty"], g[f"Qty_{p}"].sum())
    g.loc["全部类别"] = [tot.loc[p, m] for m, p in
                       [c.rsplit("_", 1) for c in g.columns]]

    for p in [BASE, CUR]:
        g[f"Price_{p}"] = g[f"Gross_{p}"] / g[f"Qty_{p}"]
        g[f"DiscRate_{p}"] = g[f"DiscountAmt_{p}"] / g[f"Gross_{p}"]
    g["SalesChange"] = g[f"Sales_{CUR}"] - g[f"Sales_{BASE}"]
    g["SalesGrowth"] = g["SalesChange"] / g[f"Sales_{BASE}"]

    allp = prods.assign(CategoryName="全部类别")
    fisher = {c: fisher_index(pd.concat([prods, allp])[lambda d: d["CategoryName"] == c])
              for c in g.index}
    rows = {}
    for c, r in g.iterrows():
        s0, s1 = r[f"Sales_{BASE}"], r[f"Sales_{CUR}"]
        w = logmean(s1, s0)
        ln_q = np.log(r[f"Qty_{CUR}"] / r[f"Qty_{BASE}"])
        ln_p = np.log(r[f"Price_{CUR}"] / r[f"Price_{BASE}"])
        ln_d = np.log((1 - r[f"DiscRate_{CUR}"]) / (1 - r[f"DiscRate_{BASE}"]))
        ln_like = np.log(fisher[c])
        rows[c] = {"FisherPriceIndex": fisher[c], "QtyEffect": w * ln_q,
                   "PriceEffect": w * ln_p, "LikePriceEffect": w * ln_like,
                   "MixEffect": w * (ln_p - ln_like), "DiscountEffect": w * ln_d}
    e = pd.DataFrame(rows).T
    g = g.join(e)
    g["Residual"] = g["SalesChange"] - g[EFFECTS].sum(axis=1)
    check("分解：各类别四项效应之和 = 实际变化（最大绝对残差）", 0,
          g["Residual"].abs().max(), tol=1e-6)
    check("分解：单价效应 = 同产品单价效应 + 组合效应（最大绝对残差）", 0,
          (g["PriceEffect"] - g["LikePriceEffect"] - g["MixEffect"]).abs().max(), tol=1e-6)
    check("各类别变化之和 = 全部类别变化", g.loc["全部类别", "SalesChange"],
          g.drop("全部类别")["SalesChange"].sum())
    return g, tot


def product_breadth(prods, g):
    """Add product-spread columns to the category table.

    Args:
        prods (pandas.DataFrame): Output of ``product_table``.
        g (pandas.DataFrame): Category table; product counts, top
            product and single-window products are added in place.

    Returns:
        None. Also appends per-category sum checks to ``CHECKS``.
    """
    for c, d in prods.groupby("CategoryName"):
        top = d.loc[d["SalesChange"].abs().idxmax()]
        g.loc[c, "ProductsUp"] = (d["SalesChange"] > 0).sum()
        g.loc[c, "ProductsDown"] = (d["SalesChange"] < 0).sum()
        g.loc[c, "TopProduct"] = top["ProductName"]
        g.loc[c, "TopProductChange"] = top["SalesChange"]
        g.loc[c, "TopProductShareOfChange"] = top["SalesChange"] / g.loc[c, "SalesChange"]
        g.loc[c, "OnlyOnePeriod"] = "、".join(
            f"{n}（{s}）" for n, s in d.loc[d["SoldIn"] != "两期均有", ["ProductName", "SoldIn"]].values)
        check(f"{c}：产品销售额变化之和 = 类别变化", g.loc[c, "SalesChange"], d["SalesChange"].sum())


def display(g):
    """Build the Chinese-labelled, rounded category table.

    Args:
        g (pandas.DataFrame): Category table after ``product_breadth``.

    Returns:
        pandas.DataFrame: Table sorted by change descending, with the
            "全部类别" row last.
    """
    pct = lambda x, d=1: NA if pd.isna(x) else f"{x * 100:+.{d}f}%"
    t = pd.DataFrame(index=g.index)
    for p in [BASE, CUR]:
        t[f"{p}年1-4月折后销售额"] = g[f"Sales_{p}"].round(2)
    t["变化金额"] = g["SalesChange"].round(2)
    t["增长率"] = g["SalesGrowth"].map(pct)
    for p in [BASE, CUR]:
        t[f"{p}数量合计（混合包装单位）"] = g[f"Qty_{p}"].astype(int)
    for p in [BASE, CUR]:
        t[f"{p}加权平均成交单价"] = g[f"Price_{p}"].round(2)
    for p in [BASE, CUR]:
        t[f"{p}有效折扣率"] = g[f"DiscRate_{p}"].map(lambda x: f"{x * 100:.2f}%")
    t["有效折扣率变化（百分点）"] = ((g[f"DiscRate_{CUR}"] - g[f"DiscRate_{BASE}"]) * 100).round(2)
    t["同产品价格指数（Fisher）"] = g["FisherPriceIndex"].round(4)
    for k in EFFECTS:
        t[EFFECT_ZH[k]] = g[k].round(2)
    for k in EFFECTS:
        t[f"{EFFECT_ZH[k]}占变化金额"] = (g[k] / g["SalesChange"]).map(lambda x: f"{x * 100:.1f}%")
    t["分解残差"] = g["Residual"].map(lambda x: f"{x:.1e}")
    for p in [BASE, CUR]:
        t[f"{p}含该类别的订单数"] = g[f"Orders_{p}"].astype(int)
    t["增长/下降产品数"] = [NA if pd.isna(u) else f"{int(u)}/{int(d)}"
                      for u, d in zip(g.get("ProductsUp"), g.get("ProductsDown"))]
    t["变化最大的产品"] = g.get("TopProduct").fillna(NA)
    t["该产品变化占类别变化"] = g.get("TopProductShareOfChange").map(
        lambda x: NA if pd.isna(x) else f"{x * 100:.0f}%")
    t["仅在一个窗口有销售的产品"] = g.get("OnlyOnePeriod").fillna("")
    body = t.drop("全部类别").sort_values("变化金额", ascending=False)
    out = pd.concat([body, t.loc[["全部类别"]]])
    out.index.name = "类别"
    return out


def setup_style():
    """Set fonts from ``CJK_FONTS`` and return the chart colours.

    Args:
        None.

    Returns:
        dict[str, str | list[str]]: Named hex colours; ``"eff"`` holds
            the four effect colours in ``EFFECTS`` order.
    """
    plt.rcParams["font.sans-serif"] = CJK_FONTS
    plt.rcParams["axes.unicode_minus"] = False
    return {"ink": "#0b0b0b", "ink2": "#52514e", "muted": "#898781", "grid": "#e1e0d9",
            "base": "#c3c2b7", "surf": "#fcfcfb", "b0": "#86b6ef", "b1": "#2a78d6",
            "eff": ["#2a78d6", "#eb6834", "#1baf7a", "#eda100"]}


def style_axes(ax, c, axis="x"):
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
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.spines["bottom"].set_color(c["base"])
    ax.tick_params(colors=c["muted"], labelsize=9, length=0)


def plot_sales_and_effects(g, lang="zh"):
    """Draw category sales by window and, separately, the decomposition.

    Each is a full-width chart: ``q4_category_sales*.png`` (sales in
    both windows) and ``q4_category_decomposition*.png`` (the four
    effects, hatched as well as coloured, with the net change marked).

    Args:
        g (pandas.DataFrame): Category table.
        lang (str): Chart language, a key of ``CHART_TEXT``; "en"
            adds an "_en" suffix to the file names.

    Returns:
        tuple[pathlib.Path, pathlib.Path]: Sales chart and
            decomposition chart written to ``OUT``.
    """
    c = setup_style()
    tx = CHART_TEXT[lang]
    b = g.drop("全部类别").sort_values("SalesChange")
    y = np.arange(len(b))
    fig, a1 = plt.subplots(figsize=(13, 6))
    fig.patch.set_facecolor(c["surf"])
    h = 0.38
    a1.barh(y + h / 2, b[f"Sales_{BASE}"], height=h - 0.04, color=c["b0"], label=tx["window"].format(BASE))
    a1.barh(y - h / 2, b[f"Sales_{CUR}"], height=h - 0.04, color=c["b1"], label=tx["window"].format(CUR))
    for yi, (_, r) in zip(y, b.iterrows()):
        a1.text(r[f"Sales_{CUR}"], yi - h / 2, f"  {r['SalesGrowth'] * 100:+.0f}%", va="center",
                fontsize=8.5, color=c["ink2"])
    a1.set_title(tx["sales"], loc="left", color=c["ink"], fontsize=12)
    a1.legend(loc="lower right", frameon=False, labelcolor=c["ink2"])
    a1.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:,.0f}"))
    a1.set_xlim(0, b[f"Sales_{CUR}"].max() * 1.15)
    a1.set_xlabel(tx["sales_x"], color=c["muted"])
    style_axes(a1, c)
    a1.set_yticks(y, b.index, color=c["ink2"], fontsize=10)
    fig.suptitle(tx["title"].format(BASE, CUR), x=0.01, ha="left", fontsize=14, color=c["ink"])
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    p1 = OUT / f"q4_category_sales{tx['suffix']}.png"
    fig.savefig(p1, dpi=150, facecolor=c["surf"])
    plt.close(fig)

    fig, a2 = plt.subplots(figsize=(13, 6.8))
    fig.patch.set_facecolor(c["surf"])
    pos, neg = np.zeros(len(b)), np.zeros(len(b))
    for k, col, hatch in zip(EFFECTS, c["eff"], ["", "//", "..", "\\\\"]):
        v = b[k].to_numpy()
        left = np.where(v >= 0, pos, neg)
        a2.barh(y, v, left=left, height=0.6, color=col, hatch=hatch, label=tx["effects"][k],
                edgecolor=c["surf"], linewidth=1)
        pos, neg = pos + np.clip(v, 0, None), neg + np.clip(v, None, 0)
    a2.scatter(b["SalesChange"], y, marker="D", s=56, color=c["ink"], zorder=3,
               edgecolors=c["surf"], linewidths=1.5, label=tx["actual"])
    for yi, v in zip(y, b["SalesChange"]):
        a2.text(pos[yi] + 900, yi, f"{v:+,.0f}", va="center", fontsize=10, color=c["ink"])
    a2.axvline(0, color=c["ink2"], lw=1.2)
    a2.set_title(tx["decomp"], loc="left", color=c["ink"], fontsize=12)
    a2.legend(loc="lower right", frameon=False, labelcolor=c["ink2"], fontsize=10)
    a2.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:,.0f}"))
    a2.set_xlim(neg.min() * 1.3, pos.max() * 1.15)
    a2.set_xlabel(tx["decomp_x"], color=c["muted"])
    style_axes(a2, c)
    a2.set_yticks(y, b.index, color=c["ink2"], fontsize=10)
    fig.suptitle(tx["decomp_title"].format(BASE, CUR), x=0.01, ha="left", fontsize=14, color=c["ink"])
    fig.text(0.01, 0.01, tx["note"], fontsize=9, color=c["muted"])
    fig.tight_layout(rect=(0, 0.06, 1, 0.95))
    p2 = OUT / f"q4_category_decomposition{tx['suffix']}.png"
    fig.savefig(p2, dpi=150, facecolor=c["surf"])
    plt.close(fig)
    return p1, p2


def plot_metrics(g, lang="zh"):
    """Draw dumbbells for quantity, average price and discount rate.

    Args:
        g (pandas.DataFrame): Category table.
        lang (str): Chart language, a key of ``CHART_TEXT``; "en"
            adds an "_en" suffix to the file name.

    Returns:
        pathlib.Path: The PNG written to ``OUT``.
    """
    c = setup_style()
    tx = CHART_TEXT[lang]
    b = g.drop("全部类别").sort_values("SalesChange")
    y = np.arange(len(b))
    specs = [("Qty", tx["qty"], lambda v: f"{v:,.0f}"),
             ("Price", tx["price"], lambda v: f"{v:,.1f}"),
             ("DiscRate", tx["disc"], lambda v: f"{v * 100:.1f}%")]
    fig, axes = plt.subplots(1, 3, figsize=(15, 5.6), sharey=True)
    fig.patch.set_facecolor(c["surf"])
    for ax, (m, title, fmt) in zip(axes, specs):
        v0, v1 = b[f"{m}_{BASE}"], b[f"{m}_{CUR}"]
        ax.hlines(y, np.minimum(v0, v1), np.maximum(v0, v1), color=c["base"], lw=2)
        ax.scatter(v0, y, s=60, color=c["b0"], zorder=3, label=tx["window"].format(BASE))
        ax.scatter(v1, y, s=60, color=c["b1"], zorder=3, label=tx["window"].format(CUR))
        for yi, a, z in zip(y, v0, v1):
            ax.text(max(a, z), yi + 0.28, f"{fmt(a)} → {fmt(z)}", ha="right", fontsize=8, color=c["ink2"])
        ax.set_title(title, loc="left", color=c["ink"], fontsize=11)
        style_axes(ax, c)
        if m == "DiscRate":
            ax.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v * 100:.0f}%"))
            ax.set_xlim(0, max(v0.max(), v1.max()) * 1.25)
        else:
            ax.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:,.0f}"))
            ax.set_xlim(0, max(v0.max(), v1.max()) * 1.12)
    axes[0].set_yticks(y, b.index, color=c["ink2"])
    axes[0].legend(loc="lower right", frameon=False, labelcolor=c["ink2"], fontsize=9)
    fig.suptitle(tx["m_title"], x=0.01, ha="left", fontsize=14, color=c["ink"])
    fig.text(0.01, 0.01, tx["m_note"], fontsize=9, color=c["muted"])
    fig.tight_layout(rect=(0, 0.03, 1, 0.94))
    path = OUT / f"q4_category_metrics{tx['suffix']}.png"
    fig.savefig(path, dpi=150, facecolor=c["surf"])
    plt.close(fig)
    return path


def main():
    """Run Q4, write all outputs to ``OUT`` and print a summary.

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

    lines = build_lines()
    prods = product_table(lines)
    g, tot = category_table(lines, prods)
    product_breadth(prods, g)
    table = display(g)
    regime, regime_info = price_regime()
    (p1, p3), p2 = plot_sales_and_effects(g), plot_metrics(g)
    plot_sales_and_effects(g, "en")
    plot_metrics(g, "en")
    regime.to_csv(OUT / "q4_price_level_check.csv", index=False, encoding="utf-8-sig")

    prod_out = prods.sort_values(["CategoryName", "SalesChange"])
    table.to_csv(OUT / "q4_category_comparison.csv", encoding="utf-8-sig")
    g.to_csv(OUT / "q4_category_raw_precision.csv", encoding="utf-8-sig")
    prod_out.to_csv(OUT / "q4_product_detail.csv", index=False, encoding="utf-8-sig")
    checks = pd.DataFrame(CHECKS)
    checks.to_csv(OUT / "q4_validation.csv", index=False, encoding="utf-8-sig")

    print("== 期间总额 ==")
    print(tot.round(2).to_string())
    print("\n== 类别对比与分解 ==")
    print(table.T.to_string())
    print("\n== 明细单价水平检查（相对各产品 1998 年单价）==")
    print(regime.round(3).to_string(index=False))
    print(f"最后一张低价明细的下单日期: {regime_info['last_low']}；"
          f"1997 年首张 1998 价格水平明细的下单日期: {regime_info['first_full']}")
    ri = regime_info
    print(f"{BASE} 窗口：{ri['lines_window']} 行明细 / {ri['products_window']} 个产品；"
          f"有 1998 年单价可比的 {ri['lines_comparable']} 行 / {ri['products_comparable']} 个产品；"
          f"无 1998 年单价的产品 {ri['products_no_1998_price']}（{ri['lines_no_1998_price']} 行）")
    print(f"  ≤{ri['last_low']}：{ri['pre_lines']} 行 / {ri['pre_products']} 个产品，"
          f"其中单价/1998单价在 0.78–0.82 的 {ri['pre_near08']} 行")
    print(f"  >{ri['last_low']}：{ri['post_lines']} 行 / {ri['post_products']} 个产品，"
          f"其中在 0.99–1.01 的 {ri['post_near10']} 行")
    print(f"  1998 年有多个单价的产品数：{ri['products_multi_price_1998']}")
    print("  例外明细：\n" + (ri["exceptions"].to_string(index=False) if len(ri["exceptions"]) else "  无"))
    ri["exceptions"].to_csv(OUT / "q4_price_level_exceptions.csv", index=False, encoding="utf-8-sig")
    pd.Series({k: (", ".join(map(str, v)) if isinstance(v, list) else v)
               for k, v in ri.items() if k != "exceptions"}, name="value").to_csv(
        OUT / "q4_price_level_coverage.csv", index_label="item", encoding="utf-8-sig")
    print("\n== 产品明细（按类别、变化排序）==")
    cols = ["CategoryName", "ProductName", "SoldIn", f"Qty_{BASE}", f"Qty_{CUR}",
            f"Price_{BASE}", f"Price_{CUR}", "PriceChange", f"Sales_{BASE}", f"Sales_{CUR}", "SalesChange"]
    print(prod_out[cols].round(3).to_string(index=False))
    print("\n== 验证 ==")
    print(checks.to_string(index=False))
    print(f"\n全部通过: {checks['通过'].all()}")
    print(f"\n图表: {p3}\n      {p1}\n      {p2}")


if __name__ == "__main__":
    main()
