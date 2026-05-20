"""
top_percentile_taxes_transfers_panel.py
=======================================

Builds a long-format panel of household income, transfers, and taxes for
the top of the income distribution: the five CBO income groups (Bottom
through Top), the four CBO sub-groups inside Top 20 (81-90, 91-95, 96-99,
Top 1), and four ultra-top groups (Top 0.1, Top 0.01, Top 0.001, Forbes 400).

Years covered: 1979-2022 for CBO groups, 2001-2022 for ultra-top groups
(the IRS Statistics of Income Table 41TS only goes back to 2001), and
1992-2014 for the Forbes 400 specifically (IRS reports the top 400 returns
under the "14intop400" series, which ends in 2014).

For each year and group the panel reports per-household dollars from:

    earned_income       ← upstream earned_income_panel.csv
    govt_transfers      ← upstream transfer_distribution_panel.csv
    priv_transfers      ← upstream income_after_taxes_transfers_panel.csv
                          (sub-group rows extrapolated below)
    Federal taxes:
        fed_pit, fed_payroll, fed_corp (excluded), fed_excise, fed_other
    State and local taxes:
        sl_sales, sl_income, sl_property, sl_mv_other
    Derived:
        total_taxes = fed_total + sl_total
        income_after_transfers_taxes = earned + govt + priv − total_taxes

Pipeline contracts
------------------
The three upstream CSVs MUST already exist in OUTPUT_DIR.  This script
crashes with an informative error if any are missing — a wrong number
silently filled in with a fallback would be worse than a crash.

    earned_income_panel.csv               column: total
    transfer_distribution_panel.csv       column: total_govt
    income_after_taxes_transfers_panel.csv column: priv_transfers

Sub-group private transfers
---------------------------
Quintile rows (Bottom-Top) read priv_transfers directly from the upstream
panel.  Sub-groups inside the Top 20 (and ultra-top) get their private-
transfer estimate by scaling the Top quintile per-HH value with a square-
root income-elasticity decay:

    priv_subgroup = priv_top_quintile *
                    (top_quintile_avg_income / subgroup_avg_income) ** 0.5

The square-root form is the same convention used for property taxes
elsewhere in this script.  It sits between flat (no decay, too generous)
and linear (over-aggressive decay) for transfers that fall slowly with
income but never reach exactly zero.  These sub-group values should be
read as upper bounds — actual ultra-top receipts are likely closer to
zero.

Output: output/top_percentile_taxes_transfers_panel.csv
"""

import os
import glob
import numpy as np
import pandas as pd


# ----------------------------------------------------------------------------
# File paths — repo-aware
# ----------------------------------------------------------------------------
# This script is meant to live at <repo>/src/.  It walks up the directory
# tree until it finds a "data/raw" folder, then searches recursively for
# input files (CBO/IRS/CEX/CPS).  Upstream panel CSVs are read from
# <repo>/output/, and this script's output is written there too.
#
# Override either folder by setting the DATA_ROOT or OUTPUT_DIR env vars.

HERE = os.path.dirname(os.path.abspath(__file__))


def find_repo_root(start):
    cur = os.path.abspath(start)
    for _ in range(8):
        if os.path.isdir(os.path.join(cur, "data", "raw")):
            return cur
        parent = os.path.dirname(cur)
        if parent == cur:
            break
        cur = parent
    return os.path.abspath(start)


REPO_ROOT  = find_repo_root(HERE)
DATA_ROOT  = os.environ.get("DATA_ROOT")  or os.path.join(REPO_ROOT, "data", "raw")
OUTPUT_DIR = os.environ.get("OUTPUT_DIR") or os.path.join(REPO_ROOT, "output")
os.makedirs(OUTPUT_DIR, exist_ok=True)


def find_file(pattern):
    """Recursively search DATA_ROOT for a file matching `pattern`.
    Returns the latest match (alphabetical sort) or None."""
    matches = sorted(glob.glob(os.path.join(DATA_ROOT, "**", pattern),
                               recursive=True))
    return matches[-1] if matches else None


def find_cbo_table(table_num):
    """Find a CBO supplemental table CSV by number (1-13).
    Returns the latest match.  Raises FileNotFoundError if nothing matches."""
    pattern = f"households_ranked_by_market_inc_table_{table_num:02d}_*_1979_*.csv"
    matches = sorted(glob.glob(os.path.join(DATA_ROOT, "**", pattern),
                               recursive=True))
    if not matches:
        raise FileNotFoundError(
            f"No CBO Table {table_num:02d} file found under {DATA_ROOT}"
        )
    return matches[-1]


def normalize_cbo_columns(df):
    """CBO has shipped two file vintages with slightly different column names.
    Rename the abbreviated 2022-vintage names to the 2018-vintage names that
    downstream code expects."""
    renames = {
        "market_inc":          "market_income",
        "business_inc":        "business_income",
        "positive_rental_inc": "positive_rental_income",
        "other_market_inc":    "other_market_income",
        "individual_inc_tax":  "individual_income_tax",
        "corporate_inc_tax":   "corporate_income_tax",
    }
    return df.rename(columns={k: v for k, v in renames.items() if k in df.columns})


def load_tpc_sl_finance(year, filepath):
    """Load State & Local Government Finance aggregates for a single year
    from the TPC/Census results.csv extract.

    The CSV format:
      * line 1: "Level: State and Local"
      * line 2: "Unit:Total (thousands), Nominal"
      * line 3: column header row
    Values have a leading $ and are in thousands.

    Returns a dict with keys: total_taxes, property, general_sales,
    selective_sales, individual_income, corporate_income, other_taxes."""
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"TPC S&L Finance file not found: {filepath}")

    df = pd.read_csv(filepath, header=2, low_memory=False)
    state_col = df.columns[0]
    year_col  = df.columns[1]

    mask = (df[state_col] == "United States") & (df[year_col] == year)
    row = df[mask]
    if row.empty:
        mask2 = (df[state_col] == "United States") & (
            df[year_col].astype(str).str.strip() == str(year)
        )
        row = df[mask2]
    if row.empty:
        available = sorted(df[df[state_col] == "United States"][year_col].unique())
        raise ValueError(f"Year {year} not in {filepath}. Available: {available}")
    row = row.iloc[0]

    def get_col(partials):
        for col in df.columns:
            cl = col.lower()
            for p in partials:
                if p.lower() in cl:
                    raw = str(row[col]).replace("$", "").replace(",", "").strip()
                    try:
                        return float(raw)
                    except (ValueError, TypeError):
                        return np.nan
        return np.nan

    total_taxes     = get_col(["(R05)", "total taxes"])
    property_tax    = get_col(["(R06)", "property tax"])
    general_sales   = get_col(["(R09)", "gen sales", "general gen sales"])
    selective_sales = get_col(["(R10)", "select sales"])
    individual_inc  = get_col(["(R27)", "individual income tax (t40)"])
    corporate_inc   = get_col(["(R28)", "corp net income"])

    components = [property_tax, general_sales, selective_sales,
                  individual_inc, corporate_inc]
    known_sum = sum(x for x in components if not np.isnan(x))
    other_taxes = (total_taxes - known_sum) if not np.isnan(total_taxes) else np.nan

    return {
        "total_taxes":       total_taxes,
        "property":          property_tax,
        "general_sales":     general_sales,
        "selective_sales":   selective_sales,
        "individual_income": individual_inc,
        "corporate_income":  corporate_inc,
        "other_taxes":       other_taxes,
    }


# ---------------------------------------------------------------------------
# PARAMETERS
# ---------------------------------------------------------------------------
income_years_to_run = range(1979, 2023)

cbo_quintile_keys = [
    "lowest_quintile", "second_quintile", "middle_quintile",
    "fourth_quintile", "highest_quintile",
]
cbo_top_subgroup_keys = [
    "percentiles_81_90", "percentiles_91_95", "percentiles_96_99", "top_1_percent",
]
cbo_top_subgroup_labels = ["81-90 pctile", "91-95 pctile", "96-99 pctile", "Top 1 percent"]
quintile_display_labels = ["Bottom", "Second", "Middle", "Fourth", "Top"]
all_cbo_keys   = cbo_quintile_keys + cbo_top_subgroup_keys
all_cbo_labels = quintile_display_labels + cbo_top_subgroup_labels

_cex_csv_label_to_cbo_key = {
    "Q1 (Bottom 20%)": "lowest_quintile",
    "Q2 (Second 20%)": "second_quintile",
    "Q3 (Middle 20%)": "middle_quintile",
    "Q4 (Fourth 20%)": "fourth_quintile",
    "Q5 (Top 20%)":    "highest_quintile",
}
niu_sentinels = {
    "INCWAGE": 99999999, "INCBUS": 99999999, "INCFARM": 99999999,
    "INCDIVID": 9999999, "INCINT": 9999999,  "INCRENT": 9999999,
    "INCRETIR": 99999999, "HHINCOME": 9999999,
}

