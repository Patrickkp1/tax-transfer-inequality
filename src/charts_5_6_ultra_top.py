"""
charts_5_6_ultra_top.py
========================
Charts 5 and 6 — same pattern as Charts 1 and 2, but for ultra-top groups:
  Top quintile, Top 0.1%, Top 0.01%, Top 0.001%, Forbes 400

OUTPUT FILES (written to ../output/ next to the panel CSVs)
-----------------------------------------------------------
  fig_real_earned_income_top_groups.png
  fig_real_income_after_taxes_transfers_top_groups.png

Year coverage by group (data availability):
  Top quintile:      1979-2022 (44 years, from CBO)
  Forbes 400:        1992-2022 (31 years, from IRS Top 400 publication)
  Top 0.1%/.01%/.001%: 2001-2022 (22 years, from IRS SOI Table T41TS)

Lines render only across the years each group has data, so coverage gaps are
visible (Forbes 400 starts in 1992, ultra-top groups start in 2001).

HOW TO RUN
----------
  python charts_5_6_ultra_top.py
"""

import os
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio

pio.templates.default = "plotly_white"

# ============================================================================
# SECTION 1 - File paths
# ============================================================================
HERE        = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR  = os.path.normpath(os.path.join(HERE, "..", "output"))
PANEL_CSV   = os.path.join(OUTPUT_DIR, "top_percentile_taxes_transfers_panel.csv")
CPI_CSV     = os.path.join(OUTPUT_DIR, "cpi_adjusted_v3_dbpi_1979_2022.csv")

# ============================================================================
# SECTION 2 - Load and prepare data
# ============================================================================
print(f"Loading: {PANEL_CSV}")
df = pd.read_csv(PANEL_CSV)

print(f"Loading: {CPI_CSV}")
cpi = (pd.read_csv(CPI_CSV)[["year", "True_CPI_idx"]]
         .rename(columns={"year": "income_year"}))

GROUPS = ["Top", "Top 0.1 percent", "Top 0.01 percent",
          "Top 0.001 percent", "Forbes 400"]

# Friendly labels for legend / annotations
LABELS = {
    "Top":               "Top 20%",
    "Top 0.1 percent":   "Top 0.1%",
    "Top 0.01 percent":  "Top 0.01%",
    "Top 0.001 percent": "Top 0.001%",
    "Forbes 400":        "Forbes 400",
}

df = df[df["group"].isin(GROUPS)].copy()
df = df.merge(cpi, on="income_year", how="left")

# Real (CPI-deflated) values in 1979 dollars
df["earned_real"] = df["earned_income"]                  / (df["True_CPI_idx"] / 100)
df["iat_real"]    = df["income_after_transfers_taxes"]   / (df["True_CPI_idx"] / 100)

# Coverage report
print("\nYear coverage by group:")
for g in GROUPS:
    sub = df[df["group"] == g].sort_values("income_year")
    if len(sub):
        print(f"  {LABELS[g]:<14} {sub['income_year'].min()}–{sub['income_year'].max()} ({len(sub)} years)")

# ============================================================================
# SECTION 3 - Shared styling
# ============================================================================
# Colors progress from cooler (Top quintile) to warmer (Forbes 400) to
# emphasize the increasing concentration as we move up the distribution.
COLORS = {
    "Top":               "#3182bd",   # blue
    "Top 0.1 percent":   "#31a354",   # green
    "Top 0.01 percent":  "#fd8d3c",   # orange
    "Top 0.001 percent": "#e6550d",   # dark orange
    "Forbes 400":        "#a50f15",   # deep red
}
DASHES = {
    "Top":               "solid",
    "Top 0.1 percent":   "dash",
    "Top 0.01 percent":  "dot",
    "Top 0.001 percent": "dashdot",
    "Forbes 400":        "solid",
}
RECESSIONS = [
    (1980, 1980), (1981, 1982), (1990, 1991),
    (2001, 2001), (2007, 2009), (2020, 2020),
]
AXIS = dict(showgrid=True, gridcolor="rgba(180,180,180,0.2)",
            zeroline=False, tickfont=dict(size=12))
# Legend below the title — five entries with longer labels ("Top 0.001%",
# "Forbes 400") wrap at the default y=1.02 position and overlap the title.
# Lower y plus extra top margin keeps the title line clear.
LEGEND = dict(orientation="h", yanchor="bottom", y=1.06,
              xanchor="center", x=0.5, font=dict(size=13),
              bgcolor="rgba(0,0,0,0)", borderwidth=0)

