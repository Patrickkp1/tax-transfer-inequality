# U.S. Household Income After Taxes and Transfers, 1979–2022

This project measures what U.S. households earn, what they receive in government and private transfers, and what they pay in federal, state and local taxes. It covers each income quintile from 1979 to 2022, plus groups inside the top 20% down to the 400 highest-income tax returns.

The Census Bureau's official "money income" leaves out in-kind government transfers (Medicare, Medicaid, SNAP, housing aid) and every tax households pay. This project adds them, using national totals from the agency that pays or collects each one.

```
income after taxes and transfers = earned income + government transfers + private transfers - taxes
```

The paper is `Measuring-Inequality-After-Taxes-and-Transfers-v24.docx`.

---

## Run order

Run from the repo folder. Each script reads the outputs of the ones before it.

```bash
pip install -r requirements.txt

# The panel
python src/state_income_tax_taxsim.py                   # 0. state income tax shares, 1979-1991 (NBER TAXSIM)
python src/build_earned_income_panel_v6.py              # 1. earned income
python src/transfer_distribution_panel_v16.py           # 2. government transfers
python src/tax_distribution_panel_v9.py                 # 3. taxes
python src/income_after_taxes_transfers_panel_v7.py     # 4. puts 1-3 together, adds private transfers
python src/top_percentile_taxes_transfers_panel_v9.py   # 5. groups inside the top 20%
python src/sensitivity_table.py                         # 6. robustness tables (Tables 1 and 2)

# Figures and tables in the paper (any order, after step 5)
python src/report_figures_v4.py             # Figures 1 and 2
python src/income_visualizations_v3.py      # Figures 4, 5 and 6
python src/charts_5_6_ultra_top_v4.py       # Figure 7
python src/per_person_figures_v2.py         # Figures 8 and 9
python src/top1_share_comparison_v4.py      # Figure 10 and Table 3
python src/inequality_decomposition.py      # Table 4
python src/appendix_group_tables_v4.py      # Tables A1-A4
python src/tax_rate_and_gini_figures_v2.py  # Figures A1 and A2

# Optional
CREDIT_BASIS=fair_value python src/transfer_distribution_panel_v16.py   # loans at fair value (footnote 19)
python src/cpi_bias_adjusted_v5_dbpi.py     # rebuild the price index and Figure 3 (downloads from FRED)
python src/group_summary_table.py           # one-page summary table (not in the paper)
python src/top1_effective_tax_rate.py       # top 1% tax rate chart (not in the paper)
```

Every script stops with an error if an input file or a year is missing, instead of filling in zeros. Inputs are found anywhere under `data/raw/`; set `DATA_ROOT` or `OUTPUT_DIR` to use other folders. Older versions of the scripts are in `src/archive/` and are not used.

Step 0 needs a second CPS extract (below) and an internet connection: it sends each tax return to NBER's TAXSIM server over ssh (built into macOS) and takes about ten minutes. To run TAXSIM locally instead, download the program from [NBER](https://taxsim.nber.org/taxsim35/low-level-local.html) and set `TAXSIM_EXE` to its path. If step 0's output is missing, step 3 warns and holds the 1991 shares for 1979–1990.

---

## What each script does

**0. state_income_tax_taxsim.py** → `output/state_income_tax_shares_taxsim.csv`
- Builds tax returns from the CPS (married couples file jointly; children under 19 living with a parent are dependents), runs each through NBER TAXSIM 35 with that year's state law, and adds them up by quintile.
- The CPS has no capital gains or itemized deductions, so TAXSIM gets zeros for those.
- Step 3 uses the year-to-year change in these shares, tied to the CPS `STATETAX` shares in 1991.

**1. build_earned_income_panel_v6.py** → `output/earned_income_panel.csv`
- Earned income = wages, self-employment and farm income, interest, dividends and rent (CPS), plus employer benefits, pension and other market income and realized capital gains (CBO Table 5).
- Wages are scaled up for CPS underreporting (Bee et al. 2023): 17.1% for the bottom quintile down to 3.6% for the top.
- Households are ranked the way CBO ranks them: income divided by the square root of household size, with 20% of people (not households) in each quintile.
- For 2014, only the redesigned 3/8 CPS sample is kept (`HFLAG == 1`).
- From the 2019 survey on, IPUMS `INCRETIR` no longer includes pensions and annuities, so the ranking rebuilds retirement income from `INCPEN1`, `INCPEN2`, `INCRANN`, `INCRET1` and `INCRET2`.
- CBO's employee retirement contributions are not added: CPS wages are pay before deductions, so they already include them.