# Forbes 400 IRS-sourced data: (total_agi_k, total_tax_k, eff_rate_pct,
#   wage_pct, capgains_pct, div_pct, partner_pct, bond_pct)
# Values are TOTALS for all 400 members, in $thousands.
# Source: IRS Statistics of Income, "Reported Sources of Income, Deductions, and
# Tax of the 400 Individual Income Tax Returns Reporting the Largest Adjusted
# Gross Incomes" (pub. 14intop400), 1992-2014.
forbes400_irs_data = {
    1992: (18_716_032,  4_936_897, 26.38,  9.74, 36.08,  7.39, 17.66, 5.21),
    1993: (18_527_854,  5_437_295, 29.35,  8.37, 48.01,  7.17, 19.90, 1.31),
    1994: (18_466_682,  5_275_239, 28.57,  8.93, 52.26,  7.66, 22.37, 1.57),
    1995: (20_345_145,  6_088_571, 29.93,  8.57, 44.10,  9.51, 21.33, 1.67),
    1996: (29_883_593,  8_309_376, 27.81,  5.52, 63.40,  5.52, 13.62, 0.69),
    1997: (37_216_831,  8_991_855, 24.16,  4.88, 66.76,  4.88, 12.29, 0.29),
    1998: (44_195_098,  9_731_299, 22.02,  3.86, 72.91,  3.86,  9.64, 0.25),
    1999: (53_543_167, 11_900_254, 22.23,  3.12, 72.97,  3.12,  7.41, 1.06),
    2000: (69_566_247, 15_507_223, 22.29,  3.93, 71.83,  3.93,  8.44, 0.74),
    2001: (52_439_444, 11_981_382, 22.85,  5.60, 66.20,  5.60,  9.40, 1.78),
    2002: (41_623_784,  9_522_648, 22.88,  5.55, 61.57,  5.55, 16.73, 1.23),
    2003: (52_496_648, 10_250_277, 19.53,  4.91, 60.59,  4.91, 15.32, 0.36),
    2004: (69_110_866, 12_550_332, 18.16,  4.30, 56.86,  4.30, 14.31, 0.24),
    2005: (85_565_478, 15_599_966, 18.23,  6.71, 58.37,  6.71, 17.47, 0.71),
    2006:(105_322_274, 18_086_563, 17.17,  7.75, 62.75,  7.75, 14.37, 0.63),
    2007:(137_903_411, 22_924_540, 16.62,  7.85, 66.29,  7.85, 12.16, 0.11),
    2008:(108_204_064, 19_593_085, 18.11,  6.78, 56.81,  6.78, 19.92, 0.65),
    2009: (80_966_919, 16_116_865, 19.91,  6.63, 45.77,  6.63, 24.50, 0.64),
    2010:(106_054_960, 19_133_979, 18.04,  6.52, 55.57,  6.52, 19.72, 0.21),
    2011: (87_938_355, 15_047_444, 17.11,  5.54, 56.75,  5.54, 21.34, 0.61),
    2012:(134_277_630, 22_449_298, 16.72,  4.38, 56.85,  4.38, 13.71, 0.31),
    2013:(105_973_516, 24_257_763, 22.89,  5.75, 51.68,  5.75, 20.23, 1.25),
    2014:(127_127_267, 29_405_179, 23.13,  4.47, 65.16,  4.47, 16.24, 0.22),
}

FORBES_400_COUNT = 400

ss_wage_base_by_year = {
    1979:22900, 1980:25900, 1981:29700, 1982:32400, 1983:35700, 1984:37800,
    1985:39600, 1986:42000, 1987:43800, 1988:45000, 1989:48000, 1990:51300,
    1991:53400, 1992:55500, 1993:57600, 1994:60600, 1995:61200, 1996:62700,
    1997:65400, 1998:68400, 1999:72600, 2000:76200, 2001:80400, 2002:84900,
    2003:87000, 2004:87900, 2005:90000, 2006:94200, 2007:97500, 2008:102000,
    2009:106800, 2010:106800, 2011:106800, 2012:110100, 2013:113700, 2014:117000,
    2015:118500, 2016:118500, 2017:127200, 2018:128400, 2019:132900, 2020:137700,
    2021:142800, 2022:147000,
}
SS_OASDI_RATE   = 0.124
HI_MEDICARE_RATE= 0.029
HI_ACA_SURTAX   = 0.009

def get_ss_wage_base(year):
    if year in ss_wage_base_by_year:
        return ss_wage_base_by_year[year]
    sy = sorted(ss_wage_base_by_year)
    if year < sy[0]:  return ss_wage_base_by_year[sy[0]]
    if year > sy[-1]: return ss_wage_base_by_year[sy[-1]]
    for i in range(len(sy)-1):
        y0, y1 = sy[i], sy[i+1]
        if y0 <= year <= y1:
            f = (year-y0)/(y1-y0)
            return int(ss_wage_base_by_year[y0] + f*(ss_wage_base_by_year[y1]-ss_wage_base_by_year[y0]))

def to_float_safe(v):
    try:
        c = str(v).replace(",","").strip()
        return float(c) if set(c).issubset(set(".-0123456789")) else np.nan
    except:
        return np.nan

def build_path(f):
    """Resolve a raw input file by recursive search under DATA_ROOT.

    Falls back to ``<DATA_ROOT>/<f>`` (which will likely fail at the
    require_file gate) if no match is found, so error messages remain
    informative.
    """
    found = find_file(f)
    return found if found else os.path.join(DATA_ROOT, f)

def upstream_path(f):
    """Resolve a panel CSV produced by upstream scripts (lives in OUTPUT_DIR)."""
    return os.path.join(OUTPUT_DIR, f)

def require_file(path):
    if not os.path.exists(path):
        raise FileNotFoundError(f"REQUIRED FILE MISSING: {path}")
    return path

def require_value(val, name, year=None, group=None):
    if val is None or (isinstance(val, float) and np.isnan(val)):
        ctx = f" (year={year}, group={group})" if year else ""
        raise ValueError(f"REQUIRED VALUE IS NaN/None: {name}{ctx} — fix data source, do not add a fallback")
    return val

# ---------------------------------------------------------------------------
# STEP -2: Upstream panels — REQUIRED, no fallbacks
# ---------------------------------------------------------------------------
print("\n" + "="*70)
print("STEP -2: Loading upstream earned income and transfer panels (REQUIRED)...")
print("="*70)

_cbo_label_to_upstream = {
    "lowest_quintile":  "Bottom",
    "second_quintile":  "Second",
    "middle_quintile":  "Middle",
    "fourth_quintile":  "Fourth",
    "highest_quintile": "Top",
}

_earned_path   = require_file(upstream_path("earned_income_panel.csv"))
_transfer_path = require_file(upstream_path("transfer_distribution_panel.csv"))
_tax_path      = require_file(upstream_path("tax_distribution_panel.csv"))
_priv_path     = require_file(upstream_path("income_after_taxes_transfers_panel.csv"))

_earned_lookup   = {}  # {year: {label: dollars}}
_transfer_lookup = {}  # {year: {label: dollars}}
_tax_lookup      = {}  # {year: {label: {col: dollars}}}
_priv_lookup     = {}  # {year: {label: dollars}}

_ei = pd.read_csv(_earned_path)
for _, row in _ei.iterrows():
    yr = int(row["income_year"])
    q  = str(row.get("quintile_name", row.get("quintile",""))).strip().capitalize()
    _earned_lookup.setdefault(yr, {})[q] = float(row["total"])
print(f"  Loaded earned_income_panel:      {len(_earned_lookup)} years ({min(_earned_lookup)}–{max(_earned_lookup)})")

_tr = pd.read_csv(_transfer_path)
for _, row in _tr.iterrows():
    yr = int(row["income_year"])
    q  = str(row["quintile"]).strip().capitalize()
    if q == "Average": continue
    _transfer_lookup.setdefault(yr, {})[q] = float(row["total_govt"])
print(f"  Loaded transfer_distribution_panel: {len(_transfer_lookup)} years ({min(_transfer_lookup)}–{max(_transfer_lookup)})")

# Upstream tax panel: methodologically consistent federal + S&L tax values per
# quintile.  This is what we anchor sub-groups to (instead of reading CBO T07
# directly, which uses a different tax decomposition that doesn't include
# OMB-derived items like estate, customs, FUTA, railroad).
_tx = pd.read_csv(_tax_path)
for _, row in _tx.iterrows():
    yr = int(row["income_year"])
    q  = str(row["quintile"]).strip().capitalize()
    if q == "Average": continue
    _tax_lookup.setdefault(yr, {})[q] = {
        "fed_pit":     float(row.get("fed_pit",     0)),
        "fed_payroll": float(row.get("fed_payroll", 0)),
        "fed_other":   float(row.get("fed_other",   0)),
        "fed_total":   float(row.get("fed_total",   0)),
        "sl_sales":            float(row.get("sl_sales",            0)),
        "sl_income":           float(row.get("sl_income",           0)),
        "sl_property_other":   float(row.get("sl_property_other",   0)),
        "sl_total":            float(row.get("sl_total",            0)),
        "total_taxes":         float(row.get("total_taxes",         0)),
    }
print(f"  Loaded tax_distribution_panel:    {len(_tax_lookup)} years ({min(_tax_lookup)}–{max(_tax_lookup)})")

# Private transfers: per-HH per-quintile from the assembled IAT panel.
# Three peer-reviewed components, computed in income_after_taxes_transfers_panel.py.
_pv = pd.read_csv(_priv_path)
for _, row in _pv.iterrows():
    yr = int(row["income_year"])
    q  = str(row["quintile"]).strip().capitalize()
    if q == "Average": continue
    _priv_lookup.setdefault(yr, {})[q] = float(row.get("priv_transfers", 0))
print(f"  Loaded income_after_taxes_transfers_panel (priv_transfers): "
      f"{len(_priv_lookup)} years ({min(_priv_lookup)}–{max(_priv_lookup)})")

def get_priv_transfers(income_year, cbo_key):
    """Return upstream per-HH private transfer for a quintile (None for sub-groups)."""
    label = _cbo_label_to_upstream.get(cbo_key)
    if label is None:
        return None
    val = _priv_lookup.get(income_year, {}).get(label)
    return require_value(val, f"priv_transfers[{label}]", year=income_year)

def compute_priv_for_subgroup(income_year, subgroup_income, top_q_avg_income):
    """
    Income-elasticity decay for sub-groups (81-90 ... Forbes 400).

    Anchored to upstream Top quintile per-HH private transfer; scaled by
    sqrt(top_q_avg_income / subgroup_avg_income).  Capped at the upstream
    Top quintile per-HH (no upward scaling) and floored at zero.
    """
    top_priv = _priv_lookup.get(income_year, {}).get("Top")
    if top_priv is None or top_priv <= 0:
        return 0.0
    if subgroup_income is None or subgroup_income <= 0 or top_q_avg_income <= 0:
        return float(top_priv)
    # Decay factor: sub-groups have higher income than Top quintile average,
    # so factor < 1.  Sqrt elasticity is sub-linear (private transfers fall
    # but don't vanish at billionaire incomes).
    decay = (top_q_avg_income / subgroup_income) ** 0.5
    decay = min(1.0, max(0.0, decay))
    return float(top_priv) * decay

def get_upstream_tax(income_year, cbo_key, col):
    label = _cbo_label_to_upstream.get(cbo_key)
    if label is None:
        return None
    yr_dict = _tax_lookup.get(income_year, {})
    grp_dict = yr_dict.get(label)
    if grp_dict is None:
        return None
    return grp_dict.get(col)

