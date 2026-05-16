"""
tax_distribution_panel.py
=========================

Builds a long-format panel of federal and state & local taxes per household
by income quintile, 1979-2022.  For each income year and each of the five
quintiles, the panel reports per-household dollars from:

    Federal taxes
        Personal income tax (CBO Table 07, per-HH averages)
        Payroll taxes — OASDI + HI (CBO Table 07)
        Other federal — excise + customs + estate/gift + FUTA + railroad
                        retirement + other retirement (CBO T07 + OMB control totals)
        Corporate income tax is NOT included in the household burden, since
        households don't write a check for it directly.

    State and local
        General + selective sales taxes  → distributed via BLS CEX consumption shares
        State individual income taxes    → distributed via CPS wage-income shares
        Property taxes                   → distributed via CPS homeownership × income
        Motor vehicle + other S&L taxes  → distributed via BLS CEX consumption shares

Data architecture
-----------------
National control totals come from administrative sources: CBO supplemental
tables 01, 07, and 12 for federal taxes and household counts; OMB Historical
Tables 2.1, 2.4, and 2.5 for excise/customs/estate/gift/FUTA/railroad/other-
retirement breakdowns; the TPC/Census State & Local Government Finance
extract (results.csv) for S&L aggregates.

Quintile-level distribution weights come from CBO Table 12 (federal),
CPS ASEC microdata via the IPUMS extract (state income tax and property
tax), and the BLS Consumer Expenditure Survey panel (sales and motor
vehicle taxes).  Households are ranked annually by market income from
the CPS so each quintile contains exactly 20 % of households in every year.

Output: output/tax_distribution_panel.csv
"""

import os
import glob
import warnings
import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")


# ----------------------------------------------------------------------------
# File paths — repo-aware
# ----------------------------------------------------------------------------
# This script is meant to live at <repo>/src/.  It walks up the directory
# tree until it finds a "data/raw" folder, then searches recursively for
# input files.  Output goes to <repo>/output/.
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


def find_file(pattern, base_dir=None, must_exist=False):
    """Recursively search `base_dir` (DATA_ROOT by default) for a file
    matching `pattern`.  Returns the latest match (alphabetical sort), or
    None.  Raises FileNotFoundError when must_exist=True and nothing matches."""
    base_dir = base_dir or DATA_ROOT
    matches = sorted(glob.glob(os.path.join(base_dir, "**", pattern),
                               recursive=True))
    if matches:
        return matches[-1]
    if must_exist:
        raise FileNotFoundError(
            f"No file matching '{pattern}' found under {base_dir}"
        )
    return None


def find_cbo_table(table_num):
    """Find a CBO supplemental table CSV by number (1-13).
    CBO ships these as 'households_ranked_by_market_inc_table_NN_*_1979_*.csv'.
    Returns the latest match.  Raises FileNotFoundError if nothing matches."""
    pattern = f"households_ranked_by_market_inc_table_{table_num:02d}_*_1979_*.csv"
    return find_file(pattern, must_exist=True)


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
        # Year column may be stored as string
        mask2 = (df[state_col] == "United States") & (
            df[year_col].astype(str).str.strip() == str(year)
        )
        row = df[mask2]
    if row.empty:
        available = sorted(df[df[state_col] == "United States"][year_col].unique())
        raise ValueError(f"Year {year} not in {filepath}. Available: {available}")
    row = row.iloc[0]

    def get_col(partials):
        """Find first column whose name contains any partial string, parse as $ thousands."""
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

    # Residual "other taxes" picks up motor vehicle licenses, severance, etc.
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
# Constants and label mappings
# ---------------------------------------------------------------------------

income_years_to_run = range(1979, 2023)

# CBO income_group labels as they appear in the raw CSVs
cbo_quintile_keys = [
    "lowest_quintile",
    "second_quintile",
    "middle_quintile",
    "fourth_quintile",
    "highest_quintile",
]

# Display labels (Title Case) and short internal keys
quintile_display_labels = ["Bottom", "Second", "Middle", "Fourth", "Top"]
quintile_short_keys     = ["bottom", "second", "middle", "fourth", "top"]

# Maps the BLS CEX CSV's verbose quintile labels to our short keys
cex_label_to_short_key = {
    "Q1 (Bottom 20%)": "bottom",
    "Q2 (Second 20%)": "second",
    "Q3 (Middle 20%)": "middle",
    "Q4 (Fourth 20%)": "fourth",
    "Q5 (Top 20%)":    "top",
}