**2. transfer_distribution_panel_v16.py** → `output/transfer_distribution_panel.csv`
- National totals: BEA NIPA Table 3.12 for every program BEA counts as a social benefit.
- Other sources fill in what BEA leaves out:
  - rental and public housing aid, internet discounts, flood insurance net cost (OMB)
  - school, child care and summer meals, and donated food (USDA)
  - Lifeline (USAC)
  - FEMA home repair grants (OpenFEMA)
  - public transit and Amtrak operating losses (BEA Tables 3.8 and 3.17)
  - 2021 rent and mortgage relief (BEA Table 5.11)
  - the subsidy value of federal loans: student loans, USDA home loans, SBA disaster home loans, and FHA, VA and USDA mortgage guarantees (OMB Federal Credit Supplement)
- Social Security is split into retirement (OASI) and disability (DI) using the SSA trust fund reports.
- Medicare is net of the premiums enrollees pay (Medicare Trustees).
- Each program is split across quintiles using CBO Tables 5 and 6, the Survey of Consumer Finances (loans, FEMA, flood insurance) or the Consumer Expenditure Survey (transit). Household counts come from CBO Table 1.
- Refundable credits (EITC, child tax credit) are counted once, as lower income taxes, not as transfers.
- Also writes `credit_subsidy.csv`, `student_loan_subsidy.csv` and `v16_additions.csv`.

**3. tax_distribution_panel_v9.py** → `output/tax_distribution_panel.csv`
- **Federal income, payroll, corporate and excise taxes:** CBO Table 7.
- **Customs, estate and gift taxes, and other social insurance taxes:** OMB totals. Estate and gift taxes are split using Treasury's Office of Tax Analysis shares.
- **Corporate income tax:** federal and state, assigned the way CBO does it, with 75% on owners of capital and 25% on workers.
- **State and local taxes** (Census totals), split by:
  - sales and other taxes: consumer spending shares (BLS CEX)
  - income tax: CPS `STATETAX` (income years 1991–2022); for 1979–1990, NBER TAXSIM (step 0), tied to the CPS in 1991
  - property tax on homes: CPS `PROPTAX` (income years 1991–2017), with the total from BEA; 2018–2022 follow average property tax by income fifth in the CEX, tied to the CPS in 2017; the 1991 shares are held for 1979–1990
- Property taxes paid by businesses are left out.

**4. income_after_taxes_transfers_panel_v7.py** → `output/income_after_taxes_transfers_panel.csv`
- Combines steps 1–3 and adds the corporate tax to earned income, so the same dollars appear in income and in taxes.
- **Private transfers** have two parts:
  - what CPS households report receiving: child support, alimony, help from outside the household, other income;
  - charitable giving that reaches poor households: 30.6% of Giving USA giving, not counting gifts to foundations. It is split by each quintile's share of poor households.
