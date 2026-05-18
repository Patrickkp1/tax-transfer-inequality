"""
income_visualizations.py
=========================
Four charts on U.S. household income by quintile, 1979-2022.

FOLDER STRUCTURE
-----------------
  simplified_scripts/
    income_visualizations.py   <-- this file
  output/
    income_after_taxes_transfers_panel.csv
    cpi_adjusted_v3_dbpi_1979_2022.csv

HOW TO RUN
----------
  python income_visualizations.py

OUTPUT FILES (written to ../output/ next to the panel CSVs)
-----------------------------------------------------------
  fig_real_earned_income_by_quintile.png
  fig_real_income_after_taxes_transfers_by_quintile.png
  fig_effective_tax_rate_by_quintile.png
  fig_iat_pct_of_earned_by_quintile.png
  fig_cumulative_income_growth_nominal_vs_real.png
"""

import os
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio
from plotly.subplots import make_subplots

pio.templates.default = "plotly_white"

# =============================================================================
# SECTION 1 - File paths
# =============================================================================
HERE       = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.normpath(os.path.join(HERE, "..", "output"))
INCOME_CSV = os.path.join(OUTPUT_DIR, "income_after_taxes_transfers_panel.csv")
CPI_CSV    = os.path.join(OUTPUT_DIR, "cpi_adjusted_v3_dbpi_1979_2022.csv")

# =============================================================================
# SECTION 2 - Load and prepare data
# =============================================================================
print(f"Loading: {INCOME_CSV}")
df = pd.read_csv(INCOME_CSV)

print(f"Loading: {CPI_CSV}")
cpi = (pd.read_csv(CPI_CSV)[["year", "True_CPI_idx"]]
         .rename(columns={"year": "income_year"}))

QUINTILES = ["Bottom", "Second", "Middle", "Fourth", "Top"]
df = df[df["quintile"].isin(QUINTILES)].copy()
df = df.merge(cpi, on="income_year", how="left")

# real_value = nominal / (CPI_index / 100)
df["earned_real"] = df["earned"] / (df["True_CPI_idx"] / 100)
df["iat_real"]    = df["iat"]    / (df["True_CPI_idx"] / 100)

print(f"Rows: {len(df)} | Years: {df['income_year'].min()}-{df['income_year'].max()}\n")

# =============================================================================
# SECTION 3 - Shared styling constants and helper functions
# =============================================================================
BASE_YEAR = 1979

COLORS = {
    "Bottom": "#1f77b4",
    "Second": "#2ca02c",
    "Middle": "#ff7f0e",
    "Fourth": "#9467bd",
    "Top":    "#d62728",
}
DASHES = {
    "Bottom": "solid",
    "Second": "dash",
    "Middle": "dot",
    "Fourth": "dashdot",
    "Top":    "solid",
}
RECESSIONS = [
    (1980, 1980), (1981, 1982), (1990, 1991),
    (2001, 2001), (2007, 2009), (2020, 2020),
]
AXIS = dict(showgrid=True, gridcolor="rgba(180,180,180,0.2)",
            zeroline=False, tickfont=dict(size=12))
LEGEND = dict(orientation="h", yanchor="bottom", y=1.02,
              xanchor="center", x=0.5, font=dict(size=13),
              bgcolor="rgba(0,0,0,0)", borderwidth=0)
DOLLAR_TICKS  = [1000, 2000, 5000, 10000, 20000, 50000, 100000, 200000, 500000]
DOLLAR_LABELS = ["$1k", "$2k", "$5k", "$10k", "$20k", "$50k", "$100k", "$200k", "$500k"]
POSITIONS     = [10, 30, 50, 70, 90]


def shade_recessions(fig, row=None, col=None):
    for start, end in RECESSIONS:
        kw = dict(x0=start - 0.4, x1=end + 0.4,
                  fillcolor="rgba(210,210,210,0.35)",
                  line_width=0, layer="below")
        if row is not None:
            kw["row"] = row
            kw["col"] = col
        fig.add_vrect(**kw)
    return fig


