# U.S. Household Income, Taxes, and Transfers
## A Reproducible Distributional Panel, 1979–2022

This project builds a long-format distributional accounting panel covering
earned income, government transfers, private transfers, and the full tax
burden (federal + state & local) for U.S. households by income quintile from
1979 through 2022. Upper-tail groups (the 81–90, 91–95, 96–99 sub-groups,
the Top 1%, Top 0.1%, Top 0.01%, Top 0.001%, and the Forbes 400) are
included where data permit.

The pipeline supplements CPS ASEC microdata with administrative control
totals from the CBO, IRS Statistics of Income, BEA NIPA, OMB Historical
Tables, BLS, SSA, CMS, USDA, USAC, the Tax Policy Center / Census State &
Local Government Finance survey, and Giving USA. Every dollar of income,
transfer, and tax is traced back to a primary public source.

The framing draws on Phil Gramm, Robert Ekelund, and John Early's
*The Myth of American Inequality* (Rowman & Littlefield, 2022), which
argues that the official Census Bureau "money income" measure is the wrong
quantity for distributional analysis — it omits both two-thirds of federal
transfer payments (Medicare, Medicaid, SNAP, housing, EITC, refundable
CTC) and 100% of taxes paid. This project replicates that argument's data
architecture end-to-end from public sources rather than relying on the
book's intermediate appendices.

---

## Why this project exists

The U.S. Census Bureau's official income-inequality measure counts only
"money income" — wages, salaries, and a handful of cash transfers (Social
Security, SSI, public assistance, unemployment insurance). It excludes:

* **Roughly two-thirds of all federal transfer payments** — Medicare,
  Medicaid, SNAP, housing assistance, the EITC, and the refundable Child
  Tax Credit. None of these flow through household checking accounts the
  way the 1947-vintage Census definition required.
* **All federal, state, and local taxes paid.** A household earning $200K
  and a household earning $30K both contribute their *pretax* figure to
  the Census ranking, even though the higher-income household typically
  loses ~33% of pretax income to taxes and the lower-income household ~7%.

The mismatch has grown over the period this panel covers. In 1947, government
transfers were 2.5% of personal income and Census counted >90% of them. By
1979, transfers had risen to 11.8% and Census counted less than half. By
2017, transfers were 18.2% of personal income and Census counted roughly
one-third. The taxes-paid omission has the opposite tilt at the top: the
federal tax code became more progressive post-1979, so the gap between
Census's pretax measure and a post-fisc measure has widened systematically.

---

## Repository structure

