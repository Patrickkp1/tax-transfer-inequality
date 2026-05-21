#!/usr/bin/env python3
"""
CPI Bias-Adjusted Inflation Analysis — DBPI Edition (1979–2022)
================================================================
Replicates and extends Figure 6.1 of:
  Early, Furth & Rector — "The Myth of American Inequality" (2022), Ch. 6

THREE HEADLINE SERIES (all indices, Base=100 in 1979):
  1. CPI-U         — Official BLS (upper bound on cost-of-living)
  2. Chained CPI   — PCEPI (1979–1999) spliced to C-CPI-U (2000–2022)
                     Removes SUBSTITUTION BIAS only (~0.5pp/yr)
  3. True CPI      — Chained CPI further deflated for NEW PRODUCT + QUALITY BIAS

MEDICAL COMPONENT SERIES (Base=0% in 1999):
  • CPI Medical Care (CPIMEDSL) — Official BLS medical
  • Chained CPI Medical (SUUR0000SAM) — Substitution-corrected
  • BLS Disease-Based Price Index (DBPI) — measures cost to treat a CONDITION,
    not just price of medical services; preferred: Adjusted Quantities,
    Comorbidity Adjusted, Cumulative, Smoothed (per Oct 2024 BLS technical docs)

HOW THE AUTHORS GOT "CHAINED CPI" BEFORE 1999
----------------------------------------------
The C-CPI-U was first published by BLS in December 2000, covering data from
December 1999 forward. For pre-1999 years the standard substitute is the BEA's
Personal Consumption Expenditure Price Index (PCEPI), which uses a Fisher Ideal
(superlative) index formula that also eliminates substitution bias. The two series
are spliced at year 2000 by rescaling PCEPI to the C-CPI-U level. PCEPI is from
NIPA Table 2.8.4, available on FRED as series "PCEPI". The approach is cited
directly in the book's Figure 6.1 source notes.

ABOUT THE DBPI
--------------
The BLS Disease-Based Price Index measures the average cost to TREAT A DISEASE
rather than the price of individual medical goods/services. It captures efficiency
gains from changing treatment mixes (e.g., fewer hospitalizations, more outpatient).
Key specification used here per Oct 2024 BLS Technical Documentation:
  • Adjusted Quantities (DBPI, not Lowe) — quantity mix allowed to change
  • Comorbidity Adjusted — treatment units allocated via pro-rationing method
  • Cumulative index (base = December 1998 = 1)
  • Smoothed Quantities — January utilization jumps spread over the year

NOTE: The 2024 DBPI vintage differs from the 2018 vintage cited in the book
(which reported 1999–2017 DBPI rise = 40.7%). The current preferred spec shows
+50.5% for 1999–2017. This reflects ICD-9 to ICD-10 methodology updates and
periodic MEPS revisions documented in the Oct 2024 technical guide. Both show
the same direction: CPI Medical substantially overstates true medical inflation.

ABOUT CPI SHELTER / HOUSING QUALITY BIAS
-----------------------------------------
This is the most contested bias. Gordon (2006, NBER w11776) finds the CPI
rent index is biased DOWNWARD over most of the 20th century — i.e., BLS already
OVER-adjusts for quality improvements in shelter. Moulton & Moses (1997, Brookings)
also challenged the Boskin Commission's shelter bias estimate, arguing the
proportional apartment-size adjustment overstated quality improvement.
The 2022 National Academies report on CPI modernization notes shelter remains
"inherently difficult to measure" with no consensus method across OECD countries.
The Boskin Commission estimated a 0.25pp/yr UPWARD bias in shelter CPI from
missed quality improvements; Gordon's work suggests this may actually be close to
zero or even slightly negative.
Bottom line: shelter is the one component where the sign of bias is genuinely
contested in peer-reviewed literature. The True CPI line in this script does NOT
apply a separate shelter bias correction — it uses only the documented
quality/new-product bias from Boskin/Moulton (2018) applied at the all-items level.

BIAS SCHEDULE (pp/yr of remaining upward bias after substitution removed):
---------------------------------------------------------------------------
  1979–1999   0.60   Boskin Commission (1996) — pre-BLS geometric mean reform
  2000–2017   0.37   Moulton (2018) / Lebow-Rudd (2003) — post-BLS reforms residual
  2018–2022   0.30   Post BLS hedonic mobile phone expansion (Jan 2018; 83.8% of
                     feature changes captured vs 4.5% pre-reform)

DATA SOURCES (all via FRED, no API key required):
-------------------------------------------------
  CPIAUCSL        BLS CPI-U all items — https://data.bls.gov/PDQWeb/cu
  PCEPI           BEA PCE Price Index — spliced to C-CPI-U at Dec 1999
                  https://apps.bea.gov/iTable — NIPA Table 2.8.4
  SUUR0000SA0     BLS Chained CPI-U (from Dec 1999) — https://data.bls.gov/PDQWeb/su
  CPIMEDSL        BLS CPI Medical Care
  SUUR0000SAM     BLS Chained CPI Medical Care
  CUSR0000SAH1    BLS CPI Shelter
  SUUR0000SAH1    BLS Chained CPI Shelter
  CUSR0000SETB01  BLS CPI Telephone Hardware (electronics proxy)

DBPI SOURCE (manual download required):
  https://www.bls.gov/pir/diseasehome.htm
  File: "DBPIs for 17 Broad Categories (XLSX)"
  Place as: dbpis-for-17-broad-categories.xlsx in the script's folder.
  Specification used: Disease=All Diseases, Type=Cumulative, Quantities=Adjusted,
                      Comorbidity=Adjustment, Smoothed=Smooth

REFERENCES:
  Boskin et al. (1996) — Advisory Commission to Study the CPI
  Gordon (2006) — NBER WP 11776 — CPI rent downward bias
  Lebow & Rudd (2003) — Federal Reserve — Measurement Error in CPI
  Meyer & Sullivan (2013) — NBER WP 18718 — http://www.nber.org/papers/w18718
  Moulton (2018) — Brookings — https://www.brookings.edu/research/
                               themeasurement-of-output-prices-and-productivity
  Moulton & Moses (1997) — Brookings — Addressing Quality Change Issue in CPI
  National Academies (2022) — Modernizing the CPI for the 21st Century
  BLS DBPI Technical Documentation (Oct 2024) — https://www.bls.gov/pir/diseasehome.htm

USAGE:
  pip install pandas numpy requests plotly kaleido openpyxl
  python cpi_bias_adjusted_v3_dbpi.py
"""