def centered_title(text):
    return dict(text=f"<b>{text}</b>", font=dict(size=17),
                x=0.5, xanchor="center", pad=dict(b=12))


def cum_growth(col, y0=1979, y1=2022):
    return [
        round((df.loc[(df["quintile"] == q) & (df["income_year"] == y1), col].values[0] /
               df.loc[(df["quintile"] == q) & (df["income_year"] == y0), col].values[0] - 1) * 100, 1)
        for q in QUINTILES
    ]


def log_axis_range(series, pad_below=0.7, pad_above=2.2):
    """
    Compute [log_min, log_max] for a log y-axis from a full data series.

    WHY USE THE FULL SERIES (not just end values):
    If you compute the range from only the 2022 endpoint values, the axis zooms
    in on 2022 and clips the lower 1979 starting values — making the bottom
    quintiles appear to start mid-chart or get cut off entirely.

    pad_below: multiplier below data min (default 0.7 = 30% headroom)
    pad_above: multiplier above data max (default 2.2 = 120% headroom for labels)
    """
    return [np.log10(series.min() * pad_below),
            np.log10(series.max() * pad_above)]


def make_paper_y(log_min, log_max):
    """
    Returns a function that maps a dollar value to a paper [0,1] y-coordinate.

    WHY THIS EXISTS:
    On a log y-axis, add_annotation with yref='y' works in log-space, which
    causes closely-spaced values (e.g. $24k and $26k) to render on top of each
    other. Converting to paper [0,1] coordinates gives pixel-accurate placement
    at any output resolution or scale factor.
    """
    def converter(val):
        return (np.log10(val) - log_min) / (log_max - log_min)
    return converter


def save_chart(fig, filename):
    # Charts are written to the same output/ folder as the panel CSVs so
    # everything generated by this project ends up in one place. Width is
    # set explicitly to 1300px so the long centered footer text doesn't
    # get cropped by Plotly's default 700px export width.
    path = os.path.join(OUTPUT_DIR, filename)
    fig.write_image(path, width=1300, height=fig.layout.height or 780, scale=2)
    print(f"Saved: {filename}")


# =============================================================================
# SECTION 4 - Chart 1: Real earned income BEFORE taxes & transfers (log scale)
# =============================================================================
earned_end, earned_pct = {}, {}
for q in QUINTILES:
    sub   = df[df["quintile"] == q].sort_values("income_year")
    v0    = sub.loc[sub["income_year"] == BASE_YEAR, "earned_real"].values[0]
    v_end = sub["earned_real"].iloc[-1]
    earned_end[q] = v_end
    earned_pct[q] = round((v_end / v0 - 1) * 100)

y1_range   = log_axis_range(df["earned_real"].dropna(), pad_below=0.7, pad_above=2.2)
to_paper_y1 = make_paper_y(*y1_range)
Y1_OFFSETS  = {"Bottom": 0.0, "Second": 0.0, "Middle": 0.0, "Fourth": 0.0, "Top": 0.0}

fig1 = go.Figure()
for q in QUINTILES:
    sub = df[df["quintile"] == q].sort_values("income_year")
    fig1.add_trace(go.Scatter(
        x=sub["income_year"], y=sub["earned_real"],
        mode="lines", name=q,
        line=dict(color=COLORS[q], width=2.5, dash=DASHES[q]),
    ))

x1_label = (2022 - 1979) / (2030 - 1979) + 0.012
for q in QUINTILES:
    fig1.add_annotation(
        xref="paper", yref="paper",
        x=x1_label,
        y=to_paper_y1(earned_end[q]) + Y1_OFFSETS[q],
        text=f"  ${earned_end[q]/1000:.0f}k  +{earned_pct[q]}%",
        xanchor="left", yanchor="middle", showarrow=False,
        font=dict(size=11, color=COLORS[q]),
    )

