"""Read-only structure and quality checks of Northwind Database.xlsx.

Provides the xlsx reader and CJK font fallbacks reused by Q1-Q5.
"""

import re
import sys
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

import pandas as pd

XLSX = Path(__file__).with_name("Northwind Database.xlsx")
NS = {
    "m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "pr": "http://schemas.openxmlformats.org/package/2006/relationships",
}
# Built-in Excel number formats that represent dates or times.
DATE_FMT_IDS = set(range(14, 23)) | set(range(45, 48))
# Chart fonts tried in order: Windows, macOS, Linux CJK fonts, then
# matplotlib's bundled DejaVu Sans (no Chinese glyphs).
CJK_FONTS = ["Microsoft YaHei", "SimHei", "PingFang SC", "Hiragino Sans GB",
             "Heiti SC", "Noto Sans CJK SC", "Source Han Sans SC",
             "WenQuanYi Zen Hei", "Arial Unicode MS", "DejaVu Sans"]


def col_index(ref):
    """Convert a cell reference to a zero-based column index.

    Args:
        ref (str): Uppercase A1-style reference, e.g. ``"AB12"``.

    Returns:
        int: Column index, 0 for column A.
    """
    letters = re.match(r"[A-Z]+", ref).group()
    n = 0
    for ch in letters:
        n = n * 26 + ord(ch) - 64
    return n - 1


def load_workbook(path):
    """Read every sheet of an xlsx file without openpyxl.

    Row 1 becomes the header; blank header cells are named
    ``"<blank col N>"``. Cells with a date number format become
    ``pandas.Timestamp``; other numbers stay ``float``. Blank strings
    are dropped. Each DataFrame's ``attrs["cells_outside_header"]``
    lists column indices that hold data beyond the header width.

    Args:
        path (str | pathlib.Path): Workbook to read; opened read-only.

    Returns:
        dict[str, pandas.DataFrame]: Sheet name to its data rows, in
            workbook order; an empty DataFrame for an empty sheet.
    """
    with zipfile.ZipFile(path) as z:
        shared = []
        if "xl/sharedStrings.xml" in z.namelist():
            root = ET.fromstring(z.read("xl/sharedStrings.xml"))
            for si in root.findall("m:si", NS):
                shared.append("".join(t.text or "" for t in si.iter(f"{{{NS['m']}}}t")))

        styles = ET.fromstring(z.read("xl/styles.xml"))
        custom_date = set()
        numfmts = styles.find("m:numFmts", NS)
        if numfmts is not None:
            for nf in numfmts:
                code = nf.get("formatCode", "").lower()
                if re.search(r"[dmy]", re.sub(r"\[.*?\]|\".*?\"", "", code)):
                    custom_date.add(int(nf.get("numFmtId")))
        xf_is_date = [
            int(xf.get("numFmtId", 0)) in DATE_FMT_IDS | custom_date
            for xf in styles.find("m:cellXfs", NS)
        ]

        rels = ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
        targets = {r.get("Id"): r.get("Target") for r in rels.findall("pr:Relationship", NS)}
        wb = ET.fromstring(z.read("xl/workbook.xml"))

        sheets = {}
        for sh in wb.find("m:sheets", NS):
            name = sh.get("name")
            target = targets[sh.get(f"{{{NS['r']}}}id")]
            root = ET.fromstring(z.read("xl/" + target.lstrip("/").removeprefix("xl/")))
            rows = {}
            for row in root.iter(f"{{{NS['m']}}}row"):
                r = int(row.get("r"))
                for c in row.findall("m:c", NS):
                    v = c.find("m:v", NS)
                    t = c.get("t")
                    if t == "inlineStr":
                        val = "".join(x.text or "" for x in c.iter(f"{{{NS['m']}}}t"))
                    elif v is None or v.text is None:
                        continue
                    elif t == "s":
                        val = shared[int(v.text)]
                    elif t in ("str", "e"):
                        val = v.text
                    elif t == "b":
                        val = bool(int(v.text))
                    else:
                        val = float(v.text)
                        s = int(c.get("s", 0))
                        if xf_is_date[s]:
                            val = pd.Timestamp("1899-12-30") + pd.to_timedelta(val, unit="D")
                    if isinstance(val, str) and val.strip() == "":
                        continue
                    rows.setdefault(r, {})[col_index(c.get("r"))] = val
            if not rows:
                sheets[name] = pd.DataFrame()
                continue
            header_row = rows.pop(min(rows))
            ncol = max(header_row) + 1
            headers = [str(header_row.get(i, f"<blank col {i + 1}>")).strip() for i in range(ncol)]
            extra = {i for r in rows.values() for i in r if i >= ncol}
            data = [[r.get(i) for i in range(ncol)] for _, r in sorted(rows.items())]
            df = pd.DataFrame(data, columns=headers)
            df.attrs["cells_outside_header"] = sorted(extra)
            sheets[name] = df
    return sheets