# CPS "not in universe" sentinel values — any value at or above these is
# a placeholder (not actual income) and should be treated as zero
niu_sentinels = {
    "INCWAGE":  99999999, "INCBUS":   99999999, "INCFARM":  99999999,
    "INCDIVID":  9999999, "INCINT":    9999999, "INCRENT":   9999999,
    "INCRETIR": 99999999, "HHINCOME":  9999999,
}

# ---------------------------------------------------------------------------
# Step -1: Load the BLS CEX year-specific expenditure share panel
# ---------------------------------------------------------------------------
# The CEX panel tells us how total household consumption spending is split
# across quintiles in each year. We use this to distribute sales taxes and
# motor-vehicle / other S&L taxes, since consumption is a better proxy for
# those burdens than income.

def load_cex_weights_panel():
    """
    Read the BLS CEX expenditure-share CSV and return a nested dict:
      {income_year -> {quintile_short_key -> normalized_weight}}

    Derivation of weights:
      1984–1992: weight_q = Q_avg_dollars / sum(Q1..Q5 avg dollars)
                 (BLS CEX Table 1 — equal consumer unit counts per quintile)
      1993:      direct percent shares from BLS CEX Table 1100
      1994–2022: direct percent shares from BLS CEX Table 55 / Table 1101
      1979–1983: 1984 proxy weights (no BLS CEX data before 1984)
    """
    cex_file = find_file(
        "cex_sales_tax_distribution_weights_detailed_COMPLETE.csv"
    )
    if cex_file is None or not os.path.exists(cex_file):
        raise FileNotFoundError(
            "CEX weights file not found under DATA_ROOT.\n"
            "Place cex_sales_tax_distribution_weights_detailed_COMPLETE.csv "
            "anywhere under data/raw/ (e.g. data/raw/bls_ce/)."
        )

    df = pd.read_csv(cex_file)
    panel = {}
    for _, row in df.iterrows():
        year    = int(row["year"])
        q_short = cex_label_to_short_key.get(row["quintile"])
        if q_short is None:
            continue
        if year not in panel:
            panel[year] = {}
        panel[year][q_short] = float(row["normalized_weight"])

    return panel


def get_cex_shares_for_year(cex_panel, income_year):
    """
    Return the CEX expenditure shares for a given income year.
    Falls back to the nearest earlier year if this exact year isn't in the panel.
    """
    if income_year in cex_panel:
        return cex_panel[income_year]

    # Try nearest earlier year first (we prefer not to extrapolate forward)
    earlier_years = sorted(y for y in cex_panel if y <= income_year)
    if earlier_years:
        return cex_panel[max(earlier_years)]

    # Last resort: use the earliest available year (shouldn't happen with 1979+ coverage)
    return cex_panel[min(cex_panel)]


print("=" * 70)
print("STEP -1: Loading BLS CEX year-specific expenditure share panel...")
print("=" * 70)

cex_panel = load_cex_weights_panel()
print(f"  Loaded CEX weights for years: {min(cex_panel)}–{max(cex_panel)}")
print(f"  Example 2017 weights: {cex_panel.get(2017)}")

# Keep 2017 shares handy as a last-resort fallback constant
cex_shares_2017_fallback = cex_panel.get(2017, {
    "bottom": 0.087, "second": 0.131, "middle": 0.168,
    "fourth": 0.226, "top":    0.389,
})

# ---------------------------------------------------------------------------
# Helper: safe numeric conversion
# ---------------------------------------------------------------------------

def to_float_safe(raw_value):
    """
    Convert a cell value to float, returning NaN if it can't be parsed.
    Handles comma-formatted numbers (e.g., "1,234") and strips whitespace.
    """
    try:
        cleaned = str(raw_value).replace(",", "").strip()
        if set(cleaned).issubset(set(".-0123456789")):
            return float(cleaned)
        return np.nan
    except Exception:
        return np.nan

# ---------------------------------------------------------------------------
# Step 0: Load the full CPS ASEC panel (done once, reused across all years)
# ---------------------------------------------------------------------------
# The CPS provides person-level income and homeownership data. We use it to
# figure out how property taxes and state income taxes are distributed across
# quintiles, since those burdens track homeownership and wages respectively.

def find_cps_file():
    """Return the full path to the CPS extract file, or None if not found."""
    return find_file("cps_00015.csv")

print("=" * 70)
print("STEP 0: Loading CPS ASEC panel (all survey years)...")
print("=" * 70)

cps_filepath = find_cps_file()
if cps_filepath is None:
    print("ERROR: No CPS ASEC file found.")
    sys.exit(1)

print(f"  File: {cps_filepath}")
raw_cps = pd.read_csv(cps_filepath, low_memory=False)
print(f"  Loaded {len(raw_cps):,} person records")