shade_recessions(fig1)
fig1.update_yaxes(type="log", tickvals=DOLLAR_TICKS, ticktext=DOLLAR_LABELS,
                  range=y1_range,
                  title=dict(text="Avg Household Income (1979 $, log scale)", font=dict(size=13)), **AXIS)
fig1.update_xaxes(range=[1979, 2030],
                  title=dict(text="Year", font=dict(size=13), standoff=30), **AXIS)
fig1.update_layout(
    title=centered_title("Real Earned Income by Quintile (1979-2022)"),
    legend=LEGEND, margin=dict(l=80, r=100, t=90, b=160),
)
fig1.add_annotation(
    text="Before taxes & transfers  ·  True CPI deflated to 1979 dollars  ·  Log scale  ·  +% = cumul. real growth 1979-2022<br>"
         "Grey bands = NBER recessions  ·  Source: CBO / CPS",
    xref="paper", yref="paper", x=0.5, y=-0.17,
    xanchor="center", yanchor="top", showarrow=False,
    align="center", font=dict(size=11, color="#555"))
save_chart(fig1, "fig_real_earned_income_by_quintile.png")


# =============================================================================
# SECTION 5 - Chart 2: Real income AFTER taxes & transfers (log scale)
#
# KEY DIFFERENCE FROM CHART 1: the y-axis range is computed from ALL data points
# across all years (1979-2022), not just the 2022 endpoint values. Using only
# endpoint values zoomed the axis into 2022 levels and cut off the lower 1979
# starting points for Bottom/Second/Middle quintiles.
#
# LABEL PLACEMENT: uses paper-coordinate conversion (make_paper_y) because
# yref="y" on a log axis causes labels to stack when values are close. See the
# make_paper_y docstring above for full explanation.
#
# OVERLAP FIX: Bottom=$24k, Second=$26k, Middle=$30k at 2022 cluster within
# ~0.05 paper units. Y2_OFFSETS nudges them apart by ~2.5% paper each.
# =============================================================================
iat_end, iat_pct = {}, {}
for q in QUINTILES:
    sub   = df[df["quintile"] == q].sort_values("income_year")
    v0    = sub.loc[sub["income_year"] == BASE_YEAR, "iat_real"].values[0]
    v_end = sub["iat_real"].iloc[-1]
    iat_end[q] = v_end
    iat_pct[q] = round((v_end / v0 - 1) * 100)

# Use full series so the axis shows all data from 1979, not just 2022 values
y2_range    = log_axis_range(df["iat_real"].dropna(), pad_below=0.7, pad_above=2.2)
to_paper_y2 = make_paper_y(*y2_range)

Y2_OFFSETS = {
    "Bottom": -0.025,   # nudge down
    "Second":  0.000,   # true position
    "Middle": +0.025,   # nudge up
    "Fourth":  0.000,
    "Top":     0.000,
}

fig2 = go.Figure()
for q in QUINTILES:
    sub = df[df["quintile"] == q].sort_values("income_year")
    fig2.add_trace(go.Scatter(
        x=sub["income_year"], y=sub["iat_real"],
        mode="lines", name=q,
        line=dict(color=COLORS[q], width=2.5, dash=DASHES[q]),
    ))

x2_label = (2022 - 1979) / (2030 - 1979) + 0.012
for q in QUINTILES:
    fig2.add_annotation(
        xref="paper", yref="paper",
        x=x2_label,
        y=to_paper_y2(iat_end[q]) + Y2_OFFSETS[q],
        text=f"  ${iat_end[q]/1000:.0f}k  +{iat_pct[q]}%",
        xanchor="left", yanchor="middle", showarrow=False,
        font=dict(size=12, color=COLORS[q]),
    )

shade_recessions(fig2)
fig2.update_yaxes(type="log", tickvals=DOLLAR_TICKS, ticktext=DOLLAR_LABELS,
                  range=y2_range,
                  title=dict(text="Avg Household Income (1979 $, log scale)", font=dict(size=13)), **AXIS)