- **Per person.** Also reports income per person (divided by CBO's average household size for the quintile) and size-adjusted income (divided by the square root of that size).

**5. top_percentile_taxes_transfers_panel_v9.py** → `output/top_percentile_taxes_transfers_panel.csv`
- **Groups:**
  - CBO groups inside the top 20%: 81–90th, 91–95th and 96–99th percentiles, and the top 1%;
  - IRS groups: top 0.1%, 0.01% and 0.001% (2001–2022);
  - the 400 highest-income returns (IRS, 1992–2014; estimated after 2014).
- **State and local taxes** follow ITEP's Who Pays? 7th edition rates by income group. Above the top 1%, the top-1% rate is held.
- **Private transfers** are the top-20% amount for every top group.
- **Estate and corporate taxes** for the IRS groups scale with non-wage income.

**6. sensitivity_table.py** → `output/sensitivity_table.csv`, `output/sensitivity_table_top_groups.csv`
- The top/bottom ratio after taxes and transfers in 1979 and 2022 under each change: size-adjusted; per person; Medicaid counted at 50% and 20% of its cost; no Medicaid or Medicare; and a 95% range for CPS sampling error (households re-drawn 300 times).
- For the top groups: state and local taxes proportional to income instead of ITEP's rates, and the range of the estimated top-400 tax rate for 2022.

**Figures and tables**

| Script | Makes | In the paper |
|---|---|---|
| `report_figures_v4.py` | top/bottom ratio; 2022 net fiscal position | Figures 1, 2 |
| `cpi_bias_adjusted_v5_dbpi.py` | `cpi_adjusted_v3_dbpi_1979_2022.csv`, price index chart | Figure 3 |
| `income_visualizations_v3.py` | real earned income, real income after taxes and transfers, net tax rate, by quintile | Figures 4, 5, 6 |
| `charts_5_6_ultra_top_v4.py` | real income for the top groups | Figure 7 |
| `per_person_figures_v2.py` | ratio measured three ways; real income per person | Figures 8, 9 |
| `top1_share_comparison_v4.py` | top 1% share next to CBO, Piketty–Saez–Zucman and Auten–Splinter | Figure 10, Table 3 |
| `inequality_decomposition.py` | what drove the change in the ratio and the Gini | Table 4 |
| `appendix_group_tables_v4.py` | parts of income, transfers and taxes by group, 1979 and 2022 | Tables A1–A4 |
| `tax_rate_and_gini_figures_v2.py` | Gini coefficients; tax rate by group | Figures A1, A2 |

Real-dollar charts are in 2022 dollars, using the bias-adjusted price index in `output/cpi_adjusted_v3_dbpi_1979_2022.csv`.

---

## Raw data (`data/raw/`)

| Folder | File(s) | Used by | Source |
|---|---|---|---|
| (top level) | `cps_00015.csv` | 1, 3, 4, 6 | IPUMS CPS ASEC, survey years 1980–2023. Not in the repo: download it yourself (see below). |
| (top level) | `cps_taxsim_1980_1992.csv` | 0 | IPUMS CPS ASEC, survey years 1980–1992. Not in the repo (see below). |
| `cbo/` | `households_ranked_by_market_inc_table_01/03/05/06/07/12_*.csv` | 1–5, appendix tables | [CBO, The Distribution of Household Income, 2022](https://www.cbo.gov/publication/61911) (January 2026), Additional Data for Researchers |
| `cbo/` | `61911-additional-data-for-researchers.zip` | top 1% share (Table 10 is read from the zip) | same |
| `bea/` | `Table-1.xlsx` (NIPA Table 3.12) | 2 | BEA |
| `bea/` | `NipaDataQ_W027RC.csv` (rent and mortgage relief) | 2 | BEA |
| `bea/` | `NipaDataA_transit.csv` (transit and rail series from Tables 3.8, 3.13, 3.17) | 2 | BEA |
| `bea/` | `A2016C1A027NBEA.csv` (property tax on owner-occupied homes) | 3 | BEA via FRED |
| `bea/` | `NipaDataA_CON150.csv` | 3 | BEA |
| `bea/` | `PCEPI_annual.csv` | 1, 3, 5 | BEA PCE price index via FRED |
| `oasdi/` | `OASI_Trust_Fund_Cost_*.csv`, `DI_Trust_Fund_Cost_*.csv` | 2 | SSA |
| `meds/` | `Operations of the Hospital Insurance (HI) Trust Fund*.xlsx`, `...Part B Account*.xlsx`, `...Part D Account*.xlsx` | 2 | Medicare Trustees Report 2025, Expanded and Supplementary Tables |
| `omb/` | `outlays_fy2027.xlsx` | 2 | OMB Public Budget Database, FY2027 |
| `omb/` | `BUDGET-2027-FCS.xlsx` | 2 | OMB Federal Credit Supplement, FY2027 |
| `omb/` | `BUDGET-2027-DB-3.xlsx`, `BUDGET-2027-TAB-3-4.xlsx`, `BUDGET-2027-TAB-3-5.xlsx` | 3 | OMB Historical Tables 2.4 and 2.5, FY2027 |
| `usda/` | `cncost.xlsx`, `ccsummar.xlsx`, `sfsummar.xlsx`, `fdfoodcosts-sum*.xlsx` | 2 | USDA FNS (school, child care and summer meals; food distribution) |
| `usac/` | `USAC_USF_Disbursements_1998_2022.xlsx` | 2 | USAC annual reports |
| `fema/` | `HousingAssistanceOwners*.csv`, `DisasterDeclarationsSummaries*.csv`, `NfipClaims_v3_selected_columns*.csv` | 2 | [OpenFEMA](https://www.fema.gov/about/openfema/data-sets) |
| `sba/` | `*Disaster_Loan_Data_FY*.xlsx` or `sba_disaster_loan_data_fy*.xlsx` | 2 | [SBA Disaster Loan Data](https://data.sba.gov/dataset/disaster-loan-data) |
| `scf/` | `scfp1989excel.zip` … `scfp2022excel.zip` | 2 | [Federal Reserve, Survey of Consumer Finances](https://www.federalreserve.gov/econres/scfindex.htm), summary extract |
| `census_sl/` | `results.csv` | 3 | Census State and Local Government Finances (Tax Policy Center query system) |
| `bls_ce/` | `cex_sales_tax_distribution_weights_detailed_COMPLETE.csv` | 3 | BLS Consumer Expenditure Survey (PDF tables in the same folder) |
| `bls_ce/` | `cex_property_tax_by_quintile_2017_2022.csv` | 3 | [BLS Consumer Expenditure Survey, Table 1101](https://www.bls.gov/cex/tables/calendar-year/mean-item-share-average-standard-error/cu-income-quintiles-before-taxes-2022.xlsx) |
| `bls_ce/` | `cx_530311_intracity_transit_quintiles.csv` | 2 | [BLS CE time series](https://download.bls.gov/pub/time.series/cx/) |
| `treasury_ota/` | `Authors_Compilation-treasury_estate_gift_shares.csv` | 3, 5 | Treasury Office of Tax Analysis distribution tables (in the same folder) |
| `giving_USA/` | `giving_usa_recipients_1979_2022.csv` | 4 | Giving USA (PDFs in the same folder) |
| `irs_soi/` | `22in41ts.xls`, `*in03etr.xls`, `*in43ts.xls` | 5 | IRS Statistics of Income, Tables 4.1 and 4.3 |
| `forbes-400-irs/` | `14intop400.pdf` | 5 (typed into the script) | IRS, The 400 Individual Income Tax Returns Reporting the Largest Adjusted Gross Incomes |
| `itep/` | `ITEP_WhoPays7_Data_Jan2024rev.xlsx` | 5 | [ITEP, Who Pays? 7th edition](https://itep.org/wp-content/uploads/ITEP-Who-Pays-7th-edition.pdf) |
| `psz/` | `PSZ2022AppendixTablesII(Distrib).xlsx` | top 1% share | [Piketty, Saez and Zucman](https://gabriel-zucman.eu/usdina/), Tables II, February 2022 update |
| `auten_splinter/` | `AS2024_TableA1_top1.csv` | top 1% share | [Auten and Splinter (2024)](http://davidsplinter.com/AutenSplinter-Tax_Data_and_Inequality.pdf), Table A1 |
| `src/` | `dbpis-for-17-broad-categories.xlsx` | price index | [BLS Disease-Based Price Indexes](https://www.bls.gov/pir/disease/dbpis-for-17-broad-categories.xlsx) |

### CPS extract (IPUMS)

Register at [cps.ipums.org](https://cps.ipums.org). The extract is ASEC only, in CSV format, saved as `data/raw/cps_00015.csv`.

- **Samples:** survey years 1980–2023, including both 2014 samples.
- **Variables (28):**

`YEAR SERIAL RELATE ASECWTH ASECFLAG HFLAG INCWAGE INCBUS INCFARM INCDIVID INCINT INCRENT INCRETIR INCDRT INCCHILD INCASIST INCOTHER INCALIM INCALOTH OFFPOV FILESTAT STATETAX PROPTAX INCPEN1 INCPEN2 INCRANN INCRET1 INCRET2`

### TAXSIM extract (IPUMS)

A second ASEC-only CSV extract, saved as `data/raw/cps_taxsim_1980_1992.csv`.

- **Samples:** survey years 1980–1992.
- **Variables (18):**

`YEAR SERIAL PERNUM ASECWTH STATEFIP AGE SPLOC MOMLOC POPLOC INCWAGE INCBUS INCFARM INCSS INCRETIR INCINT INCDIVID INCRENT INCDRT`

IPUMS data cannot be reposted, so neither file is in the repo.

---

## Main assumptions

- Medicare and Medicaid are counted at what the government spends. The sensitivity table shows the ratio with Medicaid at 50% and 20% of cost.
- Headline results are per household. Per-person and size-adjusted results are reported alongside.
- State income tax shares for 1979–1990 come from NBER TAXSIM, without capital gains or itemized deductions. Property tax shares before 1991 are held at their 1991 level. Property tax shares after 2017 follow the Consumer Expenditure Survey, tied to the CPS in 2017.
- Sales and excise taxes are split by consumer spending, as CBO does for federal excise taxes.
- OMB, USDA and Census fiscal-year figures are used as calendar years.
- Inside the top 20%, the ITEP state and local tax rates reflect 2024 law and are used for every year.
- For the top 400 returns, 2015–2022 are estimated, and wage shares before 2014 are held at 2014.
- Pandemic loans and relief payments to nonprofits (2020–2022) are counted as transfers, as BEA counts them.

The paper's Limitations section discusses each of these.

---

## License

MIT for the code and the files in `output/`. Raw data keep each publisher's terms; the CPS extract requires an IPUMS account.

## Citation

```
Poleshuk, Patrick. (2026). U.S. Household Income After Taxes and Transfers, 1979–2022.
https://github.com/Patrickkp1/tax-transfer-inequality
```

NBER TAXSIM: Feenberg, D., and E. Coutts. (1993). An Introduction to the TAXSIM Model. Journal of Policy Analysis and Management 12(1): 189–194.

IPUMS CPS: Flood, S., et al. (2024). IPUMS CPS: Version 12.0 [dataset]. Minneapolis, MN: IPUMS. https://doi.org/10.18128/D030.V12.0