# Zero out any NIU sentinel values so they don't contaminate income calculations
for col_name, threshold in niu_sentinels.items():
    if col_name in raw_cps.columns:
        raw_cps[col_name] = pd.to_numeric(raw_cps[col_name], errors="coerce").fillna(0)
        raw_cps.loc[raw_cps[col_name] >= threshold, col_name] = 0
    else:
        raw_cps[col_name] = 0.0

# Make sure all income/weight/ownership columns are numeric types
for col_name in list(niu_sentinels.keys()) + ["ASECWTH", "OWNERSHP"]:
    if col_name in raw_cps.columns:
        raw_cps[col_name] = pd.to_numeric(raw_cps[col_name], errors="coerce").fillna(0)

print(f"  Survey years: {sorted(raw_cps['YEAR'].unique())[0]}–{sorted(raw_cps['YEAR'].unique())[-1]}")

# ---------------------------------------------------------------------------
# Step 1: Load CBO Tables 01, 07, and 12 (all years at once)
# ---------------------------------------------------------------------------
# We load all three tables up front rather than re-reading the file each year.
# Table 01 gives us household counts, Table 07 gives per-HH federal taxes,
# and Table 12 gives us quintile shares for distributing OMB-only line items.

print("\nSTEP 1: Loading CBO Tables 01, 07, 12...")

def load_full_cbo_table(table_number):
    """Load a multi-year CBO supplemental CSV, normalize column names, return DataFrame."""
    file_path = find_cbo_table(table_number)
    print(f"  T{table_number:02d}: {os.path.basename(file_path)}")
    df = pd.read_csv(file_path)
    df = normalize_cbo_columns(df)
    return df

cbo_table01 = load_full_cbo_table(1)
cbo_table07 = load_full_cbo_table(7)
cbo_table12 = load_full_cbo_table(12)


def slice_cbo_for_year(full_cbo_df, year, household_type="all_households"):
    """
    Filter a CBO DataFrame to a specific year and household type,
    then set income_group as the index for easy row lookups.
    Returns None if no matching rows are found.
    """
    mask = (full_cbo_df["household_type"] == household_type) & (full_cbo_df["year"] == year)
    subset = full_cbo_df[mask].copy()
    if subset.empty:
        return None
    return subset.set_index("income_group")

# ---------------------------------------------------------------------------
# Step 2: Parse OMB Budget Historical Tables (done once for all fiscal years)
# ---------------------------------------------------------------------------
# OMB tables give us national aggregates for tax categories that CBO doesn't
# break out at the quintile level (customs, estate/gift, FUTA, etc.).
# We'll use those aggregates alongside CBO quintile shares to distribute them.

print("\nSTEP 2: Parsing OMB Budget Historical Tables...")


def parse_omb_table21(file_path):
    """
    Parse OMB Table 2.1 (Receipts by Source).
    Returns a DataFrame indexed by fiscal year with columns for each receipt category.
    """
    raw = pd.read_excel(file_path, header=None)

    # Column positions for each receipt category (0-based)
    col_positions = {
        "individual_income": 1, "corporate_income": 2,
        "social_insurance":  3, "excise_taxes":     6,
        "other_receipts":    7, "total_receipts":   8,
    }

    records = []
    for _, row in raw.iloc[4:].iterrows():
        year_val = to_float_safe(row[0])
        if np.isnan(year_val) or not (1940 <= year_val <= 2030):
            continue
        record = {"year": int(year_val)}
        for field, col_idx in col_positions.items():
            record[field] = to_float_safe(row[col_idx])
        records.append(record)

    return pd.DataFrame(records).set_index("year")