fig2.update_xaxes(range=[1979, 2030],
                  title=dict(text="Year", font=dict(size=13), standoff=30), **AXIS)
fig2.update_layout(
    title=centered_title("Real Income After Taxes & Transfers by Quintile (1979-2022)"),
    legend=LEGEND, margin=dict(l=80, r=80, t=90, b=160),
)
fig2.add_annotation(
    text="After all taxes, govt & private transfers  ·  True CPI deflated to 1979 dollars  ·  Log scale  ·  +% = cumul. real growth 1979-2022<br>"
         "Grey bands = NBER recessions  ·  Source: CBO / CPS",
    xref="paper", yref="paper", x=0.5, y=-0.17,
    xanchor="center", yanchor="top", showarrow=False,
    align="center", font=dict(size=11, color="#555"))
save_chart(fig2, "fig_real_income_after_taxes_transfers_by_quintile.png")


# =============================================================================
# SECTION 6 - Chart 3: Effective Tax Rate — two stacked panels
#
# Formula: (taxes - govt_transfers - priv_transfers) / earned * 100
#   Income before taxes (IBT) = earned income only
#   Income after taxes  (IAT) = earned + govt_transfers + priv_transfers − taxes
#   ETR = (taxes − govt_transfers − priv_transfers) / earned
#       Negative = net recipient (all transfers received > taxes paid)
#       Positive = net payer    (taxes paid > all transfers received)
#
# Both government and private transfers (charity, child support, alimony)
# are netted against taxes to produce a household's true fiscal position.
#
# Two stacked panels because the bottom-quintile rate dips far below the rest.
# A shared y-axis would compress Q2-Top into an unreadable band near zero.
# Y-ranges are computed from the data (no hardcoded magic numbers) so the
# chart re-renders cleanly when upstream panels are rebuilt.
# =============================================================================

# Pre-compute ETRs for each quintile up front (used for axis ranges + traces)
etr_by_q = {}
for q in QUINTILES:
    sub = df[df["quintile"] == q].sort_values("income_year").copy()
    sub["etr"] = ((sub["taxes"] - sub["govt_transfers"] - sub["priv_transfers"])
                  / sub["earned"] * 100)
    etr_by_q[q] = sub

_bot = etr_by_q["Bottom"]["etr"]
_upper = pd.concat([etr_by_q[q]["etr"] for q in ["Second", "Middle", "Fourth", "Top"]])
bot_y_min = float(_bot.min()) - 100
bot_y_max = float(_bot.max()) + 50
up_y_min  = float(_upper.min()) - 10
up_y_max  = float(_upper.max()) + 10

fig3 = make_subplots(
    rows=2, cols=1,
    shared_xaxes=True,
    row_heights=[0.5, 0.5],
    vertical_spacing=0.12,
    subplot_titles=["Bottom Quintile", "Second through Top Quintile"],
)

fig3.add_trace(go.Scatter(
    x=etr_by_q["Bottom"]["income_year"],
    y=etr_by_q["Bottom"]["etr"].round(1),
    mode="lines", name="Bottom",
    line=dict(color=COLORS["Bottom"], width=2.5),
    hovertemplate="Year %{x}<br>ETR: %{y:.1f}%<extra>Bottom</extra>",
    showlegend=True,
), row=1, col=1)

# Annotate the 2021 COVID trough on the bottom-quintile panel (data-driven)
_bot_df = etr_by_q["Bottom"]
_bot_min_idx = _bot_df["etr"].idxmin()
_bot_min_yr  = int(_bot_df.loc[_bot_min_idx, "income_year"])
_bot_min_val = float(_bot_df.loc[_bot_min_idx, "etr"])
fig3.add_annotation(
    x=_bot_min_yr, y=_bot_min_val,
    text=f"{_bot_min_yr} trough: {_bot_min_val:.0f}%",
    xanchor="right", showarrow=True, arrowhead=2,
    ax=-50, ay=-40,
    arrowcolor=COLORS["Bottom"], arrowwidth=1.5,
    font=dict(size=10, color=COLORS["Bottom"]),
    bgcolor="rgba(255,255,255,0.85)",
    bordercolor=COLORS["Bottom"], borderwidth=1,
    row=1, col=1,
)

