"""Q2: concentration of 1997 discounted sales across customers.

Writes tables, checks and a Pareto chart to outputs/q2_customers/.
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from inspect_northwind import CJK_FONTS
from q1_country_markets import load

OUT = Path(__file__).with_name("outputs") / "q2_customers"
YEAR = 1997
START, END = pd.Timestamp(f"{YEAR}-01-01"), pd.Timestamp(f"{YEAR}-12-31")
NA = "不适用"
TOP_NS = [1, 5, 10]
CORE_CUM_SHARE = 0.80      # customers making up the first 80% of sales
FREQ_MIN_ORDERS = 6        # 75th percentile of 1997 order counts
FREQ_MIN_QUARTERS = 3      # bought in at least 3 of 4 quarters
SINGLE_ORDER_SHARE = 0.50  # one order >= 50% of the customer's sales

SEG_REPEAT = "头部·持续多次购买"
SEG_LUMPY = "未满足持续购买规则的头部客户"
SEG_TAIL_REPEAT = "其余客户·满足持续购买规则"
SEG_TAIL_OTHER = "其余客户·未满足持续购买规则"
SEG_NONE = f"{YEAR}年无订单"
TAG_LOW_FREQ = "低频"
TAG_FEW_QUARTERS = "季度覆盖不足"
TAG_DOMINANT = "单笔主导"
# Chart text per language; "en" charts are written with an "_en" suffix.
CHART_TEXT = {
    "zh": {"suffix": "",
           "repeat": "累计贡献约80%销售额的前{n}名客户·满足持续购买规则",
           "lumpy": "前{n}名中未满足持续购买规则的头部客户（{tags}，见客户表）",
           "tail": "其余客户（第{n1}名起）",
           "rule": "持续购买规则：订单≥{mo}、≥{mq}个季度有订单、最大单笔<{share}",
           "bars": "{year} 年各客户折后销售额（降序，不含运费，未标注币种）",
           "first": "{}：{:,.0f}", "top": "前{n}：{y:.1f}%", "cum": "前 {n} 名客户累计 {y:.1f}%",
           "cumtitle": "累计销售额占比（公司内部，%）",
           "xlabel": "客户排名（按 {year} 年销售额，1 = 最大；共 {count} 个有订单客户，完整名单见客户表）",
           "title": "客户销售额帕累托图：{year} 年全年"},
    "en": {"suffix": "_en",
           "repeat": "Top {n} customers (~80% of sales) · meet the repeat rule",
           "lumpy": "Top {n} customers · miss the repeat rule (low frequency / few quarters / "
                    "single-order dominated)",
           "tail": "Other customers (rank {n1}+)",
           "rule": "Repeat rule: ≥{mo} orders, orders in ≥{mq} quarters, largest order <{share}",
           "bars": "{year} discounted sales per customer (descending; freight excluded; no currency field)",
           "first": "{}: {:,.0f}", "top": "Top {n}: {y:.1f}%", "cum": "Top {n} customers: {y:.1f}%",
           "cumtitle": "Cumulative share of company sales (%)",
           "xlabel": "Customer rank by {year} sales (1 = largest; {count} customers with orders; names in the table)",
           "title": "Customer sales Pareto chart: full year {year}"},
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


def year_orders(det, ords):
    """Return 1997 detail lines and order-level discounted sales.

    Join and total checks are appended to ``CHECKS``.

    Args:
        det (pandas.DataFrame): Order details with ``Sales``.
        ords (pandas.DataFrame): Orders with datetime ``OrderDate``.

    Returns:
        tuple[pandas.DataFrame, pandas.DataFrame]: 1997 detail lines
            with CustomerID and OrderDate, and one row per 1997 order
            with ``Sales`` and ``Lines``.
    """
    o = ords[(ords["OrderDate"] >= START) & (ords["OrderDate"] <= END)]
    raw = det[det["OrderID"].isin(o["OrderID"])]
    lines = raw.merge(o[["OrderID", "CustomerID", "OrderDate"]], on="OrderID",
                      how="left", validate="many_to_one")
    check(f"{YEAR} 明细关联订单前后行数", len(raw), len(lines))
    check(f"{YEAR} 明细关联订单前后销售额", raw["Sales"].sum(), lines["Sales"].sum())
    check(f"{YEAR} 关联后 CustomerID 为空的行数", 0, lines["CustomerID"].isna().sum())

    per_order = lines.groupby(["OrderID", "CustomerID", "OrderDate"], as_index=False).agg(
        Sales=("Sales", "sum"), Lines=("ProductID", "size"))
    check(f"{YEAR} 有明细的订单数 = Orders 表订单数", len(o), len(per_order))
    check(f"{YEAR} 订单级销售额合计 = 明细级合计", lines["Sales"].sum(), per_order["Sales"].sum())
    return lines, per_order


def customer_table(per_order, cus, ords):
    """Aggregate 1997 orders to one row per customer, inactive included.

    Total checks are appended to ``CHECKS``.

    Args:
        per_order (pandas.DataFrame): Second output of ``year_orders``.
        cus (pandas.DataFrame): Customers.
        ords (pandas.DataFrame): Orders, for reference counts.

    Returns:
        pandas.DataFrame: All customers indexed by CustomerID, sorted
            by 1997 sales descending, with share, cumulative share,
            rank, order stats, ``Core`` flag and segment columns.
    """
    g = per_order.groupby("CustomerID").agg(
        Sales=("Sales", "sum"),
        Orders=("OrderID", "nunique"),
        Lines=("Lines", "sum"),
        MaxOrderSales=("Sales", "max"),
        MedianOrderSales=("Sales", "median"),
        ActiveMonths=("OrderDate", lambda s: s.dt.to_period("M").nunique()),
        ActiveQuarters=("OrderDate", lambda s: s.dt.quarter.nunique()),
        FirstOrder=("OrderDate", "min"),
        LastOrder=("OrderDate", "max"),
    )
    t = cus[["CustomerID", "CompanyName", "Country"]].set_index("CustomerID").join(g, how="left")
    for c in ["Sales", "Orders", "Lines", "ActiveMonths", "ActiveQuarters"]:
        t[c] = t[c].fillna(0)
    total = t["Sales"].sum()
    t["Share"] = t["Sales"] / total
    t["AOV"] = t["Sales"] / t["Orders"].replace(0, np.nan)
    t["MaxOrderShare"] = t["MaxOrderSales"] / t["Sales"].replace(0, np.nan)
    t = t.sort_values(["Sales", "Orders"], ascending=[False, False])
    t["Rank"] = np.where(t["Sales"] > 0, np.arange(1, len(t) + 1), np.nan)
    t["CumShare"] = t["Share"].cumsum()
    # Core = customers needed to reach 80%, including the one that crosses it.
    t["Core"] = (t["CumShare"].shift(fill_value=0) < CORE_CUM_SHARE) & (t["Sales"] > 0)
    t["Segment"], t["SegmentReason"], t["RuleTags"] = zip(*t.apply(segment, axis=1))

    o97 = ords[(ords["OrderDate"] >= START) & (ords["OrderDate"] <= END)]
    check("客户销售额合计 = 全年总额（订单级）", per_order["Sales"].sum(), total)
    check("客户订单数合计 = Orders 表 1997 年行数", len(o97), t["Orders"].sum())
    check("客户订单数合计 = Orders 表 1997 年唯一 OrderID", o97["OrderID"].nunique(), t["Orders"].sum())
    check("有订单客户数 = Orders 表 1997 年唯一 CustomerID", o97["CustomerID"].nunique(),
          (t["Orders"] > 0).sum())
    check("Orders 表 1997 年 CustomerID 都能在 Customers 表找到", 0,
          (~o97["CustomerID"].isin(cus["CustomerID"])).sum())
    check("客户内部销售额占比合计 = 100%", 1.0, t["Share"].sum(), tol=1e-12)
    check("客户数（含无订单客户）= Customers 表行数", len(cus), len(t))
    return t


def segment(r):
    """Classify a customer by 1997 sales rank and buying pattern.

    Args:
        r (pandas.Series): One row of the customer table.

    Returns:
        tuple[str, str, str]: Segment label, the rule detail behind it,
            and unmet-rule tags joined by "、" (empty if all met).
    """
    if r["Orders"] == 0:
        return SEG_NONE, "1997 年没有订单", ""
    why, tags = [], []
    if r["Orders"] < FREQ_MIN_ORDERS:
        why.append(f"订单{int(r['Orders'])}张<{FREQ_MIN_ORDERS}")
        tags.append(TAG_LOW_FREQ)
    if r["ActiveQuarters"] < FREQ_MIN_QUARTERS:
        why.append(f"仅{int(r['ActiveQuarters'])}个季度有订单")
        tags.append(TAG_FEW_QUARTERS)
    if r["MaxOrderShare"] >= SINGLE_ORDER_SHARE:
        why.append(f"最大单笔占{r['MaxOrderShare']:.0%}")
        tags.append(TAG_DOMINANT)
    met = (f"订单≥{FREQ_MIN_ORDERS}、覆盖≥{FREQ_MIN_QUARTERS}个季度、"
           f"最大单笔<{SINGLE_ORDER_SHARE:.0%}")
    if r["Core"]:
        if not tags:
            return SEG_REPEAT, met, ""
        return SEG_LUMPY, "；".join(why), "、".join(tags)
    if not tags:
        return SEG_TAIL_REPEAT, met, ""
    return SEG_TAIL_OTHER, "；".join(why), "、".join(tags)


def concentration(t):
    """Compute top-N shares and other concentration measures.

    Top-N shares are checked against the cumulative column; results
    go to ``CHECKS``.

    Args:
        t (pandas.DataFrame): Output of ``customer_table``, sorted by
            sales descending.

    Returns:
        pandas.DataFrame: One row per metric with value and note.
    """
    act = t[t["Sales"] > 0]
    total = act["Sales"].sum()
    rows = []
    for n in TOP_NS:
        top = act.nlargest(n, "Sales")
        share = top["Sales"].sum() / total
        rows.append({"指标": f"前{n}大客户销售额占比", "数值": share,
                     "说明": "、".join(top.index)})
        check(f"前{n}大客户占比（nlargest 独立计算 vs 累计列）", share, act["CumShare"].iloc[n - 1])
    for thr in [0.5, 0.8]:
        n = int((act["CumShare"].shift(fill_value=0) < thr).sum())
        rows.append({"指标": f"达到{thr:.0%}销售额所需客户数", "数值": n,
                     "说明": f"占有订单客户的 {n / len(act):.1%}"})
    hhi = (act["Share"] ** 2).sum()
    rows += [
        {"指标": "有订单客户数", "数值": len(act), "说明": f"Customers 表共 {len(t)} 个客户"},
        {"指标": "前20%客户（按人数）销售额占比", "数值":
            act["Sales"].head(int(np.ceil(0.2 * len(act)))).sum() / total,
         "说明": f"前 {int(np.ceil(0.2 * len(act)))} 个客户"},
        {"指标": "HHI（客户销售额占比平方和）", "数值": hhi, "说明": "越接近 0 越分散"},
        {"指标": "等效客户数（1/HHI）", "数值": 1 / hhi, "说明": "相当于多少个同等规模客户"},
        {"指标": f"{YEAR}年折后销售额合计", "数值": total, "说明": "不含运费，未标注币种"},
    ]
    return pd.DataFrame(rows)


def segment_summary(t):
    """Summarise customers, sales and order behaviour per segment.

    Total checks are appended to ``CHECKS``.

    Args:
        t (pandas.DataFrame): Customer table.

    Returns:
        pandas.DataFrame: One row per segment, with shares of company
            sales and, for head segments, of head-customer sales.
    """
    order = [SEG_REPEAT, SEG_LUMPY, SEG_TAIL_REPEAT, SEG_TAIL_OTHER, SEG_NONE]
    s = t.groupby("Segment").agg(
        客户数=("Sales", "size"), 销售额=("Sales", "sum"), 订单数=("Orders", "sum"),
        客户中位订单数=("Orders", "median"), 客户中位最大单笔占比=("MaxOrderShare", "median"))
    core_n, core_sales = int(t["Core"].sum()), t.loc[t["Core"], "Sales"].sum()
    s["占公司全年销售额"] = s["销售额"] / t["Sales"].sum()
    s[f"占前{core_n}名客户销售额"] = np.where(s.index.isin([SEG_REPEAT, SEG_LUMPY]),
                                        s["销售额"] / core_sales, np.nan)
    s["平均客单价"] = s["销售额"] / s["订单数"].replace(0, np.nan)
    s = s.reindex([x for x in order if x in s.index])
    check("各分组销售额之和 = 全年总额", t["Sales"].sum(), s["销售额"].sum())
    check("各分组客户数之和 = 客户总数", len(t), s["客户数"].sum())
    check(f"前{core_n}名两组销售额之和 = 前{core_n}名销售额", core_sales,
          s.loc[[SEG_REPEAT, SEG_LUMPY], "销售额"].sum())
    return s


def tag_summary(t):
    """Break down head customers missing the repeat rule by unmet rule.

    Tags overlap: one customer can miss several rules, so per-tag rows
    do not add up; the combination rows do (checked in ``CHECKS``).

    Args:
        t (pandas.DataFrame): Customer table.

    Returns:
        pandas.DataFrame: Rows per single tag and per exact tag
            combination, with customers, sales and shares.
    """
    m = t[t["Segment"] == SEG_LUMPY]
    total, core_sales = t["Sales"].sum(), t.loc[t["Core"], "Sales"].sum()
    core_col = f"占前{int(t['Core'].sum())}名客户销售额"
    groups = [("单项标注（可重叠）", tag, m[m["RuleTags"].str.contains(tag)])
              for tag in [TAG_LOW_FREQ, TAG_FEW_QUARTERS, TAG_DOMINANT]]
    groups += [("精确组合（互斥）", combo, g) for combo, g in m.groupby("RuleTags")]
    rows = [{"类型": kind, "标注": tag, "客户数": len(g), "客户": "、".join(g.index),
             "销售额": g["Sales"].sum(), "占公司全年销售额": g["Sales"].sum() / total,
             core_col: g["Sales"].sum() / core_sales} for kind, tag, g in groups]
    out = pd.DataFrame(rows)
    combos = out[out["类型"] == "精确组合（互斥）"]
    check("未满足规则的头部客户：互斥组合销售额之和 = 该组销售额", m["Sales"].sum(),
          combos["销售额"].sum())
    return out


def threshold_sensitivity(t):
    """Count head customers meeting the repeat rule at other thresholds.

    Args:
        t (pandas.DataFrame): Customer table.

    Returns:
        pandas.DataFrame: Repeat-buyer count and sales shares per
            (min orders, min quarters) pair, head customers only.
    """
    core = t[t["Core"]]
    rows = []
    for mo in [5, 6, 7]:
        for mq in [3, 4]:
            rep = core[(core["Orders"] >= mo) & (core["ActiveQuarters"] >= mq)
                       & (core["MaxOrderShare"] < SINGLE_ORDER_SHARE)]
            rows.append({"最少订单数": mo, "最少季度数": mq,
                         f"前{len(core)}名中满足持续购买规则的客户数": len(rep),
                         "其销售额占公司全年销售额": rep["Sales"].sum() / t["Sales"].sum(),
                         f"其销售额占前{len(core)}名客户销售额": rep["Sales"].sum() / core["Sales"].sum()})
    return pd.DataFrame(rows)


def display_table(t):
    """Build the Chinese-labelled, rounded customer table.

    Args:
        t (pandas.DataFrame): Customer table.

    Returns:
        pandas.DataFrame: Rounded table for CSV output.
    """
    def pct(x, d=1):
        """Format a ratio as a percentage.

        Args:
            x (float): Ratio; NaN allowed.
            d (int): Decimal places.

        Returns:
            str: e.g. "9.9%", or "不适用" for NaN.
        """
        return NA if pd.isna(x) else f"{x * 100:.{d}f}%"

    d = pd.DataFrame(index=t.index)
    d["排名"] = t["Rank"].map(lambda x: "" if pd.isna(x) else int(x))
    d["公司名称"] = t["CompanyName"]
    d["国家"] = t["Country"]
    d["折后销售额"] = t["Sales"].round(2)
    d["公司内部销售额占比"] = t["Share"].map(pct)
    d["累计占比"] = t["CumShare"].map(pct)
    d["订单数"] = t["Orders"].astype(int)
    d["客单价"] = t["AOV"].round(2)
    d["最大单笔订单销售额"] = t["MaxOrderSales"].round(2)
    d["最大单笔占该客户销售额"] = t["MaxOrderShare"].map(lambda x: pct(x, 0))
    d["有订单的月份数"] = t["ActiveMonths"].astype(int)
    d["有订单的季度数"] = t["ActiveQuarters"].astype(int)
    d["年内首单日期"] = t["FirstOrder"].dt.strftime("%Y-%m-%d").fillna("")
    d["年内末单日期"] = t["LastOrder"].dt.strftime("%Y-%m-%d").fillna("")
    d[f"属于累计贡献约80%销售额的前{int(t['Core'].sum())}名客户"] = t["Core"].map(
        {True: "是", False: "否"})
    d["购买模式分组"] = t["Segment"]
    d["未满足的规则"] = t["RuleTags"]
    d["分组依据"] = t["SegmentReason"]
    d.index.name = "CustomerID"
    return d


def plot_pareto(t, lang="zh"):
    """Draw sorted customer sales above and cumulative share below.

    The cumulative curve gets its own panel instead of a second y-axis.
    The x-axis shows customer ranks, with the top three named; bars of
    head customers that miss the repeat rule are hatched as well as
    coloured.

    Args:
        t (pandas.DataFrame): Customer table, sorted by sales.
        lang (str): Chart language, a key of ``CHART_TEXT``; "en"
            adds an "_en" suffix to the file name.

    Returns:
        pathlib.Path: The PNG written to ``OUT``.
    """
    plt.rcParams["font.sans-serif"] = CJK_FONTS
    plt.rcParams["axes.unicode_minus"] = False
    ink, ink2, muted, grid, base_c, surf = "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#c3c2b7", "#fcfcfb"
    colors = {SEG_REPEAT: "#2a78d6", SEG_LUMPY: "#eb6834",
              SEG_TAIL_REPEAT: "#c3c2b7", SEG_TAIL_OTHER: "#c3c2b7"}

    a = t[t["Sales"] > 0]
    x = np.arange(1, len(a) + 1)
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(16, 9.5), sharex=True,
                                   gridspec_kw={"height_ratios": [1.5, 1]})
    fig.patch.set_facecolor(surf)
    # Hatch the "misses the rule" bars so the groups differ beyond colour.
    lumpy = (a["Segment"] == SEG_LUMPY).to_numpy()
    ax1.bar(x[~lumpy], a["Sales"][~lumpy], width=0.8, color=a["Segment"][~lumpy].map(colors))
    ax1.bar(x[lumpy], a["Sales"][lumpy], width=0.8, color=colors[SEG_LUMPY], hatch="//",
            edgecolor=surf, linewidth=0)
    n_core = int(a["Core"].sum())
    tx = CHART_TEXT[lang]
    kw = {"n": n_core, "n1": n_core + 1, "year": YEAR, "count": len(a), "mo": FREQ_MIN_ORDERS,
          "mq": FREQ_MIN_QUARTERS, "share": f"{SINGLE_ORDER_SHARE:.0%}",
          "tags": f"{TAG_LOW_FREQ}/{TAG_FEW_QUARTERS}/{TAG_DOMINANT}"}
    handles = [matplotlib.patches.Patch(facecolor=colors[seg], edgecolor=surf, hatch=hatch,
                                        label=tx[key].format(**kw))
               for seg, key, hatch in [(SEG_REPEAT, "repeat", ""), (SEG_LUMPY, "lumpy", "//"),
                                       (SEG_TAIL_OTHER, "tail", "")]]
    ax1.legend(handles=handles, loc="upper right", frameon=False, labelcolor=ink2, fontsize=10,
               title=tx["rule"].format(**kw), title_fontsize=9, alignment="left")
    ax1.set_title(tx["bars"].format(**kw), loc="left", color=ink, fontsize=12)
    for i in range(3):
        ax1.annotate(tx["first"].format(a.index[i], a["Sales"].iloc[i]), (x[i], a["Sales"].iloc[i]),
                     xytext=(10, -4 - 2 * i), textcoords="offset points", fontsize=9.5, color=ink2)

    ax2.plot(x, a["CumShare"] * 100, color="#2a78d6", lw=2)
    ax2.axhline(80, color=base_c, lw=1, ls="--")
    ax2.axhline(50, color=base_c, lw=1, ls="--")
    core_n = int(a["Core"].sum())
    half_n = int((a["CumShare"].shift(fill_value=0) < 0.5).sum())
    for n in TOP_NS + [half_n, core_n]:
        y = a["CumShare"].iloc[n - 1] * 100
        ax2.plot(n, y, "o", ms=7, color="#2a78d6", mec=surf, mew=2)
        lab = (tx["top"] if n in TOP_NS else tx["cum"]).format(n=n, y=y)
        off = (8, -14) if n in TOP_NS else (-8, 8)
        ax2.annotate(lab, (n, y), xytext=off, textcoords="offset points", fontsize=9,
                     color=ink2, ha="left" if n in TOP_NS else "right")
    ax2.set_ylim(0, 105)
    ax2.set_title(tx["cumtitle"], loc="left", color=ink, fontsize=12)
    ax2.text(len(a), 81.5, "80%", ha="right", fontsize=8, color=muted)
    ax2.text(len(a), 51.5, "50%", ha="right", fontsize=8, color=muted)

    for ax in (ax1, ax2):
        ax.set_facecolor(surf)
        ax.grid(axis="y", color=grid, lw=0.6)
        ax.set_axisbelow(True)
        for s in ("top", "right", "left"):
            ax.spines[s].set_visible(False)
        ax.spines["bottom"].set_color(base_c)
        ax.tick_params(colors=muted, labelsize=9, length=0)
    ax1.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:,.0f}"))
    # Rank ticks at the marked thresholds plus every 10th rank; customer
    # names are left to the table to keep the axis readable.
    ticks = {1, 5, 10, half_n, n_core, len(a)} | set(range(20, len(a), 10))
    ax2.set_xticks(sorted(t for t in ticks if all(abs(t - m) > 2 for m in (half_n, n_core) if m != t)))
    ax2.tick_params(axis="x", labelcolor=ink2, labelsize=9)
    ax2.set_xlim(0.3, len(a) + 0.7)
    ax2.set_xlabel(tx["xlabel"].format(**kw), color=muted)
    fig.suptitle(tx["title"].format(**kw), x=0.01, ha="left", fontsize=14, color=ink)
    fig.tight_layout(rect=(0, 0, 1, 0.97))
    path = OUT / f"q2_customer_pareto{tx['suffix']}.png"
    fig.savefig(path, dpi=150, facecolor=surf)
    plt.close(fig)
    return path


def spot_check(cid, lines, t):
    """Trace one customer's 1997 figures back to raw lines.

    Writes the customer's lines as CSV to ``OUT`` and appends the
    comparisons to ``CHECKS``.

    Args:
        cid (str): CustomerID to trace; must have 1997 orders.
        lines (pandas.DataFrame): First output of ``year_orders``.
        t (pandas.DataFrame): Customer table.

    Returns:
        str: Plain-text walkthrough of the check.
    """
    d = lines[lines["CustomerID"] == cid][["OrderID", "OrderDate", "ProductID", "UnitPrice",
                                           "Quantity", "Discount", "Sales"]]
    d = d.sort_values(["OrderDate", "OrderID", "ProductID"])
    d.to_csv(OUT / f"spotcheck_{cid}_lines.csv", index=False, encoding="utf-8-sig")
    po = d.groupby(["OrderID", "OrderDate"], as_index=False).agg(Lines=("ProductID", "size"),
                                                                 Sales=("Sales", "sum"))
    po["ShareOfCustomer"] = po["Sales"] / po["Sales"].sum()
    r = t.loc[cid]
    s, n = po["Sales"].sum(), po["OrderID"].nunique()
    check(f"抽查 {cid} 销售额", s, r["Sales"])
    check(f"抽查 {cid} 订单数", n, r["Orders"])
    check(f"抽查 {cid} 最大单笔占比", po["ShareOfCustomer"].max(), r["MaxOrderShare"])
    fmt = lambda v: f"{v:.6f}".rstrip("0").rstrip(".")
    return "\n".join([
        f"核验客户：{cid}（{r['CompanyName']}，{r['Country']}）",
        f"步骤 1  Orders 表：CustomerID = {cid}，OrderDate 在 {START.date()} 至 {END.date()}，共 {n} 张订单。",
        "步骤 2  Orders Details 表中这些订单的明细，Sales = UnitPrice×Quantity×(1−Discount)：",
        d.to_string(index=False, float_format=fmt),
        "\n步骤 3  按订单汇总（ShareOfCustomer = 该订单占此客户全年销售额）：",
        po.to_string(index=False, float_format=fmt),
        f"\n步骤 4  汇总：销售额={s:.6f}  订单数={n}  客单价={s / n:.6f}  最大单笔占比={po['ShareOfCustomer'].max():.4f}"
        f"  有订单季度数={po['OrderDate'].dt.quarter.nunique()}",
        f"        客户表：销售额={r['Sales']:.6f}  订单数={int(r['Orders'])}  客单价={r['AOV']:.6f}  "
        f"最大单笔占比={r['MaxOrderShare']:.4f}  季度数={int(r['ActiveQuarters'])}",
        f"        分组：{r['Segment']}（{r['SegmentReason']}）",
        f"        公司内部销售额占比 = {s:.6f} / {t['Sales'].sum():.6f} = {r['Share']:.4%}",
    ])


def main():
    """Run Q2, write all outputs to ``OUT`` and print a summary.

    The first command-line argument, if given, names the spot-check
    CustomerID (default "RATTC").

    Args:
        None.

    Returns:
        None.
    """
    sys.stdout.reconfigure(encoding="utf-8")
    pd.set_option("display.width", 250)
    pd.set_option("display.max_columns", 40)
    pd.set_option("display.max_rows", 120)
    OUT.mkdir(parents=True, exist_ok=True)
    cid =sys.argv[1] if len(sys.argv) > 1 else "RATTC"

    det, ords, cus = load()
    lines, per_order = year_orders(det, ords)
    raw_total = det.loc[det["OrderID"].isin(
        ords.loc[(ords["OrderDate"] >= START) & (ords["OrderDate"] <= END), "OrderID"]), "Sales"].sum()
    t = customer_table(per_order, cus, ords)
    check("客户销售额合计 = 原始明细直接筛选的全年总额", raw_total, t["Sales"].sum())
    conc = concentration(t)
    segs = segment_summary(t)
    tags = tag_summary(t)
    sens = threshold_sensitivity(t)
    table = display_table(t)
    chart = plot_pareto(t)
    plot_pareto(t, "en")
    spot = spot_check(cid, lines, t)

    table.to_csv(OUT / "q2_customer_table.csv", encoding="utf-8-sig")
    t.to_csv(OUT / "q2_customer_raw_precision.csv", encoding="utf-8-sig")
    conc.to_csv(OUT / "q2_concentration_summary.csv", index=False, encoding="utf-8-sig")
    segs.to_csv(OUT / "q2_segment_summary.csv", encoding="utf-8-sig")
    tags.to_csv(OUT / "q2_unmet_rule_breakdown.csv", index=False, encoding="utf-8-sig")
    sens.to_csv(OUT / "q2_threshold_sensitivity.csv", index=False, encoding="utf-8-sig")
    per_order.sort_values(["CustomerID", "OrderDate"]).to_csv(
        OUT / "q2_order_sales_1997.csv", index=False, encoding="utf-8-sig")
    checks = pd.DataFrame(CHECKS)
    checks.to_csv(OUT / "q2_validation.csv", index=False, encoding="utf-8-sig")
    (OUT / f"spotcheck_{cid}.txt").write_text(spot, encoding="utf-8")

    print("== 集中度 ==")
    print(conc.to_string(index=False))
    print("\n== 分组汇总 ==")
    print(segs.round(3).to_string())
    print("\n== 未满足持续购买规则的头部客户：按未满足规则拆分 ==")
    print(tags.round(4).to_string(index=False))
    print("\n== 阈值敏感性（仅累计贡献约80%销售额的头部客户）==")
    print(sens.round(3).to_string(index=False))
    print("\n== 客户表 ==")
    print(table.to_string())
    print("\n== 验证 ==")
    print(checks.to_string(index=False))
    print(f"\n全部通过: {checks['通过'].all()}")
    print(f"\n图表: {chart}")
    print("\n" + spot)


if __name__ == "__main__":
    main()
