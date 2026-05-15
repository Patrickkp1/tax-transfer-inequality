"""
build_earned_income_panel.py
============================

Builds a long-format panel of average household earned income by quintile,
1979-2022.  Earned income is decomposed into three components:

    (1) Labor income       = wages + self-employment + farm earnings
    (2) Employer benefits  = employer-paid health insurance, employer payroll
                             tax share, deferred comp contributions, and
                             other market income captured by CBO
    (3) Capital income     = dividends + interest + rent + realized cap gains

CPS ASEC (IPUMS extract) provides labor income and most capital income at
the household level.  CBO Supplemental Table 5 provides employer-side
benefits and realized capital gains by quintile, since CPS does not capture
those well.

I apply a percentile-specific correction to CPS wages to account for the
well-documented under-reporting in survey data.  The correction comes from
Bee, Gathright, and Rothbaum (2023), Census SEHSD Working Paper 2023-02
("National Experimental Wellbeing Statistics, Version 1"), which linked
CPS responses to W-2, IRS DER, LEHD, 1040, and 1099-R administrative
records and measured the gap by percentile.

Output: output/earned_income_panel.csv
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


def find_file(pattern):
    """Recursively search DATA_ROOT for a file matching `pattern`.
    Returns the latest match (alphabetical sort) or None."""
    matches = sorted(glob.glob(os.path.join(DATA_ROOT, "**", pattern),
                               recursive=True))
    return matches[-1] if matches else None


CPS_FILE     = find_file("cps_00015.csv")
CPI_FILE     = find_file("cpi_adjusted_v3_dbpi_1979_2022.csv")
CBO_T05_FILE = find_file("households_ranked_by_market_inc_table_05_*_1979_*.csv")

if CPS_FILE is None:
    raise FileNotFoundError("Couldn't find cps_00015.csv under " + DATA_ROOT)
if CBO_T05_FILE is None:
    raise FileNotFoundError("Couldn't find CBO Table 5 under " + DATA_ROOT)

print(f"CPS file:      {CPS_FILE}")
print(f"CBO Table 5:   {CBO_T05_FILE}")
print(f"CPI file:      {CPI_FILE}")
print(f"Output folder: {OUTPUT_DIR}")


# ----------------------------------------------------------------------------
# Constants and lookup tables
# ----------------------------------------------------------------------------

# CBO Table 5 column names that, summed together, equal "employer-provided
# benefits."  These are the four pieces of pre-tax pre-transfer income that
# CBO assigns to households but which workers don't see as cash wages.
BENEFIT_COLS = [
    "employer_contrib_health_ins",
    "employer_share_payroll_taxes",
    "employee_contrib_deferred_comp",
    "other_market_income",
]


# IPUMS uses sentinel codes (huge numbers) instead of NaN when an income
# question is "not in universe" for a respondent.  These need to be zeroed
# before any arithmetic.  Reference: IPUMS-CPS variable documentation.
NIU_SENTINELS = {
    "INCWAGE":  99999999, "INCBUS":   99999999, "INCFARM":  99999999,
    "INCSS":      999999, "INCRETIR": 99999999, "INCSSI":     999999,
    "INCINT":    9999999, "INCUNEMP":   999999, "INCWKCOM":   999999,
    "INCVET":   99999999, "INCDISAB": 99999999, "INCDIVID":  9999999,
    "INCRENT":   9999999, "INCASIST": 99999999, "INCOTHER":  9999999,
    "INCTOT":  999999999, "INCCHILD":   999999, "INCALIM":   9999999,
    "INCEDUC":  99999999, "INCDRT":   99999999, "INCGOV":    9999999,
    "INCALOTH": 99999999, "INCPENS":  99999999, "INCRANN":  99999999,
}


# ECEC = Employer Cost for Employee Compensation.  BLS reports that benefits
# are roughly 21.6% of total compensation for civilian workers.  I only use
# this number to construct a sort key for ranking households by total
# earned income.  It does NOT enter the published benefit value — that
# comes directly from CBO Table 5.
ECEC_RATE = 0.216


# Quintile labels for output rows.
Q_LABELS = {1: "Bottom", 2: "Second", 3: "Middle", 4: "Fourth", 5: "Top"}


# CBO publishes income groups with verbose labels; map them to integers 1-5.
CBO_QUINTILE_MAP = {
    "lowest_quintile":  1,
    "second_quintile":  2,
    "middle_quintile":  3,
    "fourth_quintile":  4,
    "highest_quintile": 5,
}


# ----------------------------------------------------------------------------
# CPS wage under-reporting correction
# ----------------------------------------------------------------------------
# Source: Bee, Gathright, and Rothbaum (2023), Census SEHSD-WP-2023-02,
# "National Experimental Wellbeing Statistics, Version 1" (NEWS V1),
# Section 5.3, p. 37.
#
# Census linked CPS ASEC household responses to administrative records
# (W-2, IRS DER, LEHD, 1040, 1099-R) for income year 2018 and measured how
# much CPS under-reports total household pretax money income at four
# percentile anchors:
#
#     10th pct: +17.1%
#     25th pct: +10.3%
#     50th pct:  +6.8%
#     75th pct:  +3.6%
#
# I take those anchors and linearly interpolate to get one correction
# factor per quintile, using the quintile midpoint percentile:
#
#     Q1 (10th pct):  17.1%   <- published anchor
#     Q2 (30th pct):   9.6%   <- linear interp between 25th and 50th
#     Q3 (50th pct):   6.8%   <- published anchor
#     Q4 (70th pct):   4.2%   <- linear interp between 50th and 75th
#     Q5 (90th pct):   3.6%   <- 75th pct held flat (Bee et al. find that
#                                top earners actually OVER-report relative
#                                to W-2, so holding flat is conservative)
#
# Applied only to labor income (wages + self-employment + farm).  CBO and
# BEA series for benefits and capital income are not corrected because
# those are sourced from administrative records already.

NEWS_LABOR_CORRECTION = {
    1: 0.171,
    2: 0.096,
    3: 0.068,
    4: 0.042,
    5: 0.036,
}


# ----------------------------------------------------------------------------
# Step 1: Load the CPS extract
# ----------------------------------------------------------------------------

print("\nLoading CPS ASEC extract...")
cps = pd.read_csv(CPS_FILE, low_memory=False)
print(f"  {len(cps):,} person records")

# Replace NIU sentinel codes with 0
for col, sentinel in NIU_SENTINELS.items():
    if col in cps.columns:
        cps[col] = pd.to_numeric(cps[col], errors="coerce").fillna(0)
        cps.loc[cps[col] >= sentinel, col] = 0
    else:
        # Column might be absent in older IPUMS extracts (e.g. INCDIVID
        # before 1988).  Fill with zero so downstream sums stay clean.
        cps[col] = 0.0

# Make sure key numeric columns are actually numeric
for col in ("AGE", "ASECWTH"):
    if col in cps.columns:
        cps[col] = pd.to_numeric(cps[col], errors="coerce").fillna(0)


# ----------------------------------------------------------------------------
# Step 2: Load CBO Table 5 (employer benefits + capital gains by quintile)
# ----------------------------------------------------------------------------

print("\nLoading CBO Table 5...")
cbo = pd.read_csv(CBO_T05_FILE)

# CBO has shipped two file vintages with slightly different column names.
# Rename the abbreviated 2022-vintage names to the 2018-vintage names we use.
column_renames = {
    "market_inc":          "market_income",
    "business_inc":        "business_income",
    "positive_rental_inc": "positive_rental_income",
    "other_market_inc":    "other_market_income",
    "individual_inc_tax":  "individual_income_tax",
    "corporate_inc_tax":   "corporate_income_tax",
}
cbo = cbo.rename(columns={k: v for k, v in column_renames.items()
                          if k in cbo.columns})

# Keep only "all households" (CBO publishes other splits) and the five
# quintile rows (drop sub-group rows like top_1_percent).
cbo = cbo[cbo["household_type"] == "all_households"].copy()
cbo["quintile"] = cbo["income_group"].map(CBO_QUINTILE_MAP)
cbo = cbo.dropna(subset=["quintile"])
cbo["quintile"] = cbo["quintile"].astype(int)

# Make sure benefit and cap_gains columns exist; fill missing with 0
for col in BENEFIT_COLS + ["capital_gains", "year"]:
    if col not in cbo.columns:
        cbo[col] = 0.0
    cbo[col] = pd.to_numeric(cbo[col], errors="coerce").fillna(0)

# Sum the four benefit columns into one number per quintile-year
cbo["benefits_total"] = cbo[BENEFIT_COLS].sum(axis=1)

# Build a lookup: cbo_lookup[year][quintile] -> {"benefits": $, "capgains": $}
cbo_lookup = {}
for _, row in cbo.iterrows():
    yr = int(row["year"])
    q  = int(row["quintile"])
    if yr not in cbo_lookup:
        cbo_lookup[yr] = {}
    cbo_lookup[yr][q] = {
        "benefits": float(row["benefits_total"]),
        "capgains": float(row["capital_gains"]),
    }
print(f"  CBO years: {min(cbo_lookup)} - {max(cbo_lookup)}")


# ----------------------------------------------------------------------------
# Step 3: Load the True-COL inflation index (optional)
# ----------------------------------------------------------------------------
# Source: Early, Furth, and Rector (2022).  This is CPI-U with the Boskin
# substitution and quality biases removed.  It's stored only because a
# downstream visualization script uses it for real-dollar charts.

if CPI_FILE is not None and os.path.exists(CPI_FILE):
    cpi = pd.read_csv(CPI_FILE, usecols=["year", "True_CPI_idx"])
    true_cpi = dict(zip(cpi["year"].astype(int), cpi["True_CPI_idx"]))
    print(f"  Loaded True-COL: {min(true_cpi)} - {max(true_cpi)}")
else:
    true_cpi = {}
    print("  True-COL CSV not found — downstream real-dollar charts will use CPI-U.")


# ----------------------------------------------------------------------------
# Step 4: Build the panel year by year
# ----------------------------------------------------------------------------
# For each income year (1979-2022) the steps are:
#
#   (a) Pull the matching CPS survey year (income_year + 1).  CPS asks
#       respondents about the prior calendar year, so survey year 1980
#       captures income year 1979.
#
#   (b) Compute labor income, capital income, and a benefit-proxy at the
#       household level.
#
#   (c) Sort households by total earned income (the sort key) and assign
#       them to quintiles using cumulative population share weighted by
#       ASECWTH.
#
#   (d) Apply the NEWS percentile-specific labor under-reporting correction
#       at the quintile level.
#
#   (e) Compute weighted-average wages, benefits, capital, and total per
#       quintile and append a row to the output panel.

panel_rows = []
skipped_years = []

for income_year in range(1979, 2023):

    # CPS asks about prior calendar year, so survey year is income_year + 1
    survey_year = income_year + 1
    yr = cps[cps["YEAR"] == survey_year].copy()
    if yr.empty:
        skipped_years.append(income_year)
        continue

    # Pre-1988, IPUMS bundles dividends + rent + trust into a single
    # variable (INCDRT) instead of breaking out INCDIVID and INCRENT.
    # Use whichever is available.
    pre_1988 = (survey_year < 1988)
    if pre_1988:
        yr["capital_inc"] = yr["INCDRT"] + yr["INCINT"]
    else:
        yr["capital_inc"] = yr["INCDIVID"] + yr["INCINT"] + yr["INCRENT"]

    # Labor income: wages + self-employment + farm
    yr["labor_inc"] = yr["INCWAGE"] + yr["INCBUS"] + yr["INCFARM"]

    # Benefit proxy used for the SORT KEY only.  We assume wage earners
    # also receive non-cash benefits worth ECEC_RATE share of total comp.
    # The published benefit numbers come from CBO Table 5, not from this
    # proxy.
    is_wage_earner = (yr["INCWAGE"] > 0)
    yr["benefit_proxy"] = 0.0
    yr.loc[is_wage_earner, "benefit_proxy"] = (
        yr.loc[is_wage_earner, "INCWAGE"] / (1.0 - ECEC_RATE) * ECEC_RATE
    )

    # Aggregate from person-level to household-level.  SERIAL is the
    # household ID.  ASECWTH (the household weight) is the same for every
    # person in a household, so taking "first" is correct.
    hh = yr.groupby("SERIAL").agg(
        weight       = ("ASECWTH",       "first"),
        labor        = ("labor_inc",     "sum"),
        capital      = ("capital_inc",   "sum"),
        benefit_prox = ("benefit_proxy", "sum"),
        pension      = ("INCRETIR",      "sum"),
        n_persons    = ("AGE",           "count"),
    ).reset_index()
    if hh.empty:
        skipped_years.append(income_year)
        continue

    # Sort key: labor + benefit proxy + retirement + capital.  This is the
    # full pre-tax pre-transfer earned-income concept, including non-cash
    # comp.  Sort ascending, then walk down the cumulative weighted
    # population share to assign quintiles.
    hh["sort_key"] = (hh["labor"] + hh["benefit_prox"]
                      + hh["pension"] + hh["capital"])
    hh = hh.sort_values("sort_key").reset_index(drop=True)
    cum_frac = hh["weight"].cumsum() / hh["weight"].sum()

    # Default everyone to Q5, then shift down based on cumulative share.
    # Using <= boundaries means the household exactly at 0.20 lands in Q1.
    hh["quintile"] = 5
    hh.loc[cum_frac <= 0.80, "quintile"] = 4
    hh.loc[cum_frac <= 0.60, "quintile"] = 3
    hh.loc[cum_frac <= 0.40, "quintile"] = 2
    hh.loc[cum_frac <= 0.20, "quintile"] = 1

    # Apply the NEWS percentile-specific labor under-reporting correction.
    # Each household gets multiplied by (1 + correction) on its labor
    # income, where the correction depends on its quintile.
    hh["correction_pct"]  = hh["quintile"].map(NEWS_LABOR_CORRECTION)
    hh["labor_corrected"] = hh["labor"] * (1.0 + hh["correction_pct"])

    # Compute weighted-average values within each quintile
    for q in [1, 2, 3, 4, 5]:
        in_q = (hh["quintile"] == q)
        weights = hh.loc[in_q, "weight"]
        if weights.sum() == 0:
            continue

        wages_raw   = float(np.average(hh.loc[in_q, "labor"],           weights=weights))
        wages       = float(np.average(hh.loc[in_q, "labor_corrected"], weights=weights))
        avg_corr    = float(np.average(hh.loc[in_q, "correction_pct"],  weights=weights))
        cps_capital = float(np.average(hh.loc[in_q, "capital"],         weights=weights))

        # Get CBO benefits + capital gains for this year/quintile.  If the
        # year is outside CBO coverage, snap to the nearest available year.
        cbo_year = income_year
        if cbo_year not in cbo_lookup:
            cbo_year = min(cbo_lookup, key=lambda y: abs(y - income_year))
        benefits = cbo_lookup[cbo_year][q]["benefits"]
        capgains = cbo_lookup[cbo_year][q]["capgains"]

        # Final capital income = CPS dividends/interest/rent + CBO realized cap gains
        capital = cps_capital + capgains

        # Quintile ceiling = max sort_key value in this quintile.
        # Useful for plots and sanity-checks downstream.
        ceiling = float(hh.loc[in_q, "sort_key"].max())

        panel_rows.append({
            "income_year":              income_year,
            "quintile":                 q,
            "quintile_name":            Q_LABELS[q],
            "wages":                    round(wages),
            "wages_raw":                round(wages_raw),
            "labor_correction_pct":     round(avg_corr * 100, 2),
            "labor_correction_nominal": round(wages - wages_raw),
            "benefits":                 round(benefits),
            "capital_income":           round(capital),
            "total":                    round(wages + benefits + capital),
            "max_earned_income":        round(ceiling),
            "n_households":             int(in_q.sum()),
            "survey_year":              survey_year,
            "pre_1988_flag":            int(pre_1988),
        })

    print(f"  processed {income_year}")


if skipped_years:
    print(f"\nSkipped years (CPS data missing): {skipped_years}")


# ----------------------------------------------------------------------------
# Step 5: Save the panel
# ----------------------------------------------------------------------------

panel = pd.DataFrame(panel_rows)
output_path = os.path.join(OUTPUT_DIR, "earned_income_panel.csv")
panel.to_csv(output_path, index=False)
print(f"\nWrote {len(panel)} rows to {output_path}")