# Tick range covers $100k (Top quintile floor in 1979) to $1B (Forbes 400 ceiling)
DOLLAR_TICKS  = [100_000,    300_000,    1_000_000,    3_000_000,
                 10_000_000, 30_000_000, 100_000_000,  300_000_000]
DOLLAR_LABELS = ["$100k",    "$300k",    "$1M",        "$3M",
                 "$10M",     "$30M",     "$100M",      "$300M"]


def shade_recessions(fig):
    for start, end in RECESSIONS:
        fig.add_vrect(x0=start - 0.4, x1=end + 0.4,
                      fillcolor="rgba(210,210,210,0.35)",
                      line_width=0, layer="below")
    return fig


def centered_title(text):
    # Title size 16 (vs 17 in income_visualizations) because chart 6's title
    # "Real Income After Taxes & Transfers by Top Income Group (1979-2022)" is
    # long enough to bleed past the chart edges at size 17 + bold + scale=2.
    return dict(text=f"<b>{text}</b>", font=dict(size=16),
                x=0.5, xanchor="center", pad=dict(b=12))


def log_axis_range(series, pad_below=0.7, pad_above=2.2):
    """[log_min, log_max] from full series (not just endpoints)."""
    return [np.log10(series.min() * pad_below),
            np.log10(series.max() * pad_above)]


def make_paper_y(log_min, log_max):
    """Map a value to paper [0,1] y-coordinate on a log axis."""
    def converter(val):
        return (np.log10(val) - log_min) / (log_max - log_min)
    return converter


def save_chart(fig, filename):
    # Charts are written to the same output/ folder as the panel CSVs so
    # everything generated by this project ends up in one place.
    path = os.path.join(OUTPUT_DIR, filename)
    # Explicit width=1300 so the long title and footer text don't get cropped.
    # Default kaleido width is 700px which is too narrow for the long footnotes.
    fig.write_image(path, width=1300, height=780, scale=2)
    print(f"Saved: {filename}")


def fmt_dollar(val):
    """Compact dollar formatting: $300k / $5M / $400M."""
    if val >= 1e8:
        return f"${val/1e6:.0f}M"
    if val >= 1e7:
        return f"${val/1e6:.1f}M"
    if val >= 1e6:
        return f"${val/1e6:.2f}M"
    if val >= 1e3:
        return f"${val/1e3:.0f}k"
    return f"${val:.0f}"


def cum_growth(group, value_col):
    """Cumulative real growth (%) from the group's first available year to last."""
    sub = df[df["group"] == group].sort_values("income_year")
    if len(sub) < 2:
        return 0
    v0    = sub[value_col].iloc[0]
    v_end = sub[value_col].iloc[-1]
    return round((v_end / v0 - 1) * 100)


def first_year(group):
    sub = df[df["group"] == group].sort_values("income_year")
    return int(sub["income_year"].iloc[0]) if len(sub) else None


# ============================================================================
# SECTION 4 - Chart 5: Real EARNED INCOME (before taxes & transfers)
# ============================================================================
print("\nBuilding Chart 5...")

# End values + growth labels
earned_end, earned_pct, earned_y0 = {}, {}, {}
for g in GROUPS:
    sub   = df[df["group"] == g].sort_values("income_year")
    if len(sub) == 0:
        continue
    earned_end[g] = sub["earned_real"].iloc[-1]
    earned_pct[g] = cum_growth(g, "earned_real")
    earned_y0[g]  = first_year(g)

y5_range    = log_axis_range(df["earned_real"].dropna(), pad_below=0.7, pad_above=2.2)
to_paper_y5 = make_paper_y(*y5_range)

# Manual nudges to prevent label overlap when end values cluster on log axis.
Y5_OFFSETS = {
    "Top":               -0.010,
    "Top 0.1 percent":    0.000,
    "Top 0.01 percent":   0.000,
    "Top 0.001 percent":  0.000,
    "Forbes 400":         0.000,
}

fig5 = go.Figure()
for g in GROUPS:
    sub = df[df["group"] == g].sort_values("income_year")
    fig5.add_trace(go.Scatter(
        x=sub["income_year"], y=sub["earned_real"],
        mode="lines", name=LABELS[g],
        line=dict(color=COLORS[g], width=2.5, dash=DASHES[g]),
    ))

# End-of-line labels: $value + growth % from group's start year
x5_label = (2022 - 1979) / (2030 - 1979) + 0.012
for g in GROUPS:
    if g not in earned_end:
        continue
    fig5.add_annotation(
        xref="paper", yref="paper",
        x=x5_label,
        y=to_paper_y5(earned_end[g]) + Y5_OFFSETS[g],
        text=f"  {fmt_dollar(earned_end[g])}  +{earned_pct[g]}%",
        xanchor="left", yanchor="middle", showarrow=False,
        font=dict(size=11, color=COLORS[g]),
    )

