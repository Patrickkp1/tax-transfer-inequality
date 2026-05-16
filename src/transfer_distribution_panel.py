"""
transfer_distribution_panel.py
==============================

Builds a long-format panel of average government transfer payments per
household by quintile, 1979-2022.  For each income year and each of the
five quintiles, the panel reports per-household dollars from:

    OASI                 — old-age Social Security
    Medicare             — net of enrollee premiums and beneficiary cost sharing
    SSDI                 — Social Security Disability Insurance
    Medicaid + CHIP
    SNAP                 — food stamps
    Other federal        — UI, TANF, SSI, housing, EITC, etc.
    State and local      — S&L safety-net programs

National program totals come from administrative sources (SSA Trustees,
NHE, BEA NIPA Table 3.12, OMB Historical Tables, USDA, etc.).  Quintile
allocation weights come from CBO supplemental tables 5 and 6, except for
OASI where the script optionally re-ranks households by earned income
using a CPS extract when available.

Medicare is reported NET of beneficiary-paid Part B/D premiums and out-of-
pocket cost sharing, so the figure reflects only the government-financed
portion of the benefit.

Output: output/transfer_distribution_panel.csv
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


def find_file(pattern, must_exist=False):
    """Recursively search DATA_ROOT for a file matching `pattern`.
    Returns the latest match (alphabetical sort) or None.
    Raises FileNotFoundError when must_exist=True and nothing matches."""
    matches = sorted(glob.glob(os.path.join(DATA_ROOT, "**", pattern),
                               recursive=True))
    if matches:
        return matches[-1]
    if must_exist:
        raise FileNotFoundError(
            f"No file matching '{pattern}' found under {DATA_ROOT}"
        )
    return None


def find_cbo_table(table_num):
    """Find a CBO supplemental table CSV by number (1-13).
    Returns the latest match.  Raises FileNotFoundError if nothing matches."""
    pattern = f"households_ranked_by_market_inc_table_{table_num:02d}_*_1979_*.csv"
    return find_file(pattern, must_exist=True)


# Discover input files.  All set to None when not found, so downstream
# code can gracefully skip data sources that haven't been downloaded yet.
oasi_trust_fund_csv  = find_file("OASI_Trust_Fund_Cost_*.csv")
di_trust_fund_csv    = find_file("DI_Trust_Fund_Cost_*.csv")
nhe_excel            = find_file("NHE*.xls*")
bea_nipa_excel       = find_file("Table*.xlsx")           # BEA NIPA 3.12
cbo_table05_csv      = find_cbo_table(5)
cbo_table06_csv      = find_cbo_table(6)
nslp_excel           = find_file("cncost*.xlsx")           # USDA school lunch
wic_excel            = find_file("wisummary*.xlsx")        # USDA WIC
# Housing Subfunction 604 totals are extracted directly from the OMB Public
# Budget Database (outlays_fy*.xlsx) by summing Subfunction Code == 604.
# This is the same file used for LIHEAP, Head Start, TANF, etc. in
# load_crs_programs() — keeping all OMB-derived numbers in one source.
# USAC Lifeline disbursements: hand-cleaned authoritative panel built from
# USAC Annual Reports 1999–2024 + the official Lifeline Data & Statistics
# xlsx, with per-year High Cost / Lifeline / E-Rate / Rural Health Care
# columns. The script reads the "Lifeline ($M)" column.
usac_lifeline_excel  = find_file("USAC_USF_Disbursements*.xlsx", must_exist=True)

# OMB Public Budget Database (account-level outlays). The script's CRS
# program rows (LIHEAP=1560, Head Start=1586, CCDBG=1577, CCE=1594,
# SSBG=1584, Foster Care=1592, TANF=1596) reference this file's row layout
# specifically. The summary BUDGET-*-HIST.xlsx file has a different,
# multi-sheet structure and CANNOT substitute — do not rename it to match.
omb_outlays_excel    = find_file("outlays_fy*.xlsx", must_exist=True)

# Optional full CPS extract — used to build OASI quintile weights from
# earned-income-ranked households.  If not present, the script falls back
# to CBO Table 05 social_security shares.
cps_extract_csv = (find_file("cps_00015.csv")
                   or os.path.join(DATA_ROOT, "cps_00015.csv"))

output_csv = os.path.join(OUTPUT_DIR, "transfer_distribution_panel.csv")


# ----------------------------------------------------------------------------
# Medicare offsets (premiums + cost sharing)
# ----------------------------------------------------------------------------
# Gross Medicare outlays overstate the government-financed transfer because
# beneficiaries pay a meaningful share themselves.  We net out two pieces
# below before distributing Medicare across quintiles:
#
#   (1) Part B + Part D enrollee-paid premiums.  Source: CMS Medicare
#       Trustees Reports (SMI summary tables).  Part D started in 2006;
#       Part B goes back to 1966.  Excludes government-funded LIS subsidies.
#
#   (2) Beneficiary out-of-pocket cost sharing (deductibles + coinsurance).
#       Source: MedPAC Payment Basics and CMS Actuarial Reports.
#
# Units in both dicts: $millions.

medicare_part_b_and_d_premiums = {
    1979:  5_300, 1980:  6_100, 1981:  7_100, 1982:  8_200, 1983:  8_900,
    1984:  9_900, 1985: 11_000, 1986: 11_800, 1987: 13_300, 1988: 15_100,
    1989: 17_100, 1990: 19_800, 1991: 20_500, 1992: 22_300, 1993: 23_800,
    1994: 25_400, 1995: 26_800, 1996: 27_300, 1997: 28_400, 1998: 31_500,
    1999: 32_700, 2000: 33_400, 2001: 34_200, 2002: 34_700, 2003: 35_100,
    2004: 37_200, 2005: 42_400, 2006: 57_200, 2007: 62_800, 2008: 66_900,
    2009: 69_800, 2010: 71_200, 2011: 74_200, 2012: 78_400, 2013: 82_100,
    2014: 82_700, 2015: 84_300, 2016: 87_200, 2017: 88_600, 2018: 91_100,
    2019: 92_800, 2020: 95_700, 2021: 98_200, 2022:102_400,
}

medicare_beneficiary_cost_sharing = {
    1979:  2_500, 1980:  3_000, 1981:  3_600, 1982:  4_200, 1983:  4_700,
    1984:  5_300, 1985:  6_000, 1986:  6_500, 1987:  7_400, 1988:  8_400,
    1989:  9_600, 1990: 11_000, 1991: 11_500, 1992: 12_300, 1993: 13_000,
    1994: 13_800, 1995: 14_600, 1996: 15_200, 1997: 16_200, 1998: 17_500,
    1999: 18_400, 2000: 19_200, 2001: 20_100, 2002: 20_900, 2003: 21_600,
    2004: 23_000, 2005: 25_600, 2006: 34_800, 2007: 38_600, 2008: 41_800,
    2009: 44_200, 2010: 45_500, 2011: 47_600, 2012: 50_200, 2013: 52_400,
    2014: 52_900, 2015: 53_800, 2016: 55_600, 2017: 56_800, 2018: 58_300,
    2019: 59_600, 2020: 61_500, 2021: 63_200, 2022: 66_100,
}


# ---------------------------------------------------------------------------
# Constants and lookup tables
# ---------------------------------------------------------------------------

years_to_run = list(range(1979, 2023))

quintile_names   = ["bottom", "second", "middle", "fourth", "top"]

# Maps CBO income_group text labels to our short quintile names
cbo_to_quintile_name = {
    "lowest_quintile":  "bottom",
    "second_quintile":  "second",
    "middle_quintile":  "middle",
    "fourth_quintile":  "fourth",
    "highest_quintile": "top",
}

# Total US households by year (Census CPS Table HH-1, thousands)
total_households_by_year = {
    1979: 80776, 1980: 82368, 1981: 83527, 1982: 83918, 1983: 85290,
    1984: 86789, 1985: 88458, 1986: 89479, 1987: 91066, 1988: 92830,
    1989: 93347, 1990: 94312, 1991: 95669, 1992: 96426, 1993: 97107,
    1994: 98990, 1995: 99627, 1996:101018, 1997:101018, 1998:102528,
    1999:103874, 2000:104705, 2001:108209, 2002:109297, 2003:111278,
    2004:112000, 2005:113146, 2006:114384, 2007:116011, 2008:117181,
    2009:117181, 2010:118682, 2011:119927, 2012:121084, 2013:122459,
    2014:124587, 2015:125819, 2016:126224, 2017:127586, 2018:128451,
    2019:129931, 2020:128451, 2021:129000, 2022:131434,
}


# ---------------------------------------------------------------------------
# Data loaders
# ---------------------------------------------------------------------------

def load_trust_fund_data():
    """Load OASI and DI Trust Fund benefit payments from CSV. Returns two dicts: {year: $M}."""
    oasi_payments = pd.read_csv(oasi_trust_fund_csv).set_index("Year")["Benefit_Payments"].to_dict()
    di_payments   = pd.read_csv(di_trust_fund_csv).set_index("Year")["Benefit_Payments"].to_dict()
    return oasi_payments, di_payments


def load_nhe_lookup():
    """
    Parse the National Health Expenditures workbook (NHE2024.xls).
    Returns a function: get_nhe(row_index, year) -> value in $millions.
    """
    raw = pd.read_excel(nhe_excel, sheet_name="NHE24", header=None)

    # Build a dict mapping calendar year → column index from row 1 (the year header)
    year_to_col = {}
    for col_idx, cell_val in enumerate(raw.iloc[1, :]):
        try:
            year = int(float(str(cell_val)))
            if 1960 <= year <= 2030:
                year_to_col[year] = col_idx
        except:
            pass

    def get_nhe(row_idx, year):
        if year not in year_to_col:
            return 0.0
        try:
            return float(raw.iloc[row_idx, year_to_col[year]])
        except:
            return 0.0

    return get_nhe


def load_bea_lookup():
    """
    Parse BEA NIPA Table 3.12 (Table-1.xlsx).
    Returns a function: get_bea(line_number, year) -> value in $millions.

    Key lines used in this script:
      L5  = Social Security (OASI+DI combined) — NOT used directly; we use
            Trust Fund CSVs for a cleaner OASI/DI split
      L6  = Medicare
      L7  = Unemployment insurance (all levels)
      L12 = Railroad retirement
      L13 = Pension Benefit Guaranty Corporation
      L14 = Veterans life insurance
      L15 = Workers compensation (federal employees only)
      L16 = Military medical insurance (TRICARE/CHAMPVA)
      L17 = Veterans benefits (pension, disability, readjustment)
      L21 = SNAP
      L22 = Black lung benefits
      L23 = Supplemental Security Income (SSI)
      L25 = Refundable tax credits (EITC + refundable CTC)
      L26 = Other federal transfers (nonprofits, disaster relief,
            COBRA subsidies, ACA cost-sharing, etc.)
      L27 = Total S&L government social benefits
      L32 = S&L Medical care / Medicaid (state share only)
      L40 = S&L Education transfers (qualifying-condition only)
      L41 = S&L Employment and training
      L42 = S&L Other state transfers
    """
    raw = pd.read_excel(bea_nipa_excel, header=None)

    # Row 5 of the spreadsheet contains the year headers
    year_to_col = {}
    for col_idx, cell_val in enumerate(raw.iloc[5, :]):
        try:
            year = int(float(str(cell_val)))
            if 1960 <= year <= 2030:
                year_to_col[year] = col_idx
        except:
            pass

    # Column 0 contains BEA line numbers; build a row-index map from those
    line_to_row = {}
    for row_idx in range(7, len(raw)):
        try:
            line_num = int(float(str(raw.iloc[row_idx, 0])))
            line_to_row[line_num] = row_idx
        except:
            pass

    def get_bea(line_num, year):
        if line_num not in line_to_row or year not in year_to_col:
            return 0.0
        try:
            return float(raw.iloc[line_to_row[line_num], year_to_col[year]])
        except:
            return 0.0

    return get_bea


def load_nslp_data():
    """
    Load USDA NSLP + SBP total federal cost by fiscal year.
    Returns {fiscal_year: $millions}.
    """
    raw = pd.read_excel(nslp_excel, sheet_name=0, header=None)

    # Find the header row by looking for "Fiscal Year" in column 0
    header_row = None
    for idx, val in enumerate(raw.iloc[:, 0].astype(str)):
        if "Fiscal Year" in val:
            header_row = idx
            break

    df = pd.read_excel(nslp_excel, sheet_name=0, header=header_row)
    df.columns = [str(c).strip() for c in df.columns]

    year_col  = next(c for c in df.columns if "Fiscal" in c or "Year" in c)
    value_col = next(c for c in df.columns if "Total Federal" in c)

    df = df[[year_col, value_col]].copy()
    df.columns = ["fiscal_year", "cost_millions"]
    df = df[pd.to_numeric(df["fiscal_year"], errors="coerce").notna()].copy()
    df["fiscal_year"]   = df["fiscal_year"].astype(float).astype(int)
    df["cost_millions"] = pd.to_numeric(df["cost_millions"], errors="coerce")

    return dict(zip(df["fiscal_year"], df["cost_millions"]))


def load_wic_data():
    """
    Load USDA WIC total costs by fiscal year.
    Returns {fiscal_year: $millions}.
    """
    raw = pd.read_excel(wic_excel, sheet_name=0, header=None)

    header_row = None
    for idx, val in enumerate(raw.iloc[:, 0].astype(str)):
        if "Fiscal Year" in val:
            header_row = idx
            break

    df = pd.read_excel(wic_excel, sheet_name=0, header=header_row)
    df.columns = [str(c).strip() for c in df.columns]

    year_col  = next(c for c in df.columns if "Fiscal" in c or "Year" in c)
    value_col = next(c for c in df.columns if "Total" in c and "Cost" in c)

    df = df[[year_col, value_col]].copy()
    df.columns = ["fiscal_year", "cost_millions"]
    df = df[pd.to_numeric(df["fiscal_year"], errors="coerce").notna()].copy()
    df["fiscal_year"]   = df["fiscal_year"].astype(float).astype(int)
    df["cost_millions"] = pd.to_numeric(df["cost_millions"], errors="coerce")

    return dict(zip(df["fiscal_year"], df["cost_millions"]))


def load_housing_604_data():
    """
    Load Subfunction 604 (Housing Assistance) outlays from the OMB Public
    Budget Database (outlays_fy*.xlsx).

    Source: OMB Public Budget Database (account-level outlays). The file
    has one row per (account x subfunction) combination; this function
    sums all rows tagged with Subfunction Code == 604.

    The same OMB workbook is also used by load_crs_programs() for LIHEAP,
    Head Start, TANF, etc. — reading 604 directly from it (instead of from
    a hand-extracted CSV) keeps every OMB-derived number in one source.

    Returns {year: total_outlays_millions}.

    Note: only the HCV + Project-Based Rental Assistance portion of these
    outlays counts as a direct-to-person transfer. Use housing_transfer_fraction()
    to get the era-specific split before adding to Col 6.
    """
    if not os.path.exists(omb_outlays_excel):
        print(f"  [WARN] {os.path.basename(omb_outlays_excel)} not found — housing omitted from Col 6.")
        return {}

    df = pd.read_excel(omb_outlays_excel)
    sub604 = df[df["Subfunction Code"] == 604].copy()

    # OMB year columns are '1962', '1963', …, '2027'. Values are $thousands;
    # we convert to $millions to match the rest of the pipeline.
    out = {}
    for yr in range(1979, 2023):
        col = str(yr)
        if col not in df.columns:
            continue
        out[yr] = round(pd.to_numeric(sub604[col], errors="coerce").fillna(0).sum() / 1000.0)

    df = pd.DataFrame({"year": list(out.keys()), "outlays_millions": list(out.values())})
    df["year"]            = pd.to_numeric(df["year"], errors="coerce")
    df["outlays_millions"] = pd.to_numeric(df["outlays_millions"], errors="coerce")
    df = df.dropna()
    df["year"] = df["year"].astype(int)

    return dict(zip(df["year"], df["outlays_millions"]))


def load_usac_lifeline_data():
    """
    Load USAC Universal Service Fund Lifeline disbursements by calendar year.
    Source: USAC_USF_Disbursements_1998_2022.xlsx
    Returns {year: lifeline_disbursements_millions}.

    Coverage is 1998–2022 only. Years outside this range return 0 —
    we don't impute any values. Lifeline launched in 1985 but was negligible
    before the late 1990s, and no confirmed annual totals exist for 1985–1997.

    Only the Lifeline program is included. E-Rate, High Cost, and Rural Health
    Care are not income-conditioned household transfers.

    BEA excludes Lifeline from 3.12 because USAC pays telecom carriers directly
    (classified as a subsidy to business). This workflow includes it as a transfer because
    it is income-conditioned and ultimately benefits low-income households.
    """
    if not os.path.exists(usac_lifeline_excel):
        print(f"  [WARN] {os.path.basename(usac_lifeline_excel)} not found — Lifeline omitted from Col 6.")
        return {}

    raw = pd.read_excel(usac_lifeline_excel, sheet_name=0, header=None)

    # Find the header row by looking for "year" in any cell
    header_row = None
    for row_idx, row_data in raw.iterrows():
        if any(str(v).strip().lower() == "year" for v in row_data):
            header_row = row_idx
            break

    if header_row is None:
        print("  [WARN] Could not find header row in USAC xlsx — Lifeline omitted.")
        return {}

    df = pd.read_excel(usac_lifeline_excel, sheet_name=0, header=header_row)
    df.columns = [str(c).strip() for c in df.columns]

    year_col     = next((c for c in df.columns if c.lower() == "year"), None)
    lifeline_col = next((c for c in df.columns if "lifeline" in c.lower()), None)

    if not year_col or not lifeline_col:
        print(f"  [WARN] Expected 'Year' and 'Lifeline' columns — found: {list(df.columns)}")
        return {}

    df = df[[year_col, lifeline_col]].copy()
    df.columns = ["year", "lifeline_millions"]
    df["year"]             = pd.to_numeric(df["year"], errors="coerce")
    df["lifeline_millions"] = pd.to_numeric(df["lifeline_millions"], errors="coerce")
    df = df.dropna()
    df["year"] = df["year"].astype(int)

    result = dict(zip(df["year"], df["lifeline_millions"]))
    print(f"  USAC Lifeline loaded: {len(result)} years ({min(result)}–{max(result)})")
    return result


def housing_transfer_fraction(year):
    """
    Returns the fraction of OMB 604 outlays that represent direct-to-person
    transfers (Housing Choice Vouchers + Project-Based Rental Assistance).

    The rest of 604 outlays — public housing operations (~30–38%), CDBG and
    HOME grants (~10–16%), and administrative costs (~5–10%) — are government
    services or formula grants to localities, not personal transfers.

    Era fractions reflect HUD program composition history:
      pre-1983 : 0.30  HCV just created (1974); public housing still dominant
      1983–1989: 0.45  HCV expanding; project-based still a large share
      1990–1997: 0.55  HCV growth accelerates post-Stewart B. McKinney Act
      1998+     : 0.62  HCV + PBRA stable majority after QHWRA (1998)
    """
    if year < 1983:
        return 0.30
    elif year < 1990:
        return 0.45
    elif year < 1998:
        return 0.55
    else:
        return 0.62


def load_crs_programs():
    """
    Load federal transfer programs that are absent from BEA 3.12 "To persons"
    and must be sourced directly from OMB or HHS/ACF administrative records.

    Sources
    -------
    OMB Public Budget Database (outlays_fy2027.xlsx), April 2026 release.
    Row indices are OMB file row numbers (0-based in pandas).
    Dollar units in OMB file are $thousands — converted to $millions here.

    AFDC federal outlays (pre-TANF, FY1979–1996): sourced from HHS/ACF
    "Welfare Indicators Report" (AFDC-TANF.pdf), Table TANF 3 — Federal Funds
    column (benefits + administrative). TANF begins FY1997 from OMB row 1596.

    Why these programs are absent from BEA 3.12
    ---------------------------------------------
    BEA 3.12 footnotes 7, 9, and 11 confirm the omissions:
      - L26 "Other" = nonprofit payments, student aid, disaster relief,
        COBRA, ACA cost-sharing. No TANF, Head Start, LIHEAP, CCDF, or
        Foster Care federal share appears here.
      - L35 "Family assistance" (S&L) = STATE-funded TANF/AFDC only.
      - L39 "Other" (S&L) = state share of foster care and WIC only.
    Federal block grants flow through states but originate as federal outlays;
    BEA excludes them from "To persons" by design.

    Programs included
    -----------------
    liheap      : Low Income Home Energy Assistance (OMB row 1560).
                  1979–1980 values are the predecessor community services
                  energy component — real OMB data, not imputed.
    head_start  : Children & Families Services Programs grant (OMB row 1586).
                  Includes Head Start, Early Head Start, and ACF programs.
    ccdf        : Child Care Dev Block Grant (row 1577) +
                  Child Care Entitlement (row 1594, mandatory).
                  CCDBG starts 1993; CCE starts 1997 (PRWORA).
                  Pre-1993 child care was within AFDC admin (already counted).
    ssbg        : Social Services Block Grant / Title XX (OMB row 1584).
    foster_care : Foster Care and Permanency Payments (OMB row 1592).
                  Title IV-E created by the Adoption Assistance Act of 1980;
                  1979–1980 values are correctly zero.
    afdc_tanf   : FY1979–1996 → AFDC federal (benefits + admin) from AFDC-TANF.pdf.
                  FY1997–2022 → TANF mandatory grant from OMB row 1596.

    Returns
    -------
    dict[str, dict[int, float]]
      Keys: 'liheap', 'head_start', 'ccdf', 'ssbg', 'foster_care', 'afdc_tanf'
      Values: {year: $millions} for 1979–2022 (0.0 where unavailable)
    """
    if not os.path.exists(omb_outlays_excel):
        print(f"  [WARN] {os.path.basename(omb_outlays_excel)} not found — CRS programs omitted from Col 6.")
        empty_series = {yr: 0.0 for yr in range(1979, 2023)}
        return {prog: dict(empty_series) for prog in
                ('liheap', 'head_start', 'ccdf', 'ssbg', 'foster_care', 'afdc_tanf')}

    omb_df = pd.read_excel(omb_outlays_excel)

    def extract_series(row_idx):
        """Pull a full year series from one OMB row, converting $K → $M."""
        series = {}
        for yr in range(1979, 2023):
            try:
                series[yr] = float(omb_df.loc[row_idx, str(yr)]) / 1000.0
            except Exception:
                series[yr] = 0.0
        return series

    liheap_series     = extract_series(1560)
    head_start_series = extract_series(1586)
    ccdbg_series      = extract_series(1577)
    cce_series        = extract_series(1594)
    ssbg_series       = extract_series(1584)
    foster_care_series = extract_series(1592)
    tanf_series        = extract_series(1596)   # TANF mandatory grant, 1997+

    # CCDF = discretionary block grant + mandatory entitlement
    ccdf_series = {yr: ccdbg_series[yr] + cce_series[yr] for yr in range(1979, 2023)}

    # AFDC federal: use HHS/ACF administrative data through 1996, then switch to OMB TANF
    # Units: $millions (benefits + administrative combined)
    afdc_historical = {
        1979:  5825+683,  1980:  6448+750,  1981:  6928+835,  1982:  6922+878,
        1983:  7332+915,  1984:  7707+876,  1985:  7817+890,  1986:  8239+993,
        1987:  8914+1081, 1988:  9125+1194, 1989:  9433+1211, 1990: 10149+1358,
        1991: 11165+1373, 1992: 12258+1459, 1993: 12270+1518, 1994: 12512+1680,
        1995: 12019+1770, 1996: 11065+1633,
    }

    afdc_tanf_series = {}
    for yr in range(1979, 2023):
        if yr <= 1996:
            afdc_tanf_series[yr] = float(afdc_historical.get(yr, 0))
        else:
            afdc_tanf_series[yr] = tanf_series[yr]

    return {
        'liheap':      liheap_series,
        'head_start':  head_start_series,
        'ccdf':        ccdf_series,
        'ssbg':        ssbg_series,
        'foster_care': foster_care_series,
        'afdc_tanf':   afdc_tanf_series,
    }


def load_cbo_tables():
    """Load CBO Tables 05 and 06, normalize column names, and return both DataFrames."""
    table05 = pd.read_csv(cbo_table05_csv)
    table06 = pd.read_csv(cbo_table06_csv)
    table05.columns = [c.strip().lower().replace(" ", "_") for c in table05.columns]
    table06.columns = [c.strip().lower().replace(" ", "_") for c in table06.columns]
    return table05, table06


def get_cbo_quintile_shares(cbo_df, year, column_name, household_type="all_households"):
    """
    Extract quintile distribution weights from a CBO table for a given year and column.
    Returns a length-5 array of shares that sum to 1.0.
    Falls back to the nearest available year if an exact match isn't found.
    """
    available_years = sorted(cbo_df["year"].unique())
    lookup_year = year if year in available_years else min(available_years, key=lambda y: abs(y - year))

    subset = cbo_df[
        (cbo_df["year"] == lookup_year) &
        (cbo_df["household_type"] == household_type) &
        (cbo_df["income_group"].isin(cbo_to_quintile_name))
    ].copy()

    subset["quintile"] = subset["income_group"].map(cbo_to_quintile_name)
    subset = subset.set_index("quintile")

    raw_shares = np.array(
        [float(subset.loc[q, column_name]) if q in subset.index else 0.0
         for q in quintile_names],
        dtype=float,
    )

    total = raw_shares.sum()
    return raw_shares / total if total > 0 else np.ones(5) / 5.0


def load_cps_oasi_shape(cps_file_path):
    """
    Compute OASI quintile shares from the full CPS extract, ranking households
    by a broad income ranking key that matches build_earned_income_panel.py:

        ranking_income = labor (INCWAGE + INCBUS + INCFARM)
                       + retirement/pension income (INCRETIR)
                       + capital income (INCDIVID + INCINT + INCRENT)

    This broader ranking prevents retirees with $0 wages from being pushed
    entirely to the bottom quintiles, which causes OASDI to be over-concentrated
    at the bottom of the distribution.
    Employer benefit proxy is not available in the CPS extract and is omitted.
    Capital income columns (INCDIVID, INCINT, INCRENT) were added in 1988;
    for earlier survey years they are set to 0 if absent.

    Uses INCSS (Social Security received) as the transfer amount to distribute.
    Falls back to CBO T05 social_security weights if the file isn't present.
    Returns {survey_year: length-5 share array}.
    """
    if not os.path.exists(cps_file_path):
        print(f"  [INFO] {os.path.basename(cps_file_path)} not found — using CBO social_security shape for OASDI.")
        return {}

    print(f"  Loading CPS INCSS distribution from {os.path.basename(cps_file_path)} ...")
    header_cols = pd.read_csv(cps_file_path, nrows=0).columns.tolist()
    weight_col  = "ASECWTH" if "ASECWTH" in header_cols else "ASECWT"

    # Read additional columns needed for broad ranking income.
    # INCDIVID, INCINT, INCRENT were added in 1988; gracefully request them
    # and fall back to 0 for years/rows where they are absent.
    read_cols = ["YEAR", "RELATE", weight_col, "INCWAGE", "INCBUS", "INCFARM",
                 "INCSS", "INCRETIR", "INCDIVID", "INCINT", "INCRENT"]
    available_cols = [c for c in read_cols if c in header_cols]
    cps = pd.read_csv(
        cps_file_path,
        usecols=available_cols,
    )
    cps.rename(columns={weight_col: "survey_weight"}, inplace=True)

    # Keep only household reference persons (RELATE == 101) to avoid double-counting
    cps = cps[cps["RELATE"] == 101].copy()

    # Coerce all income columns; fill missing columns with 0 for pre-1988 surveys
    for col in ["INCWAGE", "INCBUS", "INCFARM", "INCRETIR", "INCDIVID", "INCINT", "INCRENT"]:
        if col in cps.columns:
            cps[col] = pd.to_numeric(cps[col], errors="coerce").fillna(0).clip(lower=0)
        else:
            cps[col] = 0

    # Broad ranking income: labor + retirement/pension + capital
    # Matches build_earned_income_panel.py (minus employer benefit proxy, unavailable in CPS)
    cps["ranking_income"] = (
        cps["INCWAGE"] + cps["INCBUS"] + cps["INCFARM"]   # labor income
        + cps["INCRETIR"]                                  # pensions / retirement distributions
        + cps["INCDIVID"] + cps["INCINT"] + cps["INCRENT"] # capital income
    )
    cps["INCSS"] = pd.to_numeric(cps["INCSS"], errors="coerce").fillna(0).clip(lower=0)

    oasi_shapes_by_year = {}
    for survey_year, year_group in cps.groupby("YEAR"):
        year_group = year_group.dropna(subset=["survey_weight"]).sort_values("ranking_income")
        weights     = year_group["survey_weight"].values.astype(float)
        cum_weights = np.cumsum(weights) / weights.sum()

        # Cut points at the 20th, 40th, 60th, and 80th percentiles
        cut_points = [0] + [np.searchsorted(cum_weights, pct, "left")
                            for pct in [0.20, 0.40, 0.60, 0.80]] + [len(year_group)]

        ss_received = year_group["INCSS"].values
        quintile_totals = np.array(
            [(ss_received[int(cut_points[i]):int(cut_points[i+1])]
              * weights[int(cut_points[i]):int(cut_points[i+1])]).sum()
             for i in range(5)],
            dtype=float,
        )

        total_ss = quintile_totals.sum()
        oasi_shapes_by_year[int(survey_year)] = (
            quintile_totals / total_ss if total_ss > 0 else np.ones(5) / 5.0
        )

    print(f"  CPS OASI shapes built for {len(oasi_shapes_by_year)} years.")
    return oasi_shapes_by_year


# ---------------------------------------------------------------------------
# Core computation
# ---------------------------------------------------------------------------

def distribute_to_quintiles(national_total_millions, quintile_shares, households_per_quintile):
    """
    Distribute a national program total ($M) across quintiles using the given
    share weights. Returns per-household dollar amounts (rounded to nearest $).
    """
    return np.round(
        (national_total_millions * 1_000_000.0 * quintile_shares) / households_per_quintile
    ).astype(int)


def build_results_panel(
    oasi_payments, di_payments, get_nhe, get_bea,
    nslp_data, wic_data, housing_604_data, lifeline_data,
    crs_programs, cbo_t05, cbo_t06, cps_oasi_shapes,
    use_cps_oasi_shape=False
):
    """
    Main loop: for each income year, compute transfer per-HH by program and
    quintile, then assemble into a long-format panel DataFrame.
    """
    all_rows = []

    for year in years_to_run:
        num_households     = total_households_by_year.get(year, 120000)
        households_per_quintile = num_households * 1000 / 5.0

        # --- Col 1: OASI — SSA OASI Trust Fund benefit payments ($M) ---
        oasi_national = float(oasi_payments.get(year, 0))

        # --- Col 3: SSDI — SSA DI Trust Fund benefit payments ($M) ---
        ssdi_national = float(di_payments.get(year, 0))

        # --- Col 2: Medicare (net of beneficiary premiums and cost-sharing) ---
        # Standard practice in distributional analysis is to subtract enrollee-paid
        # premiums and deductibles/coinsurance from gross Medicare outlays so the
        # transfer reflects only the government-financed portion.
        medicare_gross    = get_nhe(6, year)
        medicare_premiums = medicare_part_b_and_d_premiums.get(year, 0.0)
        medicare_costshare = medicare_beneficiary_cost_sharing.get(year, 0.0)
        medicare_net      = max(medicare_gross - medicare_premiums - medicare_costshare, 0.0)

        # --- Col 4: Medicaid + CHIP — NHE rows 7 and 10 ($M) ---
        # NHE captures the full program cost (federal + state shares combined),
        # treating the full program cost as part of the transfer system, with state contributions
        # "reflected in the federal program total."
        medicaid_chip_national = get_nhe(7, year) + get_nhe(10, year)

        # --- Col 5: SNAP — BEA L21 only ($M) ---
        # NSLP (school lunch), SBP (school breakfast), and WIC are food-assistance
        # programs that flow to households but are tracked separately from SNAP.
        # We move them to Other Federal rather than letting them inflate this column.
        snap_national = get_bea(21, year)

        # --- Col 6: Other Federal ($M) ---
        # BEA 3.12 lines:
        #   L7  = Unemployment insurance   L12 = Railroad retirement
        #   L13 = PBGC pension insurance   L14 = Veterans life insurance
        #   L15 = Federal workers comp     L16 = TRICARE / military medical
        #   L17 = Veterans benefits         L22 = Black lung
        #   L23 = SSI                       L25 = Refundable tax credits (EITC + CTC)
        #   L26 = Other (nonprofits, disaster relief, COBRA, ACA cost-sharing)
        bea_other_lines = sum(get_bea(ln, year) for ln in [7,12,13,14,15,16,17,22,23,25,26])

        # OMB 604 Housing Assistance: only the HCV + PBRA transfer portion.
        # BEA excludes these because USAC pays landlords (classified as business
        # subsidies). We include them since they are income-conditioned transfers.
        housing_total_outlays  = housing_604_data.get(year, 0.0)
        housing_transfer_share = housing_transfer_fraction(year)
        housing_transfer       = housing_total_outlays * housing_transfer_share

        # USAC Lifeline: confirmed 1998–2022; zero outside that range (no imputation)
        lifeline_national = lifeline_data.get(year, 0.0)

        # CRS/OMB unattributable programs (absent from BEA 3.12 "To persons"):
        # LIHEAP, Head Start, CCDF, SSBG, Foster Care IV-E, AFDC/TANF federal.
        # Non-duplication confirmed via BEA footnotes 7, 9, 11.
        crs_total = sum(
            crs_programs[prog].get(year, 0.0)
            for prog in ('liheap', 'head_start', 'ccdf', 'ssbg', 'foster_care', 'afdc_tanf')
        )

        # NSLP and WIC are grouped with Other Federal nutrition and family-support transfers
        nslp_national = nslp_data.get(year, 0)
        wic_national  = wic_data.get(year, 0)

        other_federal_national = (
            bea_other_lines + housing_transfer + lifeline_national + crs_total
            + nslp_national + wic_national
        )

        # --- Col 7: State & Local — BEA 3.12 formula ($M) ---
        # BEA 3.12 structure:
        #   L27 = S&L total social benefits (contains L28, L31, L40, L41, L42)
        #   L31 = Public assistance (contains L32 through L39)
        #   L32 = Medical care (state Medicaid + state CHIP = $585B in 2017)
        #
        # FIX: The previous formula (L27 - L32) + L40 + L41 + L42 DOUBLE-COUNTS
        # L40, L41, L42 because those lines are already sub-components of L27.
        # The correct formula is simply: L27 - L32.
        #   - L32 (all S&L medical care) is subtracted to avoid double-counting
        #     with Col 4, which already uses NHE full-program Medicaid+CHIP costs
        #     (including the state share). Subtracting all of L32 (not just L33
        #     Medicaid) avoids double-counting CHIP and state health programs
        #     that are captured in NHE rows 7 and 10.
        #   - L40 (education transfers), L41 (employment & training), L42 (other)
        #     are NOT added separately — they are already inside L27.
        state_local_national = max(0.0, get_bea(27, year) - get_bea(32, year))

        # --- Distribution weights ---
        # OASI: use CPS earned-income shape when available; otherwise fall back to CBO Table 05
        # OASI quintile shape: use CBO Table 05 social_security column.
        # We previously tried building this from CPS microdata (ranking by
        # earned+pension+capital income), but the CPS sample currently in
        # workspace (cps_00015.csv) is too small for stable per-quintile
        # estimates and produced spurious distributions. CBO T05 publishes
        # the per-HH social_security amount by quintile directly, smoothed
        # across hundreds of thousands of underlying records, so it's the
        # right anchor here. (Pass --use-cps to override and use CPS shape.)
        if use_cps_oasi_shape and year in cps_oasi_shapes:
            oasi_shares = cps_oasi_shapes[year]
        else:
            oasi_shares = get_cbo_quintile_shares(cbo_t05, year, "social_security")
        medicare_shares  = get_cbo_quintile_shares(cbo_t05, year, "medicare")
        medicaid_shares  = get_cbo_quintile_shares(cbo_t06, year, "medicaid_and_chip")
        snap_shares      = get_cbo_quintile_shares(cbo_t06, year, "snap")
        means_tested_shares = get_cbo_quintile_shares(cbo_t06, year, "means_tested_transfers")

        # --- Distribute national totals to per-HH quintile amounts ---
        per_hh_oasi     = distribute_to_quintiles(oasi_national,          oasi_shares,         households_per_quintile)
        per_hh_ssdi     = distribute_to_quintiles(ssdi_national,          means_tested_shares, households_per_quintile)
        per_hh_medicare = distribute_to_quintiles(medicare_net,           medicare_shares,     households_per_quintile)
        per_hh_medicaid = distribute_to_quintiles(medicaid_chip_national, medicaid_shares,     households_per_quintile)
        per_hh_snap     = distribute_to_quintiles(snap_national,          snap_shares,         households_per_quintile)
        # Split other_federal_national into sub-buckets and apply the correct CBO shape
        # for each sub-program.  UI is NOT bottom-concentrated (CBO Table 05 shows it
        # peaks in the second quintile); routing all of other_federal through
        # means_tested_shares would over-weight the bottom two quintiles.
        ui_shares = get_cbo_quintile_shares(cbo_t05, year, "unemployment_insurance")
        # Fall back to social_insurance_benefits if unemployment_insurance not found
        if ui_shares.sum() == 0 or np.all(ui_shares == ui_shares[0]):
            ui_shares = get_cbo_quintile_shares(cbo_t05, year, "social_insurance_benefits")
        si_shares  = get_cbo_quintile_shares(cbo_t05, year, "social_insurance_benefits")
        ssi_shares = get_cbo_quintile_shares(cbo_t06, year, "ssi")
        mt_shares  = means_tested_shares  # already computed above

        # Decompose other_federal_national into individual program buckets ($M)
        ui_natl          = get_bea(7,  year)                              # L7  = Unemployment insurance
        veterans_natl    = get_bea(17, year) + get_bea(14, year)         # L17 = Vet benefits + L14 = Vet life ins
        ssi_natl         = get_bea(23, year)                             # L23 = Supplemental Security Income
        eitc_ctc_natl    = get_bea(25, year)                             # L25 = Refundable tax credits (EITC+CTC)
        tricare_natl     = get_bea(16, year)                             # L16 = Military medical (TRICARE/CHAMPVA)
        fed_workers_natl = get_bea(15, year)                             # L15 = Federal workers comp
        other_misc_natl  = max(0.0,
            other_federal_national
            - ui_natl - veterans_natl - ssi_natl
            - eitc_ctc_natl - tricare_natl - fed_workers_natl
        )

        # Distribute each sub-bucket with its appropriate shape
        per_hh_ui      = distribute_to_quintiles(ui_natl,          ui_shares,  households_per_quintile)  # UI peaks in Q2
        per_hh_vet     = distribute_to_quintiles(veterans_natl,    si_shares,  households_per_quintile)  # vets are mid-dist
        per_hh_ssi     = distribute_to_quintiles(ssi_natl,         ssi_shares, households_per_quintile)  # SSI is bottom-heavy
        per_hh_eitc    = distribute_to_quintiles(eitc_ctc_natl,    mt_shares,  households_per_quintile)  # EITC phases out ~$50K
        per_hh_tricare = distribute_to_quintiles(tricare_natl,     si_shares,  households_per_quintile)  # employment-based
        per_hh_fedwc   = distribute_to_quintiles(fed_workers_natl, si_shares,  households_per_quintile)  # employment-based
        per_hh_misc    = distribute_to_quintiles(other_misc_natl,  mt_shares,  households_per_quintile)  # remainder

        per_hh_other = per_hh_ui + per_hh_vet + per_hh_ssi + per_hh_eitc + per_hh_tricare + per_hh_fedwc + per_hh_misc
        per_hh_sl       = distribute_to_quintiles(state_local_national,   means_tested_shares, households_per_quintile)

        # Build one row per quintile, plus an average row
        year_quintile_rows = []
        for i, quintile_name in enumerate(quintile_names):
            total_federal = int(
                per_hh_oasi[i] + per_hh_ssdi[i] + per_hh_medicare[i]
                + per_hh_medicaid[i] + per_hh_snap[i] + per_hh_other[i]
            )
            total_govt = total_federal + int(per_hh_sl[i])

            year_quintile_rows.append(dict(
                income_year       = year,
                quintile          = quintile_name,
                num_households    = num_households,
                hh_per_quintile   = int(households_per_quintile),
                total_govt        = total_govt,
                total_fed         = total_federal,
                oasdi             = int(per_hh_oasi[i]),
                ssdi              = int(per_hh_ssdi[i]),
                medicare          = int(per_hh_medicare[i]),
                medicaid_chip     = int(per_hh_medicaid[i]),
                snap              = int(per_hh_snap[i]),
                other_fed         = int(per_hh_other[i]),
                state_local       = int(per_hh_sl[i]),
                oasi_shape_source = "CPS_earned_income" if (use_cps_oasi_shape and year in cps_oasi_shapes) else "CBO_T05_social_security",
            ))

        all_rows.extend(year_quintile_rows)

        # Append an average row (simple mean across the 5 quintiles)
        average_row = dict(
            income_year       = year,
            quintile          = "average",
            num_households    = num_households,
            hh_per_quintile   = int(households_per_quintile),
            oasi_shape_source = "",
        )
        for col in ["total_govt", "total_fed", "oasdi", "ssdi", "medicare",
                    "medicaid_chip", "snap", "other_fed", "state_local"]:
            average_row[col] = round(sum(r[col] for r in year_quintile_rows) / 5)

        all_rows.append(average_row)

    return pd.DataFrame(all_rows)



# ---------------------------------------------------------------------------
# Quick summary
# ---------------------------------------------------------------------------

def print_summary_snapshot(results_panel):
    """Print a compact 2017 snapshot for a quick reasonableness check."""
    df_2017 = results_panel[results_panel["income_year"] == 2017].copy()
    if df_2017.empty:
        print("No 2017 rows available for snapshot check.")
        return

    print("=" * 100)
    print("2017 reasonableness check ($/household)")
    print(df_2017[[
        "quintile", "total_govt", "total_fed", "oasdi", "ssdi", "medicare",
        "medicaid_chip", "snap", "other_fed", "state_local"
    ]].to_string(index=False))
    print("=" * 100)



# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("Loading transfer data sources...")
    oasi_payments, di_payments = load_trust_fund_data()
    get_nhe           = load_nhe_lookup()
    get_bea           = load_bea_lookup()
    nslp_data         = load_nslp_data()
    wic_data          = load_wic_data()
    housing_604_data  = load_housing_604_data()
    lifeline_data     = load_usac_lifeline_data()
    crs_programs      = load_crs_programs()
    cbo_t05, cbo_t06  = load_cbo_tables()
    cps_oasi_shapes   = load_cps_oasi_shape(cps_extract_csv)


    print("\nBuilding transfer panel...")
    results_panel = build_results_panel(
        oasi_payments, di_payments, get_nhe, get_bea,
        nslp_data, wic_data, housing_604_data, lifeline_data,
        crs_programs, cbo_t05, cbo_t06, cps_oasi_shapes,
    )

    results_panel.to_csv(output_csv, index=False)
    print(f"Saved panel to {output_csv} (shape: {results_panel.shape})")

    print()
    print_summary_snapshot(results_panel)

    print()
    print("2017 snapshot ($/household):")
    print("-" * 95)
    display_cols = ["quintile", "total_govt", "total_fed", "oasdi", "ssdi", "medicare",
                    "medicaid_chip", "snap", "other_fed", "state_local"]
    print(results_panel[results_panel["income_year"] == 2017][display_cols].to_string(index=False))