```
tax-transfer-inequality/
│
├── README.md                  ← this file
├── LICENSE                    ← MIT
├── requirements.txt           ← Python dependencies
│
├── src/                       ← canonical Python scripts (9 files)
│   ├── build_earned_income_panel.py            Stage 1
│   ├── transfer_distribution_panel.py          Stage 2
│   ├── tax_distribution_panel.py               Stage 3
│   ├── income_after_taxes_transfers_panel.py   Stage 4
│   ├── top_percentile_taxes_transfers_panel.py Stage 5
│   ├── income_visualizations.py                Charts 1–4 (quintile-level)
│   ├── charts_5_6_ultra_top.py                 Charts 5–6 (top-of-distribution)
│   ├── report_figures.py                       Charts for the research report
│   ├── cpi_bias_adjusted_v3_dbpi.py            True-CPI deflator builder
│   └── reserve + data scripts/                 retired helpers, kept for audit
│
├── notebooks/                 ← Jupyter versions of the nine scripts above
│   ├── 01_build_earned_income_panel.ipynb
│   ├── 02_transfer_distribution_panel.ipynb
│   ├── 03_tax_distribution_panel.ipynb
│   ├── 04_income_after_taxes_transfers_panel.ipynb
│   ├── 05_top_percentile_taxes_transfers_panel.ipynb
│   ├── 06_income_visualizations.ipynb
│   ├── 07_charts_5_6_ultra_top.ipynb
│   ├── 08_report_figures.ipynb
│   ├── 09_cpi_bias_adjusted_v3_dbpi.ipynb
│   └── README.md
│
├── tools/
│   └── py_to_nb.py            ← regenerate notebooks from src/
│
├── data/raw/                  ← every administrative input the scripts read
│   ├── bea/                   BEA NIPA Table 3.12 (government social benefits)
│   ├── bls_ce/                BLS Consumer Expenditure Survey
│   ├── bls_pumd/              BLS CE public-use microdata, intrvw15-22.zip
│   ├── cbo/                   CBO distributional supplemental tables 01–12
│   ├── census_sl/             TPC/Census State & Local Government Finance
│   ├── forbes-400-irs/        IRS Top 400 PDFs, 1992–2014
│   ├── giving_USA/            Giving USA recipient totals 1979–2022 (CSV)
│   ├── irs_soi/               IRS SOI Table 4.1 + Table 3/4.3 income composition
│   ├── itep/                  ITEP "Who Pays?" cross-reference (not in pipeline)
│   ├── meds/                  CMS National Health Expenditures (Medicare)
│   ├── oasdi/                 SSA OASI/DI Trust Fund Cost CSVs
│   ├── omb/                   OMB Historical Tables 2.1/2.4/2.5 + outlays_fy2027
│   ├── psz/                   Piketty-Saez-Zucman DINA tables (cross-reference)
│   ├── ahs/                   American Housing Survey (reserve)
│   ├── usac/                  USAC USF Lifeline disbursements + annual reports
│   └── usda/                  USDA NSLP, WIC, SNAP outlay tables
│
├── output/                    ← all generated artefacts
│   ├── earned_income_panel.csv
│   ├── transfer_distribution_panel.csv
│   ├── tax_distribution_panel.csv
│   ├── income_after_taxes_transfers_panel.csv
│   ├── top_percentile_taxes_transfers_panel.csv
│   ├── cpi_adjusted_v3_dbpi_1979_2022.csv
│   ├── cpi_headline_v3.png
│   └── fig_*.png  (9 generated charts)
│
└── docs/                      ← written documentation
    ├── research_report.tex
    ├── research_report.pdf
    └── DATA_DICTIONARY_AND_METHODOLOGY.md   (early-vintage reference, retained)
```

Each panel-builder script auto-discovers `data/raw/` by walking up from its
own location, so the pipeline runs the same whether the script lives in
`src/` or in `notebooks/`. Override either folder by setting `DATA_ROOT`
or `OUTPUT_DIR` environment variables.

---

## Pipeline

```
                               ┌── CPS ASEC microdata (IPUMS)
                               ├── CBO Table 5 (income composition)
                               ├── BLS ECEC benefit rates (inline constants)
                               └── True CPI deflator (Early & Furth 2021)
                                          │
                                          ▼
                            build_earned_income_panel.py  ── Stage 1
                                          │
                                          ▼
                              earned_income_panel.csv
                                          │
                                          │
       CPS ASEC ─────────────────────────────────────┐
       CBO T05/T06 (income & means-tested) ──────────┤
       SSA OASI & DI Trust Fund Cost ────────────────┤
       CMS NHE (Medicare) ───────────────────────────┤  ──►  transfer_distribution_panel.py
       BEA NIPA Table 3.12 ──────────────────────────┤              │  ── Stage 2
       OMB outlays_fy2027 (Function 604 + CRS) ──────┤              ▼
       USDA NSLP + WIC ──────────────────────────────┤   transfer_distribution_panel.csv
       USAC USF Lifeline ────────────────────────────┘              │
                                                                    │
       CPS ASEC (homeowner × wage) ────────┐                        │
       CBO T01/T07/T12 ────────────────────┤                        │
       OMB Tables 2.1 / 2.4 / 2.5 ─────────┤  ──►  tax_distribution_panel.py
       TPC/Census S&L Finance (results.csv)┤              │  ── Stage 3
       BLS CEX expenditure-share panel ────┘              ▼
                                                tax_distribution_panel.csv
                                                                    │
   earned_income_panel.csv ──────────┐                              │
   transfer_distribution_panel.csv ──┤                              │
   tax_distribution_panel.csv ───────┤  ──►  income_after_taxes_transfers_panel.py
   CPS ASEC (private-transfer cols) ─┤              │   ── Stage 4
   Giving USA recipient CSV ─────────┘              ▼
                                  income_after_taxes_transfers_panel.csv
                                                                    │
   CBO T01/T03/T05/T07 ───────────────┐                              │
   IRS T41TS (22in41ts.xls) ──────────┤                              │
   IRS Top 400 (1992-2014 PDFs)   ────┤                              │
   IRS Table 3 / 4.3 (2014–2022 xls) ─┤  ──►  top_percentile_taxes_transfers_panel.py
   TPC/Census S&L Finance ────────────┤                  │   ── Stage 5
   BLS CEX expenditure-share panel ───┤                  ▼
   CPS ASEC ──────────────────────────┘  top_percentile_taxes_transfers_panel.csv
                                                                    │
                                                                    ▼
                              Visualization layer (Stages 6–8):
                              income_visualizations.py    →  5 figures
                              charts_5_6_ultra_top.py     →  2 figures
                              report_figures.py           →  2 figures
                              cpi_bias_adjusted_v3_dbpi.py →  True CPI series + 2 figures
```

