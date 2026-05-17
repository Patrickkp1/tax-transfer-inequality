"""
income_after_taxes_transfers_panel.py
=====================================

Builds a long-format panel of household income before and after taxes &
transfers, by quintile, 1979-2022.  This is the assembly stage of the
pipeline — it stitches together three upstream panels and adds a fourth
component (private transfers) estimated here.

Inputs read from output/:
    earned_income_panel.csv             column: total
    transfer_distribution_panel.csv     column: total_govt
    tax_distribution_panel.csv          column: total_taxes

Derived columns:
    Income Before Taxes (IBT) = earned + govt transfers + private transfers
    Income After Taxes  (IAT) = IBT − taxes
    tax_pct_ibt               = taxes / IBT × 100

Private transfer methodology
-----------------------------
Private transfers are estimated using three components, each distributed
across quintiles using empirically grounded weights:

    Component A — Child support + alimony (CPS INCCHILD + INCALIM).
        Source: Census CPS Child Support Supplement 2018 (income year 2017).
        Custodial parents cluster at Q2/Q3; Q1 has low enforcement rates.
        Weights: Q1=15%, Q2=35%, Q3=28%, Q4=14%, Q5=8%.

    Component B — Informal household cash assistance (CPS INCASIST/INCOTHER).
        Source: Karen (2023), LIS Working Paper No. 851, Table 2, Model 1.
        Uses bivariate odds ratios of receiving an informal transfer vs.
        the Q3 reference group, normalized to sum to 1.

    Component C — Giving USA household-directed charitable donations.
        Source: Giving USA 2014 Data Tables (1979-2013) and annual report
        highlights (2014-2022).  Each recipient category gets a fraction
        representing the share of donations that actually reach households
        (Religion 5%, Education 5%, Human Services 50%, Health 8%,
        Public-Society 5%, Foundations 0%, International 25%, Arts 0%,
        Environment 0%, Individuals 100%).
        Quintile distribution of the HH-directed total: Q1=45%, Q2=30%,
        Q3=15%, Q4=6%, Q5=4% (from Feeding America client mix and CBO
        means-tested transfer distribution).

CPS column availability by era:
    Pre-1988:  Only INCALOTH (combined alimony + assistance proxy)
    1988-2018: INCCHILD, INCASIST, INCOTHER, INCALIM all present
    2019+:     INCALIM absorbed into INCOTHER

Output: output/income_after_taxes_transfers_panel.csv
"""

import os
import sys
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
# input files.  Upstream panel CSVs are read from <repo>/output/ and the
# final panel is written there too.
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


def build_path(filename):
    """Resolve a raw input file by recursive search under DATA_ROOT.
    Falls back to DATA_ROOT/<filename> if no match — the caller can decide
    whether the missing file is fatal."""
    found = find_file(filename)
    return found if found else os.path.join(DATA_ROOT, filename)


def upstream_path(filename):
    """Return the full path to an upstream panel CSV in OUTPUT_DIR."""
    return os.path.join(OUTPUT_DIR, filename)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

income_years_to_run = range(1979, 2023)
quintile_labels = ["Bottom", "Second", "Middle", "Fourth", "Top"]

# ---------------------------------------------------------------------------
# Distributional weights — all sourced from peer-reviewed literature
# ---------------------------------------------------------------------------

# Component A: child support + alimony weights
# Source: Census CPS Child Support Supplement 2018 (income year 2017).
# Custodial parents are concentrated in Q2/Q3; Q1 has low enforcement rates.
child_support_weights = {
    "Bottom": 0.15, "Second": 0.35, "Middle": 0.28, "Fourth": 0.14, "Top": 0.08,
}

# Component B: informal cash assistance weights (INCASIST / INCOTHER)
# Source: Karen (2023), LIS WP 851, Table 2, Model 1 — bivariate odds ratios
# of receiving an informal transfer relative to the Q3 reference group.
# We normalize the raw odds so they sum to 1 and can be used as shares.
karen_raw_odds = {"Bottom": 4.06, "Second": 1.54, "Middle": 1.00, "Fourth": 0.67, "Top": 0.65}
odds_sum = sum(karen_raw_odds.values())
informal_assistance_weights = {q: karen_raw_odds[q] / odds_sum for q in quintile_labels}

# Component C: Giving USA household-directed quintile shares
# Source: Feeding America (94% of clients below 185% FPL) and CBO (2020)
# means-tested transfer distribution. Lower quintiles receive the vast
# majority of direct charitable transfers.
giving_usa_quintile_weights = {
    "Bottom": 0.45, "Second": 0.30, "Middle": 0.15, "Fourth": 0.06, "Top": 0.04,
}