import os, io, requests, warnings
import numpy as np
import pandas as pd
import plotly.graph_objects as go

warnings.filterwarnings("ignore")


# ═══════════════════════════════════════════════════════════════════════════
# 0. OUTPUT FOLDER (write CSV + PNG to <repo>/output/, same as everything else)
# ═══════════════════════════════════════════════════════════════════════════
# This script may live one or two folders deep under <repo>/src/, so we walk
# upward looking for a sibling 'output/' (or a 'data/raw/' marker that pins
# the repo root). Override with the OUTPUT_DIR env var if you want.

HERE = os.path.dirname(os.path.abspath(__file__))


def find_repo_root(start):
    cur = os.path.abspath(start)
    for _ in range(8):
        if (os.path.isdir(os.path.join(cur, "data", "raw"))
                or os.path.isdir(os.path.join(cur, "output"))):
            return cur
        parent = os.path.dirname(cur)
        if parent == cur:
            break
        cur = parent
    return os.path.abspath(start)


REPO_ROOT  = find_repo_root(HERE)
OUTPUT_DIR = os.environ.get("OUTPUT_DIR") or os.path.join(REPO_ROOT, "output")
os.makedirs(OUTPUT_DIR, exist_ok=True)


def out_path(filename):
    """Resolve a filename to a full path inside OUTPUT_DIR."""
    return os.path.join(OUTPUT_DIR, filename)


# ═══════════════════════════════════════════════════════════════════════════
# 1. FRED DATA FETCHING
# ═══════════════════════════════════════════════════════════════════════════

FRED_BASE = "https://fred.stlouisfed.org/graph/fredgraph.csv?id="

def fetch_fred(series_id: str) -> pd.DataFrame:
    r = requests.get(FRED_BASE + series_id, timeout=30)
    r.raise_for_status()
    df = pd.read_csv(io.StringIO(r.text))
    df.columns = ["date", "value"]
    df["date"] = pd.to_datetime(df["date"])
    df["year"] = df["date"].dt.year
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    return df.groupby("year")["value"].mean().reset_index().rename(columns={"value": series_id})


# ═══════════════════════════════════════════════════════════════════════════
# 2. LOAD BLS DISEASE-BASED PRICE INDEX
# ═══════════════════════════════════════════════════════════════════════════