---

## Stage descriptions

### Stage 1 — `build_earned_income_panel.py`
Per-household earned income by quintile, 1979–2022. Households are ranked
annually by total earned income using CPS ASEC survey weights.

* Earned income = wages + employer benefits (BLS ECEC-imputed) +
  business income + financial income (interest, dividends, rent, retirement).
* Employer-paid benefits are imputed from year-specific BLS Employer Costs
  for Employee Compensation (ECEC) ratios applied to wages.
* A small in-kind compensation correction is added to the lower quintiles
  to account for non-cash compensation not captured by CPS ASEC, consistent
  with Meyer & Sullivan (2012). The corrections are: Bottom +17.1%,
  Second +9.6%, Middle +6.8%, Fourth +4.2%, Top +3.6% of wage income.

Writes `output/earned_income_panel.csv` (220 rows: 5 quintiles × 44 years).

### Stage 2 — `transfer_distribution_panel.py`
Government transfer payments by quintile, 1979–2022. Covers OASI, SSDI,
Medicare (net of beneficiary-paid Part B/D premiums and out-of-pocket cost
sharing), Medicaid + CHIP, SNAP, all other federal transfers (UI, TANF,
SSI, EITC, housing, etc.), and state & local safety-net programs.

National program totals come from administrative sources rather than
self-reported CPS receipts (which substantially underreport in-kind
benefits):

| Program | National-total source |
|---|---|
| OASI | SSA *Annual Statistical Supplement, 2025*, Table 4.A1 |
| SSDI | SSA *Annual Statistical Supplement, 2025*, Table 4.A2 |
| Medicare (gross) | CMS National Health Expenditure, NHE2024.xlsx |
| Medicare premium offset | CMS Medicare Trustees Report (SMI summary tables) |
| Medicare cost-share offset | MedPAC Payment Basics; CMS Actuarial Reports |
| Medicaid + CHIP | BEA NIPA Table 3.12 |
| SNAP | BEA NIPA Table 3.12 |
| Other cash | BEA NIPA Table 3.12 |
| Housing Subfunction 604 | OMB Public Budget Database `outlays_fy2027.xlsx`, summed across all rows with Subfunction Code = 604 |
| LIHEAP, Head Start, CCDBG, CCE, SSBG, Foster Care, TANF | OMB Public Budget Database, account-level rows |
| NSLP | USDA cncost.xlsx |
| WIC | USDA wisummary.xlsx |
| Lifeline (USAC USF) | USAC `USAC_USF_Disbursements_1998_2022.xlsx` (hand-cleaned panel built from USAC Annual Reports 1999–2024) |

**Quintile distribution weights** come from CBO Tables 5 and 6, except for
OASI where the script re-ranks households by earned income using the CPS
ASEC extract when available (and falls back to CBO Table 5 social-security
shares otherwise). Medicare is reported net of premiums and out-of-pocket
cost-sharing so the figure reflects only the government-financed portion.

Writes `output/transfer_distribution_panel.csv` (220 rows).

### Stage 3 — `tax_distribution_panel.py`
Full household tax burden (federal + state & local) by quintile, 1979–2022.

**Federal taxes** — personal income, payroll (OASDI + Medicare HI), excise,
estate/gift, customs, FUTA, railroad retirement, and other retirement —
come from CBO Tables 07 and 12 (per-household averages and quintile shares),
supplemented with OMB Historical Tables 2.1, 2.4, and 2.5 (`BUDGET-2022-TAB-3-1/3-4/3-5.xlsx`)
to back out specific receipt categories. Corporate income tax is excluded
from the household burden — households don't write a check for it directly.