# ---------------------------------------------------------------------------
# Giving USA household-directed fractions by recipient category
# ---------------------------------------------------------------------------
# For each Giving USA category, this fraction represents the share of total
# donations that ultimately flow through to individual US households as a
# direct private transfer (as opposed to funding institutional operations,
# international relief, or endowments).
giving_hh_directed_fractions = {
    "Religion":               0.05,  # ~3–5% of church budgets go to direct aid (FACTS on Finance 2022)
    "Education":              0.05,  # scholarships and student aid paid directly to individuals
    "Human Services":         0.50,  # ~40–50% net of staffing/logistics (Urban Institute Form 990 data)
    "Foundations":            0.00,  # pass-through vehicles — including here would double-count
    "Health":                 0.08,  # hospital charity care + patient assistance programs (0.05–0.10 range)
    "Public-Society Benefit": 0.05,  # community development grants, some direct aid
    "International Affairs":  0.25,  # GiveDirectly, UNICEF, food/medicine cash transfers (0.20–0.40 range)
    "Arts/Culture/Humanities":0.00,  # institutional — does not reach individual households
    "Environment/Animals":    0.00,  # institutional
    "Individuals":            1.00,  # by definition: these are direct gifts to individuals
}

# ---------------------------------------------------------------------------
# Giving USA annual totals by recipient category (in $billions)
# ---------------------------------------------------------------------------
# Giving USA annual totals by recipient category (in $billions)
# ---------------------------------------------------------------------------
# Loaded from data/raw/giving_USA/giving_usa_recipients_*.csv.
#
# Source provenance (CSV column source_ref):
#   1979-2013 (A): Giving USA 2014 Data Tables PDF, page 4-5
#                  ("Contributions by type of recipient organization,
#                  1973-2013, in billions of current dollars")
#   2014-2022 (B-J): Giving USA 2015-2023 annual report releases, one per
#                    publication year. The 2023 report covers data year 2022
#                    and confirms the most recent row.
#
# Coverage caveats inherited from the source data:
#   * "International Affairs" and "Environment/Animals" not tracked before
#     1987; CSV records NaN, which is treated as $0 by the helper below.
#   * "Individuals" (direct gifts) only broken out from 2004 forward; same.
#   * 2017 "Individuals" is NaN in the CSV because the 2018 release did not
#     publish it as a separate line item; treated as $0 here.
#   * "unallocated_B" is NOT mapped to any recipient category. It represents
#     reporting residuals (early years had positive values; from ~1995 the
#     residual flips negative as Giving USA refines methodology). Treating it
#     as a recipient would double-count.

def _load_giving_usa_csv():
    """Locate and parse the Giving USA recipient CSV under DATA_ROOT.
    Returns ({year: {category: $B or None}}, csv_path)."""
    matches = sorted(glob.glob(
        os.path.join(DATA_ROOT, "**", "giving_usa_recipients_*.csv"),
        recursive=True))
    if not matches:
        raise FileNotFoundError(
            "No giving_usa_recipients_*.csv found under DATA_ROOT.\n"
            f"Expected location: {DATA_ROOT}/giving_USA/"
            "giving_usa_recipients_1979_2022.csv"
        )
    csv_path = matches[-1]
    df = pd.read_csv(csv_path)

    # Map CSV column -> label expected by giving_hh_directed_fractions.
    # total_giving_B and unallocated_B are intentionally excluded.
    col_to_category = {
        "religion_B":               "Religion",
        "education_B":              "Education",
        "human_services_B":         "Human Services",
        "health_B":                 "Health",
        "public_society_benefit_B": "Public-Society Benefit",
        "arts_culture_humanities_B":"Arts/Culture/Humanities",
        "international_affairs_B":  "International Affairs",
        "environment_animals_B":    "Environment/Animals",
        "gifts_to_foundations_B":   "Foundations",
        "gifts_to_individuals_B":   "Individuals",
    }
    out = {}
    for _, row in df.iterrows():
        year_data = {}
        for col, cat in col_to_category.items():
            v = row.get(col)
            year_data[cat] = None if pd.isna(v) else float(v)
        out[int(row["year"])] = year_data
    return out, csv_path


giving_usa_by_recipient, _giving_usa_csv_path = _load_giving_usa_csv()
print(f"  Loaded Giving USA recipient totals from "
      f"{os.path.relpath(_giving_usa_csv_path, DATA_ROOT)} "
      f"({len(giving_usa_by_recipient)} years: "
      f"{min(giving_usa_by_recipient)}-{max(giving_usa_by_recipient)})")