def load_dbpi(filepath: str = "dbpis-for-17-broad-categories.xlsx") -> pd.DataFrame | None:
    """
    Load the BLS DBPI from the locally downloaded file.
    Preferred specification (per Oct 2024 BLS Technical Documentation):
      Disease=All Diseases, Type=Cumulative, Quantities=Adjusted,
      Comorbidity=Adjustment, Smoothed=Smooth
    Returns annual average cumulative index, base = Dec 1998 = 1.
    """
    if not os.path.exists(filepath):
        print(f"  [INFO] DBPI file not found at '{filepath}'.")
        print("         Download from: https://www.bls.gov/pir/diseasehome.htm")
        print("         File: 'DBPIs for 17 Broad Categories (XLSX)'")
        return None
    try:
        raw = pd.read_excel(filepath, sheet_name="Index", header=0)
        date_cols = [c for c in raw.columns
                     if isinstance(c, str) and len(c) == 6 and c.isdigit()]
        dates = pd.to_datetime([f"{c[:4]}-{c[4:6]}-01" for c in date_cols])

        # Preferred spec: All Diseases, Cumulative, Adjusted, Comorbidity Adjusted, Smooth
        mask = (
            (raw["Disease Selected"] == "All Diseases") &
            (raw["Index Type"] == "Cumulative") &
            (raw["Fixed Quantities or Adjusted Quantities"] == "Adjusted") &
            (raw["Comorbidity Adjustment"] == "Adjustment") &
            (raw["Smoothed Quantities"] == "Smooth")
        )
        row = raw[mask]
        if len(row) == 0:
            print("  [WARN] Could not find preferred DBPI spec. Trying without comorbidity adjustment...")
            mask2 = (
                (raw["Disease Selected"] == "All Diseases") &
                (raw["Index Type"] == "Cumulative") &
                (raw["Fixed Quantities or Adjusted Quantities"] == "Adjusted")
            )
            row = raw[mask2].iloc[[0]]

        vals = row[date_cols].iloc[0].astype(float)
        ts = pd.Series(vals.values, index=dates, name="dbpi_cumulative")
        ann = ts.resample("YE").mean()
        ann.index = ann.index.year
        result = ann.reset_index()
        result.columns = ["year", "dbpi_cumulative"]
        print(f"  ✓ DBPI loaded: {result.year.min()}–{result.year.max()}")
        return result
    except Exception as e:
        print(f"  [WARN] Could not parse DBPI: {e}")
        return None


# ═══════════════════════════════════════════════════════════════════════════
# 3. FETCH ALL DATA
# ═══════════════════════════════════════════════════════════════════════════

print("Fetching FRED data...")
SERIES = ["CPIAUCSL", "PCEPI", "SUUR0000SA0",
          "CPIMEDSL", "SUUR0000SAM", "CUSR0000SAH1", "SUUR0000SAH1", "CUSR0000SETB01"]

years = list(range(1979, 2023))
df = pd.DataFrame({"year": years})
for sid in SERIES:
    df = df.merge(fetch_fred(sid), on="year", how="left")
    print(f"  ✓ {sid}")

print("\nLoading DBPI...")
dbpi = load_dbpi(os.path.join(HERE, "dbpis-for-17-broad-categories.xlsx"))
if dbpi is not None:
    df = df.merge(dbpi, on="year", how="left")


# ═══════════════════════════════════════════════════════════════════════════
# 4. CONSTRUCT SERIES
# ═══════════════════════════════════════════════════════════════════════════

# Splice: PCEPI (1979–1999) → C-CPI-U (2000–2022)
scale = df.loc[df.year==2000, "SUUR0000SA0"].values[0] / df.loc[df.year==2000, "PCEPI"].values[0]
df["Chained_spliced"] = np.where(df.year < 2000, df["PCEPI"] * scale, df["SUUR0000SA0"])

# Normalize all headline series to 100 in 1979
for col, base_col in [("CPI_U_idx","CPIAUCSL"), ("Chained_idx","Chained_spliced")]:
    base = df.loc[df.year==1979, base_col].values[0]
    df[col] = df[base_col] / base * 100

# Quality + New Product bias: compound annual deflator
BIAS_SCHEDULE = [
    (1979, 1999, 0.60),   # Boskin (1996)
    (2000, 2017, 0.37),   # Moulton (2018) / Lebow-Rudd (2003)
    (2018, 2022, 0.30),   # Post BLS hedonic phone expansion
]
def get_bias(y):
    for s, e, r in BIAS_SCHEDULE:
        if s <= y <= e: return r
    return 0.37

df["quality_bias_pp"] = df["year"].apply(get_bias)
cum = 1.0; deflators = []
for _, row in df.iterrows():
    if row["year"] == 1979: deflators.append(1.0)
    else:
        cum *= (1 + row["quality_bias_pp"] / 100)
        deflators.append(cum)
