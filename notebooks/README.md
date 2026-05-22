# Notebooks

Jupyter-notebook versions of the nine Python scripts in `src/`.  Each notebook
is split into cells along the existing section markers in the underlying
script, so you can step through the pipeline incrementally rather than running
the whole thing end-to-end.

## Setup

```bash
# From the repo root
pip install -r requirements.txt
pip install jupyter        # not in requirements.txt because it's only
                           # needed for the notebooks, not for the scripts

jupyter notebook notebooks/   # or `jupyter lab notebooks/`
```

Each notebook expects to find `data/raw/` and `output/` folders relative to the
repo root (the same `find_repo_root()` helper used by the `.py` versions walks
up the directory tree to locate them).

## Run order

The pipeline has dependencies between stages — later notebooks read CSVs
written by earlier ones from `output/`.  Run them in numeric order.

| # | Notebook | Reads | Writes |
|---|---|---|---|
| 01 | `01_build_earned_income_panel.ipynb` | CPS ASEC (`cps_00015.csv`), True CPI, CBO Table 5 | `earned_income_panel.csv` |
| 02 | `02_transfer_distribution_panel.ipynb` | CPS, CBO T05/T06, SSA OASI/DI, CMS NHE, BEA NIPA 3.12, USDA NSLP/WIC, OMB 604, USAC, OMB outlays_fy2027 | `transfer_distribution_panel.csv` |
| 03 | `03_tax_distribution_panel.ipynb` | CPS, CBO T01/T07/T12, OMB Tables 2.1/2.4/2.5, TPC S&L Finance, BLS CEX | `tax_distribution_panel.csv` |
| 04 | `04_income_after_taxes_transfers_panel.ipynb` | The three above + CPS + Giving USA recipient CSV | `income_after_taxes_transfers_panel.csv` |
| 05 | `05_top_percentile_taxes_transfers_panel.ipynb` | All four above + CPS + IRS T41TS + IRS Top 400 + IRS Table 3/4.3 + BLS CEX + TPC S&L | `top_percentile_taxes_transfers_panel.csv` |
| 06 | `06_income_visualizations.ipynb` | All five panel CSVs + CPI deflator | `fig_real_earned_income_by_quintile.png`, `fig_real_income_after_taxes_transfers_by_quintile.png`, `fig_effective_tax_rate_by_quintile.png`, `fig_iat_pct_of_earned_by_quintile.png`, `fig_cumulative_income_growth_nominal_vs_real.png` |
| 07 | `07_charts_5_6_ultra_top.ipynb` | Top percentile panel + CPI | `fig_real_earned_income_top_groups.png`, `fig_real_income_after_taxes_transfers_top_groups.png` |
| 08 | `08_report_figures.ipynb` | IAT panel | `fig_inequality_ratio_before_after_fisc.png`, `fig_net_fiscal_position_by_quintile_2022.png` |
| 09 | `09_cpi_bias_adjusted_v3_dbpi.ipynb` | FRED API (live), BLS DBPI xlsx | `cpi_adjusted_v3_dbpi_1979_2022.csv`, `cpi_headline_v3.png`, `cpi_medical_v3.png` |

Notebook 09 produces the True CPI deflator the other notebooks consume — but
because it queries FRED at runtime, the repo ships with a pre-computed copy of
its output (`cpi_adjusted_v3_dbpi_1979_2022.csv`) in `output/`.  You only need
to re-run notebook 09 when you want a fresh pull of the underlying FRED series.

## Notes

* The notebooks are kept in sync with the scripts in `src/` by running the
  conversion script `tools/py_to_nb.py` (not in this folder).  Edit the `.py`
  files; the notebooks are derived artefacts.
* All output goes to the repo's `output/` folder regardless of which directory
  Jupyter was launched from — the `find_repo_root()` cell at the top of each
  notebook handles path resolution.
* The notebooks do not have pre-executed cell output stored, so they're small
  and diff-friendly in Git.  Run them locally to see the prints and figures.
