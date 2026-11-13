"""Q3: 1997 order-level shipping time by shipper and ship-to country.

Writes tables, checks, a spot-check and charts to outputs/q3_shipping/.
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from inspect_northwind import CJK_FONTS, XLSX, load_workbook

OUT = Path(__file__).with_name("outputs") / "q3_shipping"
YEAR = 1997
START, END = pd.Timestamp(f"{YEAR}-01-01"), pd.Timestamp(f"{YEAR}-12-31")
SMALL_N = 10
# Review threshold chosen for this analysis, not a business service standard.
REVIEW_DAYS = 14
EXCEL_EPOCH = pd.Timestamp("1899-12-30")
SMALL = "小样本"
# Chart text per language; "en" charts are written with an "_en" suffix.
CHART_TEXT = {
    "zh": {"suffix": "", "ship_label": "{s}（n={n}，中位 {m:g} 天，P90 {p:.1f} 天）",
           "xdays": "发货耗时（日历天，ShippedDate − OrderDate）",
           "ecdf": "累计分布：在 X 天内发货的订单比例（%）",
           "ecdf_y": "已发货订单占比（%）", "review": "{} 天（分析排查阈值）",
           "ship_title": "{year} 年发货耗时累计分布：按承运商（ShipVia）",
           "ship_note": "注：发货耗时包含内部处理与等待时间，组间差异不能归因于承运商；"
                        "数据无送达日期。中位数接近，但 United Package 在约 7–25 天区间的累计发货比例较低。",
           "row": "n={n}  中位 {m:g}  P90 {p:.1f}  >14天 {o}/{shipped}  晚于要求 {late}/{shipped}",
           "small": "  小样本", "small_group": "以下为小样本国家（<{} 单），仅参考",
           "dot": "订单（≥10 单的国家）", "dot_small": "订单（小样本 <10 单）",
           "late": "发货晚于要求日期的订单", "median": "中位数", "p90": "P90",
           "cty_title": "{year} 年各收货国家（ShipCountry）订单发货耗时：每个点是一张订单，"
                        "按耗时 >14 天订单数排序",
           "cty_note": "注：发货耗时包含内部处理与等待时间；数据无送达日期，不能分析准时送达。",
           "legend_cols": 5},
    "en": {"suffix": "_en", "ship_label": "{s} (n={n}, median {m:g} d, P90 {p:.1f} d)",
           "xdays": "Shipping time (calendar days, ShippedDate − OrderDate)",
           "ecdf": "Share of orders shipped within X days of the order date",
           "ecdf_y": "Orders shipped (%)", "review": "{} days (review threshold)",
           "ship_title": "Order-to-shipment time by shipper (ShipVia), {year} orders",
           "ship_note": "Note: shipping time = ShippedDate − OrderDate. It includes internal handling and waiting, so "
                        "it is not delivery or carrier transit time,\nand differences cannot be attributed to the "
                        "shipper. Medians are close; United Package's line is lower between about day 7 and day 25.",
           "row": "n={n}  median {m:g}  P90 {p:.1f}  >14 d {o}/{shipped}  late {late}/{shipped}",
           "small": "  small sample", "small_group": "Below: small samples (<{} orders), reference only",
           "dot": "Order (country with ≥10 orders)", "dot_small": "Order (small sample, <10)",
           "late": "Shipped after RequiredDate", "median": "Median", "p90": "P90",
           "cty_title": "Order-to-shipment time of each {year} order by ship-to country (one dot per order; "
                        "sorted by orders over 14 days)",
           "cty_note": "Note: shipping time includes internal handling and waiting; there is no delivery "
                       "date, so on-time delivery cannot be measured.",
           "legend_cols": 3},
}

CHECKS = []


def check(name, expected, actual, tol=1e-9):
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


def load_orders():
    """Load 1997 orders with shipper names, shipping time and lateness.

    Args:
        None.

    Returns:
        tuple[pandas.DataFrame, pandas.DataFrame]: 1997 orders (one row
            per OrderID) with ``Shipper``, ``ShipDays`` (calendar days,
            NaN if unshipped), ``AllowedDays`` and ``Late`` (1.0/0.0,
            NaN if unshipped); and the full typed Orders table.
    """
    sheets = load_workbook(XLSX)
    ords, shp = sheets["Orders"].copy(), sheets["Shippers"].copy()
    ords["OrderID"] = ords["OrderID"].astype("int64")
    ords["ShipVia"] = ords["ShipVia"].astype("int64")
    shp["ShipperID"] = shp["ShipperID"].astype("int64")
    for c in ["OrderDate", "RequiredDate", "ShippedDate"]:
        ords[c] = pd.to_datetime(ords[c])

    o = ords[(ords["OrderDate"] >= START) & (ords["OrderDate"] <= END)].copy()
    o = o.merge(shp[["ShipperID", "CompanyName"]].rename(
        columns={"ShipperID": "ShipVia", "CompanyName": "Shipper"}),
        on="ShipVia", how="left", validate="many_to_one")
    o["Shipper"] = o["ShipVia"].astype(str) + " " + o["Shipper"]
    # NaN stays NaN for unshipped orders; never filled with 0.
    o["ShipDays"] = (o["ShippedDate"] - o["OrderDate"]).dt.days
    o["AllowedDays"] = (o["RequiredDate"] - o["OrderDate"]).dt.days
    o["Late"] = np.where(o["ShippedDate"].notna(), o["ShippedDate"] > o["RequiredDate"], np.nan)
    return o, ords


def validate(o, ords):
    """Run row-count, date and duration checks into ``CHECKS``.

    Args:
        o (pandas.DataFrame): 1997 orders from ``load_orders``.
        ords (pandas.DataFrame): Full Orders table.

    Returns:
        dict[str, int]: ``missing_shipped``, ``negative`` and
            ``zero_day`` order counts.
    """
    ref = ords[(ords["OrderDate"] >= START) & (ords["OrderDate"] <= END)]
    check(f"{YEAR} 订单数 = Orders 表按 OrderDate 筛选的行数", len(ref), len(o))
    check(f"{YEAR} OrderID 无重复", o["OrderID"].nunique(), len(o))
    check("关联承运商后行数不变", len(ref), len(o))
    check("ShipVia 关联不上 Shippers 的订单数", 0, o["Shipper"].isna().sum())
    for c in ["OrderDate", "RequiredDate"]:
        check(f"{c} 缺失数", 0, o[c].isna().sum())
    times = sum(((o[c].dt.normalize() != o[c]) & o[c].notna()).sum()
                for c in ["OrderDate", "RequiredDate", "ShippedDate"])
    check("日期含时分秒的单元格数（应为 0，耗时为整日历天）", 0, times)
    neg = int((o["ShipDays"] < 0).sum())
    check("负发货耗时订单数", 0, neg)
    check("发货日早于下单日（同上，独立判断）", 0, (o["ShippedDate"] < o["OrderDate"]).sum())
    check("RequiredDate 早于 OrderDate 的订单数", 0, (o["RequiredDate"] < o["OrderDate"]).sum())
    miss = int(o["ShippedDate"].isna().sum())
    check("缺失发货日期的订单 ShipDays 为空而非 0", miss, o["ShipDays"].isna().sum())
    return {"missing_shipped": miss, "negative": neg, "zero_day": int((o["ShipDays"] == 0).sum())}


def group_stats(o, by, label):
    """Summarise shipping time and lateness per group.

    Percentiles use numpy's default linear interpolation over shipped
    orders only.

    Group sums are checked against totals into ``CHECKS``.

    Args:
        o (pandas.DataFrame): 1997 orders.
        by (str): Column to group on.
        label (str): Chinese name of the grouping; becomes the index
            name and appears in check names.

    Returns:
        pandas.DataFrame: One row per group plus a "全部" row, with
            unrounded counts, percentiles, lateness and
            ``SmallSample`` ("小样本" when under 10 orders).
    """
    def stats(g):
        """Compute shipping-time and lateness statistics for one group.

        Args:
            g (pandas.DataFrame): Orders in the group.

        Returns:
            pandas.Series: Counts, median, P90, mean, max, orders over
                ``REVIEW_DAYS``, late count and rate, 14-day windows.
        """
        s =g["ShipDays"].dropna()
        late = g.loc[g["ShippedDate"].notna(), "Late"].astype(bool)
        return pd.Series({
            "Orders": len(g),
            "Shipped": len(s),
            "MissingShipped": g["ShippedDate"].isna().sum(),
            "Median": s.median() if len(s) else np.nan,
            "P90": np.percentile(s, 90) if len(s) else np.nan,
            "Mean": s.mean() if len(s) else np.nan,
            "Max": s.max() if len(s) else np.nan,
            "OverReview": (s > REVIEW_DAYS).sum(),
            "LateCount": late.sum(),
            "LateRate": late.mean() if len(late) else np.nan,
            "Window14Count": (g["AllowedDays"] == 14).sum(),
        })

    t = o.groupby(by).apply(stats, include_groups=False)
    t.loc["全部"] = stats(o)
    t.index.name = label
    t["SmallSample"] = np.where((t["Orders"] < SMALL_N) & (t.index != "全部"), SMALL, "")
    check(f"按{label}：各组订单数之和 = 总订单数", len(o), t.drop("全部")["Orders"].sum())
    check(f"按{label}：各组延迟单数之和 = 总延迟单数", t.loc["全部", "LateCount"],
          t.drop("全部")["LateCount"].sum())
    return t


def display(t, label):
    """Format a group table with explicit denominators.

    Args:
        t (pandas.DataFrame): Output of ``group_stats``.
        label (str): Chinese name of the grouping; not used.

    Returns:
        pandas.DataFrame: Chinese-labelled table sorted by median then
            P90 descending, with the "全部" row last.
    """
    d = pd.DataFrame(index=t.index)
    d["订单数"] = t["Orders"].astype(int)
    d["已发货订单数"] = t["Shipped"].astype(int)
    d["缺失发货日期订单数"] = t["MissingShipped"].astype(int)
    d["发货耗时中位数（天）"] = t["Median"]
    d["发货耗时P90（天）"] = t["P90"].round(1)
    d["平均值（天，仅参考）"] = t["Mean"].round(1)
    d["最长（天）"] = t["Max"].astype("Int64")
    d[f"耗时>{REVIEW_DAYS}天订单（分析排查阈值，非服务标准）"] = (
        t["OverReview"].astype(int).astype(str) + "/" + t["Shipped"].astype(int).astype(str))
    d["发货晚于要求日期订单数"] = t["LateCount"].astype(int)
    d["发货晚于要求日期比例"] = [
        f"{r.LateRate:.1%}（{int(r.LateCount)}/{int(r.Shipped)}）" for r in t.itertuples()]
    d["要求期限为14天的订单"] = (t["Window14Count"].astype(int).astype(str) + "/"
                         + t["Orders"].astype(int).astype(str))
    d["样本提示"] = t["SmallSample"]
    body = d.drop("全部").sort_values(["发货耗时中位数（天）", "发货耗时P90（天）"], ascending=False)
    return pd.concat([body, d.loc[["全部"]]])


def ecdf_table(o):
    """Tabulate the share of orders shipped within each day count.

    Args:
        o (pandas.DataFrame): 1997 orders.

    Returns:
        pandas.DataFrame: Rows are day counts 1..max; one column per
            shipper (% shipped within that many days) and its gap in
            points to the best of the first three shipper columns.
    """
    days = range(1, int(o["ShipDays"].max()) + 1)
    t = pd.DataFrame({s: [(g["ShipDays"].dropna() <= d).mean() * 100 for d in days]
                      for s, g in o.groupby("Shipper")}, index=days)
    t.index.name = "发货耗时≤X天"
    for s in list(t.columns):
        t[f"{s} 与最高者差（百分点）"] = t[s] - t[[c for c in t.columns[:3]]].max(axis=1)
    return t.round(1)


def setup_style():
    """Set fonts from ``CJK_FONTS`` and return the chart colours.

    Args:
        None.

    Returns:
        dict[str, str | list[str]]: Named hex colours; ``"s"`` holds
            the three shipper series colours.
    """
    plt.rcParams["font.sans-serif"] = CJK_FONTS
    plt.rcParams["axes.unicode_minus"] = False
    return {"ink": "#0b0b0b", "ink2": "#52514e", "muted": "#898781", "grid": "#e1e0d9",
            "base": "#c3c2b7", "surf": "#fcfcfb", "s": ["#2a78d6", "#eb6834", "#1baf7a"],
            "dot": "#2a78d6", "dot_small": "#c3c2b7", "late": "#e34948"}


def style_axes(ax, c, grid_axis="x"):
    """Apply the recessive grid and spine style to one axes.

    Args:
        ax (matplotlib.axes.Axes): Axes to style.
        c (dict): Colours from ``setup_style``.
        grid_axis (str): Axis to draw gridlines on.

    Returns:
        None.
    """
    ax.set_facecolor(c["surf"])
    ax.grid(axis=grid_axis, color=c["grid"], lw=0.6)
    ax.set_axisbelow(True)
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.spines["bottom"].set_color(c["base"])
    ax.tick_params(colors=c["muted"], labelsize=9, length=0)


def plot_shippers(o, t, lang="zh"):
    """Draw the per-shipper cumulative distribution of shipping days.

    A dashed vertical line marks the ``REVIEW_DAYS`` review threshold.
    Line styles repeat the colour coding.

    Args:
        o (pandas.DataFrame): 1997 orders.
        t (pandas.DataFrame): Shipper stats from ``group_stats``.
        lang (str): Chart language, a key of ``CHART_TEXT``; "en"
            adds an "_en" suffix to the file name.

    Returns:
        pathlib.Path: The PNG written to ``OUT``.
    """
    c = setup_style()
    tx = CHART_TEXT[lang]
    shippers = sorted(o["Shipper"].unique())
    styles = ["-", "--", ":"]
    fig, a1 = plt.subplots(figsize=(13, 6.2))
    fig.patch.set_facecolor(c["surf"])
    xmax = int(o["ShipDays"].max()) + 1
    for i, s in enumerate(shippers):
        d = np.sort(o.loc[o["Shipper"] == s, "ShipDays"].dropna().to_numpy())
        y = np.arange(1, len(d) + 1) / len(d) * 100
        r = t.loc[s]
        a1.step(d, y, where="post", color=c["s"][i], lw=2.4, ls=styles[i % 3],
                label=tx["ship_label"].format(s=s, n=int(r.Shipped), m=r.Median, p=r.P90))
    a1.axhline(50, color=c["base"], lw=1, ls="--")
    a1.axhline(90, color=c["base"], lw=1, ls="--")
    a1.axvline(REVIEW_DAYS, color=c["muted"], lw=1, ls="-.")
    a1.text(REVIEW_DAYS + 0.3, 4, tx["review"].format(REVIEW_DAYS), fontsize=9, color=c["muted"])
    a1.text(xmax, 51, "50%", ha="right", fontsize=8, color=c["muted"])
    a1.text(xmax, 91, "90%", ha="right", fontsize=8, color=c["muted"])
    a1.set_xlim(0, xmax)
    a1.set_ylim(0, 102)
    a1.set_xlabel(tx["xdays"], color=c["muted"])
    a1.set_title(tx["ecdf"], loc="left", color=c["ink"], fontsize=12)
    a1.set_ylabel(tx["ecdf_y"], color=c["muted"])
    a1.legend(loc="lower right", frameon=False, labelcolor=c["ink2"], fontsize=10)
    style_axes(a1, c, "both")
    fig.suptitle(tx["ship_title"].format(year=YEAR), x=0.01, ha="left",
                 fontsize=14, color=c["ink"])
    fig.text(0.01, 0.01, tx["ship_note"], fontsize=9, color=c["muted"])
    fig.tight_layout(rect=(0, 0.06, 1, 0.95))
    path = OUT / f"q3_shipping_by_shipper{tx['suffix']}.png"
    fig.savefig(path, dpi=150, facecolor=c["surf"])
    plt.close(fig)
    return path


def plot_countries(o, t, lang="zh"):
    """Plot each order's shipping time per country with median and P90.

    Countries with at least ``SMALL_N`` orders come first, sorted by
    orders over ``REVIEW_DAYS`` and then P90; small samples follow
    below a separator, sorted by order count, so their position does
    not suggest priority.

    Args:
        o (pandas.DataFrame): 1997 orders.
        t (pandas.DataFrame): Country stats from ``group_stats``.
        lang (str): Chart language, a key of ``CHART_TEXT``; "en"
            adds an "_en" suffix to the file name.

    Returns:
        pathlib.Path: The PNG written to ``OUT``.
    """
    c = setup_style()
    tx = CHART_TEXT[lang]
    rest = t.drop("全部")
    big = rest[rest["SmallSample"] != SMALL].sort_values(["OverReview", "P90"], ascending=False)
    small_rows = rest[rest["SmallSample"] == SMALL].sort_values("Orders", ascending=False)
    body = pd.concat([big, small_rows]).iloc[::-1]  # first row ends up at the top
    fig, ax = plt.subplots(figsize=(13, 10))
    fig.patch.set_facecolor(c["surf"])
    rng = np.random.default_rng(0)
    ax.axhline(len(small_rows) - 0.5, color=c["base"], lw=1)
    ax.text(38.5, len(small_rows) - 0.75, tx["small_group"].format(SMALL_N), ha="right", va="top",
            fontsize=9, color=c["muted"])
    for yi, (country, r) in enumerate(body.iterrows()):
        small = r["SmallSample"] == SMALL
        g = o[o["ShipCountry"] == country].dropna(subset=["ShipDays"])
        jitter = rng.uniform(-0.22, 0.22, len(g))
        col = np.where(g["Late"].astype(bool), c["late"], c["dot_small"] if small else c["dot"])
        ax.scatter(g["ShipDays"], yi + jitter, s=22, c=col, alpha=0.75, linewidths=0)
        ax.plot([r["Median"]] * 2, [yi - 0.36, yi + 0.36], color=c["ink"], lw=2.2)
        ax.plot([r["P90"]] * 2, [yi - 0.28, yi + 0.28], color=c["ink2"], lw=1.4, ls=(0, (2, 1.5)))
        ax.text(39.5, yi, tx["row"].format(n=int(r["Orders"]), m=r["Median"], p=r["P90"],
                                           o=int(r["OverReview"]), late=int(r["LateCount"]),
                                           shipped=int(r["Shipped"]))
                + (tx["small"] if small else ""),
                va="center", fontsize=8.5, color=c["muted"] if small else c["ink2"])
    ax.set_yticks(range(len(body)), [f"{x}" for x in body.index], color=c["ink2"])
    ax.set_xlim(0, 39)
    ax.set_ylim(-0.7, len(body) - 0.3)
    ax.set_xlabel(tx["xdays"], color=c["muted"])
    handles = [
        matplotlib.lines.Line2D([], [], marker="o", ls="", color=c["dot"], label=tx["dot"]),
        matplotlib.lines.Line2D([], [], marker="o", ls="", color=c["dot_small"], label=tx["dot_small"]),
        matplotlib.lines.Line2D([], [], marker="o", ls="", color=c["late"], label=tx["late"]),
        matplotlib.lines.Line2D([], [], color=c["ink"], lw=2.2, label=tx["median"]),
        matplotlib.lines.Line2D([], [], color=c["ink2"], lw=1.4, ls=(0, (2, 1.5)), label=tx["p90"]),
    ]
    ax.legend(handles=handles, loc="upper center", bbox_to_anchor=(0.5, -0.06), ncol=tx["legend_cols"],
              frameon=False, labelcolor=c["ink2"], fontsize=9)
    style_axes(ax, c, "x")
    ax.set_title(tx["cty_title"].format(year=YEAR), loc="left", color=c["ink"], fontsize=13)
    fig.text(0.01, 0.01, tx["cty_note"], fontsize=9, color=c["muted"])
    fig.tight_layout(rect=(0, 0.03, 0.8, 1))
    path = OUT / f"q3_shipping_by_country{tx['suffix']}.png"
    fig.savefig(path, dpi=150, facecolor=c["surf"])
    plt.close(fig)
    return path


def spot_check(oid, o):
    """Recompute one order's shipping time from Excel date serials.

    The comparisons are appended to ``CHECKS``.

    Args:
        oid (int): OrderID to check; must be a shipped 1997 order.
        o (pandas.DataFrame): 1997 orders.

    Returns:
        str: Plain-text walkthrough of the date arithmetic.
    """
    r = o.set_index("OrderID").loc[oid]
    serial = {c: (r[c] - EXCEL_EPOCH).days for c in ["OrderDate", "RequiredDate", "ShippedDate"]}
    days = serial["ShippedDate"] - serial["OrderDate"]
    allowed = serial["RequiredDate"] - serial["OrderDate"]
    check(f"抽查订单 {oid}：序列号相减 = 脚本发货耗时", days, r["ShipDays"])
    check(f"抽查订单 {oid}：晚于要求日期判断", float(serial["ShippedDate"] > serial["RequiredDate"]),
          float(r["Late"]))
    return "\n".join([
        f"抽查订单：OrderID = {oid}",
        f"  客户 {r['CustomerID']}，收货国家 {r['ShipCountry']}，承运商 ShipVia={r['ShipVia']}（{r['Shipper']}）",
        f"  OrderDate    = {r['OrderDate'].date()}  （Excel 日期序列号 {serial['OrderDate']}）",
        f"  RequiredDate = {r['RequiredDate'].date()}  （序列号 {serial['RequiredDate']}）",
        f"  ShippedDate  = {r['ShippedDate'].date()}  （序列号 {serial['ShippedDate']}）",
        f"  发货耗时 = {serial['ShippedDate']} − {serial['OrderDate']} = {days} 天；脚本结果 {r['ShipDays']:g} 天",
        f"  要求期限 = {serial['RequiredDate']} − {serial['OrderDate']} = {allowed} 天",
        f"  ShippedDate > RequiredDate？{serial['ShippedDate']} > {serial['RequiredDate']} → "
        f"{'是，计为发货晚于要求日期' if serial['ShippedDate'] > serial['RequiredDate'] else '否'}",
        "  在 Excel 中复核：Orders 表找到该 OrderID，把三个日期单元格格式改为“常规”即可看到序列号，"
        "用 ShippedDate − OrderDate 得到天数。",
    ])


def main():
    """Run Q3, write all outputs to ``OUT`` and print a summary.

    The first command-line argument, if given, is the spot-check
    OrderID; otherwise the longest late order is used.

    Args:
        None.

    Returns:
        None.
    """
    sys.stdout.reconfigure(encoding="utf-8")
    pd.set_option("display.width", 250)
    pd.set_option("display.max_columns", 30)
    OUT.mkdir(parents=True, exist_ok=True)

    o, ords = load_orders()
    info = validate(o, ords)
    oid = int(sys.argv[1]) if len(sys.argv) > 1 else int(
        o.loc[o["Late"].astype(bool)].sort_values("ShipDays", ascending=False)["OrderID"].iloc[0])
    by_ship = group_stats(o, "Shipper", "承运商")
    by_cty = group_stats(o, "ShipCountry", "收货国家")
    window = pd.crosstab(o["AllowedDays"], o["Late"].astype(bool), margins=True, margins_name="合计")
    window.columns = [{False: "未晚于要求日期", True: "晚于要求日期"}.get(c, c) for c in window.columns]
    window.index.name = "要求期限（RequiredDate − OrderDate，天）"
    spot = spot_check(oid, o)
    p1, p2 = plot_shippers(o, by_ship), plot_countries(o, by_cty)
    plot_shippers(o, by_ship, "en")
    plot_countries(o, by_cty, "en")

    ship_t, cty_t = display(by_ship, "承运商"), display(by_cty, "收货国家")
    ship_t.to_csv(OUT / "q3_by_shipper.csv", encoding="utf-8-sig")
    cty_t.to_csv(OUT / "q3_by_country.csv", encoding="utf-8-sig")
    by_ship.to_csv(OUT / "q3_by_shipper_raw.csv", encoding="utf-8-sig")
    by_cty.to_csv(OUT / "q3_by_country_raw.csv", encoding="utf-8-sig")
    window.to_csv(OUT / "q3_required_window_vs_late.csv", encoding="utf-8-sig")
    ecdf_table(o).to_csv(OUT / "q3_shipper_cumulative_share_by_day.csv", encoding="utf-8-sig")
    o[["OrderID", "CustomerID", "ShipCountry", "ShipVia", "Shipper", "OrderDate", "RequiredDate",
       "ShippedDate", "ShipDays", "AllowedDays", "Late"]].sort_values("OrderID").to_csv(
        OUT / "q3_orders_1997.csv", index=False, encoding="utf-8-sig")
    checks = pd.DataFrame(CHECKS)
    checks.to_csv(OUT / "q3_validation.csv", index=False, encoding="utf-8-sig")
    (OUT / f"spotcheck_order_{oid}.txt").write_text(spot, encoding="utf-8")

    print("== 数据检查 ==")
    print(f"1997 年订单数={len(o)}；缺失发货日期={info['missing_shipped']}；"
          f"负耗时={info['negative']}；0 天耗时={info['zero_day']}")
    print("\n== 按承运商 ==")
    print(ship_t.to_string())
    print("\n== 按收货国家 ==")
    print(cty_t.to_string())
    print("\n== 要求期限与发货晚于要求日期 ==")
    print(window.to_string())
    print("\n== 验证 ==")
    print(checks.to_string(index=False))
    print(f"\n全部通过: {checks['通过'].all()}")
    print(f"\n图表: {p1}\n      {p2}")
    print("\n" + spot)


if __name__ == "__main__":
    main()