for q in ["Second", "Middle", "Fourth", "Top"]:
    sub = etr_by_q[q]
    fig3.add_trace(go.Scatter(
        x=sub["income_year"], y=sub["etr"].round(1),
        mode="lines", name=q,
        line=dict(color=COLORS[q], width=2.5, dash=DASHES[q]),
        hovertemplate=f"Year %{{x}}<br>ETR: %{{y:.1f}}%<extra>{q}</extra>",
        showlegend=True,
    ), row=2, col=1)

for row in [1, 2]:
    shade_recessions(fig3, row=row, col=1)
    fig3.add_hline(y=0, line_dash="dot",
                   line_color="rgba(0,0,0,0.4)", line_width=1.5,
                   row=row, col=1)

fig3.update_yaxes(range=[bot_y_min, bot_y_max], title_text="Effective Tax Rate (%)",
                  row=1, col=1, **AXIS)
fig3.update_yaxes(range=[up_y_min, up_y_max], title_text="Effective Tax Rate (%)",
                  row=2, col=1, **AXIS)
fig3.update_xaxes(range=[1979, 2023], row=2, col=1, **AXIS)
fig3.update_xaxes(range=[1979, 2023], row=1, col=1, **AXIS)

# Custom legend below the plot so it doesn't collide with subplot titles
LEGEND_BELOW = dict(orientation="h", yanchor="top", y=-0.12,
                    xanchor="center", x=0.5, font=dict(size=12),
                    bgcolor="rgba(0,0,0,0)", borderwidth=0)

fig3.update_layout(
    title=centered_title("Effective Tax Rate by Income Quintile (1979-2022)"),
    legend=LEGEND_BELOW, height=820,
    margin=dict(l=80, r=50, t=90, b=180),
)
fig3.add_annotation(
    text=("(Taxes − Govt Transfers − Private Transfers) ÷ Earned Income · "
          "Negative = net recipient · Positive = net payer<br>"
          "Grey bands = NBER recessions · Source: CBO / CPS"),
    xref="paper", yref="paper", x=0.5, y=-0.20,
    xanchor="center", yanchor="top", showarrow=False,
    align="center", font=dict(size=11, color="#666"))
save_chart(fig3, "fig_effective_tax_rate_by_quintile.png")


# =============================================================================
# SECTION 6b - Chart 3b: Income After Taxes as % of Earned Income
#
# Income After Taxes & Transfers as a percentage of Earned Income
# (i.e. IAT ÷ Earned × 100).  100% = fiscally neutral household.
#   Values > 100% → transfers exceed taxes (net recipient)
#   Values < 100% → taxes exceed transfers (net payer)
#   Values = 100% → fiscally neutral
#
# Easier to read than Chart 3 because all values are positive. The bottom
# quintile's enormous ratios (1,000-2,400%+) reflect the same finding as
# Chart 3's deeply-negative ETRs — just expressed as a multiplier.
#
# Two stacked panels for the same reason as Chart 3: Bottom dwarfs Q2-Top.
# =============================================================================

iat_by_q = {}
for q in QUINTILES:
    sub = df[df["quintile"] == q].sort_values("income_year").copy()
    sub["iat_pct"] = sub["iat"] / sub["earned"] * 100
    iat_by_q[q] = sub

_iat_bot = iat_by_q["Bottom"]["iat_pct"]
_iat_upper = pd.concat([iat_by_q[q]["iat_pct"] for q in ["Second", "Middle", "Fourth", "Top"]])
bot_y_lo = max(0.0, float(_iat_bot.min()) - 100)
bot_y_hi = float(_iat_bot.max()) + 150
up_y_lo  = float(_iat_upper.min()) - 10
up_y_hi  = float(_iat_upper.max()) + 15