def giving_usa_hh_directed_dollars(income_year):
    """
    Compute the total household-directed Giving USA amount (in billions of dollars)
    for a given income year, using the category-weighted fraction methodology.

    For each Giving USA recipient category, we multiply that category's total
    reported giving ($B) by the fraction of those donations that ultimately
    flow to individual households as a private transfer. Summing across all
    categories gives the national HH-directed total.

    This replaces the simpler "15% of total giving" heuristic used in v4/v5.
    The category-weighted approach matters because the Giving USA recipient mix
    shifts significantly over time — Foundation giving (0% HH-directed) grew
    from ~8% in 1979 to ~14% by 2012, which the flat-rate approach would
    incorrectly count as household income.

    Returns
    -------
    (hh_total_billions, breakdown_dict)
      hh_total_billions  — total HH-directed giving in $B for this year
      breakdown_dict     — per-category detail for diagnostic printing
    Returns (None, {}) if the year isn't in our data.
    """
    year_data = giving_usa_by_recipient.get(income_year)
    if year_data is None:
        return None, {}

    breakdown = {}
    total_hh_billions = 0.0

    for category, amount_billions in year_data.items():
        if amount_billions is None:
            # This category wasn't tracked yet in this year (see notes above)
            continue
        hh_fraction = giving_hh_directed_fractions.get(category, 0.0)
        hh_amount   = amount_billions * hh_fraction
        breakdown[category] = {
            "amount_b": amount_billions,
            "frac":     hh_fraction,
            "hh_b":     hh_amount,
        }
        total_hh_billions += hh_amount

    return total_hh_billions, breakdown


# ---------------------------------------------------------------------------
# CPS "not in universe" sentinel values (from IPUMS CPS codebook)
# ---------------------------------------------------------------------------
# Any CPS value at or above these thresholds is a placeholder code, not real
# income data. We zero these out before any calculations.
private_transfer_niu_sentinels = {
    "INCCHILD": 999999,
    "INCASIST": 9999999,
    "INCOTHER": 9999999,
    "INCALIM":  999999,
    "INCALOTH": 99999,
}

# ===========================================================================
# STEP 0: Verify that all upstream panel CSVs exist before we begin
# ===========================================================================
# This script depends on outputs from the three prior scripts. If any are
# missing, we print a clear error message and exit rather than producing
# garbage results with silent zeros.

print("=" * 72)
print("income_after_taxes_panel.py — Income After Transfers and Taxes")
print("All income years 1979–2022")
print("=" * 72)

required_upstream_files = {
    "earned_income_panel.csv": "Earned Income panel",
    "transfer_distribution_panel.csv": "Government Transfer panel",
    "tax_distribution_panel.csv": "Tax Distribution panel",
}

missing_files = []
for fname, label in required_upstream_files.items():
    if not os.path.exists(upstream_path(fname)):
        missing_files.append(f"  ✗ {fname}  [{label}]")

if missing_files:
    print()
    print("ERROR: Required upstream panel CSVs not found.")
    print("Run the following scripts first:")
    for msg in missing_files:
        print(msg)
    print()
    print("  python build_earned_income_panel.py")
    print("  python transfer_distribution_panel.py")
    print("  python tax_distribution_panel.py")
    sys.exit(1)

print()
for fname, label in required_upstream_files.items():
    print(f"  ✓ {fname}  [{label}]")

# ===========================================================================
# STEP 1: Load the three upstream panel CSVs into lookup dicts
# ===========================================================================
# We index each panel by (income_year, quintile) so per-year lookups are O(1).

print()
print("=" * 72)
print("STEP 1  Loading upstream table panels")
print("=" * 72)

# ── Table 2.1: Earned Income ─────────────────────────────────────────────
t21_raw = pd.read_csv(upstream_path("earned_income_panel.csv"))
earned_lookup = {}
for _, row in t21_raw.iterrows():
    yr    = int(row["income_year"])
    qname = str(row["quintile_name"]).strip().capitalize()
    val   = float(row["total"])
    if yr not in earned_lookup:
        earned_lookup[yr] = {}
    earned_lookup[yr][qname] = val
print(f"  Table 2.1: {len(earned_lookup)} income years, "
      f"{min(earned_lookup)}–{max(earned_lookup)}")