def parse_omb_table24(file_path):
    """
    Parse OMB Table 2.4 (Social Insurance & Excise Breakdown).
    Returns a DataFrame indexed by fiscal year.

    Key rows used (0-based row indices in the spreadsheet):
      Row 7  = OASI payroll taxes
      Row 8  = DI payroll taxes
      Row 9  = HI (Medicare) payroll taxes
      Row 12 = Railroad retirement trust fund receipts
      Row 13 = Railroad SSA-equivalent receipts
      Row 18 = Unemployment insurance (FUTA)
      Row 22 = Other retirement taxes
      Row 23 = Total social insurance receipts
      Row 53 = Total excise taxes
    """
    raw = pd.read_excel(file_path, header=None)

    # Row 2 of the spreadsheet contains fiscal years as column headers
    year_to_col = {}
    for col_idx in range(1, raw.shape[1]):
        try:
            year_val = int(float(raw.iloc[2, col_idx]))
            if 1940 <= year_val <= 2030:
                year_to_col[year_val] = col_idx
        except (ValueError, TypeError):
            pass

    def clean_cell(raw_value):
        """Convert a cell to float, returning 0.0 for blank or placeholder values."""
        cleaned = str(raw_value).replace(",", "").strip()
        if cleaned in ("nan", "..........", "", "*", "—", "N/A"):
            return 0.0
        try:
            return float(cleaned)
        except ValueError:
            return 0.0

    # Map field names to their row index in the spreadsheet
    row_index_map = {
        "oasi":                  7,
        "di":                    8,
        "hi":                    9,
        "railroad_trust":       12,
        "railroad_ssa_equiv":   13,
        "unemployment_insurance": 18,
        "other_retirement":     22,
        "total_social_insurance": 23,
        "total_excise":         53,
    }

    records = []
    for year_val, col_idx in sorted(year_to_col.items()):
        record = {"year": year_val}
        for field, row_idx in row_index_map.items():
            record[field] = clean_cell(raw.iloc[row_idx, col_idx])

        # Derived aggregates
        record["oasdi"]            = record["oasi"] + record["di"]
        record["cbo_payroll"]      = record["oasdi"] + record["hi"]
        record["railroad"]         = record["railroad_trust"] + record["railroad_ssa_equiv"]
        record["non_cbo_social"]   = (record["unemployment_insurance"] +
                                      record["other_retirement"] + record["railroad"])
        records.append(record)

    return pd.DataFrame(records).set_index("year")


def parse_omb_table25(file_path):
    """
    Parse OMB Table 2.5 (Other Receipts Breakdown).
    Returns a DataFrame indexed by fiscal year.
    """
    raw = pd.read_excel(file_path, header=None)

    col_positions = {
        "total_other":    1, "estate_gift":    2,
        "customs_duties": 3, "misc_total":     4,
        "fed_reserve":    5, "misc_other":     6,
    }

    records = []
    for _, row in raw.iloc[4:].iterrows():
        year_val = to_float_safe(row[0])
        if np.isnan(year_val) or not (1940 <= year_val <= 2030):
            continue
        record = {"year": int(year_val)}
        for field, col_idx in col_positions.items():
            record[field] = to_float_safe(row[col_idx])
        records.append(record)

    return pd.DataFrame(records).set_index("year")


def find_omb_file(glob_pattern, table_label):
    """
    Find an OMB file by recursive search under DATA_ROOT. Returns the most
    recent match.  Raises FileNotFoundError if nothing is found.
    """
    found = find_file(glob_pattern)
    if found is None:
        raise FileNotFoundError(
            f"No OMB {table_label} file found under DATA_ROOT "
            f"matching: {glob_pattern}"
        )
    return found


# Patterns are forgiving — the year prefix and "(1)"/"(2)" suffixes added by
# browser re-downloads are all matched.
omb_t21_path = find_omb_file("BUDGET-*-TAB-3-1*.xls*", "Table 2.1")
omb_t24_path = find_omb_file("BUDGET-*-TAB-3-4*.xls*", "Table 2.4")
omb_t25_path = find_omb_file("BUDGET-*-TAB-3-5*.xls*", "Table 2.5")

print(f"  OMB T21: {os.path.basename(omb_t21_path)}")
print(f"  OMB T24: {os.path.basename(omb_t24_path)}")
print(f"  OMB T25: {os.path.basename(omb_t25_path)}")

omb21 = parse_omb_table21(omb_t21_path)
omb24 = parse_omb_table24(omb_t24_path)
omb25 = parse_omb_table25(omb_t25_path)

print(f"  OMB T21 years: {omb21.index.min()}–{omb21.index.max()}")
print(f"  OMB T24 years: {omb24.index.min()}–{omb24.index.max()}")
print(f"  OMB T25 years: {omb25.index.min()}–{omb25.index.max()}")


def get_omb_row(omb_df, year):
    """
    Return the OMB row for a given fiscal year.
    If the exact year isn't available, use the most recent earlier year.
    """
    if year in omb_df.index:
        return omb_df.loc[year]
    earlier = [y for y in omb_df.index if y <= year]
    if earlier:
        return omb_df.loc[max(earlier)]
    return omb_df.iloc[-1]

# ---------------------------------------------------------------------------
# Step 3: Build CPS distributional weights for a single income year
# ---------------------------------------------------------------------------
# For each year we need to know how to split property taxes and state income
# taxes across quintiles. Property taxes track homeownership × income, while
# state income taxes track wages. Sales/MV taxes come from CEX consumption shares.