shade_recessions(fig5)
fig5.update_yaxes(type="log",
                  tickvals=DOLLAR_TICKS, ticktext=DOLLAR_LABELS,
                  range=y5_range,
                  title=dict(text="Avg Household Income (1979 $, log scale)",
                             font=dict(size=13)),
                  **AXIS)
fig5.update_xaxes(range=[1979, 2030],
                  title=dict(text="Year", font=dict(size=13), standoff=30),
                  **AXIS)
fig5.update_layout(
    title=centered_title("Real Earned Income by Top Income Group (1979-2022)"),
    legend=LEGEND, margin=dict(l=100, r=140, t=140, b=140),
)
fig5.add_annotation(
    text="Before taxes & transfers  ·  True CPI deflated to 1979 dollars  ·  Log scale  ·  +% = cumul. real growth from group's first year<br>"
         "Top 20%: 1979-2022  ·  Forbes 400: 1992-2022  ·  Top 0.1%/.01%/.001%: 2001-2022  ·  Source: CBO / IRS SOI / IRS Top 400",
    xref="paper", yref="paper", x=0.5, y=-0.22,
    xanchor="center", yanchor="top", showarrow=False,
    align="center", font=dict(size=11, color="#555"))
save_chart(fig5, "fig_real_earned_income_top_groups.png")


# ============================================================================
# SECTION 5 - Chart 6: Real INCOME AFTER taxes & transfers
# ============================================================================
print("\nBuilding Chart 6...")

iat_end, iat_pct = {}, {}
for g in GROUPS:
    sub = df[df["group"] == g].sort_values("income_year")
    if len(sub) == 0:
        continue
    iat_end[g] = sub["iat_real"].iloc[-1]
    iat_pct[g] = cum_growth(g, "iat_real")

y6_range    = log_axis_range(df["iat_real"].dropna(), pad_below=0.7, pad_above=2.2)
to_paper_y6 = make_paper_y(*y6_range)

Y6_OFFSETS = {
    "Top":               -0.010,
    "Top 0.1 percent":    0.000,
    "Top 0.01 percent":   0.000,
    "Top 0.001 percent":  0.000,
    "Forbes 400":         0.000,
}

fig6 = go.Figure()
for g in GROUPS:
    sub = df[df["group"] == g].sort_values("income_year")
    fig6.add_trace(go.Scatter(
        x=sub["income_year"], y=sub["iat_real"],
        mode="lines", name=LABELS[g],
        line=dict(color=COLORS[g], width=2.5, dash=DASHES[g]),
    ))

x6_label = (2022 - 1979) / (2030 - 1979) + 0.012
for g in GROUPS:
    if g not in iat_end:
        continue
    fig6.add_annotation(
        xref="paper", yref="paper",
        x=x6_label,
        y=to_paper_y6(iat_end[g]) + Y6_OFFSETS[g],
        text=f"  {fmt_dollar(iat_end[g])}  +{iat_pct[g]}%",
        xanchor="left", yanchor="middle", showarrow=False,
        font=dict(size=11, color=COLORS[g]),
    )

shade_recessions(fig6)
fig6.update_yaxes(type="log",
                  tickvals=DOLLAR_TICKS, ticktext=DOLLAR_LABELS,
                  range=y6_range,
                  title=dict(text="Avg Household Income (1979 $, log scale)",
                             font=dict(size=13)),
                  **AXIS)
fig6.update_xaxes(range=[1979, 2030],
                  title=dict(text="Year", font=dict(size=13), standoff=30),
                  **AXIS)
fig6.update_layout(
    title=centered_title("Real Income After Taxes & Transfers by Top Income Group (1979-2022)"),
    legend=LEGEND, margin=dict(l=100, r=140, t=140, b=140),
)
fig6.add_annotation(
    text="After all taxes, govt & private transfers  ·  True CPI deflated to 1979 dollars  ·  Log scale  ·  +% = cumul. real growth from group's first year<br>"
         "Top 20%: 1979-2022  ·  Forbes 400: 1992-2022  ·  Top 0.1%/.01%/.001%: 2001-2022  ·  Source: CBO / IRS SOI / IRS Top 400",
    xref="paper", yref="paper", x=0.5, y=-0.22,
    xanchor="center", yanchor="top", showarrow=False,
    align="center", font=dict(size=11, color="#555"))
save_chart(fig6, "fig_real_income_after_taxes_transfers_top_groups.png")

print("\nDone.")