# ── Table 2.2: Government Transfers ──────────────────────────────────────
t22_raw = pd.read_csv(upstream_path("transfer_distribution_panel.csv"))
govt_transfer_lookup = {}
for _, row in t22_raw.iterrows():
    yr    = int(row["income_year"])
    qname = str(row["quintile"]).strip().capitalize()
    if qname == "Average":
        continue
    val = float(row["total_govt"])
    if yr not in govt_transfer_lookup:
        govt_transfer_lookup[yr] = {}
    govt_transfer_lookup[yr][qname] = val

    # Also capture households-per-quintile for CPS scaling (v17 uses n_hh_per_q;
    # earlier versions used n_q — try both column names)
    for col_candidate in ("n_hh_per_q", "n_q"):
        if col_candidate in row.index:
            try:
                govt_transfer_lookup[yr]["_n_q"] = float(row[col_candidate])
            except (ValueError, TypeError):
                pass
            break
    for col_candidate in ("n_hh_total", "n_total"):
        if col_candidate in row.index:
            try:
                govt_transfer_lookup[yr]["_n_total"] = float(row[col_candidate])
            except (ValueError, TypeError):
                pass
            break

print(f"  Table 2.2: {len(govt_transfer_lookup)} income years, "
      f"{min(govt_transfer_lookup)}–{max(govt_transfer_lookup)}")

# ── Table 2.3: Taxes ──────────────────────────────────────────────────────
t23_raw = pd.read_csv(upstream_path("tax_distribution_panel.csv"))
taxes_lookup = {}
for _, row in t23_raw.iterrows():
    yr    = int(row["income_year"])
    qname = str(row["quintile"]).strip().capitalize()
    val   = float(row["total_taxes"])
    if yr not in taxes_lookup:
        taxes_lookup[yr] = {}
    taxes_lookup[yr][qname] = val
print(f"  Table 2.3: {len(taxes_lookup)} income years, "
      f"{min(taxes_lookup)}–{max(taxes_lookup)}")

# Identify years present in all three panels — these are the years we can assemble
years_with_all_data = sorted(set(earned_lookup) & set(govt_transfer_lookup) & set(taxes_lookup))
print(f"\n  Years with complete data across all three panels: {len(years_with_all_data)} "
      f"({years_with_all_data[0]}–{years_with_all_data[-1]})")

missing_from_run = [y for y in income_years_to_run if y not in years_with_all_data]
if missing_from_run:
    print(f"  Skipping years not in all three panels: {missing_from_run}")

# ===========================================================================
# STEP 2: Load the CPS ASEC panel (once, all years)
# ===========================================================================
# The CPS provides private transfer income at the household level. We load
# the full multi-year file once rather than re-reading it inside the year loop.

print()
print("=" * 72)
print("STEP 2  Loading CPS ASEC panel (all survey years)")
print("=" * 72)

cps_candidate_files = ["cps_00015.csv", "cps_00010.csv"]

def find_cps_file():
    """Search for the CPS ASEC extract in the script directory."""
    for filename in cps_candidate_files:
        full_path = build_path(filename)
        if os.path.exists(full_path):
            return full_path
    return None

cps_filepath = find_cps_file()
if cps_filepath is None:
    print("ERROR: No CPS ASEC file found. Tried:")
    for c in cps_candidate_files:
        print(f"  {build_path(c)}")
    sys.exit(1)

print(f"  File: {cps_filepath}")
raw_cps = pd.read_csv(cps_filepath, low_memory=False)
print(f"  Loaded {len(raw_cps):,} person records")

# ASECFLAG==1 filters to March supplement records only (excludes basic monthly CPS)
if "ASECFLAG" in raw_cps.columns:
    raw_cps = raw_cps[raw_cps["ASECFLAG"] == 1].copy()
    print(f"  After ASECFLAG==1 filter: {len(raw_cps):,} records")

if "YEAR" not in raw_cps.columns:
    print("ERROR: CPS file has no YEAR column.")
    sys.exit(1)

survey_years_available = sorted(raw_cps["YEAR"].unique())
print(f"  Survey years present: {survey_years_available[0]}–{survey_years_available[-1]}")
income_years_in_cps = set(int(y) - 1 for y in survey_years_available)
print(f"  Income years covered: {min(income_years_in_cps)}–{max(income_years_in_cps)}")