**State and local taxes** are distributed from TPC/Census State & Local
Government Finance national totals (`results.csv`) using three keys:

| Component | Distribution key | Source |
|---|---|---|
| Sales (general + selective) | Year-specific quintile expenditure shares | BLS CEX panel (1984+; 1979–1983 use 1984 proxy) |
| Motor vehicle + other | Same CEX expenditure shares | BLS CEX panel |
| Property | Homeownership × household income proxy | CPS ASEC `OWNERSHP` × earned |
| State individual income | Wage income shares | CPS ASEC `INCWAGE` |

Writes `output/tax_distribution_panel.csv` (220 rows).

### Stage 4 — `income_after_taxes_transfers_panel.py`
Assembly stage. Joins the three upstream panels and adds **private
transfers** to compute Income Before Taxes (IBT) and Income After Taxes
and Transfers (IAT):

```
IBT = earned + govt_transfers + private_transfers
IAT = IBT − total_taxes
```

Private transfers come from three independent components:

| Component | Source | Distribution weights |
|---|---|---|
| Child support + alimony | CPS `INCCHILD`, `INCALIM`, `INCALOTH` | Census Child Support Supplement 2018; Q1=15%, Q2=35%, Q3=28%, Q4=14%, Q5=8% |
| Informal cash assistance | CPS `INCASIST`, `INCOTHER` | Karen (2023) LIS WP 851 Table 2 Model 1, normalized bivariate odds ratios |
| Household-directed charitable giving | `data/raw/giving_USA/giving_usa_recipients_1979_2022.csv` | Feeding America client distribution × CBO means-tested transfer shares |

For the Giving USA component, each recipient category is multiplied by the
share of donations actually reaching households:

| Recipient category | HH-directed fraction | Rationale |
|---|---|---|
| Religion | 5% | Food pantries, emergency cash from congregations |
| Education | 5% | Direct scholarships and student aid |
| Human Services | 50% | Feeding America, food banks, emergency cash |
| Foundations | 0% | Pass-through vehicles; counting would double-count |
| Health | 8% | Hospital charity care, patient assistance programs |
| Public-Society Benefit | 5% | Community development, some direct aid |
| International Affairs | 25% | GiveDirectly, food/medicine transfers |
| Arts / Culture | 0% | Institutional; does not reach individual households |
| Environment / Animals | 0% | Institutional |
| Individuals | 100% | By definition |

The quintile distribution of the household-directed total follows Feeding
America's published client income distribution: Q1=45%, Q2=30%, Q3=15%,
Q4=6%, Q5=4%.

Writes `output/income_after_taxes_transfers_panel.csv` (264 rows: 6 groups × 44 years).

### Stage 5 — `top_percentile_taxes_transfers_panel.py`
Extends the framework to ultra-high-income groups beyond the top quintile:
the 81–90, 91–95, 96–99, and Top 1% sub-groups (from CBO), plus Top 0.1%,
Top 0.01%, and Top 0.001% (from IRS Table 4.1 Time Series, 2001–2022),
and the Forbes 400 (from IRS Top 400 publications, 1992–2014, with
T41TS-based estimates for 2015–2022).

* IRS Table 3 / 4.3 income-composition files (`*in03etr*.xls` for 2014–2018,
  `*in43ts*.xls` for 2019–2022 — IRS renamed the table in 2019 with no
  schema change) feed labor / capital / pass-through splits.
* State & local taxes for ultra-top groups are scaled from the Top
  quintile burden using income-elasticity proxies (square root for
  property taxes, etc.).
* Private transfers for sub-groups inside the Top 20 are estimated by
  scaling the Top quintile per-HH value with a square-root income-elasticity
  decay. These should be read as upper bounds (actual ultra-top receipts
  likely closer to zero).

Writes `output/top_percentile_taxes_transfers_panel.csv` (~493 rows).

### Stages 6–8 — Visualizations
Three scripts that read the panels and produce nine figures, all written
to `output/`:

| Script | Figure |
|---|---|
| `income_visualizations.py` | `fig_real_earned_income_by_quintile.png`, `fig_real_income_after_taxes_transfers_by_quintile.png`, `fig_effective_tax_rate_by_quintile.png`, `fig_iat_pct_of_earned_by_quintile.png`, `fig_cumulative_income_growth_nominal_vs_real.png` |
| `charts_5_6_ultra_top.py` | `fig_real_earned_income_top_groups.png`, `fig_real_income_after_taxes_transfers_top_groups.png` |
| `report_figures.py` | `fig_inequality_ratio_before_after_fisc.png`, `fig_net_fiscal_position_by_quintile_2022.png` |

### Stage 9 — True CPI deflator (`cpi_bias_adjusted_v3_dbpi.py`)
Constructs the inflation index used to deflate the panels to real dollars.
Pulls eight series from FRED and the BLS Disease-Based Price Index (DBPI)
to produce three headline series: CPI-U (official), Chained CPI / PCEPI
(substitution bias removed), and True CPI (substitution + quality +
new-product bias removed).

Writes `output/cpi_adjusted_v3_dbpi_1979_2022.csv` and two PNGs.

The True CPI series compounds an empirical quality / new-product bias
schedule on top of the substitution-corrected index:

| Years | Remaining bias (pp/yr) | Source |
|---|---|---|
| 1979–1999 | 0.60 | Boskin Commission (1996) — pre-BLS geometric-mean reform |
| 2000–2017 | 0.37 | Moulton (2018) / Lebow & Rudd (2003) — post-reform residual |
| 2018–2022 | 0.30 | Post-BLS hedonic mobile-phone expansion (Jan 2018) |

By 2022, the cumulative gap between CPI-U (+303%) and True CPI (+176%) is
127 percentage points. The choice of deflator is not distributionally
neutral: the bottom quintile's real after-tax-and-transfer income grows
129% over 1979–2022 under True CPI but only ~33% under CPI-U.

---

## Output panels

| File | Rows | Description |
|---|---:|---|
| `earned_income_panel.csv` | 220 (5 × 44) | Earned income components by quintile |
| `transfer_distribution_panel.csv` | 220 | Government transfers by quintile |
| `tax_distribution_panel.csv` | 220 | Full federal + S&L tax burden by quintile |
| `income_after_taxes_transfers_panel.csv` | 264 (6 × 44) | IBT / IAT assembly with private transfers |
| `top_percentile_taxes_transfers_panel.csv` | ~493 | Ultra-top distributional accounting |
| `cpi_adjusted_v3_dbpi_1979_2022.csv` | 44 | Deflators: CPI-U, Chained CPI, True CPI |

---

## Headline findings

(All figures from the panels; see `docs/research_report.pdf` for full
discussion.)

* **Earned income at the bottom shrank in real terms.** Real earned income
  for the bottom quintile fell 48% between 1979 and 2022 (Early & Furth
  True CPI). For the top quintile it rose 108%.
* **After taxes and transfers, every quintile gained.** Real income after
  taxes and transfers rose 129% for the bottom quintile, 201% for the
  middle, and 349% for the top quintile.
* **The before/after gap matters quantitatively.** The top-to-bottom
  earned-income ratio in 2022 is 96×. The top-to-bottom IAT ratio is
  4.4×. In 1979, those two ratios were 24× and 2.3× respectively. The
  fiscal system is doing increasing redistributive work.
* **Effective tax rates differ sharply across quintiles in 2022.** The
  bottom quintile has a signed effective rate of −1,341% of earned income
  (transfers far exceed taxes). The middle is roughly fiscally neutral at
  −2%. The Top 1% pays +32%; the Top 0.001% pays +28%.
* **The very top is taxed at a slightly lower effective rate than the rest
  of the top quintile**, consistent with the larger capital-gains share of
  AGI at higher percentiles (preferential rates) and the cap on payroll
  taxes.

---

## How to reproduce

### Setup

```bash
git clone https://github.com/Patrickkp1/tax-transfer-inequality.git
cd tax-transfer-inequality
pip install -r requirements.txt
```

### One-time data downloads

The repo includes most administrative inputs, but two require external
accounts or large downloads:

* **CPS ASEC microdata (`data/raw/cps_00015.csv`)** — register at
  [cps.ipums.org](https://cps.ipums.org), build an extract using survey
  years 1980–2023 and the variable list under "CPS variables required"
  below, place the resulting CSV at `data/raw/cps_00015.csv`. IPUMS
  requires an end-user agreement; the extract is not redistributed in
  this repo.

* **CBO supplemental tables** — download the latest distributional
  supplement Excel from [cbo.gov/publication/59509](https://www.cbo.gov/publication/59509),
  place the CSV exports of tables 01, 03, 05, 06, 07, and 12 in
  `data/raw/cbo/`. The filenames the scripts expect match the pattern
  `households_ranked_by_market_inc_table_XX_*_1979_*.csv`.

All other inputs are already in `data/raw/` after a fresh clone.

### Execution order

Pipeline stages 1–5 must run in order (later stages read CSVs written by
earlier ones). Visualization stages 6–8 can run after stage 5 in any
order.

```bash
# Stage 1 — earned income
python src/build_earned_income_panel.py

# Stage 2 — government transfers
python src/transfer_distribution_panel.py

# Stage 3 — tax distribution
python src/tax_distribution_panel.py

# Stage 4 — IBT / IAT assembly with private transfers
python src/income_after_taxes_transfers_panel.py

# Stage 5 — ultra-top groups
python src/top_percentile_taxes_transfers_panel.py

# Charts (any order after stage 5)
python src/income_visualizations.py
python src/charts_5_6_ultra_top.py
python src/report_figures.py

# Optional: refresh the True CPI deflator (queries FRED at runtime)
python src/cpi_bias_adjusted_v3_dbpi.py
```

Or use the Jupyter equivalents — `jupyter notebook notebooks/` and step
through `01_*` through `09_*` in numeric order.

### Compile the research report

The PDF in `docs/research_report.pdf` is built from `research_report.tex`
plus the figures in `output/`. To rebuild:

```bash
cd docs
pdflatex research_report.tex
pdflatex research_report.tex   # second pass resolves cross-references
```

Requires a TeX distribution (MacTeX, TeX Live, or Overleaf for online
compilation).

---

## CPS variables required (IPUMS extract)

The pipeline expects these variables in the IPUMS CPS extract:

* **Identifiers**: `YEAR`, `SERIAL`, `ASECWTH`, `ASECFLAG`, `RELATE`
* **Demographics**: `AGE`, `EMPSTAT`, `SCHLCOLL`, `OWNERSHP`
* **Hours**: `WKSWORK1`, `UHRSWORKLY`, `UHRSWORK1`, `HOURWAGE`, `PAIDHOUR`
* **Earned income**: `INCWAGE`, `INCBUS`, `INCFARM`
* **Capital / retirement income**: `INCDIVID`, `INCINT`, `INCRENT`, `INCRETIR`
* **Aggregates**: `HHINCOME`
* **Private transfers**: `INCCHILD`, `INCASIST`, `INCOTHER`, `INCALIM`, `INCALOTH`

---

## Methodology appendix

This section is preserved from the original methodology blueprint
(`docs/DATA_DICTIONARY_AND_METHODOLOGY.md`) and documents the early-vintage
design choices that informed the current pipeline. The current scripts
have diverged from this blueprint in several places (most notably: S&L
taxes are no longer ITEP-based; private transfers are no longer scaled
from Gramm's 2017 values; the panel structure now produces five separate
CSVs instead of one master `comprehensive_panel.csv`). It is retained here
for audit purposes.

### Income concept

The income concept we attempt to measure for each household is:

```
IAT  =  E + G + P − T
```

where:

* `E` (earned income) — wages, employer benefits, business and financial income
* `G` (government transfers) — cash + in-kind, both social insurance and means-tested
* `P` (private transfers) — child support, alimony, informal cash assistance, household-directed charitable giving
* `T` (total taxes) — federal + state + local, individual only (corporate excluded)

The Census Bureau "money income" measure used in headline inequality
statistics is conceptually `E + G_cash` — it omits in-kind transfers
(`G − G_cash`), all of `P`, and all of `T`. Households are also *ranked*
by money income, not by a post-fisc concept, so a retired household
receiving $30K in Medicare benefits and a working-age household earning
$30K from wages appear in the same Census quintile despite very different
consumption capacity.

### Why True CPI rather than CPI-U

Any statement about real income growth depends on the price index used to
convert nominal dollars across decades. The default CPI-U is known to
overstate true inflation, and the overstatement compounds. Three documented
biases:

* **Substitution bias** (~0.5pp/yr) — CPI-U is a modified-Laspeyres index
  that holds expenditure shares fixed within a basket cycle; consumers
  substitute toward cheaper alternatives, but the index doesn't capture
  this. Removing it produces the "Chained CPI / PCEPI" line using BEA's
  PCEPI for 1979–1999 spliced to BLS's C-CPI-U from 2000.
* **Quality bias** — CPI assumes a 2022 car or phone is the same product
  as its 1979 counterpart, which it isn't. Boskin (1996) estimated 0.6pp/yr;
  Moulton (2018) estimates 0.37pp/yr post-2000 reforms; ~0.30pp/yr after
  BLS expanded hedonic adjustment to mobile phones in 2018.
* **New-product bias** — smartphones, GPS, video streaming, mRNA vaccines
  enter the index only after they reach mass adoption; their early-period
  welfare gains never appear in the price history.

The "True CPI" series compounds the documented bias schedule on top of the
substitution-corrected index, producing 176% cumulative inflation 1979–2022
versus 303% for the official CPI-U. Cross-checked against the BLS
Disease-Based Price Index for medical care, which shows ~50% cumulative
inflation 1999–2017 vs ~75% for official CPI Medical Care.

### S&L tax distribution methodology

The current pipeline distributes State & Local tax totals from TPC/Census
using three keys (BLS CEX expenditure shares for sales; CPS homeownership ×
income for property; CPS wage income for state income tax). An earlier
vintage of the project used ITEP "Who Pays?" effective tax rates applied
to CBO income, snapshot at 2024 law. That approach has the virtue of being
simple but the disadvantage of assuming S&L tax structures haven't changed
over 1979–2022 — which is plainly wrong (many states adopted income taxes
mid-period; Prop 13 capped property taxes in 1978; etc.). The CEX/CPS
approach used in the current pipeline picks up year-specific expenditure
patterns at the cost of more moving parts.

### Quintile ordering in the early years

A careful reader will notice that in `fig_real_income_after_taxes_transfers_by_quintile.png`
the Bottom and Second quintile lines nearly overlap and slightly cross for
the first few years of the panel (1979–1985). This is not a measurement
error but a real feature of the late-1970s post-fisc distribution.

In 1979 the Bottom quintile's per-household IAT was $9,029, slightly
above the Second quintile's $8,637. The cause is demographic: the Bottom
quintile in the late 1970s was disproportionately retired-elderly
households living on Social Security — very low earned income (~$2,800),
large OASI benefits (~$8,100), almost no income tax. The Second quintile
was disproportionately working-poor households earning roughly five times
more in the market (~$13,400) but paying ~$7,800 in taxes and receiving
only ~$3,000 in transfers.

The ordering normalizes after about 1985 as the EITC expanded (raising
Second-quintile post-tax income), AFDC and other cash welfare programs
tightened (lowering Bottom-quintile transfers), and the elderly-retired
share of the bottom quintile fell.

### Cross-validation sources retained in `data/raw/`

The repo includes several datasets that are not directly read by the
current pipeline but are useful for cross-validation:

* `data/raw/psz/PSZ2022AppendixTablesII(Distrib).xlsx` — Piketty-Saez-Zucman
  Distributional National Accounts (1913–2022). Used to spot-check top-income
  shares in the ultra-top panel.
* `data/raw/itep/ITEP_WhoPays7_Data_Jan2024rev.xlsx` — ITEP "Who Pays?" 7th
  Edition (state-by-state effective tax rates, 2024 tax law). Used in early
  vintages and retained for sensitivity analysis.
* `data/raw/ahs/` — American Housing Survey microdata for housing-quality
  cross-checks.
* `data/raw/bls_pumd/intrvw{15,16,…,22}.zip` — BLS CEX Public Use Microdata
  for sensitivity analysis of the CEX expenditure-share keys.

### Known limitations

1. **Medicare valuation.** The panel reports Medicare net of beneficiary-paid
   Part B/D premiums and out-of-pocket cost-sharing. An alternative is to
   value Medicare at insurance-equivalent value, which is substantially
   lower than gross outlays.
2. **Corporate income tax incidence.** Excluded from the household burden
   in this panel; tax-incidence literature is not unanimous. Sensitivity
   analysis with alternative assumptions (100% capital, 50/50, 100% labor)
   is straightforward to run.
3. **Private transfer fractions.** The household-directed fractions
   (Religion 5%, Health 8%, etc.) are central estimates with wide bounds.
4. **Static state and local tax shares.** The CEX expenditure shares used
   to distribute S&L sales taxes are pulled annually 1984–2022, but
   1979–1983 uses a 1984 proxy.
5. **CPS underreporting.** In-kind transfers are systematically
   underreported in CPS ASEC; the pipeline mitigates this by using
   administrative national totals and CBO distribution weights rather
   than CPS receipts directly.
6. **Forbes 400 post-2014.** IRS discontinued the Top 400 publication
   after 2014. The 2015–2022 Forbes 400 estimates extrapolate from IRS
   Table 4.1 Time Series Top 0.001% data and should be read with
   appropriate caution.

---

## Dependencies

See `requirements.txt`. Tested with Python 3.10–3.13.

```
pandas>=2.0
numpy>=1.23
openpyxl>=3.1
xlrd==1.2.0      # required for legacy .xls files; pinned because 2.0+ dropped .xls support
plotly>=5.18
kaleido==0.2.1   # PNG export backend for plotly; pinned for stability
requests>=2.28
```

Plus `jupyter` for the notebooks (not in `requirements.txt` because it's
only used for the notebooks, not the canonical `.py` scripts).

---

## License

MIT License — see `LICENSE`. The source code, scripts, and derived panel
CSVs in `output/` are MIT-licensed. The upstream administrative data in
`data/raw/` retains each publisher's original license; the CPS ASEC
extract in particular requires IPUMS registration and an end-user agreement.

---

## Citation

```
Poleshuk, Patrick. (2026). U.S. Household Income, Taxes, and Transfers:
A Reproducible Distributional Panel, 1979–2022. GitHub repository:
https://github.com/Patrickkp1/tax-transfer-inequality
```

For IPUMS CPS, also cite:

```
Flood, S., King, M., Rodgers, R., Ruggles, S., Warren, J. R., &
Westberry, M. (2024). Integrated Public Use Microdata Series, Current
Population Survey: Version 12.0 [dataset]. Minneapolis, MN: IPUMS.
https://doi.org/10.18128/D030.V12.0
```

---

## References

* Boskin, M., Dulberger, E., Gordon, R., Griliches, Z., & Jorgenson, D.
  (1996). *Toward a More Accurate Measure of the Cost of Living: Final
  Report to the Senate Finance Committee.*
* CBO (2023). *The Distribution of Household Income, 1979–2020.*
  Supplemental data tables.
* Early, D., & Furth, S. (2021). "A Better Price Index." Mercatus Center.
* Gramm, P., Ekelund, R., & Early, J. (2022). *The Myth of American
  Inequality: How Government Biases Policy Debate.* Rowman & Littlefield.
* Karen, R. (2023). "The Distribution of Private Transfers." *LIS Working
  Paper Series*, No. 851.
* Lebow, D., & Rudd, J. (2003). "Measurement Error in the Consumer Price
  Index: Where Do We Stand?" *Journal of Economic Literature*, 41(1).
* Meyer, B., & Sullivan, J. (2012). "Identifying the Disadvantaged: Official
  Poverty, Consumption Poverty, and the New Supplemental Poverty Measure."
  *Journal of Economic Perspectives*, 26(3): 111–136.
* Moulton, B. (2018). "The Measurement of Output, Prices, and Productivity:
  What's Changed Since the Boskin Commission?" Brookings Institution.
* Piketty, T., Saez, E., & Zucman, G. (2018). "Distributional National
  Accounts: Methods and Estimates for the United States." *Quarterly
  Journal of Economics*, 133(2): 553–609.
* Yagan, D. (2023). "What Is the Average Federal Individual Income Tax Rate
  on the Wealthiest Americans?" *Oxford Review of Economic Policy*, 39(3).