def get_earned_income(income_year, cbo_key):
    label = _cbo_label_to_upstream.get(cbo_key)
    if label is None:
        raise KeyError(f"No upstream label for CBO key '{cbo_key}'")
    val = _earned_lookup.get(income_year, {}).get(label)
    return require_value(val, f"earned_income[{label}]", year=income_year)

def get_govt_transfers(income_year, cbo_key):
    label = _cbo_label_to_upstream.get(cbo_key)
    if label is None:
        raise KeyError(f"No upstream label for CBO key '{cbo_key}'")
    val = _transfer_lookup.get(income_year, {}).get(label)
    return require_value(val, f"govt_transfers[{label}]", year=income_year)

# ---------------------------------------------------------------------------
# CEX PANEL
# ---------------------------------------------------------------------------
def load_cex_weights_panel():
    cex_path = require_file(build_path("cex_sales_tax_distribution_weights_detailed_COMPLETE.csv"))
    df = pd.read_csv(cex_path)
    panel = {}
    for _, row in df.iterrows():
        yr = int(row["year"])
        ck = _cex_csv_label_to_cbo_key.get(str(row["quintile"]).strip())
        if ck is None: continue
        panel.setdefault(yr, {})[ck] = float(row["normalized_weight"])
    return panel

def get_cex_shares_for_year(panel, year):
    if year in panel: return panel[year]
    earlier = sorted(y for y in panel if y <= year)
    if not earlier:
        raise ValueError(f"CEX panel has no data for year={year} or earlier")
    return panel[max(earlier)]

print("\n" + "="*70)
print("STEP -1: Loading BLS CEX year-specific expenditure share panel...")
print("="*70)
cex_panel = load_cex_weights_panel()
print(f"  Loaded CEX weights for {len(cex_panel)} years ({min(cex_panel)}–{max(cex_panel)})")

# ---------------------------------------------------------------------------
# CBO TABLES
# ---------------------------------------------------------------------------
print("\n" + "="*70)
print("STEP 0: Loading CBO tables (all years)...")
print("="*70)

def load_cbo_table(n):
    fp = find_cbo_table(n)
    print(f"  T{n:02d}: {os.path.basename(fp)}")
    return normalize_cbo_columns(pd.read_csv(fp))

cbo_t01 = load_cbo_table(1)
cbo_t03 = load_cbo_table(3)
cbo_t05 = load_cbo_table(5)
cbo_t06 = load_cbo_table(6)   # Means-tested transfers (for sub-group MT shape)
cbo_t07 = load_cbo_table(7)

def slice_cbo_for_year(df, year, htype="all_households"):
    mask = (df["household_type"]==htype) & (df["year"]==year)
    sub  = df[mask].copy()
    if sub.empty: return None
    return sub.set_index("income_group").drop(columns=["household_type","year"], errors="ignore")

# ---------------------------------------------------------------------------
# IRS SOI T41TS  —  BUG A + BUG B FIXED
# ---------------------------------------------------------------------------
print("\nSTEP 1: Loading IRS SOI Table 4.1 time-series...")

t41ts_column_map = {
    "total":1, "top0.001":2, "top0.01":3, "top0.1":4, "top1":5,
    "top2":6,  "top5":7,     "top10":8,   "top25":10, "top50":13,
}

# IRS T41TS XLS has a fixed structure (verified against 22in41ts.xls):
# The file is a single wide sheet.  Section data rows are at fixed offsets:
#
#   Row 6       "Number of returns:" header
#   Rows 7–28   n_returns data  (2001–2022, one row per year)
#   Row 29      "Adjusted gross income floor..." header  ← NOT parsed (causes contamination)
#   Row 75      "Adjusted gross income (millions of dollars):" header
#   Rows 76–97  agi_m data      (2001–2022)
#   Row 98      "Total income tax (millions of dollars):" header
#   Rows 99–120 tax_m data      (2001–2022)
#   Row 121     "Average tax rate (percentage):" header
#   Rows 122–143 avg_rate data  (2001–2022)
#
# Columns (0-indexed):
#   1=Total  2=Top0.001%  3=Top0.01%  4=Top0.1%  5=Top1%  6=Top2%  7=Top3%
#
# Using hard-coded offsets (like v4) avoids ALL section-boundary contamination bugs.

T41TS_SECTIONS = {
    "n_returns": 6,    # header row; data at +1..+22
    "agi_m":     75,
    "tax_m":     98,
    "avg_rate":  121,
}
T41TS_YEARS = list(range(2001, 2023))  # 22 years → 22 data rows per section

# Recursive glob — picks up the IRS T41TS file from anywhere under data/raw/
# (e.g. data/raw/irs_soi/22in41ts.xls).  IRS_T41TS env var still takes priority.
t41ts_glob = sorted(
    glob.glob(os.path.join(DATA_ROOT, "**", "*in41ts*.xls"),  recursive=True) +
    glob.glob(os.path.join(DATA_ROOT, "**", "*in41ts*.xlsx"), recursive=True)
)
t41ts_filepath = os.environ.get("IRS_T41TS") or (t41ts_glob[-1] if t41ts_glob else None)

if not t41ts_filepath or not os.path.exists(str(t41ts_filepath)):
    raise FileNotFoundError(
        "REQUIRED FILE MISSING: IRS T41TS file (*in41ts*.xls).  "
        "Set IRS_T41TS env var or place the file in the script directory."
    )

print(f"  File: {os.path.basename(t41ts_filepath)}")
raw = pd.read_excel(t41ts_filepath, header=None, sheet_name=0)
print(f"  Shape: {raw.shape}")

# Verify section headers at expected rows so a format change causes a hard crash
_expected_headers = {
    6:   "number of returns",
    75:  "adjusted gross income (millions",
    98:  "total income tax (millions",
    121: "average tax rate",
}
for row_idx, expected_fragment in _expected_headers.items():
    actual = str(raw.iloc[row_idx, 0]).strip().lower()
    if expected_fragment not in actual:
        raise ValueError(
            f"T41TS FORMAT CHANGED — row {row_idx} expected to contain "
            f"'{expected_fragment}' but found: '{actual[:80]}'"
        )

t41ts_data = {}

for metric, header_row in T41TS_SECTIONS.items():
    for offset, yr in enumerate(T41TS_YEARS):
        data_row = header_row + 1 + offset
        if data_row >= len(raw):
            raise ValueError(f"T41TS: ran out of rows reading {metric} for year {yr} (row {data_row})")
        # Verify the year value in col 0 matches what we expect
        try:
            actual_yr = int(float(str(raw.iloc[data_row, 0]).strip()))
        except:
            raise ValueError(f"T41TS: expected year {yr} at row {data_row} col 0, got '{raw.iloc[data_row, 0]}'")
        if actual_yr != yr:
            raise ValueError(f"T41TS: expected year {yr} at row {data_row} col 0, got {actual_yr} — file format may have changed")
        t41ts_data.setdefault(yr, {})
        for pk, ci in t41ts_column_map.items():
            t41ts_data[yr].setdefault(pk, {})
            try:
                val = float(str(raw.iloc[data_row, ci]).replace(",", "").strip())
            except:
                val = np.nan
            t41ts_data[yr][pk][metric] = val

print(f"  Loaded {len(t41ts_data)} years: {min(t41ts_data)}–{max(t41ts_data)}")


# Sanity: n_returns must be monotonically increasing as group gets larger (cumulative)
# top0.001 < top0.01 < top0.1 < top1 for each year
for yr in [2001, 2010, 2022]:
    vals = [t41ts_data[yr][pk]["n_returns"]
            for pk in ["top0.001","top0.01","top0.1","top1"]]
    for i in range(len(vals)-1):
        if vals[i] >= vals[i+1]:
            raise ValueError(
                f"T41TS {yr}: n_returns not strictly increasing across cumulative groups "
                f"{vals} — column map is wrong"
            )
print("  ✓ n_returns monotonicity check passed (2001, 2010, 2022)")

def get_t41ts_value(year, pk, metric):
    val = t41ts_data.get(year, {}).get(pk, {}).get(metric, np.nan)
    return val  # callers must require_value() themselves when the value is critical

# ---------------------------------------------------------------------------
# Forbes 400 — post-2014 extension via T41TS top0.001% ratios
# Ratios computed from 2001–2014 overlap; no fallback — if T41TS is missing
# this will propagate NaN and crash at require_value() downstream.
# ---------------------------------------------------------------------------
def compute_forbes400_extension_ratios():
    tr, ar = [], []
    for yr, tup in forbes400_irs_data.items():
        if yr < 2001: continue
        tm = t41ts_data.get(yr, {}).get("top0.001", {}).get("tax_m", np.nan)
        am = t41ts_data.get(yr, {}).get("top0.001", {}).get("agi_m", np.nan)
        if np.isnan(tm) or np.isnan(am) or tm <= 0 or am <= 0:
            continue
        # tup[0] = total_agi_k ($thousands), tup[1] = total_tax_k ($thousands)
        # T41TS agi_m / tax_m are in $millions for the top0.001% group
        tr.append((tup[1] / 1_000.0) / tm)   # both now in $millions
        ar.append((tup[0] / 1_000.0) / am)
    if not tr:
        raise ValueError(
            "Forbes 400 extension ratios: no overlap years found between "
            "forbes400_irs_data and T41TS top0.001%.  Check T41TS parsing."
        )
    tax_r, agi_r = float(np.median(tr)), float(np.median(ar))
    print(f"  [Forbes400] Extension ratios from {len(tr)} overlap years (2001–2014):")
    print(f"    Tax ratio (F400/top0.001%): {tax_r:.4f}  range {min(tr):.3f}–{max(tr):.3f}")
    print(f"    AGI ratio (F400/top0.001%): {agi_r:.4f}  range {min(ar):.3f}–{max(ar):.3f}")
    return tax_r, agi_r

print("\n  Computing Forbes 400 / top-0.001% extension ratios...")
FORBES400_TAX_RATIO, FORBES400_AGI_RATIO = compute_forbes400_extension_ratios()