def as_key(s):
    """Normalise a key column so 5.0 and '5' compare equal.

    Args:
        s (pandas.Series): Key values: floats, strings or missing.

    Returns:
        pandas.Series: Stripped strings, integral floats without
            ``.0``, and None for missing values.
    """
    def norm(x):
        """Normalise one key value.

        Args:
            x (object): Cell value.

        Returns:
            str | None: Normalised key, or None if missing.
        """
        if x is None or (isinstance(x, float) and pd.isna(x)):
            return None
        if isinstance(x, float) and x.is_integer():
            return str(int(x))
        return str(x).strip()
    return s.map(norm)


def main():
    """Print the inspection report to stdout.

    With ``--structure-only`` as the first command-line argument, only
    the per-sheet structure section is printed.

    Args:
        None.

    Returns:
        None.
    """
    sys.stdout.reconfigure(encoding="utf-8")
    pd.set_option("display.width", 200)
    pd.set_option("display.max_columns", 50)
    sheets = load_workbook(XLSX)

    print("=" * 70, "\n1. SHEETS\n")
    for name, df in sheets.items():
        print(f"[{name}] rows={len(df)} (excl. header) cols={df.shape[1]}"
              + (f"  cells beyond header cols: {df.attrs['cells_outside_header']}"
                 if df.attrs.get("cells_outside_header") else ""))
        dup = df.columns[df.columns.duplicated()].tolist()
        if dup:
            print(f"    !! duplicated column names: {dup}")
        for i, c in enumerate(df.columns):
            col = df.iloc[:, i]
            nonnull = col.notna().sum()
            types = sorted({type(x).__name__ for x in col.dropna()})
            sample = col.dropna().head(3).tolist()
            print(f"    - [{i + 1}] {c!r}: non-null={nonnull}/{len(df)} types={types} sample={sample}")
        print()

    if len(sys.argv) > 1 and sys.argv[1] == "--structure-only":
        return
    checks(sheets)


def formula_cells(path):
    """List formula cells per sheet.

    Args:
        path (str | pathlib.Path): Workbook to read; opened read-only.

    Returns:
        dict[str, list[tuple[str, str | None]]]: Sheet name to
            ``(cell_ref, formula)`` pairs; sheets without formulas are
            omitted. Shared-formula followers have formula None.
    """
    out = {}
    with zipfile.ZipFile(path) as z:
        rels = ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
        targets = {r.get("Id"): r.get("Target") for r in rels.findall("pr:Relationship", NS)}
        wb = ET.fromstring(z.read("xl/workbook.xml"))
        for sh in wb.find("m:sheets", NS):
            root = ET.fromstring(z.read("xl/" + targets[sh.get(f"{{{NS['r']}}}id")]))
            found = [(c.get("r"), c.find("m:f", NS).text)
                     for c in root.iter(f"{{{NS['m']}}}c") if c.find("m:f", NS) is not None]
            if found:
                out[sh.get("name")] = found
    return out


