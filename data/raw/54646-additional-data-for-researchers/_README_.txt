# The Distribution of Household Income, 2015--Additional Data for Researchers

The data contained here supplement information provided in CBO's November 2018
slide deck "The Distribution of Household Income, 2015."
www.cbo.gov/publication/54646

## Contents
There are 37 files in this zipped archive file--a _README_.txt file (this file) 
and three sets of 12 files. Each set uses a different income measure to rank 
households and construct income groups:
    * inc_after_trans_tax
    * inc_before_trans_tax
    * market_inc

The files with households ranked by inc_before_trans_tax contain the same data 
that are available in the file "54646-supplemental-data.xlsx."

    * _README_.txt
    
    * households_ranked_by_inc_after_trans_tax_table_01_demographics_1979_2015.csv
    * households_ranked_by_inc_after_trans_tax_table_02_income_group_minimums_1979_2015.csv
    * households_ranked_by_inc_after_trans_tax_table_03_average_household_income_1979_2015.csv
    * households_ranked_by_inc_after_trans_tax_table_04_median_household_income_1979_2015.csv
    * households_ranked_by_inc_after_trans_tax_table_05_components_inc_before_transfers_taxes_1979_2015.csv
    * households_ranked_by_inc_after_trans_tax_table_06_components_means_tested_transfers_1979_2015.csv
    * households_ranked_by_inc_after_trans_tax_table_07_components_federal_taxes_1979_2015.csv
    * households_ranked_by_inc_after_trans_tax_table_08_means_tested_transfer_rates_1979_2015.csv
    * households_ranked_by_inc_after_trans_tax_table_09_federal_tax_rates_1979_2015.csv
    * households_ranked_by_inc_after_trans_tax_table_10_household_income_shares_1979_2015.csv
    * households_ranked_by_inc_after_trans_tax_table_11_means_tested_transfer_shares_1979_2015.csv
    * households_ranked_by_inc_after_trans_tax_table_12_federal_tax_shares_1979_2015.csv
    
    * households_ranked_by_inc_before_trans_tax_table_01_demographics_1979_2015.csv
    * households_ranked_by_inc_before_trans_tax_table_02_income_group_minimums_1979_2015.csv
    * households_ranked_by_inc_before_trans_tax_table_03_average_household_income_1979_2015.csv
    * households_ranked_by_inc_before_trans_tax_table_04_median_household_income_1979_2015.csv
    * households_ranked_by_inc_before_trans_tax_table_05_components_inc_before_transfers_taxes_1979_2015.csv
    * households_ranked_by_inc_before_trans_tax_table_06_components_means_tested_transfers_1979_2015.csv
    * households_ranked_by_inc_before_trans_tax_table_07_components_federal_taxes_1979_2015.csv
    * households_ranked_by_inc_before_trans_tax_table_08_means_tested_transfer_rates_1979_2015.csv
    * households_ranked_by_inc_before_trans_tax_table_09_federal_tax_rates_1979_2015.csv
    * households_ranked_by_inc_before_trans_tax_table_10_household_income_shares_1979_2015.csv
    * households_ranked_by_inc_before_trans_tax_table_11_means_tested_transfer_shares_1979_2015.csv
    * households_ranked_by_inc_before_trans_tax_table_12_federal_tax_shares_1979_2015.csv
    
    * households_ranked_by_market_inc_table_01_demographics_1979_2015.csv
    * households_ranked_by_market_inc_table_02_income_group_minimums_1979_2015.csv
    * households_ranked_by_market_inc_table_03_average_household_income_1979_2015.csv
    * households_ranked_by_market_inc_table_04_median_household_income_1979_2015.csv
    * households_ranked_by_market_inc_table_05_components_inc_before_transfers_taxes_1979_2015.csv
    * households_ranked_by_market_inc_table_06_components_means_tested_transfers_1979_2015.csv
    * households_ranked_by_market_inc_table_07_components_federal_taxes_1979_2015.csv
    * households_ranked_by_market_inc_table_08_means_tested_transfer_rates_1979_2015.csv
    * households_ranked_by_market_inc_table_09_federal_tax_rates_1979_2015.csv
    * households_ranked_by_market_inc_table_10_household_income_shares_1979_2015.csv
    * households_ranked_by_market_inc_table_11_means_tested_transfer_shares_1979_2015.csv
    * households_ranked_by_market_inc_table_12_federal_tax_shares_1979_2015.csv

To open the files without read-only access, save the zipped archive to a
local file directory and extract the files to a new directory.

## General Notes
All data files are in comma-separated values format.
Column headings are in row 1; data start in row 2.