def build_cps_weights_for_year(income_year):
    """
    Compute quintile distribution shares for each S&L tax type.

    CPS survey year = income year + 1 (the YEAR column in the CPS file stores
    the survey year, which reports prior-year income).

    Returns a dict keyed by quintile short key:
      "property_share"  — homeownership × household income share
      "income_share"    — wage income (INCWAGE) share
      "sales_share"     — BLS CEX year-specific consumption expenditure share
      "mv_other_share"  — same as sales_share (same consumption proxy)
    """
    survey_year = income_year + 1

    # Pull the year-specific CEX consumption shares for this income year
    cex_shares = get_cex_shares_for_year(cex_panel, income_year)

    # Filter CPS to household reference persons only (RELATE == 101 = head of household)
    # Using heads only avoids double-counting household income across multiple members
    year_cps = raw_cps[
        (raw_cps["YEAR"] == survey_year) & (raw_cps["RELATE"] == 101)
    ].copy()

    if year_cps.empty:
        # Some early CPS files are labeled by income year rather than survey year
        year_cps = raw_cps[
            (raw_cps["YEAR"] == income_year) & (raw_cps["RELATE"] == 101)
        ].copy()

    if year_cps.empty:
        # No CPS data at all — use uniform property/income weights but keep CEX sales shares
        print(f"  WARNING: No CPS data for survey_year={survey_year}; using uniform property/income weights")
        return {
            q: {"property_share": 0.2, "income_share": 0.2,
                "sales_share": cex_shares[q], "mv_other_share": cex_shares[q]}
            for q in quintile_short_keys
        }

    # Drop households with implausible total income (NIU flag = 9,999,990+)
    year_cps["HHINCOME"] = pd.to_numeric(year_cps["HHINCOME"], errors="coerce")
    year_cps = year_cps[year_cps["HHINCOME"] < 9999990].dropna(subset=["HHINCOME", "ASECWTH"])

    # Build market income for quintile ranking — wages, business, farm, capital, and pension income
    market_income_cols = ["INCWAGE", "INCBUS", "INCFARM", "INCDIVID",
                          "INCINT", "INCRENT", "INCRETIR"]
    for col_name in market_income_cols:
        if col_name not in year_cps.columns:
            year_cps[col_name] = 0.0

    year_cps["market_income"] = year_cps[market_income_cols].clip(lower=0).sum(axis=1)

    # Compute weighted quintile income thresholds (the 20th, 40th, 60th, 80th percentiles)
    survey_weights = year_cps["ASECWTH"].values
    market_incomes = year_cps["market_income"].values
    sorted_order   = np.argsort(market_incomes)
    cumulative_w   = np.cumsum(survey_weights[sorted_order])
    total_weight   = cumulative_w[-1]

    quintile_thresholds = []
    for pct_cutoff in [0.20, 0.40, 0.60, 0.80]:
        idx = np.searchsorted(cumulative_w, pct_cutoff * total_weight)
        quintile_thresholds.append(market_incomes[sorted_order[min(idx, len(sorted_order) - 1)]])

    def assign_quintile(income_value):
        for i, threshold in enumerate(quintile_thresholds):
            if income_value <= threshold:
                return quintile_short_keys[i]
        return quintile_short_keys[-1]

    year_cps["quintile"] = year_cps["market_income"].apply(assign_quintile)

    # Property-tax proxy: homeowners pay property tax, so weight by ownership × income.
    # OWNERSHP == 10 or 12 means owned/being purchased (i.e., a homeowner).
    if "OWNERSHP" in year_cps.columns:
        year_cps["is_homeowner"] = year_cps["OWNERSHP"].isin([10, 12]).astype(float)
    else:
        year_cps["is_homeowner"] = 0.5   # assume 50% if ownership data is missing

    year_cps["property_tax_proxy"] = year_cps["is_homeowner"] * year_cps["HHINCOME"].clip(lower=0)

    # Income-tax proxy: state income taxes follow wage income most closely
    year_cps["income_tax_proxy"] = year_cps["INCWAGE"].clip(lower=0)

    # Aggregate weighted totals by quintile, then normalize to shares
    property_totals = {}
    income_totals   = {}

    for q in quintile_short_keys:
        in_q    = year_cps[year_cps["quintile"] == q]
        weights = in_q["ASECWTH"]
        property_totals[q] = (in_q["property_tax_proxy"] * weights).sum()
        income_totals[q]   = (in_q["income_tax_proxy"]   * weights).sum()

    total_property = sum(property_totals.values())
    total_income   = sum(income_totals.values())

    quintile_weights = {}
    for q in quintile_short_keys:
        quintile_weights[q] = {
            "property_share":  property_totals[q] / total_property if total_property > 0 else 0.2,
            "income_share":    income_totals[q]   / total_income   if total_income   > 0 else 0.2,
            "sales_share":     cex_shares[q],    # year-specific BLS CEX share
            "mv_other_share":  cex_shares[q],    # same consumption proxy for MV/other
        }

    return quintile_weights