def get_forbes400_data(year):
    """
    Returns (total_agi_k, total_tax_k, eff_rate, wp, cgp, dp, pp, bp).
    total_agi_k / total_tax_k are in $thousands for all 400 members.
    Raises ValueError for post-2014 years if T41TS top0.001% data is missing.
    Returns None for years before 1992 (no data at all).
    """
    if year in forbes400_irs_data:
        return forbes400_irs_data[year]
    if year < 1992:
        return None
    # Post-2014: derive from T41TS top0.001%
    t001_agi = get_t41ts_value(year, "top0.001", "agi_m")
    t001_tax = get_t41ts_value(year, "top0.001", "tax_m")
    require_value(t001_agi, f"T41TS top0.001% agi_m (for Forbes400 post-2014 estimate)", year=year)
    require_value(t001_tax, f"T41TS top0.001% tax_m (for Forbes400 post-2014 estimate)", year=year)
    # Convert T41TS millions → $thousands (same units as forbes400_irs_data)
    est_agi_k = t001_agi * FORBES400_AGI_RATIO * 1_000.0
    est_tax_k = t001_tax * FORBES400_TAX_RATIO * 1_000.0
    est_rate  = (est_tax_k / est_agi_k * 100) if est_agi_k > 0 else 0.0
    _, _, _, wp, cgp, dp, pp, bp = forbes400_irs_data[2014]  # income composition from last actual year
    return (est_agi_k, est_tax_k, round(est_rate, 2), wp, cgp, dp, pp, bp)

# ---------------------------------------------------------------------------
# IRS Table 3 income composition
# ---------------------------------------------------------------------------
# IRS publishes annual income composition by AGI percentile (top 0.001%,
# top 0.01%, top 0.1%, top 1%, etc.) for individual returns excluding
# dependents.  We use it to split AGI into labor / capital / pass-through
# components for ultra-top groups.
#
# Filename history: this used to be "Table 3" (NNin03etr.xls) for tax
# years 2014-2018, then IRS renumbered it to "Table 4.3" (NNin43ts.xls)
# starting with tax year 2019.  Same shape, same row order, same columns.
# The glob below picks up both naming conventions so the cache covers
# 2014-2022 once all files are present.
print("\nSTEP 2: Scanning for single-year IRS Table 3 / 4.3 composition files...")
irs_t3_row_map = {
    "all_returns":8,"top0.001":9,"top0.01":10,"top0.1":11,
    "top1":12,"top2":13,"top5":16,"top10":17,
}
irs_t3_col_map = {
    "n_returns":1,"agi_k":3,"wages_k":5,"interest_k":7,"dividends_k":9,
    "cap_gains_pref_k":15,"business_k":17,"partnerships_k":21,"income_tax_k":63,
}
irs_t3_composition_cache = {}
irs_t3_paths = sorted(
    glob.glob(os.path.join(DATA_ROOT, "**", "*in03etr*.xls"), recursive=True) +   # 2014-2018
    glob.glob(os.path.join(DATA_ROOT, "**", "*in43ts*.xls"),  recursive=True)     # 2019+
)
for fp in irs_t3_paths:
    fn = os.path.basename(fp)
    try:
        ys = int(fn[:2]); dy = 2000+ys if ys<80 else 1900+ys
        rt = pd.read_excel(fp, header=None)
        py = {}
        for gk, ri in irs_t3_row_map.items():
            if ri < len(rt):
                py[gk] = {cn:(to_float_safe(rt.iloc[ri,ci]) if ci<rt.shape[1] else np.nan)
                          for cn,ci in irs_t3_col_map.items()}
        irs_t3_composition_cache[dy] = py
        print(f"  Loaded Table 3 composition for {dy}: {fn}")
    except Exception as e:
        print(f"  Skipped {fn}: {e}")

def get_income_composition(year, pk, fallback_lp=0.0, fallback_cp=0.0, fallback_ip=0.0):
    comp = irs_t3_composition_cache.get(year, {}).get(pk)
    if comp:
        agi = comp.get("agi_k", 0) or 0
        if agi > 0:
            w  = comp.get("wages_k",          0) or 0
            cg = comp.get("cap_gains_pref_k",  0) or 0
            dv = comp.get("dividends_k",        0) or 0
            pt = comp.get("partnerships_k",     0) or 0
            bs = comp.get("business_k",         0) or 0
            return (round(w/agi*100,1), round((cg+dv)/agi*100,1),
                    round((cg+dv+pt+bs)/agi*100,1))
    return fallback_lp, fallback_cp, fallback_ip

# ---------------------------------------------------------------------------
# STEP 3: CPS ASEC (S&L distributional weights)
# ---------------------------------------------------------------------------
print("\nSTEP 3: Loading CPS ASEC (S&L distributional weights)...")
raw_cps = None
cps_path = build_path("cps_00015.csv")
if os.path.exists(cps_path):
    raw_cps = pd.read_csv(cps_path, low_memory=False)
    print(f"  Loaded {len(raw_cps):,} records")
    for col, thr in niu_sentinels.items():
        if col in raw_cps.columns:
            raw_cps[col] = pd.to_numeric(raw_cps[col], errors="coerce").fillna(0)
            raw_cps.loc[raw_cps[col] >= thr, col] = 0
        else:
            raw_cps[col] = 0.0
    for col in list(niu_sentinels.keys()) + ["ASECWTH","OWNERSHP"]:
        if col in raw_cps.columns:
            raw_cps[col] = pd.to_numeric(raw_cps[col], errors="coerce").fillna(0)
else:
    print("  WARNING: CPS file not found — uniform quintile weights will be used for S&L")

cps_weights_cache = {}

def build_cps_sl_weights(income_year):
    survey_year = income_year + 1
    year_cex    = get_cex_shares_for_year(cex_panel, income_year)
    uniform     = {k: {"sales_share":year_cex.get(k,0.2),"property_share":0.2,
                       "income_share":0.2,"mv_other_share":year_cex.get(k,0.2)}
                   for k in cbo_quintile_keys}
    if raw_cps is None:
        return uniform
    yc = raw_cps[raw_cps["YEAR"]==survey_year]
    if yc.empty: yc = raw_cps[raw_cps["YEAR"]==income_year]
    if yc.empty: return uniform
    heads = yc[yc["RELATE"]==101].copy()
    heads = heads[heads["HHINCOME"]<9999990].dropna(subset=["HHINCOME","ASECWTH"])
    mkt_cols = ["INCWAGE","INCBUS","INCFARM","INCDIVID","INCINT","INCRENT","INCRETIR"]
    for c in mkt_cols:
        if c not in heads.columns: heads[c] = 0
    heads["market_income"] = heads[mkt_cols].clip(lower=0).sum(axis=1)
    wts = heads["ASECWTH"].values; incs = heads["market_income"].values
    order = np.argsort(incs); cumw = np.cumsum(wts[order]); totw = cumw[-1]
    thresholds = [incs[order[min(np.searchsorted(cumw, q*totw), len(order)-1)]]
                  for q in [0.2,0.4,0.6,0.8]]
    def assign_q(v):
        for i,t in enumerate(thresholds):
            if v <= t: return cbo_quintile_keys[i]
        return cbo_quintile_keys[-1]
    heads["qkey"] = heads["market_income"].apply(assign_q)
    heads["is_owner"]   = (heads["OWNERSHP"].isin([10,12]).astype(float)
                           if "OWNERSHP" in heads.columns else 0.5)
    heads["prop_proxy"] = heads["is_owner"] * heads["HHINCOME"].clip(lower=0)
    heads["inc_proxy"]  = heads["INCWAGE"].clip(lower=0)
    prop_tot = {k:(heads[heads["qkey"]==k]["prop_proxy"]*heads[heads["qkey"]==k]["ASECWTH"]).sum()
                for k in cbo_quintile_keys}
    inc_tot  = {k:(heads[heads["qkey"]==k]["inc_proxy"] *heads[heads["qkey"]==k]["ASECWTH"]).sum()
                for k in cbo_quintile_keys}
    tp = sum(prop_tot.values()) or 1
    ti = sum(inc_tot.values())  or 1
    return {k: {"sales_share":    year_cex.get(k, 0.2),
                "property_share": prop_tot[k]/tp,
                "income_share":   inc_tot[k]/ti,
                "mv_other_share": year_cex.get(k, 0.2)}
            for k in cbo_quintile_keys}

print("  Building CPS weight cache for all years...")
for yr in income_years_to_run:
    cps_weights_cache[yr] = build_cps_sl_weights(yr)
print(f"  Done — {len(cps_weights_cache)} years cached")

# ---------------------------------------------------------------------------
# STEP 4: S&L tax computation (identical methodology to tax_distribution_panel.py)
# ---------------------------------------------------------------------------
tpc_results_file = build_path("results.csv") if os.path.exists(build_path("results.csv")) else None

def get_sl_national_totals(year):
    if tpc_results_file:
        try:
            return load_tpc_sl_finance(year, filepath=tpc_results_file)
        except:
            pass
    return None