df["cum_quality_deflator"] = deflators
df["True_CPI_idx"] = df["Chained_idx"] / df["cum_quality_deflator"]

df["CPI_U_cum"]    = df["CPI_U_idx"]   - 100
df["Chained_cum"]  = df["Chained_idx"] - 100
df["True_CPI_cum"] = df["True_CPI_idx"] - 100

# Medical component — cumulative % change from 1999
for sid_col, out_col in [("CPIMEDSL","cpi_med_cum"), ("SUUR0000SAM","ccpi_med_cum")]:
    base = df.loc[df.year==1999, sid_col].values[0]
    df[out_col] = df[sid_col] / base * 100 - 100

if "dbpi_cumulative" in df.columns:
    dbpi_base = df.loc[df.year==1999, "dbpi_cumulative"].values[0]
    df["dbpi_cum"] = df["dbpi_cumulative"] / dbpi_base * 100 - 100


# ═══════════════════════════════════════════════════════════════════════════
# 5. PRINT SUMMARY
# ═══════════════════════════════════════════════════════════════════════════

print("\n── Cumulative % Change (Base = 1979 = 0%) ───────────────────────────────")
print(f"{'Year':>6}  {'CPI-U':>8}  {'Chained':>9}  {'TrueCOL':>9}  {'Bias':>10}")
print("─" * 52)
for yr in sorted(set(list(range(1979, 2023, 5)) + [2022])):
    r = df.loc[df.year==yr].iloc[0]
    print(f"{int(yr):>6}  {r.CPI_U_cum:>7.1f}%  {r.Chained_cum:>8.1f}%  "
          f"{r.True_CPI_cum:>8.1f}%  {r.CPI_U_cum-r.True_CPI_cum:>9.1f}pp")

r22 = df.loc[df.year==2022].iloc[0]
print(f"\n── 2022 Totals ─────────────────────────────────────────────────────────")
print(f"  CPI-U:                      +{r22.CPI_U_cum:.1f}%")
print(f"  Chained CPI (sub. bias −):  +{r22.Chained_cum:.1f}%")
print(f"  True CPI (all biases −):    +{r22.True_CPI_cum:.1f}%")
print(f"  Sub. overstatement:          {r22.CPI_U_cum - r22.Chained_cum:.1f}pp")
print(f"  Quality/NP overstatement:    {r22.Chained_cum - r22.True_CPI_cum:.1f}pp")
print(f"  Total overstatement:        {r22.CPI_U_cum - r22.True_CPI_cum:.1f}pp")

if "dbpi_cum" in df.columns:
    r99 = df.loc[df.year==1999].iloc[0]
    r17 = df.loc[df.year==2017].iloc[0]
    r22m= df.loc[df.year==2022].iloc[0]
    print(f"\n── Medical Care Cross-Check ─────────────────────────────────────────────")
    print(f"  CPI Medical  1999–2017:   +{r17.cpi_med_cum:.1f}%")
    print(f"  Chained CPI  1999–2017:   +{r17.ccpi_med_cum:.1f}%")
    print(f"  DBPI         1999–2017:   +{r17.dbpi_cum:.1f}%  ← true cost to treat")
    print(f"  DBPI         1999–2022:   +{r22m.dbpi_cum:.1f}%")
    print(f"  CPI Medical  1999–2022:   +{r22m.cpi_med_cum:.1f}%")
    print(f"  Overstatement 1999–2022:   {r22m.cpi_med_cum - r22m.dbpi_cum:.1f}pp")
    print(f"\n  NOTE: Book (2022) cited DBPI 1999-2017 = 40.7%. Current (Oct 2024)")
    print(f"  preferred spec shows +50.5%. Difference reflects ICD-9→ICD-10 code")
    print(f"  transition methodology updates (see Section III of BLS Tech Docs).")


# ═══════════════════════════════════════════════════════════════════════════
# 6. EXPORT CSV
# ═══════════════════════════════════════════════════════════════════════════

out_cols = ["year", "CPI_U_idx","Chained_idx","True_CPI_idx",
            "CPI_U_cum","Chained_cum","True_CPI_cum",
            "quality_bias_pp","cum_quality_deflator",
            "CPIMEDSL","SUUR0000SAM","cpi_med_cum","ccpi_med_cum",
            "CUSR0000SAH1","SUUR0000SAH1","CUSR0000SETB01"]
if "dbpi_cumulative" in df.columns:
    out_cols += ["dbpi_cumulative","dbpi_cum"]

csv_path = out_path("cpi_adjusted_v3_dbpi_1979_2022.csv")
df[out_cols].round(4).to_csv(csv_path, index=False)
print(f"\nCSV saved: {csv_path}")