# Zero out NIU sentinel values so they don't inflate private transfer totals
print("  Zeroing NIU sentinel values...")
for col_name, threshold in private_transfer_niu_sentinels.items():
    if col_name in raw_cps.columns:
        raw_cps[col_name] = pd.to_numeric(raw_cps[col_name], errors="coerce").fillna(0)
        niu_count = (raw_cps[col_name] >= threshold).sum()
        if niu_count > 0:
            raw_cps.loc[raw_cps[col_name] >= threshold, col_name] = 0
            print(f"    {col_name}: zeroed {niu_count:,} NIU rows (threshold ≥ {threshold:,})")
    else:
        raw_cps[col_name] = 0.0

# Similarly zero NIU values for market income columns used to rank households
for col_name in ["INCWAGE", "INCBUS", "INCFARM"]:
    if col_name in raw_cps.columns:
        raw_cps[col_name] = pd.to_numeric(raw_cps[col_name], errors="coerce").fillna(0)
        niu_count = (raw_cps[col_name] >= 99999999).sum()
        if niu_count > 0:
            raw_cps.loc[raw_cps[col_name] >= 99999999, col_name] = 0

raw_cps["ASECWTH"] = pd.to_numeric(raw_cps["ASECWTH"], errors="coerce").fillna(0)
raw_cps["YEAR"]    = pd.to_numeric(raw_cps["YEAR"], errors="coerce").fillna(0).astype(int)

# ===========================================================================
# STEP 3: Define private transfer computation function
# ===========================================================================

print()
print("=" * 72)
print("STEP 3  Private Transfer Three-Component Model")
print("=" * 72)
print("""
Component A weights (Census Child Support Supplement 2018):
  Bottom: 15%  Second: 35%  Middle: 28%  Fourth: 14%  Top: 8%

Component B weights (Karen 2023, LIS WP 851 — normalized odds ratios):""")
for q in quintile_labels:
    print(f"  {q}: odds={karen_raw_odds[q]:.2f}  share={informal_assistance_weights[q]:.1%}")
print("""
Giving USA HH-directed weights (Feeding America + CBO 2020):
  Bottom: 45%  Second: 30%  Middle: 15%  Fourth: 6%  Top: 4%

HH-directed amount = Σ(category_$B × category_fraction)
  Religion 5%, Education 5%, Human Services 50%, Health 8%,
  Public-Society 5%, International 25%, Foundations 0%,
  Arts 0%, Environment 0%, Individuals 100%
""")