def compute_sl_taxes_for_all_groups(year, cps_weights, households_per_quintile,
                                     group_income_map, group_n_hh_map,
                                     top_q_avg_income):
    sl_nat = get_sl_national_totals(year)
    zeros  = {"sl_sales":0,"sl_property":0,"sl_income":0,"sl_other":0,"sl_total":0}
    if not sl_nat:
        return {k: zeros.copy() for k in list(group_income_map.keys())}

    sales_nat    = (sl_nat.get("general_sales",0) + sl_nat.get("selective_sales",0)) * 1000
    property_nat =  sl_nat.get("property",0)           * 1000
    income_nat   =  sl_nat.get("individual_income",0)  * 1000
    mv_other_nat =  sl_nat.get("other_taxes",0)        * 1000

    raw_sales={}; raw_property={}; raw_income={}; raw_mv_other={}
    for qk in cbo_quintile_keys:
        w = cps_weights.get(qk, {})
        raw_sales[qk]    = w.get("sales_share",    0.2)
        raw_property[qk] = w.get("property_share", 0.2)
        raw_income[qk]   = w.get("income_share",   0.2)
        raw_mv_other[qk] = w.get("mv_other_share", 0.2)

    top_q_sales    = raw_sales["highest_quintile"]
    top_q_property = raw_property["highest_quintile"]
    top_q_income   = raw_income["highest_quintile"]
    top_q_mv       = raw_mv_other["highest_quintile"]

    def income_ratio(gk):
        gi = group_income_map.get(gk, 0)
        return max(gi / top_q_avg_income, 1.0) if top_q_avg_income > 0 else 1.0

    def raw_share(tax_type, gk):
        r = income_ratio(gk)
        n = group_n_hh_map.get(gk, households_per_quintile)
        if   tax_type == "income":   elasticity = r
        elif tax_type == "property": elasticity = np.sqrt(r)
        else:                        elasticity = np.log1p(r) / np.log(2)
        hh_frac = n / households_per_quintile if households_per_quintile > 0 else 1.0
        if   tax_type == "income":   base = top_q_income
        elif tax_type == "property": base = top_q_property
        else:                        base = top_q_sales
        return base * elasticity * hh_frac

    above_keys = cbo_top_subgroup_keys + ["top0.1","top0.01","top0.001","forbes400"]
    for gk in above_keys:
        if gk not in group_income_map: continue
        raw_sales[gk]    = raw_share("sales",    gk)
        raw_property[gk] = raw_share("property", gk)
        raw_income[gk]   = raw_share("income",   gk)
        raw_mv_other[gk] = raw_share("mv",       gk)

    present = [k for k in raw_sales if k in group_income_map or k in cbo_quintile_keys]

    def normalize(d):
        total = sum(d.get(k,0) for k in present)
        if total <= 0: return {k: d.get(k,0) for k in present}
        return {k: d.get(k,0)/total for k in present}

    ns = normalize(raw_sales); np_ = normalize(raw_property)
    ni = normalize(raw_income); nm  = normalize(raw_mv_other)

    result = {}
    for gk in present:
        nhh = group_n_hh_map.get(gk, households_per_quintile)
        if nhh <= 0:
            result[gk] = zeros.copy(); continue
        sl_s = round(sales_nat    * ns.get(gk,0) / nhh)
        sl_p = round(property_nat * np_.get(gk,0) / nhh)
        sl_i = round(income_nat   * ni.get(gk,0) / nhh)
        sl_o = round(mv_other_nat * nm.get(gk,0) / nhh)
        result[gk] = {"sl_sales":sl_s,"sl_property":sl_p,"sl_income":sl_i,
                      "sl_other":sl_o,"sl_total":sl_s+sl_p+sl_i+sl_o}
    return result

# ---------------------------------------------------------------------------
# STEP 5: Main panel loop
# ---------------------------------------------------------------------------
print("\nSTEP 5: Building panel for all years...")
print("="*70)

all_panel_rows = []