# ---------------------------------------------------------------------------
# Step 4: Build federal taxes for a single income year
# ---------------------------------------------------------------------------
# CBO Table 07 already gives us per-HH PIT, payroll, and excise by quintile.
# For the items CBO doesn't break out (estate/gift, customs, FUTA, railroad,
# other retirement), we use OMB aggregate totals and scale them using CBO
# quintile shares from Table 12.

def build_federal_taxes_for_year(income_year):
    """
    Compute per-household federal tax components for each quintile.

    Returns a dict keyed by quintile short key:
      "pit"       — personal income tax per HH
      "payroll"   — payroll taxes (OASDI + HI) per HH
      "excise"    — excise taxes per HH
      "other_fed" — estate/gift + customs + FUTA + railroad + other retirement per HH
      "total_fed" — sum of all four
    """
    t07 = slice_cbo_for_year(cbo_table07, income_year)
    t12 = slice_cbo_for_year(cbo_table12, income_year)

    if t07 is None or t12 is None:
        print(f"  WARNING: No CBO T07/T12 data for {income_year}; skipping federal taxes")
        return {q: {"pit": 0, "payroll": 0, "excise": 0, "other_fed": 0, "total_fed": 0}
                for q in quintile_short_keys}

    # OMB fiscal year = income year (Oct of prior year → Sep of income year)
    r21 = get_omb_row(omb21, income_year)
    r24 = get_omb_row(omb24, income_year)
    r25 = get_omb_row(omb25, income_year)

    # Pull the OMB national totals for items CBO doesn't distribute by quintile
    omb_estate_gift  = float(r25["estate_gift"])
    omb_customs      = float(r25["customs_duties"])
    omb_futa         = float(r24["unemployment_insurance"])   # employer payroll tax
    omb_railroad     = float(r24["railroad"])
    omb_other_ret    = float(r24["other_retirement"])
    omb_excise_total = float(r21["excise_taxes"])

    # CBO Table 07 "all_quintiles" row gives us the national per-HH average for excise/payroll.
    # We'll use the ratio OMB_item / OMB_excise to scale CBO excise into per-HH amounts
    # for each OMB-only item (treating excise as the bridge between the two sources).
    if "all_quintiles" not in t07.index:
        print(f"  WARNING: 'all_quintiles' not in CBO T07 for {income_year}")
        return {q: {"pit": 0, "payroll": 0, "excise": 0, "other_fed": 0, "total_fed": 0}
                for q in quintile_short_keys}

    all_quintiles_row = t07.loc["all_quintiles"]
    avg_excise_per_hh = float(all_quintiles_row.get("excise_taxes",  0))
    avg_payroll_per_hh = float(all_quintiles_row.get("payroll_taxes", 0))

    def scale_omb_to_per_hh(omb_millions):
        """
        Convert an OMB aggregate ($M) into a per-HH average by leveraging the
        ratio of the OMB excise total to the CBO average excise per HH.
        This effectively uses CBO excise as the scaling bridge.
        """
        if omb_excise_total > 0 and avg_excise_per_hh > 0:
            return avg_excise_per_hh * (omb_millions / omb_excise_total)
        return 0.0

    avg_estate_per_hh   = scale_omb_to_per_hh(omb_estate_gift)
    avg_customs_per_hh  = scale_omb_to_per_hh(omb_customs)
    avg_futa_per_hh     = scale_omb_to_per_hh(omb_futa)
    avg_railroad_per_hh = scale_omb_to_per_hh(omb_railroad)
    avg_other_ret_per_hh = scale_omb_to_per_hh(omb_other_ret)

    # Extract quintile shares from CBO Table 12 (values are percentages → divide by 100)
    excise_shares  = {}
    payroll_shares = {}
    pit_raw_shares = {}

    for cbo_key, short_q in zip(cbo_quintile_keys, quintile_short_keys):
        if cbo_key not in t12.index:
            excise_shares[short_q]  = 0.2
            payroll_shares[short_q] = 0.2
            pit_raw_shares[short_q] = 0.2
            continue
        t12_row = t12.loc[cbo_key]
        excise_shares[short_q]  = float(t12_row.get("excise_taxes",          0)) / 100.0
        payroll_shares[short_q] = float(t12_row.get("payroll_taxes",         0)) / 100.0
        pit_val = float(t12_row.get("individual_income_tax", 0))
        pit_raw_shares[short_q] = max(0.0, pit_val / 100.0)

    # Normalize PIT shares (T12 bottom-quintile PIT is often negative — we floor at 0)
    pit_total = sum(pit_raw_shares.values())
    pit_shares = {q: v / pit_total if pit_total > 0 else 0.2
                  for q, v in pit_raw_shares.items()}

    # Compute a household-fraction factor that reconciles CBO payroll per-HH
    # with the OMB aggregate. This is used to scale OMB-only items per quintile.
    hh_scale_factors = {}
    for cbo_key, short_q in zip(cbo_quintile_keys, quintile_short_keys):
        if cbo_key not in t07.index:
            hh_scale_factors[short_q] = 0.2
            continue
        cbo_payroll_this_q = float(t07.loc[cbo_key].get("payroll_taxes", 0))
        if cbo_payroll_this_q > 0:
            hh_scale_factors[short_q] = payroll_shares[short_q] * avg_payroll_per_hh / cbo_payroll_this_q
        else:
            hh_scale_factors[short_q] = 0.2

    # Now compute per-quintile per-HH amounts for each federal tax component
    federal_taxes_by_quintile = {}
    for cbo_key, short_q in zip(cbo_quintile_keys, quintile_short_keys):
        if cbo_key not in t07.index:
            federal_taxes_by_quintile[short_q] = {
                "pit": 0, "payroll": 0, "excise": 0, "other_fed": 0, "total_fed": 0
            }
            continue

        t07_row   = t07.loc[cbo_key]
        pit       = float(t07_row.get("individual_income_tax", 0))
        payroll   = float(t07_row.get("payroll_taxes",         0))
        excise    = float(t07_row.get("excise_taxes",          0))
        hf        = hh_scale_factors[short_q]

        def distribute_omb_item(avg_per_hh, quintile_share):
            """
            Scale a national average OMB item to a quintile-specific per-HH value,
            using the household fraction factor to correct for size differences.
            """
            return (avg_per_hh * quintile_share / hf) if hf > 0 else 0.0

        estate_per_hh    = distribute_omb_item(avg_estate_per_hh,    pit_shares[short_q])
        customs_per_hh   = distribute_omb_item(avg_customs_per_hh,   excise_shares[short_q])
        futa_per_hh      = distribute_omb_item(avg_futa_per_hh,      payroll_shares[short_q])
        railroad_per_hh  = distribute_omb_item(avg_railroad_per_hh,  payroll_shares[short_q])
        other_ret_per_hh = distribute_omb_item(avg_other_ret_per_hh, payroll_shares[short_q])

        other_fed = excise + estate_per_hh + customs_per_hh + futa_per_hh + railroad_per_hh + other_ret_per_hh
        total_fed = pit + payroll + other_fed

        federal_taxes_by_quintile[short_q] = {
            "pit":       round(pit),
            "payroll":   round(payroll),
            "excise":    round(excise),
            "other_fed": round(other_fed),
            "total_fed": round(total_fed),
        }

    return federal_taxes_by_quintile