def compute_private_transfers(income_year, all_years_cps, households_per_quintile):
    """
    Compute per-household private transfer amounts for each quintile.

    The Giving USA component uses the category-weighted HH-directed fractions
    (defined in giving_hh_directed_fractions) rather than a flat multiplier.

    Parameters
    ----------
    income_year             : int
    all_years_cps           : pd.DataFrame — full multi-year CPS ASEC extract
    households_per_quintile : float — actual HH count per quintile from Table 2.2
                              (used to scale CPS sample weights to national totals)

    Returns
    -------
    (priv_per_hh, debug_info)  — or None if no CPS data for this year

    priv_per_hh : dict {quintile -> per-HH private transfer dollars}
    debug_info  : dict with intermediate values for diagnostics
    """
    survey_year = income_year + 1
    year_cps    = all_years_cps[all_years_cps["YEAR"] == survey_year].copy()

    if year_cps.empty:
        return None

    # ── Aggregate person records to household level ───────────────────────
    # We sum private transfer income across all members of each household
    # (SERIAL is the household identifier in IPUMS CPS)
    for col_name in ["INCWAGE", "INCBUS", "INCFARM",
                     "INCCHILD", "INCASIST", "INCOTHER", "INCALIM", "INCALOTH"]:
        if col_name not in year_cps.columns:
            year_cps[col_name] = 0.0

    household_df = year_cps.groupby("SERIAL").agg(
        hh_weight = ("ASECWTH",  "first"),  # household weight (same for all members)
        hh_child  = ("INCCHILD", "sum"),    # child support income
        hh_asist  = ("INCASIST", "sum"),    # informal cash assistance
        hh_other  = ("INCOTHER", "sum"),    # other miscellaneous transfer income
        hh_alim   = ("INCALIM",  "sum"),    # alimony (reported separately pre-2019)
        hh_aloth  = ("INCALOTH", "sum"),    # combined alimony+other (pre-1988 only)
    ).reset_index()

    total_cps_weight = household_df["hh_weight"].sum()

    # Scale CPS sample weights to match the actual national household count
    # from Table 2.2. This ensures our aggregate private transfer totals are
    # nationally representative rather than CPS-sample-specific.
    if households_per_quintile and households_per_quintile > 0 and total_cps_weight > 0:
        national_total_hh = households_per_quintile * 5
        cps_scaling_factor = national_total_hh / total_cps_weight
    else:
        cps_scaling_factor = 1.0

    def weighted_national_sum(col_name):
        """Compute the weighted national aggregate for a given CPS column."""
        return (household_df[col_name] * household_df["hh_weight"]).sum() * cps_scaling_factor

    # ── Component A: child support + alimony ────────────────────────────
    if income_year >= 1988:
        # From 1988 onward CPS reports INCCHILD and INCALIM separately
        child_support_national = weighted_national_sum("hh_child")
        informal_assist_national = weighted_national_sum("hh_asist")
        other_transfer_national  = weighted_national_sum("hh_other")

        if income_year < 2019:
            # INCALIM reported separately through 2018; from 2019 it's rolled into INCOTHER
            alimony_national = weighted_national_sum("hh_alim")
        else:
            alimony_national = 0.0

        # Merge alimony into child support — both are court-ordered transfers
        # and share the same distributional pattern
        child_support_national += alimony_national
    else:
        # Pre-1988: INCALOTH is the only available proxy for informal transfers
        child_support_national   = 0.0
        informal_assist_national = weighted_national_sum("hh_aloth")
        other_transfer_national  = 0.0

    # ── Component C: Giving USA household-directed amount ───────────────
    giving_hh_billions, giving_breakdown = giving_usa_hh_directed_dollars(income_year)

    if giving_hh_billions is None:
        # Should not happen for years 1979–2022, but handle gracefully
        giving_national_dollars = 0.0
        giving_hh_billions = 0.0
        print(f"  WARNING: No Giving USA data for {income_year} — component set to $0")
    else:
        giving_national_dollars = giving_hh_billions * 1e9

    # ── Distribute each component to quintiles ──────────────────────────
    # Each component gets allocated using its own distributional weights,
    # then divided by households-per-quintile to get a per-HH dollar amount.
    households_per_q = (households_per_quintile
                        if households_per_quintile and households_per_quintile > 0
                        else total_cps_weight / 5.0)

    # National totals and their corresponding quintile weight vectors
    component_nationals = {
        "INCCHILD":    child_support_national,
        "INCASIST":    informal_assist_national,
        "INCOTHER":    other_transfer_national,
        "GivingUSA_HH": giving_national_dollars,
    }
    component_weight_vectors = {
        "INCCHILD":     child_support_weights,
        "INCASIST":     informal_assistance_weights,
        "INCOTHER":     informal_assistance_weights,   # same distribution as INCASIST
        "GivingUSA_HH": giving_usa_quintile_weights,
    }

    raw_priv_per_hh = {q: 0.0 for q in quintile_labels}
    for component, national_total in component_nationals.items():
        for q in quintile_labels:
            raw_priv_per_hh[q] += (national_total
                                   * component_weight_vectors[component][q]
                                   / households_per_q)

    priv_per_hh = {q: round(raw_priv_per_hh[q]) for q in quintile_labels}
    priv_per_hh["Average"] = round(sum(priv_per_hh[q] for q in quintile_labels) / 5)

    return priv_per_hh, {
        "total_cps_hh_weight": total_cps_weight,
        "hh_per_quintile_cps": total_cps_weight / 5.0,
        "hh_per_quintile_ref": households_per_q,
        "cps_scaling_factor":  cps_scaling_factor,
        "child_support_national": child_support_national,
        "informal_assist_national": informal_assist_national,
        "other_transfer_national": other_transfer_national,
        "giving_hh_billions":  giving_hh_billions,
        "giving_national_dollars": giving_national_dollars,
        "giving_breakdown":    giving_breakdown,
    }

# ===========================================================================
# STEP 4: Main loop — assemble Table 2.4 for all years
# ===========================================================================

print()
print("=" * 72)
print("STEP 4  Assembling Table 2.4 for all years")
print("=" * 72)

all_panel_rows = []
skipped_years  = []
cps_missing_years = []