for income_year in income_years_to_run:
    print(f"  {income_year}...", end=" ", flush=True)

    t01_yr = slice_cbo_for_year(cbo_t01, income_year)
    t03_yr = slice_cbo_for_year(cbo_t03, income_year)
    t05_yr = slice_cbo_for_year(cbo_t05, income_year)
    t07_yr = slice_cbo_for_year(cbo_t07, income_year)

    if t01_yr is None or t03_yr is None or t07_yr is None:
        print("SKIP (no CBO data)"); continue

    n_total_hh          = int(t01_yr.loc["all_quintiles","num_households"]*1e6) \
                          if "all_quintiles" in t01_yr.index else 125_000_000
    households_per_quintile = n_total_hh // 5
    irs_data_available  = income_year in t41ts_data

    if irs_data_available:
        irs_tot_ret = get_t41ts_value(income_year, "total", "n_returns")
        if np.isnan(irs_tot_ret) or irs_tot_ret <= 0:
            raise ValueError(
                f"T41TS total n_returns is NaN/zero for {income_year} — "
                f"check hard-coded row offsets in T41TS_SECTIONS"
            )
        return_to_hh_ratio = n_total_hh / irs_tot_ret
    else:
        return_to_hh_ratio = None  # only used inside irs_data_available block

    ss_wage_base       = get_ss_wage_base(income_year)
    hi_surtax_threshold = 200_000 if income_year >= 2013 else 1e12

    # cbo_implied_corp_rate: ONLY used for IRS ultra-top rows (no T07 per-group data)
    cbo_implied_corp_rate = 0.0
    if "top_1_percent" in t07_yr.index and "top_1_percent" in t03_yr.index:
        tc = float(t07_yr.loc["top_1_percent","corporate_income_tax"])
        mi = float(t03_yr.loc["top_1_percent","market_income"])
        if mi > 0:
            cbo_implied_corp_rate = tc / mi

    # ─────────────────────────────────────────────────────────────────────
    # SUB-GROUP TRANSFER ALLOCATION (methodologically consistent with upstream)
    # ─────────────────────────────────────────────────────────────────────
    # The upstream transfer_distribution_panel.csv computes per-quintile transfers
    # using BEA national aggregates × CBO quintile shares ÷ households-per-quintile.
    # That panel only has 5 quintiles. For sub-groups (81-90 ... top_1_percent)
    # and ultra-top (top 0.1, 0.01, 0.001, Forbes 400) we extend this by:
    #
    #   1. Take the upstream "top" quintile transfer total (per HH)
    #   2. Read CBO Table 05/06 sub-group transfer values directly (these come
    #      from the same CBO market-income ranking, but for finer subgroups)
    #   3. Use CBO sub-group / CBO top-quintile RATIO to scale upstream Top down
    #      to each sub-group, preserving internal consistency.
    #
    # This keeps the level (matches upstream) AND the relative shape (matches CBO).
    # CBO T05 has: social_insurance_benefits (= OASI + Medicare + UI + WC + ...)
    # CBO T06 has: means_tested_transfers      (= Medicaid + SNAP + SSI + Other)

    # Get upstream Top quintile transfer total (the anchor)
    upstream_top_govt = get_govt_transfers(income_year, "highest_quintile")

    # Get CBO Top quintile transfer values (the denominator for ratios)
    t06_yr = slice_cbo_for_year(cbo_t06, income_year)
    cbo_top_si = float(t05_yr.loc["highest_quintile", "social_insurance_benefits"]) \
                 if t05_yr is not None and "highest_quintile" in t05_yr.index else 0.0
    cbo_top_mt = float(t06_yr.loc["highest_quintile", "means_tested_transfers"]) \
                 if t06_yr is not None and "highest_quintile" in t06_yr.index else 0.0
    cbo_top_govt = cbo_top_si + cbo_top_mt

    def upstream_consistent_subgroup_transfers(cbo_subgroup_key):
        """
        Return (si, mt, total) for a CBO sub-group within the top quintile,
        scaled so that the magnitude is consistent with the upstream panel.

        Method: anchor to upstream Top quintile total, scale by sub-group/Top
        ratios from CBO T05 (SI) and T06 (MT) separately.
        """
        if cbo_subgroup_key not in t05_yr.index or cbo_top_govt <= 0:
            return 0.0, 0.0, 0.0
        cbo_sub_si = float(t05_yr.loc[cbo_subgroup_key, "social_insurance_benefits"]) \
                     if t05_yr is not None and cbo_subgroup_key in t05_yr.index else 0.0
        cbo_sub_mt = float(t06_yr.loc[cbo_subgroup_key, "means_tested_transfers"]) \
                     if t06_yr is not None and cbo_subgroup_key in t06_yr.index else 0.0
        # Component-wise ratio scaling: each component preserves its CBO shape
        # but the total magnitude is anchored to upstream Top quintile.
        # Scale = upstream_top_total / cbo_top_total
        scale = upstream_top_govt / cbo_top_govt if cbo_top_govt > 0 else 1.0
        si_scaled = cbo_sub_si * scale
        mt_scaled = cbo_sub_mt * scale
        return si_scaled, mt_scaled, si_scaled + mt_scaled

    # Top 1% transfers — used for IRS ultra-top rows (which have no CBO sub-group)
    top1_si, top1_mt, top1_govt_transfers = upstream_consistent_subgroup_transfers("top_1_percent")

    top_q_avg_income = float(t03_yr.loc["highest_quintile","market_income"]) \
                       if "highest_quintile" in t03_yr.index else 1.0

    # Top 1% private transfers — used as the upstream Top1% anchor for ultra-top decay.
    # Sub-group rows fall back to compute_priv_for_subgroup() which uses Top quintile
    # as the anchor, so this is consistent.
    cbo_top1_avg_income = float(t03_yr.loc["top_1_percent","market_income"]) \
                          if "top_1_percent" in t03_yr.index else top_q_avg_income
    top1_priv_transfers = compute_priv_for_subgroup(
        income_year, cbo_top1_avg_income, top_q_avg_income,
    )

    # Pre-gather income + n_hh for ALL groups (needed for SL computation)
    group_income_map = {}
    group_n_hh_map   = {}

    for gk in all_cbo_keys:
        if gk not in t03_yr.index: continue
        group_income_map[gk] = float(t03_yr.loc[gk,"market_income"])
        nhm = float(t01_yr.loc[gk,"num_households"]) if gk in t01_yr.index else np.nan
        group_n_hh_map[gk]   = int(nhm*1e6) if not np.isnan(nhm) else households_per_quintile

    # IRS ultra-top groups (add to maps regardless of year gate so sl_all sees them)
    if irs_data_available:
        fallback_lp = fallback_cp = fallback_ip = 0.0
        if t05_yr is not None and "top_1_percent" in t05_yr.index:
            mi_ref = float(t03_yr.loc["top_1_percent","market_income"]) \
                     if "top_1_percent" in t03_yr.index else 1.0
            if mi_ref > 0:
                try:
                    w  = float(t05_yr.loc["top_1_percent","wages"])          if "wages"          in t05_yr.columns else 0
                    cg = float(t05_yr.loc["top_1_percent","capital_gains"])  if "capital_gains"  in t05_yr.columns else 0
                    dv = float(t05_yr.loc["top_1_percent","dividends"])      if "dividends"      in t05_yr.columns else 0
                    fallback_lp = w/mi_ref*100; fallback_cp = (cg+dv)/mi_ref*100; fallback_ip = fallback_cp
                except:
                    pass

        for pk in ["top0.1","top0.01","top0.001"]:
            n_ret = get_t41ts_value(income_year, pk, "n_returns")
            agi_m = get_t41ts_value(income_year, pk, "agi_m")
            require_value(n_ret, f"T41TS {pk} n_returns", year=income_year)
            require_value(agi_m, f"T41TS {pk} agi_m",     year=income_year)
            if n_ret <= 0 or agi_m <= 0:
                raise ValueError(f"T41TS {pk} n_returns or agi_m is zero for {income_year}")
            group_income_map[pk] = agi_m * 1e6 / n_ret
            group_n_hh_map[pk]   = round(n_ret * return_to_hh_ratio)

    # Forbes 400 — always populate income map if data exists (BUG D FIX)
    f400_data = get_forbes400_data(income_year)
    if f400_data is not None:
        f400_agi_k = f400_data[0]
        # total_agi_k ($thousands for all 400) → per-person dollars
        group_income_map["forbes400"] = f400_agi_k * 1_000.0 / FORBES_400_COUNT
        group_n_hh_map["forbes400"]   = FORBES_400_COUNT

    # S&L computation — now runs for ALL years (BUG D FIX: outside irs_data_available)
    zeros_sl = {"sl_sales":0,"sl_property":0,"sl_income":0,"sl_other":0,"sl_total":0}
    sl_all = compute_sl_taxes_for_all_groups(
        year=income_year,
        cps_weights=cps_weights_cache[income_year],
        households_per_quintile=households_per_quintile,
        group_income_map=group_income_map,
        group_n_hh_map=group_n_hh_map,
        top_q_avg_income=top_q_avg_income,
    )

    # ─────────────────────────────────────────────────────────────────────────
    # Section A: CBO quintile and top sub-group rows
    # ─────────────────────────────────────────────────────────────────────────
    for gk, gl in zip(all_cbo_keys, all_cbo_labels):
        if gk not in t03_yr.index: continue
        nhm   = float(t01_yr.loc[gk,"num_households"]) if gk in t01_yr.index else np.nan
        n_hh  = int(nhm*1e6) if not np.isnan(nhm) else households_per_quintile

        # BUG C FIX: earned_income from upstream panel only (no CBO fallback)
        earned  = get_earned_income(income_year, gk) if gk in _cbo_label_to_upstream else \
                  float(t03_yr.loc[gk,"market_income"])
        # Govt transfers: quintile rows from upstream panel; sub-group rows scaled
        # to be consistent with upstream Top quintile (see
        # upstream_consistent_subgroup_transfers above).
        if gk in _cbo_label_to_upstream:
            govt_tr = get_govt_transfers(income_year, gk)
            priv_tr = get_priv_transfers(income_year, gk)
            cbo_si  = float(t03_yr.loc[gk, "social_insurance_benefits"])
            cbo_mt  = float(t03_yr.loc[gk, "means_tested_transfers"])
            # Scale SI/MT components to match upstream total
            cbo_total_t03 = cbo_si + cbo_mt
            if cbo_total_t03 > 0:
                comp_scale = govt_tr / cbo_total_t03
                cbo_si = cbo_si * comp_scale
                cbo_mt = cbo_mt * comp_scale
        else:
            # Sub-group within top quintile (81-90, 91-95, 96-99, top_1_percent)
            cbo_si, cbo_mt, govt_tr = upstream_consistent_subgroup_transfers(gk)
            # Private transfers: income-elasticity decay from upstream Top per-HH
            priv_tr = compute_priv_for_subgroup(
                income_year,
                float(t03_yr.loc[gk,"market_income"]),
                top_q_avg_income,
            )

        cbo_market_income = float(t03_yr.loc[gk,"market_income"])

        # ────────────────────────────────────────────────────────────────────
        # FEDERAL TAX VALUES (methodologically consistent with upstream)
        # ────────────────────────────────────────────────────────────────────
        # Quintile rows (Bottom–Top): pull federal taxes directly from
        #   upstream tax_distribution_panel.csv (CBO T07 PIT+payroll +
        #   OMB-derived estate/customs/FUTA/railroad/other_ret distributed
        #   via T12 shares).
        # Sub-group rows (81-90, 91-95, 96-99, top_1_percent): scale upstream
        #   Top quintile values by CBO T07 sub-group/Top RATIOS for each
        #   component (PIT, payroll, other).  This anchors levels to upstream
        #   while preserving CBO's relative shape across sub-groups.
        if gk in _cbo_label_to_upstream:
            # Quintile row — read upstream directly
            up_pit   = get_upstream_tax(income_year, gk, "fed_pit")
            up_pay   = get_upstream_tax(income_year, gk, "fed_payroll")
            up_other = get_upstream_tax(income_year, gk, "fed_other")
            up_total = get_upstream_tax(income_year, gk, "fed_total")
            require_value(up_pit,   f"upstream fed_pit[{gk}]",   year=income_year)
            require_value(up_pay,   f"upstream fed_payroll[{gk}]", year=income_year)
            require_value(up_other, f"upstream fed_other[{gk}]",  year=income_year)
            require_value(up_total, f"upstream fed_total[{gk}]",  year=income_year)
            # Split excise out of upstream fed_other using CBO T07 per-HH excise.
            # Excise IS measured per-HH per-quintile by CBO (col: excise_taxes),
            # so we use real data instead of leaving it bundled into fed_other.
            cbo_excise_per_hh = float(t07_yr.loc[gk, "excise_taxes"]) if gk in t07_yr.index else 0.0
            fed_pit   = up_pit
            fed_pay   = up_pay
            fed_corp  = 0.0   # Corporate income tax excluded: not borne directly by households
            fed_exc   = cbo_excise_per_hh
            fed_other = up_other - cbo_excise_per_hh   # remainder = estate+customs+FUTA+RR+other_ret
            fed_total = up_total
        else:
            # Sub-group row (81-90, 91-95, 96-99, top_1_percent)
            # Step 1: Get CBO T07 values for this sub-group AND for Top quintile
            cbo_sub_pit   = float(t07_yr.loc[gk, "individual_income_tax"])
            cbo_sub_pay   = float(t07_yr.loc[gk, "payroll_taxes"])
            cbo_sub_corp  = float(t07_yr.loc[gk, "corporate_income_tax"])
            cbo_sub_exc   = float(t07_yr.loc[gk, "excise_taxes"])
            cbo_sub_total = float(t07_yr.loc[gk, "federal_taxes"])
            cbo_top_pit   = float(t07_yr.loc["highest_quintile", "individual_income_tax"])
            cbo_top_pay   = float(t07_yr.loc["highest_quintile", "payroll_taxes"])
            cbo_top_total = float(t07_yr.loc["highest_quintile", "federal_taxes"])

            # Step 2: Get upstream Top quintile values (the anchor)
            up_top_pit   = get_upstream_tax(income_year, "highest_quintile", "fed_pit")
            up_top_pay   = get_upstream_tax(income_year, "highest_quintile", "fed_payroll")
            up_top_other = get_upstream_tax(income_year, "highest_quintile", "fed_other")
            up_top_total = get_upstream_tax(income_year, "highest_quintile", "fed_total")
            require_value(up_top_pit,   "upstream Top fed_pit",   year=income_year)
            require_value(up_top_pay,   "upstream Top fed_payroll", year=income_year)
            require_value(up_top_other, "upstream Top fed_other",  year=income_year)
            require_value(up_top_total, "upstream Top fed_total",  year=income_year)

            # Step 3: Component-specific scaling — PIT and payroll scale by their
            # own CBO sub/top ratio; "other" scales by the implied total ratio
            # (since CBO doesn't break out OMB-derived items).
            pit_scale     = (up_top_pit / cbo_top_pit)   if cbo_top_pit   != 0 else 0.0
            pay_scale     = (up_top_pay / cbo_top_pay)   if cbo_top_pay   > 0 else 0.0
            other_scale   = (up_top_other / cbo_top_total) if cbo_top_total > 0 else 0.0

            fed_pit   = cbo_sub_pit * pit_scale
            fed_pay   = cbo_sub_pay * pay_scale
            fed_corp  = 0.0   # Corporate income tax excluded: not borne directly by households
            # Excise: use CBO T07 per-HH directly (real data, not a proxy)
            fed_exc   = cbo_sub_exc
            # "other" for sub-group: scale upstream Top "other-minus-excise"
            # by the same ratio used for fed_other above. CBO sub-group total
            # times other_scale gives the upstream-equivalent total fed_other,
            # then subtract the sub-group's own excise to isolate non-excise items.
            scaled_other_with_excise = cbo_sub_total * other_scale
            fed_other = scaled_other_with_excise - fed_exc
            # Compute fed_total from ROUNDED components for exact integer arithmetic
            fed_total = round(fed_pit) + round(fed_pay) + round(fed_exc) + round(fed_other)

        # ─────────────────────────────────────────────────────────────────────
        # S&L TAXES (methodologically consistent with upstream)
        # ─────────────────────────────────────────────────────────────────────
        # Quintile rows: read S&L directly from upstream tax_distribution_panel.
        # Sub-group rows: scale upstream Top quintile S&L total by the local
        #   sl_all sub-group/Top ratio for shape.  This anchors levels to
        #   upstream while preserving CBO/CEX-derived sub-group shape.
        local_sl = sl_all.get(gk, zeros_sl)
        if gk in _cbo_label_to_upstream:
            up_sl_sales    = get_upstream_tax(income_year, gk, "sl_sales")    or 0.0
            up_sl_income   = get_upstream_tax(income_year, gk, "sl_income")   or 0.0
            up_sl_propoth  = get_upstream_tax(income_year, gk, "sl_property_other") or 0.0
            up_sl_total    = get_upstream_tax(income_year, gk, "sl_total")    or 0.0
            sl = {
                "sl_sales":    round(up_sl_sales),
                "sl_income":   round(up_sl_income),
                # upstream combines property+mv_other; split using local ratio
                "sl_property": round(local_sl.get("sl_property", 0)),
                "sl_other":    round(up_sl_propoth - local_sl.get("sl_property", 0)) if up_sl_propoth >= local_sl.get("sl_property", 0) else round(up_sl_propoth),
                "sl_total":    round(up_sl_total),
            }
            # If upstream property+other doesn't itemize cleanly, just split upstream property_other
            # 50/50 between sl_property and sl_other (or use local ratio)
            if local_sl.get("sl_property", 0) + local_sl.get("sl_other", 0) > 0:
                local_propother = local_sl["sl_property"] + local_sl["sl_other"]
                sl["sl_property"] = round(up_sl_propoth * local_sl["sl_property"] / local_propother)
                sl["sl_other"]    = round(up_sl_propoth * local_sl["sl_other"]    / local_propother)
        else:
            # Sub-group: anchor to upstream Top quintile total via local sub/top ratio
            up_top_sl_total = get_upstream_tax(income_year, "highest_quintile", "sl_total") or 0.0
            local_top_sl = sl_all.get("highest_quintile", zeros_sl)
            local_top_total = local_top_sl.get("sl_total", 0)
            if local_top_total > 0 and up_top_sl_total > 0:
                sl_scale = up_top_sl_total / local_top_total
                sl = {
                    "sl_sales":    round(local_sl.get("sl_sales", 0)    * sl_scale),
                    "sl_income":   round(local_sl.get("sl_income", 0)   * sl_scale),
                    "sl_property": round(local_sl.get("sl_property", 0) * sl_scale),
                    "sl_other":    round(local_sl.get("sl_other", 0)    * sl_scale),
                    "sl_total":    round(local_sl.get("sl_total", 0)    * sl_scale),
                }
                # Round-trip: re-derive sl_total from rounded components
                sl["sl_total"] = sl["sl_sales"] + sl["sl_income"] + sl["sl_property"] + sl["sl_other"]
            else:
                sl = local_sl.copy()

        total_taxes   = round(fed_total + sl["sl_total"])
        income_after  = round(earned + govt_tr + priv_tr - total_taxes)
        # Signed effective tax rate: (taxes − transfers) / earned × 100.
        # Negative for net recipients (bottom quintiles), positive for net payers.
        # Denominator is earned income only — keeps the rate interpretable as
        # "taxes minus transfers, expressed as a share of what was earned in the market."
        eff_rate      = ((total_taxes - govt_tr - priv_tr) / earned * 100
                         if earned > 0 else 0)
        # Income after taxes & transfers, expressed as a percentage of earned
        # income. Above 100 means net transfers received exceed taxes paid;
        # below 100 means the household keeps less than it earned after the
        # combined fiscal system.
        iat_pct_earn  = (income_after / earned * 100) if earned > 0 else 0

        lp = cp = ip = 0.0
        if t05_yr is not None and gk in t05_yr.index and cbo_market_income > 0:
            try:
                w  = float(t05_yr.loc[gk,"wages"])           if "wages"            in t05_yr.columns else 0
                cg = float(t05_yr.loc[gk,"capital_gains"])   if "capital_gains"    in t05_yr.columns else 0
                dv = float(t05_yr.loc[gk,"dividends"])       if "dividends"        in t05_yr.columns else 0
                it = ((float(t05_yr.loc[gk,"taxable_interest"])   if "taxable_interest"   in t05_yr.columns else 0)+
                      (float(t05_yr.loc[gk,"tax_exempt_interest"]) if "tax_exempt_interest" in t05_yr.columns else 0))
                rn = float(t05_yr.loc[gk,"positive_rental_income"]) if "positive_rental_income" in t05_yr.columns else 0
                lp = w/cbo_market_income*100; cp=(cg+dv)/cbo_market_income*100
                ip=(cg+dv+it+rn)/cbo_market_income*100
            except:
                pass

        all_panel_rows.append(dict(
            income_year=income_year, group=gl,
            n_households_M=round(nhm,2) if not np.isnan(nhm) else np.nan,
            n_households=n_hh,
            earned_income=round(earned),
            govt_transfers=round(govt_tr),
            priv_transfers=round(priv_tr),
            income_after_transfers_taxes=income_after,
            iat_pct_earned=round(iat_pct_earn, 1),
            tax_rate_pct=round(eff_rate, 1),
            social_insurance=round(cbo_si), means_tested=round(cbo_mt),
            fed_pit=round(fed_pit), fed_payroll=round(fed_pay),
            fed_corp=round(fed_corp), fed_excise=round(fed_exc),
            fed_other=round(fed_other), fed_total=round(fed_total),
            sl_sales=sl["sl_sales"], sl_income=sl["sl_income"],
            sl_property=sl["sl_property"], sl_other=sl["sl_other"], sl_total=sl["sl_total"],
            total_taxes=total_taxes, irs_data_available=irs_data_available, source="CBO",
        ))

    # ─────────────────────────────────────────────────────────────────────────
    # Section B: IRS ultra-top rows  (only when T41TS data exists)
    # ─────────────────────────────────────────────────────────────────────────
    # Pre-compute the "other federal" anchor for ultra-top rows (used by both
    # IRS T41TS and Forbes 400 sections).  Upstream only publishes 5 quintiles,
    # so we use Top quintile fed_other and scale up to Top 1% via CBO T07
    # ratio, then to ultra-top via AGI ratio.
    up_top_other = get_upstream_tax(income_year, "highest_quintile", "fed_other") or 0.0
    cbo_top_total_t07 = float(t07_yr.loc["highest_quintile", "federal_taxes"]) \
                        if "highest_quintile" in t07_yr.index else 1.0
    cbo_top1_total_t07 = float(t07_yr.loc["top_1_percent", "federal_taxes"]) \
                         if "top_1_percent" in t07_yr.index else cbo_top_total_t07
    # Scale Top quintile fed_other up to Top 1% level using CBO total ratio.
    # This is the "other federal" per HH for Top 1% under upstream methodology.
    if cbo_top_total_t07 > 0:
        up_top1_other = up_top_other * (cbo_top1_total_t07 / cbo_top_total_t07)
    else:
        up_top1_other = up_top_other
    cbo_top1_agi = float(t03_yr.loc["top_1_percent", "market_income"]) \
                   if "top_1_percent" in t03_yr.index else 1.0

    # S&L scale factor (upstream Top / local Top) — used to scale ultra-top S&L
    # taxes to upstream methodology.  Same as we use for sub-group S&L.
    up_top_sl_total_for_ultra = get_upstream_tax(income_year, "highest_quintile", "sl_total") or 0.0
    local_top_sl_for_ultra    = sl_all.get("highest_quintile", zeros_sl)
    local_top_sl_total        = local_top_sl_for_ultra.get("sl_total", 0)
    sl_scale_ultra = (up_top_sl_total_for_ultra / local_top_sl_total) \
                     if local_top_sl_total > 0 and up_top_sl_total_for_ultra > 0 else 1.0

    def scale_sl_to_upstream(local_sl_dict):
        """Scale a local sl_dict by sl_scale_ultra (anchors to upstream Top)."""
        scaled = {
            "sl_sales":    round(local_sl_dict.get("sl_sales", 0)    * sl_scale_ultra),
            "sl_income":   round(local_sl_dict.get("sl_income", 0)   * sl_scale_ultra),
            "sl_property": round(local_sl_dict.get("sl_property", 0) * sl_scale_ultra),
            "sl_other":    round(local_sl_dict.get("sl_other", 0)    * sl_scale_ultra),
        }
        scaled["sl_total"] = scaled["sl_sales"] + scaled["sl_income"] + scaled["sl_property"] + scaled["sl_other"]
        return scaled

    if irs_data_available:
        def add_ultra_top_row(gl, n_ret, agi_m, tax_m, lp, cp, ip, pk):
            # All values are required — crash on NaN rather than silently skipping
            require_value(n_ret, f"{pk} n_ret",  year=income_year)
            require_value(agi_m, f"{pk} agi_m",  year=income_year)
            require_value(tax_m, f"{pk} tax_m",  year=income_year)
            if n_ret <= 0 or agi_m <= 0:
                raise ValueError(f"{pk} n_ret or agi_m is zero for {income_year}")

            n_hhu   = round(n_ret * return_to_hh_ratio)
            avg_agi = agi_m * 1e6 / n_ret
            avg_it  = tax_m * 1e6 / n_ret
            # Private transfers for ultra-top: same income-elasticity decay,
            # anchored to upstream Top quintile per-HH.  At billionaire incomes
            # this drops to a few dollars per HH — effectively zero in practice.
            ultra_priv = compute_priv_for_subgroup(
                income_year, avg_agi, top_q_avg_income,
            )
            est_wages = avg_agi * lp / 100
            payroll_t = (min(est_wages, ss_wage_base)*SS_OASDI_RATE +
                         est_wages*HI_MEDICARE_RATE +
                         max(0.0, est_wages-hi_surtax_threshold)*HI_ACA_SURTAX)
            # "Other federal" for ultra-top: scale upstream Top 1% other by
            # AGI ratio (corporate tax ≈ proportional to income at these levels).
            # Excise and estate components are weakly income-elastic but we keep
            # the AGI scaling for consistency.
            agi_ratio_to_top1 = (avg_agi / cbo_top1_agi) if cbo_top1_agi > 0 else 1.0
            # Estimate excise for ultra-top: scale Top 1% CBO excise by AGI ratio.
            # Excise on luxury goods scales weakly with income at this level.
            cbo_top1_excise = float(t07_yr.loc["top_1_percent", "excise_taxes"]) \
                              if "top_1_percent" in t07_yr.index else 0.0
            excise_t = cbo_top1_excise * agi_ratio_to_top1
            # "Other" portion: subtract excise from the upstream-scaled total
            other_t  = (up_top1_other * agi_ratio_to_top1) - excise_t
            # Compute fed_total from ROUNDED components so component sum check
            # passes exactly (rounding can drift ±$2-3 across 5 components).
            fed_tot = round(avg_it) + round(payroll_t) + round(excise_t) + round(other_t)
            sl      = scale_sl_to_upstream(sl_all.get(pk, zeros_sl))
            total_t = round(fed_tot + sl["sl_total"])
            ia      = round(avg_agi + top1_govt_transfers + ultra_priv - total_t)
            er      = ((total_t - top1_govt_transfers - ultra_priv) / avg_agi * 100
                       if avg_agi > 0 else 0)
            iat_pct = (ia / avg_agi * 100) if avg_agi > 0 else 0
            all_panel_rows.append(dict(
                income_year=income_year, group=gl,
                n_households_M=round(n_hhu/1e6,4), n_households=n_hhu,
                earned_income=round(avg_agi), govt_transfers=round(top1_govt_transfers),
                priv_transfers=round(ultra_priv),
                income_after_transfers_taxes=ia,
                iat_pct_earned=round(iat_pct, 1),
                tax_rate_pct=round(er, 1),
                social_insurance=round(top1_si), means_tested=round(top1_mt),
                fed_pit=round(avg_it), fed_payroll=round(payroll_t),
                fed_corp=0, fed_excise=round(excise_t),
                fed_other=round(other_t), fed_total=round(fed_tot),
                sl_sales=sl["sl_sales"], sl_income=sl["sl_income"],
                sl_property=sl["sl_property"], sl_other=sl["sl_other"], sl_total=sl["sl_total"],
                total_taxes=total_t, irs_data_available=True,
                source=f"IRS T41TS {pk} cumul",
            ))

        for pk, gl in [("top0.1","Top 0.1 percent"),("top0.01","Top 0.01 percent"),
                       ("top0.001","Top 0.001 percent")]:
            nr  = get_t41ts_value(income_year, pk, "n_returns")
            agi = get_t41ts_value(income_year, pk, "agi_m")
            tax = get_t41ts_value(income_year, pk, "tax_m")
            lp, cp, ip = get_income_composition(income_year, pk, fallback_lp, fallback_cp, fallback_ip)
            add_ultra_top_row(gl, nr, agi, tax, lp, cp, ip, pk)

    # ─────────────────────────────────────────────────────────────────────────
    # Section C: Forbes 400 — runs every year data exists (BUG D FIX)
    # ─────────────────────────────────────────────────────────────────────────
    if f400_data is not None:
        f4agi_k, f4tax_k, f4rate, f4wp, f4cgp, f4dp, f4pp, f4bp = f400_data

        # total_agi_k / total_tax_k are in $thousands for all 400 members
        avg_agi_f = f4agi_k * 1_000.0 / FORBES_400_COUNT   # per-person dollars
        avg_it_f  = f4tax_k * 1_000.0 / FORBES_400_COUNT

        lp_f = f4wp; cp_f = f4cgp + f4dp; ip_f = cp_f + f4pp + f4bp
        est_w_f  = avg_agi_f * lp_f / 100
        pay_f    = (min(est_w_f, ss_wage_base)*SS_OASDI_RATE +
                    est_w_f*HI_MEDICARE_RATE +
                    max(0.0, est_w_f-hi_surtax_threshold)*HI_ACA_SURTAX)
        # "Other federal" for Forbes 400: scale upstream Top 1% other by AGI ratio.
        # Same approach as IRS ultra-top rows for methodological consistency.
        agi_ratio_f = (avg_agi_f / cbo_top1_agi) if cbo_top1_agi > 0 else 1.0
        # Excise for Forbes 400: scale Top 1% CBO excise by AGI ratio (same as ultra-top)
        cbo_top1_excise_f = float(t07_yr.loc["top_1_percent", "excise_taxes"]) \
                            if "top_1_percent" in t07_yr.index else 0.0
        excise_f = cbo_top1_excise_f * agi_ratio_f
        other_f  = (up_top1_other * agi_ratio_f) - excise_f
        # Compute fed_total from ROUNDED components for exact integer arithmetic
        fed_f    = round(avg_it_f) + round(pay_f) + round(excise_f) + round(other_f)
        sl_f     = scale_sl_to_upstream(sl_all.get("forbes400", zeros_sl))
        total_f  = round(fed_f + sl_f["sl_total"])
        # Forbes 400 private transfers: extreme income decay — essentially zero
        forbes_priv = compute_priv_for_subgroup(
            income_year, avg_agi_f, top_q_avg_income,
        )
        ia_f     = round(avg_agi_f + top1_govt_transfers + forbes_priv - total_f)
        er_f     = ((total_f - top1_govt_transfers - forbes_priv) / avg_agi_f * 100
                    if avg_agi_f > 0 else 0)
        iat_pct_f = (ia_f / avg_agi_f * 100) if avg_agi_f > 0 else 0
        src_f    = "Forbes400 actual" if income_year in forbes400_irs_data else "Forbes400 T41TS est"

        all_panel_rows.append(dict(
            income_year=income_year, group="Forbes 400",
            n_households_M=round(FORBES_400_COUNT/1e6, 6),
            n_households=FORBES_400_COUNT,
            earned_income=round(avg_agi_f), govt_transfers=round(top1_govt_transfers),
            priv_transfers=round(forbes_priv),
            income_after_transfers_taxes=ia_f,
            iat_pct_earned=round(iat_pct_f, 1),
            tax_rate_pct=round(er_f, 1),
            social_insurance=round(top1_si), means_tested=round(top1_mt),
            fed_pit=round(avg_it_f), fed_payroll=round(pay_f),
            fed_corp=0, fed_excise=round(excise_f),
            fed_other=round(other_f), fed_total=round(fed_f),
            sl_sales=sl_f["sl_sales"], sl_income=sl_f["sl_income"],
            sl_property=sl_f["sl_property"], sl_other=sl_f["sl_other"], sl_total=sl_f["sl_total"],
            total_taxes=total_f, irs_data_available=(income_year in forbes400_irs_data),
            source=src_f,
        ))

    print("done")