# ---------------------------------------------------------------------------
# Step 5: Build State & Local taxes for a single income year
# ---------------------------------------------------------------------------

def get_households_per_quintile(income_year):
    """
    Look up households per quintile from CBO Table 01.
    Falls back to 25 million (roughly 1/5 of 125M total HHs) if data is unavailable.
    """
    t01 = slice_cbo_for_year(cbo_table01, income_year)
    if t01 is None or "all_quintiles" not in t01.index:
        return 25_000_000.0
    total_hh = float(t01.loc["all_quintiles", "num_households"]) * 1e6
    return total_hh / 5.0


def build_sl_taxes_for_year(income_year, quintile_weights):
    """
    Compute per-household State & Local tax components for each quintile.

    Parameters
    ----------
    income_year      : int
    quintile_weights : dict from build_cps_weights_for_year() —
                       contains property, income, sales, and MV/other shares

    Returns a dict keyed by quintile short key:
      "sl_sales"           — general + selective sales taxes per HH
      "sl_income"          — state individual income taxes per HH
      "sl_property"        — property taxes per HH
      "sl_mv_other"        — motor vehicle + other taxes per HH
      "sl_property_other"  — property + MV/other combined (for display)
      "sl_total"           — all S&L taxes per HH
    """
    try:
        sl_totals = load_tpc_sl_finance(
            income_year,
            filepath=(find_file("results.csv")
                      or os.path.join(DATA_ROOT, "results.csv")),
        )
    except Exception as exc:
        print(f"  WARNING: TPC S&L data unavailable for {income_year}: {exc}")
        return {q: {"sl_sales": 0, "sl_income": 0, "sl_property": 0,
                    "sl_mv_other": 0, "sl_property_other": 0, "sl_total": 0}
                for q in quintile_short_keys}

    def get_dollars(key):
        """Retrieve a TPC S&L total in dollars (source is in $thousands → multiply by 1000)."""
        val = sl_totals.get(key, np.nan)
        return 0.0 if (val is None or np.isnan(val)) else float(val) * 1000.0

    # National S&L tax totals (in dollars) by category
    sales_dollars    = get_dollars("general_sales") + get_dollars("selective_sales")
    property_dollars = get_dollars("property")
    mv_other_dollars = get_dollars("other_taxes")
    income_dollars   = get_dollars("individual_income")

    hh_per_quintile = get_households_per_quintile(income_year)

    sl_taxes_by_quintile = {}
    for q in quintile_short_keys:
        weights = quintile_weights[q]
        n_hh    = hh_per_quintile

        # Distribute each S&L category using its appropriate quintile share
        sl_sales    = (sales_dollars    * weights["sales_share"])    / n_hh if n_hh > 0 else 0
        sl_income   = (income_dollars   * weights["income_share"])   / n_hh if n_hh > 0 else 0
        sl_property = (property_dollars * weights["property_share"]) / n_hh if n_hh > 0 else 0
        sl_mv_other = (mv_other_dollars * weights["mv_other_share"]) / n_hh if n_hh > 0 else 0

        sl_taxes_by_quintile[q] = {
            "sl_sales":          round(sl_sales),
            "sl_income":         round(sl_income),
            "sl_property":       round(sl_property),
            "sl_mv_other":       round(sl_mv_other),
            "sl_property_other": round(sl_property + sl_mv_other),
            "sl_total":          round(sl_sales + sl_income + sl_property + sl_mv_other),
        }

    return sl_taxes_by_quintile