# ═══════════════════════════════════════════════════════════════════════════
# 7. CHART 1 — HEADLINE: THREE INDEX COMPARISON (1979–2022)
# ═══════════════════════════════════════════════════════════════════════════

series_specs = [
    ("CPI_U_cum",    "CPI-U Official",         "solid", "#636EFA"),
    ("Chained_cum",  "Chained CPI/PCEPI",       "dash",  "#EF553B"),
    ("True_CPI_cum", "True CPI (All Biases −)", "dot",   "#00CC96"),
]

fig1 = go.Figure()
for (col, name, dash, color) in series_specs:
    fig1.add_trace(go.Scatter(
        x=df.year, y=df[col], mode="lines", name=name,
        line=dict(width=2.8, dash=dash, color=color)
    ))

for (col, name, dash, color), yo in zip(series_specs, [10, 0, -10]):
    val = float(df.loc[df.year==2022, col].values[0])
    fig1.add_annotation(x=2023, y=val+yo, text=f"+{val:.0f}%",
        showarrow=False, xanchor="left", font=dict(size=12, color=color))

fig1.update_layout(
    title=dict(text="US Inflation: Official vs Bias-Adjusted (1979–2022)", font=dict(size=18)),
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5),
    plot_bgcolor="white", paper_bgcolor="white", width=980, height=520,
    margin=dict(t=90, b=65, l=75, r=90), xaxis_range=[1979, 2025],
)
fig1.update_xaxes(title_text="Year", dtick=5, tick0=1980,
                  showgrid=True, gridcolor="#ebebeb")
fig1.update_yaxes(title_text="Cum. % Change", showgrid=True, gridcolor="#ebebeb", dtick=50)
fig1.update_traces(cliponaxis=False)
headline_path = out_path("cpi_headline_v3.png")
fig1.write_image(headline_path)
print(f"Chart saved: {headline_path}")


# ═══════════════════════════════════════════════════════════════════════════
# 8. CHART 2 — MEDICAL CARE: CPI vs Chained vs DBPI (1999–2022)
# ═══════════════════════════════════════════════════════════════════════════

if "dbpi_cum" in df.columns:
    df_med = df[df.year >= 1999].copy()
    med_specs = [
        ("cpi_med_cum",  "CPI Medical (Official)", "solid", "#636EFA"),
        ("ccpi_med_cum", "Chained CPI Medical",     "dash",  "#EF553B"),
        ("dbpi_cum",     "DBPI (Disease-Based)",    "dot",   "#00CC96"),
    ]
    fig2 = go.Figure()
    for (col, name, dash, color) in med_specs:
        fig2.add_trace(go.Scatter(
            x=df_med.year, y=df_med[col], mode="lines", name=name,
            line=dict(width=2.8, dash=dash, color=color)
        ))
    for (col, name, dash, color), yo in zip(med_specs, [8, -4, -14]):
        val = float(df_med.loc[df_med.year==2022, col].values[0])
        fig2.add_annotation(x=2022.5, y=val+yo, text=f"+{val:.0f}%",
            showarrow=False, xanchor="left", font=dict(size=12, color=color))
    # Mark ICD-9→ICD-10 break
    fig2.add_vrect(x0=2018.5, x1=2019.5, fillcolor="rgba(255,165,0,0.12)", line_width=0)
    fig2.add_annotation(x=2019, y=108, text="ICD-10<br>break", showarrow=False,
        font=dict(size=10, color="darkorange"), xanchor="center")

    fig2.update_layout(
        title=dict(text="Medical Inflation: CPI vs Disease-Based PI (1999–2022)", font=dict(size=17)),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5),
        plot_bgcolor="white", paper_bgcolor="white", width=980, height=500,
        margin=dict(t=90, b=65, l=75, r=90), xaxis_range=[1998, 2024],
    )
    fig2.update_xaxes(title_text="Year", dtick=3, showgrid=True, gridcolor="#ebebeb")
    fig2.update_yaxes(title_text="Cum % Chg (1999=0)", showgrid=True, gridcolor="#ebebeb")
    fig2.update_traces(cliponaxis=False)
    medical_path = out_path("cpi_medical_v3.png")
    fig2.write_image(medical_path)
    print(f"Chart saved: {medical_path}")

print(f"\nDone. Output folder: {OUTPUT_DIR}")
print("  cpi_adjusted_v3_dbpi_1979_2022.csv")
print("  cpi_headline_v3.png")
if "dbpi_cum" in df.columns:
    print("  cpi_medical_v3.png")