# ---------------------------------------------------------------------------
# STEP 6: Sort and save
# ---------------------------------------------------------------------------
results_panel = pd.DataFrame(all_panel_rows)
group_order   = (all_cbo_labels +
                 ["Top 0.1 percent","Top 0.01 percent","Top 0.001 percent","Forbes 400"])
gmap = {g:i for i,g in enumerate(group_order)}
results_panel["_sk"] = results_panel["group"].map(gmap).fillna(99)
results_panel = results_panel.sort_values(["income_year","_sk"]).drop(columns=["_sk"])

output_csv  = os.path.join(OUTPUT_DIR, "top_percentile_taxes_transfers_panel.csv")
results_panel.to_csv(output_csv, index=False)

print("\n" + "="*70)
print("PANEL COMPLETE")
print("="*70)
print(f"  Output : {output_csv}")
print(f"  Rows   : {len(results_panel):,}")
print(f"  Groups : {sorted(results_panel['group'].unique())}")
yf = results_panel[results_panel['group']=='Forbes 400']['income_year']
print(f"  Forbes 400 years: {yf.min()}–{yf.max()} ({len(yf)} years)")

# ---------------------------------------------------------------------------
# STEP 7: Validation — must pass or script raises
# ---------------------------------------------------------------------------
print("\n" + "="*70)
print("STEP 7: Internal arithmetic validation (crashes on failure)")
print("="*70)