fig3b = make_subplots(
    rows=2, cols=1,
    shared_xaxes=True,
    row_heights=[0.5, 0.5],
    vertical_spacing=0.12,
    subplot_titles=["Bottom Quintile", "Second through Top Quintile"],
)

fig3b.add_trace(go.Scatter(
    x=iat_by_q["Bottom"]["income_year"],
    y=iat_by_q["Bottom"]["iat_pct"].round(1),
    mode="lines", name="Bottom",
    line=dict(color=COLORS["Bottom"], width=2.5),
    hovertemplate="Year %{x}<br>IAT/Earned: %{y:.1f}%<extra>Bottom</extra>",
    showlegend=True,
), row=1, col=1)

for q in ["Second", "Middle", "Fourth", "Top"]:
    sub = iat_by_q[q]
    fig3b.add_trace(go.Scatter(
        x=sub["income_year"], y=sub["iat_pct"].round(1),
        mode="lines", name=q,
        line=dict(color=COLORS[q], width=2.5, dash=DASHES[q]),
        hovertemplate=f"Year %{{x}}<br>IAT/Earned: %{{y:.1f}}%<extra>{q}</extra>",
        showlegend=True,
    ), row=2, col=1)

for row in [1, 2]:
    shade_recessions(fig3b, row=row, col=1)
    fig3b.add_hline(y=100, line_dash="dot",
                    line_color="rgba(0,0,0,0.4)", line_width=1.5,
                    row=row, col=1)

fig3b.update_yaxes(range=[bot_y_lo, bot_y_hi], title_text="IAT ÷ Earned (%)",
                   row=1, col=1, **AXIS)
fig3b.update_yaxes(range=[up_y_lo, up_y_hi], title_text="IAT ÷ Earned (%)",
                   row=2, col=1, **AXIS)
fig3b.update_xaxes(range=[1979, 2023], row=2, col=1, **AXIS)
fig3b.update_xaxes(range=[1979, 2023], row=1, col=1, **AXIS)

LEGEND_BELOW_3B = dict(orientation="h", yanchor="top", y=-0.12,
                       xanchor="center", x=0.5, font=dict(size=12),
                       bgcolor="rgba(0,0,0,0)", borderwidth=0)

fig3b.update_layout(
    title=centered_title("Income After Taxes as % of Earned Income (1979-2022)"),
    legend=LEGEND_BELOW_3B, height=820,
    margin=dict(l=80, r=50, t=90, b=170),
)
fig3b.add_annotation(
    text=("(Earned + Govt + Private Transfers − Taxes) ÷ Earned Income  ·  100% = fiscally neutral<br>"
          "Grey bands = NBER recessions  ·  Source: CBO / CPS"),
    xref="paper", yref="paper", x=0.5, y=-0.18,
    xanchor="center", yanchor="top", showarrow=False,
    align="center", font=dict(size=11, color="#666"))
save_chart(fig3b, "fig_iat_pct_of_earned_by_quintile.png")


# =============================================================================
# SECTION 7 - Chart 4: Three-curve elephant chart
#
# Cumulative % growth 1979-2022 per quintile:
#   Blue  solid  = nominal earned BEFORE taxes & transfers
#   Green dashed = nominal income AFTER taxes & transfers
#   Red   dotted = REAL income after T&T (True CPI deflated)
#
# LABEL PLACEMENT: add_annotation called AFTER update_layout so it cannot be
# overwritten. Per-point xanchor/yanchor/xshift/yshift prevent overlap at
# Second quintile where blue=174.7 and red=183.6 (only 9% apart).
# =============================================================================
nom_before = cum_growth("earned")
nom_after  = cum_growth("iat")
real_after = cum_growth("iat_real")

fig4 = go.Figure()
fig4.add_trace(go.Scatter(x=POSITIONS, y=nom_before, mode="lines+markers",
    name="Nominal - before T&T",
    line=dict(color="#1f77b4", width=2.5),
    marker=dict(size=10, symbol="circle", color="#1f77b4")))