for income_year in years_with_all_data:

    # Check that all five quintiles are present in each upstream table
    earned_yr = earned_lookup.get(income_year, {})
    if len([q for q in quintile_labels if q in earned_yr]) < 5:
        skipped_years.append(income_year)
        print(f"  SKIP {income_year}: incomplete Table 2.1 data")
        continue

    govt_yr = govt_transfer_lookup.get(income_year, {})
    if len([q for q in quintile_labels if q in govt_yr]) < 5:
        skipped_years.append(income_year)
        print(f"  SKIP {income_year}: incomplete Table 2.2 data")
        continue

    taxes_yr = taxes_lookup.get(income_year, {})
    if len([q for q in quintile_labels if q in taxes_yr]) < 5:
        skipped_years.append(income_year)
        print(f"  SKIP {income_year}: incomplete Table 2.3 data")
        continue

    # Pull household count from Table 2.2 (needed to scale CPS to national totals)
    n_q = govt_yr.get("_n_q", None)
    if n_q is None:
        n_total = govt_yr.get("_n_total", None)
        n_q = n_total / 5 if n_total else None

    # Compute private transfers for this year
    result = compute_private_transfers(income_year, raw_cps, n_q)

    if result is None:
        # CPS data not available — use Giving USA component only (category-weighted)
        cps_missing_years.append(income_year)
        giving_hh_billions, _ = giving_usa_hh_directed_dollars(income_year)
        giving_national = (giving_hh_billions * 1e9) if giving_hh_billions else 0.0
        fallback_n_q = n_q if n_q else 100_000_000 / 5

        priv_per_hh = {
            q: round(giving_national * giving_usa_quintile_weights[q] / fallback_n_q)
            for q in quintile_labels
        }
        priv_per_hh["Average"] = round(sum(priv_per_hh[q] for q in quintile_labels) / 5)
        debug_info = {
            "total_cps_hh_weight": 0,
            "hh_per_quintile_cps": fallback_n_q,
            "child_support_national": 0, "informal_assist_national": 0,
            "other_transfer_national": 0,
            "giving_hh_billions": giving_hh_billions or 0.0,
            "giving_national_dollars": giving_national,
            "cps_scaling_factor": 0,
        }
    else:
        priv_per_hh, debug_info = result

    # ── Compute averages across quintiles (used for the "Average" row) ──
    earned_avg = round(sum(earned_yr[q] for q in quintile_labels) / 5)
    govt_avg   = round(sum(govt_yr[q]   for q in quintile_labels) / 5)
    priv_avg   = priv_per_hh["Average"]
    taxes_avg  = round(sum(taxes_yr[q]  for q in quintile_labels) / 5)

    # ── Assemble per-quintile rows ───────────────────────────────────────
    for q in quintile_labels:
        earned = earned_yr[q]
        govt   = govt_yr[q]
        priv   = priv_per_hh[q]
        taxes  = taxes_yr[q]

        income_before_taxes = earned + govt + priv
        income_after_taxes  = income_before_taxes - taxes
        # Signed net effective tax rate: (taxes − transfers) / earned × 100.
        # Negative for net recipients (bottom quintiles — households whose IAT
        # exceeds their earned income because received transfers exceed paid
        # taxes); positive for net payers (upper quintiles).  Matches the
        # formula used in Chart 3 of income_visualizations.py.
        tax_share_of_ibt = (round((taxes - govt - priv) / earned * 100, 2)
                            if earned > 0 else 0.0)
        # Income after taxes & transfers expressed as a percentage of earned
        # income. A value above 100 means net transfers received exceed taxes
        # paid (typical for the bottom of the distribution); a value below 100
        # means the household keeps less than it earned after the fiscal system.
        iat_pct_earned   = (round(income_after_taxes / earned * 100, 1)
                            if earned > 0 else 0.0)

        all_panel_rows.append({
            "income_year":    income_year,
            "quintile":       q,
            "earned":         round(earned),
            "govt_transfers": round(govt),
            "priv_transfers": round(priv),
            "ibt":            round(income_before_taxes),
            "taxes":          round(taxes),
            "iat":            round(income_after_taxes),
            "iat_pct_earned": iat_pct_earned,
            "tax_pct_ibt":    tax_share_of_ibt,
        })

    # ── Average row ──────────────────────────────────────────────────────
    ibt_avg = earned_avg + govt_avg + priv_avg
    iat_avg = ibt_avg - taxes_avg
    # Signed net rate uses earned in the denominator (same as quintile rows)
    tax_pct_avg = (round((taxes_avg - govt_avg - priv_avg) / earned_avg * 100, 2)
                   if earned_avg > 0 else 0.0)
    iat_pct_avg = (round(iat_avg / earned_avg * 100, 1)
                   if earned_avg > 0 else 0.0)

    all_panel_rows.append({
        "income_year":    income_year,
        "quintile":       "Average",
        "earned":         round(earned_avg),
        "govt_transfers": round(govt_avg),
        "priv_transfers": round(priv_avg),
        "ibt":            round(ibt_avg),
        "taxes":          round(taxes_avg),
        "iat":            round(iat_avg),
        "iat_pct_earned": iat_pct_avg,
        "tax_pct_ibt":    tax_pct_avg,
    })

    print(f"  {income_year}: earned={earned_avg:>8,}  govt={govt_avg:>8,}  "
          f"priv={priv_avg:>6,}  taxes={taxes_avg:>8,}  "
          f"IAT={iat_avg:>8,}  "
          f"scale={debug_info.get('cps_scaling_factor', 0):.0f}x  "
          f"GivingUSA_HH=${debug_info['giving_hh_billions']:.2f}B")