rp = results_panel.copy()
rp["_iat_check"]      = (rp.earned_income + rp.govt_transfers + rp.priv_transfers
                          - rp.total_taxes - rp.income_after_transfers_taxes).abs()
rp["_fedtot_check"]   = (rp.fed_pit + rp.fed_payroll + rp.fed_corp + rp.fed_excise + rp.fed_other - rp.fed_total).abs()
rp["_totaltax_check"] = (rp.fed_total + rp.sl_total - rp.total_taxes).abs()

bad_iat      = rp[rp._iat_check      > 1]
bad_fedtot   = rp[rp._fedtot_check   > 1]
bad_totaltax = rp[rp._totaltax_check > 1]

if len(bad_iat):
    raise AssertionError(f"IAT arithmetic broken for {len(bad_iat)} rows:\n{bad_iat[['income_year','group','_iat_check']].to_string()}")
if len(bad_fedtot):
    raise AssertionError(f"fed_total component sum broken for {len(bad_fedtot)} rows:\n{bad_fedtot[['income_year','group','_fedtot_check']].to_string()}")
if len(bad_totaltax):
    raise AssertionError(f"total_taxes = fed+sl broken for {len(bad_totaltax)} rows:\n{bad_totaltax[['income_year','group','_totaltax_check']].to_string()}")

print("  ✓  IAT = earned + govt + priv − total_taxes        (all rows)")
print("  ✓  fed_total = pit + payroll + corp + excise + other (all rows)")
print("  ✓  total_taxes = fed_total + sl_total              (all rows)")

# Monotonicity check: within each year, earned_income must increase as group gets smaller
mono_failures = []
order_within_year = ["Top 1 percent","Top 0.1 percent","Top 0.01 percent",
                     "Top 0.001 percent","Forbes 400"]
for yr, grp in results_panel.groupby("income_year"):
    gi = grp.set_index("group")["earned_income"]
    for i in range(len(order_within_year)-1):
        g0, g1 = order_within_year[i], order_within_year[i+1]
        if g0 in gi.index and g1 in gi.index:
            if gi[g0] >= gi[g1]:
                mono_failures.append(f"{yr}: {g0}={gi[g0]:,.0f} >= {g1}={gi[g1]:,.0f}")

if mono_failures:
    raise AssertionError(
        f"Monotonicity violation — earned_income must increase deeper into the top:\n" +
        "\n".join(mono_failures[:20])
    )
print("  ✓  Monotonicity: earned_income Top1% < Top0.1% < Top0.01% < Top0.001% < Forbes400")

# Cross-check upstream panel alignment
iat_path = upstream_path("income_after_taxes_transfers_panel.csv")
if os.path.exists(iat_path):
    iat = pd.read_csv(iat_path)
    mismatches = []
    for yr in [1990,1995,2000,2005,2010,2015,2019,2022]:
        for gl in ["Bottom","Second","Middle","Fourth","Top"]:
            tp_row  = results_panel[(results_panel.income_year==yr) & (results_panel.group==gl)]
            iat_row = iat[(iat.income_year==yr) & (iat.quintile==gl)]
            if tp_row.empty or iat_row.empty: continue
            ev = float(tp_row.iloc[0].earned_income); er = float(iat_row.iloc[0].earned)
            gv = float(tp_row.iloc[0].govt_transfers); gr = float(iat_row.iloc[0].govt_transfers)
            pv = float(tp_row.iloc[0].priv_transfers); pr = float(iat_row.iloc[0].priv_transfers)
            if abs(ev-er)/max(abs(er),1) > 0.005:
                mismatches.append(f"earned {yr} {gl}: tp={ev:,.0f} iat={er:,.0f}")
            if abs(gv-gr)/max(abs(gr),1) > 0.005:
                mismatches.append(f"govt   {yr} {gl}: tp={gv:,.0f} iat={gr:,.0f}")
            if abs(pv-pr)/max(abs(pr),1) > 0.005:
                mismatches.append(f"priv   {yr} {gl}: tp={pv:,.0f} iat={pr:,.0f}")
    if mismatches:
        raise AssertionError(
            "Upstream panel mismatch (earned/govt/priv don't match "
            "income_after_taxes_transfers_panel.csv):\n" + "\n".join(mismatches)
        )
    print("  ✓  earned + govt + priv transfers match income_after_taxes_transfers_panel.csv")

print(f"\nDone. Output: {output_csv}")