fig4.add_trace(go.Scatter(x=POSITIONS, y=nom_after, mode="lines+markers",
    name="Nominal - after T&T",
    line=dict(color="#2ca02c", width=2.5, dash="dash"),
    marker=dict(size=10, symbol="diamond", color="#2ca02c")))
fig4.add_trace(go.Scatter(x=POSITIONS, y=real_after, mode="lines+markers",
    name="Real (True CPI) - after T&T",
    line=dict(color="#d62728", width=2.5, dash="dot"),
    marker=dict(size=10, symbol="square", color="#d62728")))

fig4.update_xaxes(tickvals=POSITIONS, ticktext=QUINTILES,
                  title=dict(text="Quintile", font=dict(size=13)), **AXIS)
fig4.update_yaxes(title=dict(text="Cumulative Growth (%)", font=dict(size=13)), **AXIS)
fig4.update_layout(
    title=centered_title("Cumulative Income Growth 1979-2022: Nominal vs. Real"),
    legend=LEGEND, margin=dict(l=70, r=80, t=120, b=170),
)

# Green: always above marker
for x, y in zip(POSITIONS, nom_after):
    fig4.add_annotation(x=x, y=y, text=f"{y:.0f}%", showarrow=False,
        font=dict(size=11, color="#2ca02c"),
        xanchor="center", yanchor="bottom", yshift=10)

# Blue: below-left at Bottom+Second; below-center elsewhere
blue_cfg = [
    dict(xanchor="right",  yanchor="top", xshift=-6, yshift=-6),
    dict(xanchor="right",  yanchor="top", xshift=-6, yshift=-6),
    dict(xanchor="center", yanchor="top", xshift=0,  yshift=-8),
    dict(xanchor="center", yanchor="top", xshift=0,  yshift=-8),
    dict(xanchor="center", yanchor="top", xshift=0,  yshift=-8),
]
for i, (x, y) in enumerate(zip(POSITIONS, nom_before)):
    c = blue_cfg[i]
    fig4.add_annotation(x=x, y=y, text=f"{y:.0f}%", showarrow=False,
        font=dict(size=11, color="#1f77b4"),
        xanchor=c["xanchor"], yanchor=c["yanchor"],
        xshift=c["xshift"], yshift=c["yshift"])

# Red: right-of-marker at Bottom; right+below at Second; further below at Middle-Top
red_cfg = [
    dict(xanchor="left",   yanchor="middle", xshift=10, yshift=0),
    dict(xanchor="left",   yanchor="top",    xshift=10, yshift=0),
    dict(xanchor="center", yanchor="top",    xshift=0,  yshift=-22),
    dict(xanchor="center", yanchor="top",    xshift=0,  yshift=-22),
    dict(xanchor="center", yanchor="top",    xshift=0,  yshift=-22),
]
for i, (x, y) in enumerate(zip(POSITIONS, real_after)):
    c = red_cfg[i]
    fig4.add_annotation(x=x, y=y, text=f"{y:.0f}%", showarrow=False,
        font=dict(size=11, color="#d62728"),
        xanchor=c["xanchor"], yanchor=c["yanchor"],
        xshift=c["xshift"], yshift=c["yshift"])

# Footnote added last so update_layout cannot overwrite it
fig4.add_annotation(
    text="Blue = nominal before T&T  ·  Green = nominal after T&T  ·  Red = real (True CPI) after T&T<br>"
         "Source: CBO / CPS  ·  True CPI corrects substitution, new product & quality bias vs. CPI-U",
    xref="paper", yref="paper", x=0.5, y=-0.18,
    xanchor="center", yanchor="top", showarrow=False,
    align="center", font=dict(size=11, color="#555"))

save_chart(fig4, "fig_cumulative_income_growth_nominal_vs_real.png")
print("\nAll four charts complete.")