All years in the data are calendar years.

Households with negative income are not shown separately but are included in 
the 'all_quintiles' income_group.

### Rounding
Numbers in the data may not add up to totals because of rounding. Data files
with dollar values are rounded to the nearest hundred, and cells with dollar
values between -$50 and $50 are empty (missing). Data files with percentages
are rounded to the nearest tenth and cells with percentage values between -0.05
percent and 0.05 percent are also empty (missing). Finally, population counts
less than 0.05 million are also empty (missing).

### File Structure
Most files are sorted by three variables: household_type, income_group, and
year. 

There are four household_type values:
    * all_households
    * hh_with_children (a household with one or more people under age 18)
    * elderly_headed_hh (a household with either a head or spouse age 65 or older)
    * nonelderly_childless_hh (may have secondary elderly persons living in the
      household but no children)

Only six files are **not** sorted by those variables:

    * households_ranked_by_inc_after_trans_table_02_income_group_minimums_1979_2015.csv
    * households_ranked_by_inc_after_trans_table_04_median_household_income_1979_2015.csv
    
    * households_ranked_by_inc_before_trans_table_02_income_group_minimums_1979_2015.csv
    * households_ranked_by_inc_before_trans_table_04_median_household_income_1979_2015.csv
    
    * households_ranked_by_market_inc_table_02_income_group_minimums_1979_2015.csv
    * households_ranked_by_market_inc_table_04_median_household_income_1979_2015.csv

For the income_group_minimum tables, the values are for the income measure used
to rank households.

For the median_household_income tables, the data are identical across the three
files and represent the median income values for all_households. (The data are
duplicated solely for file-naming consistency across the household rankings.)

### Income Measures
All income measures are average 2015 dollars.

CBO adjusted income for inflation using the price index for personal consumption
expenditures, which is calculated by the Bureau of Economic Analysis (BEA).
Those data are updated regularly by BEA. The data used to make the adjustments
are from the September 27, 2018, revision of the series.

**Income groups** are created by ranking households by their size-adjusted
income before taxes and transfers. A household consists of people sharing a
housing unit, regardless of their relationships. Each income quintile (fifth)
contains approximately equal numbers of people but slightly different numbers
of households. Similarly, each percentile (hundredth) contains approximately
equal numbers of people but different numbers of households. If a household has
negative income (that is, if its business or investment losses are larger than
its other income), it is excluded from the lowest income group but included in
totals.

**Income before transfers and taxes** consists of market income plus social
insurance benefits.

**Market income** consists of labor income; business income; capital income
(including capital gains); income received in retirement for past services; and
other nongovernmental sources of income.

**Social insurance benefits** consist of benefits from Social Security (Old-Age,
Survivors, and Disability Insurance); Medicare (measured as the average cost to
the government of providing those benefits); unemployment insurance; and
workers’ compensation.

**Means-tested transfers** are cash payments and in-kind services provided
through federal, state, and local government assistance programs. Eligibility
to receive such transfers is determined primarily on the basis of income, which
must be below certain thresholds. The largest transfer programs are Medicaid
and the Children's Health Insurance Program (measured as the average cost to
the government of providing those benefits); the Supplemental Nutrition
Assistance Program (formerly known as the Food Stamp program); and
Supplemental Security Income.

**Federal taxes** consist of individual income taxes, payroll taxes, corporate
income taxes, and excise taxes. In this analysis, taxes for a given year are
the amount a household owes on the basis of income received that year,
regardless of when the taxes are paid. Taxes from those four sources accounted
for 94 percent of federal revenues in fiscal year 2014. The remaining federal
revenue sources not allocated to U.S. households include states’ deposits for
unemployment insurance, estate and gift taxes, net income earned by the Federal
Reserve, customs duties, and miscellaneous fees and fines.

**Average means-tested transfer rates** are calculated as means-tested
transfers divided by income before transfers and taxes.

**Average federal tax rates** are calculated as federal taxes divided by income
before transfers and taxes.

### Rate Measures
All rate measures use inc_before_trans_tax as the denominator, regardless of 
the income measure used to rank households.

All rates are income-weighted averages. For example, the average federal tax 
rate for any given income group is equal to the sum of all federal taxes paid
by households in the income group divided by all income before transfers and
taxes in the income group.

### Share Measures 
Shares across income quintiles sum to approximately 100 percent. Because 
households with negative income are not shown separately (and because of 
rounding errors in the other income groups), the sum of shares across 
income quintiles will be less than 100 percent.

Shares are calculated separately for each household_type.