if skipped_years:
    print(f"\n  Skipped (incomplete upstream data): {skipped_years}")
if cps_missing_years:
    print(f"  Years with no CPS data (Giving USA component only): {cps_missing_years}")

# ===========================================================================
# STEP 5: Build the panel DataFrame and save to CSV
# ===========================================================================

print()
print("=" * 72)
print("STEP 5  Building panel CSV")
print("=" * 72)

results_panel = pd.DataFrame(all_panel_rows)
print(f"  Panel shape: {results_panel.shape}")

output_csv_path = os.path.join(OUTPUT_DIR, "income_after_taxes_transfers_panel.csv")
results_panel.to_csv(output_csv_path, index=False)
print(f"  Saved → {output_csv_path}")

# ===========================================================================
# STEP 7: Giving USA category-weighted breakdown — diagnostic for select years
# ===========================================================================
# This shows exactly how the HH-directed total was computed for each benchmark
# year, which makes the methodology transparent and easy to audit.

print()
print("=" * 72)
print("STEP 7  Giving USA HH-Directed Breakdown (category-weighted, select years)")
print("=" * 72)
print()
print("  Method: HH_directed_$B = Σ(category_$B × HH_directed_fraction)")
print("  Fractions used: Religion 5%, Education 5%, Human Services 50%,")
print("                  Health 8%, Public-Society 5%, Foundations 0%,")
print("                  International 25%, Arts 0%, Environment 0%, Individuals 100%")
print()

diagnostic_years = {1979, 1990, 2000, 2005, 2010, 2017, 2020, 2022}
for year in sorted(giving_usa_by_recipient.keys()):
    if year not in diagnostic_years:
        continue

    hh_billions, breakdown = giving_usa_hh_directed_dollars(year)
    total_giving_billions  = sum(
        v for v in giving_usa_by_recipient[year].values() if v is not None
    )
    effective_rate = hh_billions / total_giving_billions if total_giving_billions > 0 else 0.0

    print(f"  {year}  Total giving: ${total_giving_billions:.2f}B  →  "
          f"HH-directed: ${hh_billions:.2f}B  "
          f"({effective_rate:.1%} effective HH rate)")

    # Print only categories that actually contribute something
    for cat, details in sorted(breakdown.items(), key=lambda x: -x[1]["hh_b"]):
        if details["hh_b"] > 0:
            print(f"    {cat:<30}: ${details['amount_b']:>6.2f}B × {details['frac']:.0%} "
                  f"= ${details['hh_b']:>6.2f}B")
    print()

# ===========================================================================
# STEP 8: Print panel summary — "Average" row for selected benchmark years
# ===========================================================================

print()
print("=" * 72)
print("STEP 8  Panel Summary — Average row, selected years")
print("=" * 72)

avg_panel = results_panel[results_panel["quintile"] == "Average"].sort_values("income_year")
print()
print(f"  {'Year':>6} {'Earned':>10} {'Govt':>10} {'Priv':>8} {'IBT':>10} "
      f"{'Taxes':>10} {'IAT':>10} {'Tax%':>7}")
print("  " + "─" * 76)

benchmark_years_to_show = {1979, 1985, 1990, 1995, 2000, 2005, 2010, 2015, 2017, 2020, 2022}
for _, row in avg_panel.iterrows():
    yr = int(row["income_year"])
    if yr in benchmark_years_to_show:
        print(f"  {yr:>6} {int(row['earned']):>10,} "
              f"{int(row['govt_transfers']):>10,} "
              f"{int(row['priv_transfers']):>8,} {int(row['ibt']):>10,} "
              f"{int(row['taxes']):>10,} {int(row['iat']):>10,} "
              f"{row['tax_pct_ibt']:>7.1f}")

print("  " + "─" * 76)
print()
print("=" * 72)
print(f"COMPLETE — income_after_taxes_transfers_panel.csv "
      f"({len(results_panel)} rows, "
      f"{results_panel['income_year'].nunique()} income years × "
      f"{results_panel['quintile'].nunique()} quintile rows)")
print("=" * 72)