def checks(sheets):
    """Print key, relationship, date and metric-availability checks.

    Args:
        sheets (dict[str, pandas.DataFrame]): Output of
            ``load_workbook`` for the Northwind workbook.

    Returns:
        None.
    """
    cat, cus, emp = sheets["Categories"], sheets["Customers"], sheets["Employees"]
    det, ords, shp = sheets["Orders Details"], sheets["Orders"], sheets["Shippers"]
    prod, sup = sheets["Product"], sheets["Suppliers"]

    print("=" * 70, "\n2. PRIMARY KEYS\n")
    pks = [("Categories", cat, ["CategoryID"]), ("Customers", cus, ["CustomerID"]),
           ("Employees", emp, ["EmployeeID"]), ("Orders", ords, ["OrderID"]),
           ("Shippers", shp, ["ShipperID"]), ("Product", prod, ["ProductID"]),
           ("Suppliers", sup, ["SupplierID"]), ("Orders Details", det, ["OrderID", "ProductID"])]
    for name, df, cols in pks:
        keys = pd.concat([as_key(df[c]) for c in cols], axis=1)
        nulls = keys.isna().any(axis=1).sum()
        dups = keys.duplicated(keep=False)
        print(f"{name} {cols}: null={nulls} duplicated_rows={dups.sum()}")
        if dups.any():
            print(df[dups].sort_values(cols).to_string())
    for name, df in sheets.items():
        full_dup = df.astype(str).duplicated().sum()
        if full_dup:
            print(f"  {name}: {full_dup} fully duplicated rows")
    nonint = {n: df[c][df[c].map(lambda x: isinstance(x, float) and not x.is_integer())].tolist()
              for n, df, cols in pks for c in cols if df[c].map(lambda x: isinstance(x, float)).any()}
    print("non-integer numeric IDs:", {k: v for k, v in nonint.items() if v} or "none")

    print("\n" + "=" * 70, "\n3. FOREIGN KEYS (child -> parent)\n")
    fks = [("Orders.CustomerID", ords["CustomerID"], "Customers.CustomerID", cus["CustomerID"]),
           ("Orders.EmployeeID", ords["EmployeeID"], "Employees.EmployeeID", emp["EmployeeID"]),
           ("Orders.ShipVia", ords["ShipVia"], "Shippers.ShipperID", shp["ShipperID"]),
           ("Orders Details.OrderID", det["OrderID"], "Orders.OrderID", ords["OrderID"]),
           ("Orders Details.ProductID", det["ProductID"], "Product.ProductID", prod["ProductID"]),
           ("Product.SupplierID", prod["SupplierID"], "Suppliers.SupplierID", sup["SupplierID"]),
           ("Product.CategoryID", prod["CategoryID"], "Categories.CategoryID", cat["CategoryID"]),
           ("Employees.ReportsTo", emp["ReportsTo"], "Employees.EmployeeID", emp["EmployeeID"])]
    for child, cs, parent, ps in fks:
        ck, pk = as_key(cs), set(as_key(ps).dropna())
        miss = ck[ck.notna() & ~ck.isin(pk)]
        unused = sorted(pk - set(ck.dropna()))
        print(f"{child} -> {parent}: child non-null={ck.notna().sum()}, "
              f"unmatched rows={len(miss)} {sorted(set(miss))[:20]}; "
              f"parent keys never referenced={len(unused)} {unused[:20]}")
    # Case/whitespace-insensitive retry for string keys.
    ck = ords["CustomerID"].str.strip().str.upper()
    print("Orders.CustomerID unmatched after strip/upper:",
          (~ck.isin(set(cus["CustomerID"].str.strip().str.upper()))).sum())

    det_o, ord_o = set(as_key(det["OrderID"])), set(as_key(ords["OrderID"]))
    print(f"orders with no detail lines: {len(ord_o - det_o)} {sorted(ord_o - det_o)[:20]}")
    print(f"detail lines per order: min={det.groupby('OrderID').size().min()} "
          f"max={det.groupby('OrderID').size().max()} "
          f"mean={det.groupby('OrderID').size().mean():.2f}")

    print("\n" + "=" * 70, "\n4. DATES\n")
    od = pd.to_datetime(ords["OrderDate"])
    print(f"OrderDate range: {od.min().date()} .. {od.max().date()}")
    by_month = od.dt.to_period("M").value_counts().sort_index()
    for y, g in by_month.groupby(by_month.index.year):
        months = sorted(p.month for p in g.index)
        print(f"  {y}: orders={g.sum()} months={months} "
              f"first={od[od.dt.year == y].min().date()} last={od[od.dt.year == y].max().date()}")
    print("orders per month:\n" + by_month.to_string())
    sd, rd = pd.to_datetime(ords["ShippedDate"]), pd.to_datetime(ords["RequiredDate"])
    print(f"ShippedDate missing: {sd.isna().sum()}; their OrderDate range: "
          f"{od[sd.isna()].min().date()} .. {od[sd.isna()].max().date()}")
    print(f"ShippedDate range: {sd.min().date()} .. {sd.max().date()}")
    print(f"ShippedDate < OrderDate: {(sd < od).sum()}; RequiredDate < OrderDate: {(rd < od).sum()}")
    print(f"shipped after RequiredDate: {(sd > rd).sum()} of {sd.notna().sum()} shipped")
    lead = (sd - od).dt.days
    print(f"days order->ship: min={lead.min()} median={lead.median()} max={lead.max()}")
    for c, s in [("Employees.BirthDate", emp["BirthDate"]), ("Employees.HireDate", emp["HireDate"])]:
        print(f"{c}: {pd.to_datetime(s).min().date()} .. {pd.to_datetime(s).max().date()}")

    print("\n" + "=" * 70, "\n5. NUMERIC FIELDS\n")
    for name, s in [("Details.UnitPrice", det["UnitPrice"]), ("Details.Quantity", det["Quantity"]),
                    ("Details.Discount", det["Discount"]), ("Orders.Freight", ords["Freight"]),
                    ("Product.Price", prod["Price"])]:
        s = pd.to_numeric(s, errors="coerce")
        print(f"{name}: min={s.min()} max={s.max()} zero={(s == 0).sum()} "
              f"negative={(s < 0).sum()} null={s.isna().sum()}")
    print("Discount values:", sorted(det["Discount"].unique().tolist()))
    print("Quantity non-integer:", (det["Quantity"] % 1 != 0).sum())

    p = prod.iloc[:, [0, 5, 6, 7, 8, 13, 15]].copy()
    p.columns = ["ProductID", "Price", "Cheap_7", "NewPrice_8", "Cheap_9", "IsCheap", "NewPrice_16"]
    print("Product extra columns (first 8 rows):\n" + p.head(8).to_string())
    print("NewPrice_8 / Price ratio:", (p["NewPrice_8"] / p["Price"]).round(4).describe().to_string())
    print("NewPrice_16 / Price ratio (non-null):",
          (p["NewPrice_16"] / p["Price"]).dropna().round(4).value_counts().to_string())
    print("Cheap_7 values:", p["Cheap_7"].value_counts().to_dict(),
          "Cheap_9 values:", p["Cheap_9"].value_counts().to_dict(),
          "IsCheap values:", p["IsCheap"].value_counts().to_dict())
    print("Price where IsCheap True: max", p.loc[p["IsCheap"], "Price"].max(),
          "| False: min", p.loc[~p["IsCheap"], "Price"].min())
    print("Price where NewPrice_16 present: max", p.loc[p["NewPrice_16"].notna(), "Price"].max(),
          "| absent: min", p.loc[p["NewPrice_16"].isna(), "Price"].min())
    print("Product rows sorted by ProductID?", prod["ProductID"].is_monotonic_increasing)

    m = det.assign(ProductID=as_key(det["ProductID"])).merge(
        p.assign(ProductID=as_key(p["ProductID"]))[["ProductID", "Price"]], on="ProductID", how="left")
    same = (m["UnitPrice"] - m["Price"]).abs() < 1e-9
    print(f"Details.UnitPrice == Product.Price: {same.sum()} of {len(m)} lines; "
          f"ratio UnitPrice/Price values: {(m['UnitPrice'] / m['Price']).round(3).value_counts().head(5).to_dict()}")

    f = formula_cells(XLSX)
    print("formula cells:", {k: (len(v), v[:3]) for k, v in f.items()} or "none")

    print("\n" + "=" * 70, "\n6. GRAIN / DOUBLE-COUNT DEMO\n")
    gross = (det["UnitPrice"] * det["Quantity"]).sum()
    net = (det["UnitPrice"] * det["Quantity"] * (1 - det["Discount"])).sum()
    print(f"distinct orders (Orders)={ords['OrderID'].nunique()}  "
          f"detail lines={len(det)}  distinct OrderID in details={det['OrderID'].nunique()}")
    print(f"gross sales (UnitPrice*Quantity)={gross:,.2f}  net of discount={net:,.2f}")
    print(f"Freight from Orders (correct grain)={ords['Freight'].sum():,.2f}")
    joined = det.merge(ords[["OrderID", "Freight"]], on="OrderID")
    print(f"Freight summed after joining to details (WRONG)={joined['Freight'].sum():,.2f}")
    print(f"row count after join={len(joined)} (would be mis-read as order count)")





if __name__ == "__main__":
    main()
