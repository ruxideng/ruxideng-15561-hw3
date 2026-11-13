"""Q1: compare Jan-Apr 1997 vs 1998 discounted sales by country.

Writes tables, checks, a spot-check and a chart to outputs/q1_country/.
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from inspect_northwind import CJK_FONTS, XLSX, load_workbook

OUT = Path(__file__).with_name("outputs") / "q1_country"
PERIODS = {
    "1997": (pd.Timestamp("1997-01-01"), pd.Timestamp("1997-04-30")),
    "1998": (pd.Timestamp("1998-01-01"), pd.Timestamp("1998-04-30")),
}
BASE, CUR = "1997", "1998"
NA = "不适用"
# Flags for figures that a few orders or customers can swing.
LOW_BASE_SHARE = 0.02    # base-period sales below 2% of the base total
FEW_CUSTOMERS = 2        # active customers <= 2 in either period
TOP_CUSTOMER_SHARE = 0.5  # one customer > 50% of a period's sales
# Chart text per language; "en" charts are written with an "_en" suffix.
CHART_TEXT = {
    "zh": {"suffix": "", "na": NA, "window": "{} 年 1–4 月",
           "sales": "折后销售额（按客户国家，未标注币种）",
           "change": "销售额变化金额（1998 − 1997），括号内为增长率",
           "title": "客户国家市场：1997 vs 1998 年同期（1–4 月）",
           "fmt": "{chg}（{g}）",
           "b_title": "各国销售额变化来自哪类客户：1998 vs 1997 年 1–4 月（折后销售额，未标注币种）",
           "b_both": "两期均购买客户的销售额变化", "b_cur": "仅 1998 窗口购买客户的销售额（+）",
           "b_base": "仅 1997 窗口购买客户的销售额（−）", "b_net": "国家净变化（三项之和）",
           "b_x": "对销售额变化的贡献（1998 − 1997）",
           "b_note": "注：按客户在两个 1–4 月窗口是否有订单分组；窗口内出现或未出现不等于新客户或流失客户。"},
    "en": {"suffix": "_en", "na": "n/a", "window": "Jan–Apr {}",
           "sales": "Discounted sales by customer country (no currency field)",
           "change": "Change in sales (1998 − 1997), growth in brackets",
           "title": "Customer-country markets: Jan–Apr 1997 vs 1998",
           "fmt": "{chg} ({g})",
           "b_title": "Where each country's change in sales came from: Jan–Apr 1998 vs Jan–Apr 1997 "
                      "(discounted sales, no currency field)",
           "b_both": "Change from customers who bought in both windows",
           "b_cur": "Sales from customers who bought in the 1998 window only (+)",
           "b_base": "Sales from customers who bought in the 1997 window only (−)",
           "b_net": "Net change of the country (sum of the three)",
           "b_x": "Contribution to the change in sales (1998 − 1997)",
           "b_note": "Note: customers are grouped by whether they ordered in each Jan–Apr window; appearing or "
                     "not appearing in a window is not the same as a new or lost customer."},
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


def load():
    """Load details, orders and customers with typed IDs and line sales.

    Args:
        None.

    Returns:
        tuple[pandas.DataFrame, pandas.DataFrame, pandas.DataFrame]:
            Order details with int IDs and ``Sales`` (UnitPrice *
            Quantity * (1 - Discount), full precision); orders with int
            IDs and datetime OrderDate/ShippedDate; customers as read.
    """
    sheets = load_workbook(XLSX)
    det = sheets["Orders Details"].copy()
    ords = sheets["Orders"].copy()
    cus = sheets["Customers"].copy()
    for df, cols in [(det, ["OrderID", "ProductID", "Quantity"]),
                     (ords, ["OrderID", "EmployeeID", "ShipVia"])]:
        for c in cols:
            df[c] = df[c].astype("int64")
    ords["OrderDate"] = pd.to_datetime(ords["OrderDate"])
    ords["ShippedDate"] = pd.to_datetime(ords["ShippedDate"])
    # Full stored precision; rounding happens only for display.
    det["Sales"] = det["UnitPrice"] * det["Quantity"] * (1 - det["Discount"])
    return det, ords, cus


def period_of(dates):
    """Label each date with its Jan-Apr comparison period.

    Args:
        dates (pandas.Series): Datetime order dates.

    Returns:
        pandas.Series: "1997", "1998", or None outside both windows.
    """
    out = pd.Series(None, index=dates.index, dtype="object")
    for label, (start, end) in PERIODS.items():
        out[(dates >= start) & (dates <= end)] = label
    return out


def build_lines(det, ords, cus):
    """Join details to orders and customers and keep both windows.

    Row counts and sales before and after each join are appended to
    ``CHECKS``.

    Args:
        det (pandas.DataFrame): Order detail lines with ``Sales``.
        ords (pandas.DataFrame): Orders from ``load``.
        cus (pandas.DataFrame): Customers.

    Returns:
        pandas.DataFrame: One row per detail line in either window,
            with ``CustomerID``, ``OrderDate``, ``ShippedDate``,
            ``Country`` and ``Period`` added.
    """
    n0, s0 = len(det), det["Sales"].sum()
    j1 = det.merge(ords[["OrderID", "CustomerID", "OrderDate", "ShippedDate"]],
                   on="OrderID", how="left", validate="many_to_one")
    check("明细关联订单后行数（全部明细）", n0, len(j1))
    check("明细关联订单后销售额（全部明细）", s0, j1["Sales"].sum())
    check("关联订单后 OrderDate 为空的行数", 0, j1["OrderDate"].isna().sum())
    j2 = j1.merge(cus[["CustomerID", "Country"]], on="CustomerID",
                  how="left", validate="many_to_one")
    check("再关联客户后行数（全部明细）", n0, len(j2))
    check("再关联客户后销售额（全部明细）", s0, j2["Sales"].sum())
    check("关联客户后 Country 为空的行数", 0, j2["Country"].isna().sum())

    j2["Period"] = period_of(j2["OrderDate"])
    lines = j2[j2["Period"].notna()].copy()

    # Independent reference: filter orders by date, then pick their lines
    # from the raw details without any join.
    for p in PERIODS:
        ids = set(ords.loc[period_of(ords["OrderDate"]) == p, "OrderID"])
        raw = det[det["OrderID"].isin(ids)]
        got = lines[lines["Period"] == p]
        check(f"{p} 期明细行数：原始明细 vs 关联后", len(raw), len(got))
        check(f"{p} 期销售额：原始明细 vs 关联后", raw["Sales"].sum(), got["Sales"].sum())
    return lines


def summarise(lines, ords):
    """Aggregate sales, orders and customers per country and window.

    Country sums are checked against totals computed directly from
    ``ords`` and ``lines``; results go to ``CHECKS``.

    Args:
        lines (pandas.DataFrame): Output of ``build_lines``.
        ords (pandas.DataFrame): Orders, for reference totals.

    Returns:
        tuple[pandas.DataFrame, pandas.DataFrame]: Country table
            (per-window Sales, Orders, Customers, Lines, AOV, plus
            changes and growth; NaN growth when the base is 0), and a
            per-window totals table indexed by "1997"/"1998".
    """
    g = lines.groupby(["Country", "Period"]).agg(
        Sales=("Sales", "sum"),
        Orders=("OrderID", "nunique"),
        Customers=("CustomerID", "nunique"),
        Lines=("OrderID", "size"),
    )
    wide = g.unstack("Period")
    wide.columns = [f"{m}_{p}" for m, p in wide.columns]
    wide = wide.reindex(columns=[f"{m}_{p}" for m in ["Sales", "Orders", "Customers", "Lines"]
                                 for p in PERIODS])
    for m in ["Sales", "Orders", "Customers", "Lines"]:
        for p in PERIODS:
            wide[f"{m}_{p}"] = wide[f"{m}_{p}"].fillna(0)
    for p in PERIODS:
        wide[f"AOV_{p}"] = np.where(wide[f"Orders_{p}"] > 0,
                                    wide[f"Sales_{p}"] / wide[f"Orders_{p}"].replace(0, np.nan),
                                    np.nan)
    wide["SalesChange"] = wide[f"Sales_{CUR}"] - wide[f"Sales_{BASE}"]
    wide["SalesGrowth"] = np.where(wide[f"Sales_{BASE}"] > 0,
                                   wide["SalesChange"] / wide[f"Sales_{BASE}"].replace(0, np.nan),
                                   np.nan)
    wide["OrdersChange"] = wide[f"Orders_{CUR}"] - wide[f"Orders_{BASE}"]
    wide["CustomersChange"] = wide[f"Customers_{CUR}"] - wide[f"Customers_{BASE}"]
    wide["AOVGrowth"] = wide[f"AOV_{CUR}"] / wide[f"AOV_{BASE}"] - 1

    # Totals computed straight from orders/lines, not from the country table.
    tot = []
    for p in PERIODS:
        o = ords[period_of(ords["OrderDate"]) == p]
        lp = lines[lines["Period"] == p]
        tot.append({"Period": p, "Sales": lp["Sales"].sum(), "Orders": o["OrderID"].nunique(),
                    "Customers": o["CustomerID"].nunique(), "Lines": len(lp)})
        check(f"{p} 各国销售额之和 = 期间总额", lp["Sales"].sum(), wide[f"Sales_{p}"].sum())
        check(f"{p} 各国订单数之和 = Orders 表期间订单数", o["OrderID"].nunique(),
              wide[f"Orders_{p}"].sum())
        check(f"{p} 各国活跃客户之和 = 期间唯一客户数", o["CustomerID"].nunique(),
              wide[f"Customers_{p}"].sum())
        check(f"{p} 各国明细行之和 = 期间明细行", len(lp), wide[f"Lines_{p}"].sum())
    totals = pd.DataFrame(tot).set_index("Period")
    totals["AOV"] = totals["Sales"] / totals["Orders"]
    check("各国销售额变化之和 = 总变化", totals.loc[CUR, "Sales"] - totals.loc[BASE, "Sales"],
          wide["SalesChange"].sum())
    return wide, totals


def concentration(lines, wide, totals):
    """Add customer-concentration columns and flags to the countries.

    Args:
        lines (pandas.DataFrame): Output of ``build_lines``.
        wide (pandas.DataFrame): Country table from ``summarise``;
            concentration columns and ``Flags`` are added in place.
        totals (pandas.DataFrame): Window totals from ``summarise``.

    Returns:
        pandas.DataFrame: Sales per (Country, CustomerID) with one
            column per window and ``Change``.
    """
    cs = lines.pivot_table(index=["Country", "CustomerID"], columns="Period",
                           values="Sales", aggfunc="sum", fill_value=0)
    cs = cs.reindex(columns=list(PERIODS), fill_value=0)
    cs["Change"] = cs[CUR] - cs[BASE]
    # Sales concentration: largest customer's share of the country's sales
    # within one period.
    for p in PERIODS:
        share = cs[p] / cs.groupby("Country")[p].transform("sum").replace(0, np.nan)
        wide[f"TopCustShare_{p}"] = share.groupby("Country").max()
        wide[f"TopCust_{p}"] = share.groupby("Country").idxmax().map(
            lambda k: k[1] if isinstance(k, tuple) else None)
    # Growth-contribution concentration: largest positive mover vs the
    # country's net change and vs the sum of all customer increases.
    up = cs[cs["Change"] > 0]
    top_up = up.loc[up.groupby("Country")["Change"].idxmax()].reset_index().set_index("Country")
    gross_up = up.groupby("Country")["Change"].sum()
    top2_up = up.groupby("Country")["Change"].apply(lambda s: s.nlargest(2).sum())
    wide["TopIncCustomer"] = top_up["CustomerID"]
    wide["TopIncChange"] = top_up["Change"]
    wide["TopIncShareOfNet"] = np.where(wide["SalesChange"] > 0,
                                        wide["TopIncChange"] / wide["SalesChange"], np.nan)
    wide["TopIncShareOfGrossUp"] = wide["TopIncChange"] / gross_up
    wide["Top2IncShareOfNet"] = np.where(wide["SalesChange"] > 0,
                                         top2_up / wide["SalesChange"], np.nan)
    wide["CustomersUp"] = (cs["Change"] > 0).groupby("Country").sum()
    wide["CustomersDown"] = (cs["Change"] < 0).groupby("Country").sum()
    # Share of the country's net change explained by its single largest mover.
    biggest = cs.loc[cs.groupby("Country")["Change"].apply(lambda s: s.abs().idxmax())]
    biggest = biggest.reset_index().set_index("Country")
    wide["BiggestMoverCustomer"] = biggest["CustomerID"]
    wide["BiggestMoverChange"] = biggest["Change"]
    wide["BiggestMoverShareOfChange"] = np.where(
        wide["SalesChange"].abs() > 0, biggest["Change"] / wide["SalesChange"], np.nan)

    flags = []
    for c, r in wide.iterrows():
        f = []
        if r[f"Sales_{BASE}"] == 0:
            f.append("基期窗口无销售、本期窗口有销售")
        elif r[f"Sales_{BASE}"] < LOW_BASE_SHARE * totals.loc[BASE, "Sales"]:
            f.append("低基数")
        if r[f"Sales_{CUR}"] == 0:
            f.append("本期窗口无销售")
        if min(r[f"Customers_{BASE}"], r[f"Customers_{CUR}"]) <= FEW_CUSTOMERS:
            f.append(f"某期客户≤{FEW_CUSTOMERS}")
        if max(r[f"TopCustShare_{BASE}"] if pd.notna(r[f"TopCustShare_{BASE}"]) else 0,
               r[f"TopCustShare_{CUR}"] if pd.notna(r[f"TopCustShare_{CUR}"]) else 0) > TOP_CUSTOMER_SHARE:
            f.append("某期最大客户销售占比>50%")
        flags.append("；".join(f))
    wide["Flags"] = flags
    return cs


def customer_evidence(cs, ords, wide, countries):
    """List customer sales, change and order dates for chosen countries.

    Args:
        cs (pandas.DataFrame): Output of ``concentration``.
        ords (pandas.DataFrame): Orders, for dates outside the windows.
        wide (pandas.DataFrame): Country table, for net change.
        countries (list[str]): Countries to include; each must be in
            ``wide``.

    Returns:
        pandas.DataFrame: One row per customer with window sales,
            shares, change and order dates, sorted by country and
            change.
    """
    e = cs.loc[cs.index.get_level_values("Country").isin(countries)].reset_index()
    e["ShareOfNetChange"] = e["Change"] / e["Country"].map(wide["SalesChange"])
    for p in PERIODS:
        e[f"Share_{p}"] = e[p] / e.groupby("Country")[p].transform("sum")
    od = ords.groupby("CustomerID")["OrderDate"]
    e["LastOrderBefore1998Window"] = e["CustomerID"].map(
        ords[ords["OrderDate"] < PERIODS[CUR][0]].groupby("CustomerID")["OrderDate"].max())
    e["OrdersAfter1998Window"] = e["CustomerID"].map(
        ords[ords["OrderDate"] > PERIODS[CUR][1]].groupby("CustomerID")["OrderDate"]
        .apply(lambda s: ", ".join(d.strftime("%Y-%m-%d") for d in s)))
    e["LastOrderOverall"] = e["CustomerID"].map(od.max())
    for c in countries:
        check(f"{c} 客户变化之和 = 国家净变化", wide.loc[c, "SalesChange"],
              e.loc[e["Country"] == c, "Change"].sum())
    return e.sort_values(["Country", "Change"])


GROUPS = ["both", "only_cur", "only_base"]


def customer_bridge(lines, ords, wide):
    """Split each country's sales change by customer buying group.

    Customers are grouped by whether they ordered in each window:
    "both" (both windows), "only_cur" (1998 window only) and
    "only_base" (1997 window only). Then, exactly,
    change = (both 1998 − both 1997) + only_cur 1998 − only_base 1997.
    Window presence says nothing about first purchase or churn; the
    out-of-window order counts are context only. Exclusivity, coverage
    and identity checks go to ``CHECKS``.

    Args:
        lines (pandas.DataFrame): Output of ``build_lines``.
        ords (pandas.DataFrame): Orders, for orders outside the windows.
        wide (pandas.DataFrame): Country table from ``summarise``.

    Returns:
        tuple[pandas.DataFrame, pandas.DataFrame]: Country bridge table
            (plus a "Total" row) with customer counts, group sales and
            the three contributions; and one row per (Country,
            CustomerID) with window sales, orders and ``Group``.
    """
    c = lines.groupby(["Country", "CustomerID", "Period"]).agg(
        Sales=("Sales", "sum"), Orders=("OrderID", "nunique")).unstack("Period", fill_value=0)
    c.columns = [f"{m}_{p}" for m, p in c.columns]
    for m in ["Sales", "Orders"]:
        for p in PERIODS:
            if f"{m}_{p}" not in c:
                c[f"{m}_{p}"] = 0
    in0, in1 = c[f"Orders_{BASE}"] > 0, c[f"Orders_{CUR}"] > 0
    c["Group"] = np.select([in0 & in1, ~in0 & in1, in0 & ~in1], GROUPS, default="none")
    # Context only: orders before the 1998 window / after the 1997 window.
    pre = ords[ords["OrderDate"] < PERIODS[CUR][0]].groupby("CustomerID")["OrderID"].nunique()
    post = ords[ords["OrderDate"] > PERIODS[BASE][1]].groupby("CustomerID")["OrderID"].nunique()
    ids = c.index.get_level_values("CustomerID")
    c["OrdersBefore1998Window"] = pre.reindex(ids).fillna(0).astype(int).to_numpy()
    c["OrdersAfter1997Window"] = post.reindex(ids).fillna(0).astype(int).to_numpy()
    # Orders before the 1998 window include the 1997 window itself, so
    # count only those outside it for the 1998-only group.
    c["OrdersBefore1998OutsideWindows"] = c["OrdersBefore1998Window"] - c[f"Orders_{BASE}"]

    def agg(d):
        """Sum one country's customers into bridge columns.

        Args:
            d (pandas.DataFrame): Customer rows of one country (or all).

        Returns:
            pandas.Series: Customer counts, group sales, contributions
                and out-of-window context counts.
        """
        b, n, l = d[d["Group"] == "both"], d[d["Group"] == "only_cur"], d[d["Group"] == "only_base"]
        r = {
            "CustBoth": len(b), "CustOnlyCur": len(n), "CustOnlyBase": len(l), "CustUnion": len(d),
            f"BothSales_{BASE}": b[f"Sales_{BASE}"].sum(), f"BothSales_{CUR}": b[f"Sales_{CUR}"].sum(),
            f"OnlyCurSales_{CUR}": n[f"Sales_{CUR}"].sum(), f"OnlyBaseSales_{BASE}": l[f"Sales_{BASE}"].sum(),
            "OnlyCurWithEarlierOrders": int((n["OrdersBefore1998OutsideWindows"] > 0).sum()),
            "OnlyBaseWithLaterOrders": int((l["OrdersAfter1997Window"] > 0).sum()),
        }
        r["BothChange"] = r[f"BothSales_{CUR}"] - r[f"BothSales_{BASE}"]
        r["OnlyCurContribution"] = r[f"OnlyCurSales_{CUR}"]
        r["OnlyBaseContribution"] = -r[f"OnlyBaseSales_{BASE}"]
        r["NetChange"] = r["BothChange"] + r["OnlyCurContribution"] + r["OnlyBaseContribution"]
        return pd.Series(r)

    br = c.groupby("Country").apply(agg, include_groups=False)
    br.loc["Total"] = agg(c.reset_index())

    check("Q1 分组：每个（国家, 客户）恰属一组", 0, (c["Group"] == "none").sum())
    union = lines.groupby("Country")["CustomerID"].nunique()
    check("Q1 分组：各国三组客户数之和 = 两期客户并集（独立计数）", union.sum(),
          br.drop("Total")[["CustBoth", "CustOnlyCur", "CustOnlyBase"]].sum().sum())
    check("Q1 分组：各国客户并集最大差异", 0,
          (br.drop("Total")["CustUnion"] - union.reindex(br.drop("Total").index)).abs().max())
    check("Q1 分组：两期均购买 + 仅基期 = 基期活跃客户", wide[f"Customers_{BASE}"].sum(),
          (br.drop("Total")["CustBoth"] + br.drop("Total")["CustOnlyBase"]).sum())
    check("Q1 分组：两期均购买 + 仅本期 = 本期活跃客户", wide[f"Customers_{CUR}"].sum(),
          (br.drop("Total")["CustBoth"] + br.drop("Total")["CustOnlyCur"]).sum())
    b = br.drop("Total")
    check("Q1 分组：各国基期销售额 = 两期均购买 + 仅基期（最大差异）", 0,
          (b[f"BothSales_{BASE}"] + b[f"OnlyBaseSales_{BASE}"] - wide[f"Sales_{BASE}"].reindex(b.index)).abs().max())
    check("Q1 分组：各国本期销售额 = 两期均购买 + 仅本期（最大差异）", 0,
          (b[f"BothSales_{CUR}"] + b[f"OnlyCurSales_{CUR}"] - wide[f"Sales_{CUR}"].reindex(b.index)).abs().max())
    check("Q1 分组：三项贡献之和 = 各国实际变化（最大差异）", 0,
          (b["NetChange"] - wide["SalesChange"].reindex(b.index)).abs().max())
    check("Q1 分组：公司三项贡献之和 = 公司总变化", wide["SalesChange"].sum(), br.loc["Total", "NetChange"])
    check("Q1 分组：各国三项贡献之和 = 公司三项贡献", br.loc["Total", ["BothChange", "OnlyCurContribution",
                                                          "OnlyBaseContribution"]].sum(),
          b[["BothChange", "OnlyCurContribution", "OnlyBaseContribution"]].sum().sum())
    return br, c


def decompose(wide, totals):
    """Split log sales growth into customers, orders/customer and AOV.

    ln(S1/S0) = ln(C1/C0) + ln(F1/F0) + ln(A1/A0), where C is active
    customers, F orders per customer and A average order value. Only
    defined when both windows have sales. Descriptive, not causal.

    Args:
        wide (pandas.DataFrame): Country table.
        totals (pandas.DataFrame): Window totals.

    Returns:
        pandas.DataFrame: One row per country plus "全部国家合计", with
            log components, order/AOV shares of the log change and a
            Chinese ``Driver`` label; NaN rows where undefined.
    """
    rows = {}
    frames = [("全部国家合计", totals.rename(columns=str.title).T)] + [
        (c, None) for c in wide.index]
    for name, _ in frames:
        if name == "全部国家合计":
            S0, S1 = totals.loc[BASE, "Sales"], totals.loc[CUR, "Sales"]
            O0, O1 = totals.loc[BASE, "Orders"], totals.loc[CUR, "Orders"]
            C0, C1 = totals.loc[BASE, "Customers"], totals.loc[CUR, "Customers"]
        else:
            r = wide.loc[name]
            S0, S1 = r[f"Sales_{BASE}"], r[f"Sales_{CUR}"]
            O0, O1 = r[f"Orders_{BASE}"], r[f"Orders_{CUR}"]
            C0, C1 = r[f"Customers_{BASE}"], r[f"Customers_{CUR}"]
        if min(S0, S1) <= 0:
            rows[name] = {"lnSales": np.nan}
            continue
        ln_s = np.log(S1 / S0)
        ln_o = np.log(O1 / O0)
        ln_a = np.log((S1 / O1) / (S0 / O0))
        ln_c = np.log(C1 / C0)
        rows[name] = {
            "lnSales": ln_s, "lnOrders": ln_o, "lnAOV": ln_a,
            "lnCustomers": ln_c, "lnOrdersPerCustomer": ln_o - ln_c,
            "OrdersShare": ln_o / ln_s if abs(ln_s) > 1e-12 else np.nan,
            "AOVShare": ln_a / ln_s if abs(ln_s) > 1e-12 else np.nan,
        }
    d = pd.DataFrame(rows).T

    def driver(r):
        """Label whether order count or AOV dominates the log change.

        Args:
            r (pandas.Series): One decomposition row.

        Returns:
            str: Chinese description, or "不适用" if undefined.
        """
        if pd.isna(r["lnSales"]):
            return NA
        o, a = r["lnOrders"], r["lnAOV"]
        if np.sign(o) != np.sign(a) and o != 0 and a != 0:
            return f"订单数{'↑' if o > 0 else '↓'}、客单价{'↑' if a > 0 else '↓'}方向相反，" \
                   f"净效果由{'订单数' if abs(o) > abs(a) else '客单价'}主导"
        return "主要伴随订单数变化" if abs(o) >= abs(a) else "主要伴随客单价变化"

    d["Driver"] = d.apply(driver, axis=1)
    check("分解恒等式 lnSales = lnOrders + lnAOV（最大残差）", 0,
          (d["lnSales"] - d["lnOrders"] - d["lnAOV"]).abs().max(), tol=1e-9)
    check("分解恒等式 lnOrders = lnCustomers + lnOrdersPerCustomer（最大残差）", 0,
          (d["lnOrders"] - d["lnCustomers"] - d["lnOrdersPerCustomer"]).abs().max(), tol=1e-9)
    return d


def display_table(wide, decomp):
    """Build the Chinese-labelled, rounded country table for output.

    Args:
        wide (pandas.DataFrame): Country table.
        decomp (pandas.DataFrame): Output of ``decompose``.

    Returns:
        pandas.DataFrame: Rounded table sorted by 1998 sales, with
            growth shown as percentage strings or "不适用".
    """
    def pct(x):
        """Format a ratio as a signed percentage.

        Args:
            x (float): Ratio, e.g. 0.25 for +25%; NaN allowed.

        Returns:
            str: e.g. "+25.0%", or "不适用" for NaN.
        """
        return NA if pd.isna(x) else f"{x * 100:+.1f}%"

    t = pd.DataFrame(index=wide.index)
    t[f"{BASE}年1-4月折后销售额"] = wide[f"Sales_{BASE}"].round(2)
    t[f"{CUR}年1-4月折后销售额"] = wide[f"Sales_{CUR}"].round(2)
    t["销售额变化金额"] = wide["SalesChange"].round(2)
    t["销售额增长率"] = wide["SalesGrowth"].map(pct)
    t[f"{BASE}订单数"] = wide[f"Orders_{BASE}"].astype(int)
    t[f"{CUR}订单数"] = wide[f"Orders_{CUR}"].astype(int)
    t[f"{BASE}活跃客户数"] = wide[f"Customers_{BASE}"].astype(int)
    t[f"{CUR}活跃客户数"] = wide[f"Customers_{CUR}"].astype(int)
    t[f"{BASE}客单价"] = wide[f"AOV_{BASE}"].round(2)
    t[f"{CUR}客单价"] = wide[f"AOV_{CUR}"].round(2)
    t["客单价变化率"] = wide["AOVGrowth"].map(pct)
    share0 = wide[f"Sales_{BASE}"] / wide[f"Sales_{BASE}"].sum()
    share1 = wide[f"Sales_{CUR}"] / wide[f"Sales_{CUR}"].sum()
    def p0(x):
        """Format a ratio as a whole-number percentage.

        Args:
            x (float): Ratio; NaN allowed.

        Returns:
            str: e.g. "38%", or "不适用" for NaN.
        """
        return NA if pd.isna(x) else f"{x * 100:.0f}%"

    t[f"{BASE}公司内部销售额占比"] = share0.map(lambda x: f"{x * 100:.1f}%")
    t[f"{CUR}公司内部销售额占比"] = share1.map(lambda x: f"{x * 100:.1f}%")
    t["公司内部占比变化（百分点）"] = ((share1 - share0) * 100).round(1)
    for p in PERIODS:
        t[f"{p}最大客户"] = wide[f"TopCust_{p}"]
        t[f"{p}最大客户销售占比"] = wide[f"TopCustShare_{p}"].map(p0)
    t["最大增量客户"] = wide["TopIncCustomer"]
    t["最大增量客户增量"] = wide["TopIncChange"].round(2)
    t["最大增量客户占国家净增量"] = wide["TopIncShareOfNet"].map(p0)
    t["前两大增量客户占国家净增量"] = wide["Top2IncShareOfNet"].map(p0)
    t["增长/下降客户数"] = (wide["CustomersUp"].astype(int).astype(str) + "/"
                      + wide["CustomersDown"].astype(int).astype(str))
    t["绝对变化最大的客户"] = wide["BiggestMoverCustomer"]
    t["该客户变化占国家净变化"] = wide["BiggestMoverShareOfChange"].map(p0)
    t["增长分解（描述性）"] = decomp["Driver"].reindex(t.index)
    t["提示"] = wide["Flags"]
    t = t.sort_values(f"{CUR}年1-4月折后销售额", ascending=False)
    t.index.name = "国家"
    return t


def plot(wide, lang="zh"):
    """Draw 1997 vs 1998 sales and the change per country.

    Args:
        wide (pandas.DataFrame): Country table.
        lang (str): Chart language, a key of ``CHART_TEXT``; "en"
            adds an "_en" suffix to the file name.

    Returns:
        pathlib.Path: The PNG written to ``OUT``.
    """
    tx = CHART_TEXT[lang]
    plt.rcParams["font.sans-serif"] = CJK_FONTS
    plt.rcParams["axes.unicode_minus"] = False
    ink, ink2, muted, grid, base_c = "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#c3c2b7"
    c_base, c_cur = "#86b6ef", "#2a78d6"   # same-hue ramp: earlier period lighter
    c_up, c_down = "#2a78d6", "#e34948"

    w = wide.sort_values(f"Sales_{CUR}", ascending=True)
    y = np.arange(len(w))
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(14, 9), sharey=True,
                                 gridspec_kw={"width_ratios": [1.25, 1]})
    fig.patch.set_facecolor("#fcfcfb")
    h = 0.38
    a1.barh(y + h / 2, w[f"Sales_{BASE}"], height=h - 0.04, color=c_base,
            label=tx["window"].format(BASE))
    a1.barh(y - h / 2, w[f"Sales_{CUR}"], height=h - 0.04, color=c_cur,
            label=tx["window"].format(CUR))
    a1.set_title(tx["sales"], loc="left", color=ink, fontsize=12)
    a1.legend(loc="lower right", frameon=False, labelcolor=ink2)

    chg = w["SalesChange"]
    a2.barh(y, chg, height=0.6, color=np.where(chg >= 0, c_up, c_down))
    a2.axvline(0, color=base_c, lw=1)
    a2.set_title(tx["change"], loc="left", color=ink, fontsize=12)
    span = chg.abs().max()
    for yi, (c, r) in zip(y, w.iterrows()):
        g = r["SalesGrowth"]
        txt = tx["fmt"].format(chg=f"{r['SalesChange']:+,.0f}",
                               g=tx["na"] if pd.isna(g) else f"{g * 100:+.0f}%")
        x = r["SalesChange"]
        a2.text(x + (0.02 * span if x >= 0 else -0.02 * span), yi, txt,
                va="center", ha="left" if x >= 0 else "right", fontsize=8, color=ink2)
    a2.set_xlim(chg.min() - 0.45 * span, chg.max() + 0.45 * span)

    for ax in (a1, a2):
        ax.set_facecolor("#fcfcfb")
        ax.grid(axis="x", color=grid, lw=0.6)
        ax.set_axisbelow(True)
        for s in ("top", "right", "left"):
            ax.spines[s].set_visible(False)
        ax.spines["bottom"].set_color(base_c)
        ax.tick_params(colors=muted, labelsize=9, length=0)
        ax.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:,.0f}"))
    a1.set_yticks(y, w.index, color=ink2)
    fig.suptitle(tx["title"], x=0.01, ha="left", fontsize=14, color=ink)
    fig.tight_layout(rect=(0, 0, 1, 0.97))
    path = OUT / f"q1_country_sales_chart{tx['suffix']}.png"
    fig.savefig(path, dpi=150, facecolor=fig.get_facecolor())
    plt.close(fig)
    return path


def plot_bridge(br, lang="zh"):
    """Draw each country's change split into the three customer groups.

    Positive parts stack right of zero and negative parts left; a
    diamond marks the net change. Hatching repeats the colour coding.

    Args:
        br (pandas.DataFrame): First output of ``customer_bridge``.
        lang (str): Chart language, a key of ``CHART_TEXT``; "en"
            adds an "_en" suffix to the file name.

    Returns:
        pathlib.Path: The PNG written to ``OUT``.
    """
    tx = CHART_TEXT[lang]
    plt.rcParams["font.sans-serif"] = CJK_FONTS
    plt.rcParams["axes.unicode_minus"] = False
    ink, ink2, muted, grid, base_c, surf = "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#c3c2b7", "#fcfcfb"
    parts = [("BothChange", tx["b_both"], "#2a78d6", ""),
             ("OnlyCurContribution", tx["b_cur"], "#1baf7a", "//"),
             ("OnlyBaseContribution", tx["b_base"], "#eb6834", "\\\\")]
    b = br.drop("Total").sort_values("NetChange")
    y = np.arange(len(b))
    fig, ax = plt.subplots(figsize=(13, 10))
    fig.patch.set_facecolor(surf)
    pos, neg = np.zeros(len(b)), np.zeros(len(b))
    for col, label, color, hatch in parts:
        v = b[col].to_numpy(dtype=float)
        ax.barh(y, v, left=np.where(v >= 0, pos, neg), height=0.62, color=color, hatch=hatch,
                edgecolor=surf, linewidth=0.8, label=label)
        pos, neg = pos + np.clip(v, 0, None), neg + np.clip(v, None, 0)
    ax.scatter(b["NetChange"], y, marker="D", s=50, color=ink, zorder=3, edgecolors=surf,
               linewidths=1.5, label=tx["b_net"])
    span = max(pos.max(), -neg.min())
    for yi, v, p in zip(y, b["NetChange"], pos):
        ax.text(p + 0.015 * span, yi, f"{v:+,.0f}", va="center", fontsize=9, color=ink2)
    ax.axvline(0, color=base_c, lw=1.2)
    ax.set_yticks(y, b.index, color=ink2, fontsize=10)
    ax.set_xlim(neg.min() * 1.15, pos.max() * 1.15)
    ax.set_xlabel(tx["b_x"], color=muted)
    ax.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:,.0f}"))
    ax.set_facecolor(surf)
    ax.grid(axis="x", color=grid, lw=0.6)
    ax.set_axisbelow(True)
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.spines["bottom"].set_color(base_c)
    ax.tick_params(colors=muted, labelsize=9, length=0)
    ax.legend(loc="lower right", frameon=False, labelcolor=ink2, fontsize=10)
    fig.suptitle(tx["b_title"], x=0.01, ha="left", fontsize=13, color=ink)
    fig.text(0.01, 0.01, tx["b_note"], fontsize=9, color=muted)
    fig.tight_layout(rect=(0, 0.03, 1, 0.96))
    path = OUT / f"q1_customer_group_bridge{tx['suffix']}.png"
    fig.savefig(path, dpi=150, facecolor=surf)
    plt.close(fig)
    return path


def spot_check(country, det, ords, cus, wide):
    """Trace one country's figures back to raw orders and lines.

    Writes the country's customers, orders and lines as CSVs to
    ``OUT`` and appends the comparisons to ``CHECKS``.

    Args:
        country (str): Customers.Country value to trace; must be in
            ``wide``.
        det (pandas.DataFrame): Order details with ``Sales``.
        ords (pandas.DataFrame): Orders.
        cus (pandas.DataFrame): Customers.
        wide (pandas.DataFrame): Country table, for figures to match.

    Returns:
        str: Plain-text walkthrough of the check.
    """
    cust = cus[cus["Country"] == country][["CustomerID", "CompanyName", "Country"]]
    o = ords[ords["CustomerID"].isin(cust["CustomerID"])].copy()
    o["Period"] = period_of(o["OrderDate"])
    o = o[o["Period"].notna()].sort_values("OrderDate")
    d = det[det["OrderID"].isin(o["OrderID"])].merge(
        o[["OrderID", "CustomerID", "OrderDate", "Period"]], on="OrderID")
    d = d[["Period", "OrderID", "OrderDate", "CustomerID", "ProductID",
           "UnitPrice", "Quantity", "Discount", "Sales"]].sort_values(["OrderDate", "OrderID", "ProductID"])
    d.to_csv(OUT / f"spotcheck_{country}_lines.csv", index=False, encoding="utf-8-sig")
    per_order = d.groupby(["Period", "OrderID", "OrderDate", "CustomerID"], as_index=False).agg(
        Lines=("ProductID", "size"), Sales=("Sales", "sum"))
    per_order.to_csv(OUT / f"spotcheck_{country}_orders.csv", index=False, encoding="utf-8-sig")
    cust.to_csv(OUT / f"spotcheck_{country}_customers.csv", index=False, encoding="utf-8-sig")

    out = [f"核验国家：{country}",
           f"步骤 1  Customers 表中 Country = '{country}' 的客户（{len(cust)} 个）：",
           cust.to_string(index=False),
           f"\n步骤 2  这些客户在两个期间的订单（Orders 表，OrderDate 在 1–4 月内）：",
           o[["Period", "OrderID", "CustomerID", "OrderDate", "ShippedDate", "Freight"]].to_string(index=False),
           "\n步骤 3  这些订单的明细行（Orders Details 表），Sales = UnitPrice×Quantity×(1−Discount)：",
           d.to_string(index=False, float_format=lambda v: f"{v:.6f}".rstrip("0").rstrip(".")),
           "\n步骤 4  按订单汇总：",
           per_order.to_string(index=False),
           "\n步骤 5  按期间汇总并与国家表比对："]
    for p in PERIODS:
        pp = per_order[per_order["Period"] == p]
        s, n, c = pp["Sales"].sum(), pp["OrderID"].nunique(), pp["CustomerID"].nunique()
        out.append(f"  {p}: 销售额={s:.6f}  订单数={n}  活跃客户={c}  客单价="
                   f"{(s / n if n else float('nan')):.6f}  | 国家表: 销售额={wide.loc[country, f'Sales_{p}']:.6f} "
                   f"订单数={int(wide.loc[country, f'Orders_{p}'])} 客户={int(wide.loc[country, f'Customers_{p}'])}")
        check(f"抽查 {country} {p} 销售额", s, wide.loc[country, f"Sales_{p}"])
        check(f"抽查 {country} {p} 订单数", n, wide.loc[country, f"Orders_{p}"])
        check(f"抽查 {country} {p} 活跃客户", c, wide.loc[country, f"Customers_{p}"])
    out.append("\n在 Excel 中复核：Orders 表按 CustomerID 筛选上面客户、OrderDate 筛选两个 1–4 月；"
               "再到 Orders Details 表按这些 OrderID 筛选，逐行计算 UnitPrice*Quantity*(1-Discount) 后求和。")
    return "\n".join(out)


def main():
    """Run Q1, write all outputs to ``OUT`` and print a summary.

    The first command-line argument, if given, names the spot-check
    country (default "Switzerland").

    Args:
        None.

    Returns:
        None.
    """
    sys.stdout.reconfigure(encoding="utf-8")
    pd.set_option("display.width", 250)
    pd.set_option("display.max_columns", 40)
    pd.set_option("display.max_rows", 100)
    OUT.mkdir(parents=True, exist_ok=True)
    country = sys.argv[1] if len(sys.argv) > 1 else "Switzerland"

    det, ords, cus = load()
    check("Customers.CustomerID 唯一（每个客户只有一个国家）", len(cus), cus["CustomerID"].nunique())
    lines = build_lines(det, ords, cus)
    wide, totals = summarise(lines, ords)
    cust_sales = concentration(lines, wide, totals)
    decomp = decompose(wide, totals)
    decliners = wide.index[wide["SalesChange"] < 0].tolist()
    evidence = customer_evidence(cust_sales, ords, wide, ["USA", "Germany"] + decliners)
    table = display_table(wide, decomp)
    chart = plot(wide)
    plot(wide, "en")
    bridge, cust_groups = customer_bridge(lines, ords, wide)
    plot_bridge(bridge)
    plot_bridge(bridge, "en")
    spot = spot_check(country, det, ords, cus, wide)

    # Sensitivity: 1998 orders not yet shipped at data cut-off.
    unshipped = lines[(lines["Period"] == CUR) & lines["ShippedDate"].isna()]

    table.to_csv(OUT / "q1_country_comparison.csv", encoding="utf-8-sig")
    wide.to_csv(OUT / "q1_country_raw_precision.csv", encoding="utf-8-sig")
    decomp.to_csv(OUT / "q1_growth_decomposition.csv", encoding="utf-8-sig")
    cust_sales.to_csv(OUT / "q1_customer_sales_by_country.csv", encoding="utf-8-sig")
    evidence.to_csv(OUT / "q1_customer_evidence.csv", index=False, encoding="utf-8-sig")
    bridge.to_csv(OUT / "q1_customer_group_bridge.csv", encoding="utf-8-sig")
    cust_groups.reset_index().to_csv(OUT / "q1_customer_groups.csv", index=False, encoding="utf-8-sig")
    checks = pd.DataFrame(CHECKS)
    checks.to_csv(OUT / "q1_validation.csv", index=False, encoding="utf-8-sig")
    (OUT / f"spotcheck_{country}.txt").write_text(spot, encoding="utf-8")

    print("== 期间总额 ==")
    print(totals.round(2).to_string())
    print("\n== 国家对比表 ==")
    print(table.to_string())
    print("\n== 集中度：当期销售集中度 vs 增长贡献集中度 ==")
    conc_cols = [f"TopCust_{BASE}", f"TopCustShare_{BASE}", f"TopCust_{CUR}", f"TopCustShare_{CUR}",
                 "SalesChange", "TopIncCustomer", "TopIncChange", "TopIncShareOfNet",
                 "TopIncShareOfGrossUp", "Top2IncShareOfNet", "CustomersUp", "CustomersDown"]
    print(wide.loc[["USA", "Germany", "Brazil"], conc_cols].round(3).to_string())
    print("\n== 客户层面证据（USA、Germany 与下滑国家）==")
    print(evidence.round(3).to_string(index=False))
    print("\n== 客户分组分解（两期均购买 / 仅本期窗口 / 仅基期窗口）==")
    print(bridge.round(2).to_string())
    print("\n== 增长分解（对数，描述性）==")
    print(decomp.round(3).to_string())
    print("\n== 1998 年 1–4 月未发货订单（截至数据末日）==")
    print(unshipped.groupby("Country").agg(Orders=("OrderID", "nunique"), Sales=("Sales", "sum"))
          .round(2).to_string())
    print("\n== 验证 ==")
    print(checks.to_string(index=False))
    print(f"\n全部通过: {checks['通过'].all()}")
    print(f"\n图表: {chart}")
    print("\n" + spot)


if __name__ == "__main__":
    main()