# ---------------------------------------------------------------------------
# Step 6: Pre-compute CPS weights for all years (cache to avoid re-running)
# ---------------------------------------------------------------------------

print("\nSTEP 3: Building CPS weights cache (all years)...")
cps_weights_cache = {}

for yr in income_years_to_run:
    survey_yr = yr + 1
    has_cps_data = (survey_yr in raw_cps["YEAR"].values) or (yr in raw_cps["YEAR"].values)

    if has_cps_data:
        cps_weights_cache[yr] = build_cps_weights_for_year(yr)
    else:
        # No CPS data for this year — use uniform property/income weights
        # but still apply year-specific CEX shares for sales/MV taxes
        fallback_cex = get_cex_shares_for_year(cex_panel, yr)
        cps_weights_cache[yr] = {
            q: {"property_share": 0.2, "income_share": 0.2,
                "sales_share": fallback_cex[q], "mv_other_share": fallback_cex[q]}
            for q in quintile_short_keys
        }

print(f"  Cached CPS weights for {len(cps_weights_cache)} years.")

# ---------------------------------------------------------------------------
# Step 7: Main loop — process all income years
# ---------------------------------------------------------------------------

print("\nSTEP 4: Building tax distribution panel for 1979–2022...")
print("=" * 70)

all_panel_rows = []

for income_year in income_years_to_run:
    print(f"  Processing {income_year}...", end=" ", flush=True)

    federal_taxes = build_federal_taxes_for_year(income_year)
    sl_taxes      = build_sl_taxes_for_year(income_year, cps_weights_cache[income_year])

    for display_label, short_q in zip(quintile_display_labels, quintile_short_keys):
        fed = federal_taxes[short_q]
        sl  = sl_taxes[short_q]

        all_panel_rows.append({
            "income_year":        income_year,
            "quintile":           display_label,
            "fed_total":          fed["total_fed"],
            "fed_pit":            fed["pit"],
            "fed_payroll":        fed["payroll"],
            "fed_other":          fed["other_fed"],
            "sl_total":           sl["sl_total"],
            "sl_sales":           sl["sl_sales"],
            "sl_income":          sl["sl_income"],
            "sl_property_other":  sl["sl_property_other"],
            "total_taxes":        fed["total_fed"] + sl["sl_total"],
        })

    print("done")

results_panel = pd.DataFrame(all_panel_rows)

# ---------------------------------------------------------------------------
# Step 8: Save the panel CSV
# ---------------------------------------------------------------------------

output_csv_path = os.path.join(OUTPUT_DIR, "tax_distribution_panel.csv")
results_panel.to_csv(output_csv_path, index=False)
print(f"\nPanel saved: {output_csv_path}")
print(f"  Rows: {len(results_panel)} ({len(list(income_years_to_run))} years × 5 quintiles)")


print("Script complete.")
print(f"Output: {output_csv_path}")
