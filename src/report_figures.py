"""
report_figures.py
=================
Two summary figures used in the LaTeX research report.  Same conventions as
income_visualizations.py: discovers the panel CSVs in <repo>/output/, writes
the PNGs back to the same folder.

  fig_inequality_ratio_before_after_fisc.png
      Top quintile / Bottom quintile income ratio over time, comparing the
      earned-income series to the after-taxes-and-transfers series.  Shows
      how much of the headline 96x ratio is driven by ranking households
      before any fiscal adjustment.

  fig_net_fiscal_position_by_quintile_2022.png
      Government transfers received, private transfers received, and taxes
      paid per household per year, by quintile, in 2022, plus the algebraic
      sum of the three.  A 'who is a net giver / receiver' chart.
"""

import os
import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio

pio.templates.default = "plotly_white"


# ----------------------------------------------------------------------------
# File paths -- find <repo>/output/ relative to this script
# ----------------------------------------------------------------------------
HERE       = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.normpath(os.path.join(HERE, "..", "output"))
PANEL_CSV  = os.path.join(OUTPUT_DIR, "income_after_taxes_transfers_panel.csv")

print(f"Loading: {PANEL_CSV}")
panel = pd.read_csv(PANEL_CSV)
panel = panel[panel["quintile"].isin(["Bottom", "Second", "Middle", "Fourth", "Top"])].copy()


# =============================================================================
# Figure 1 - Top:Bottom income ratio, earned vs IAT, 1979-2022
# =============================================================================
years = sorted(panel["income_year"].unique())
rows  = []
for yr in years:
    b = panel[(panel["income_year"] == yr) & (panel["quintile"] == "Bottom")].iloc[0]
    t = panel[(panel["income_year"] == yr) & (panel["quintile"] == "Top")].iloc[0]
    rows.append({
        "year":         int(yr),
        "earned_ratio": float(t["earned"]) / float(b["earned"]),
        "iat_ratio":    float(t["iat"])    / float(b["iat"]),
    })
ratios = pd.DataFrame(rows)

fig1 = go.Figure()
fig1.add_trace(go.Scatter(
    x=ratios["year"], y=ratios["earned_ratio"],
    mode="lines", name="Earned income (before taxes & transfers)",
    line=dict(color="#A84B2F", width=3.0),
))
fig1.add_trace(go.Scatter(
    x=ratios["year"], y=ratios["iat_ratio"],
    mode="lines", name="Income after taxes & transfers",
    line=dict(color="#20808D", width=3.0),
))

# End-of-series labels
last = ratios.iloc[-1]
fig1.add_annotation(
    x=int(last["year"]), y=float(last["earned_ratio"]),
    text=f"  {last['earned_ratio']:.0f}x ",
    showarrow=False, xanchor="left", yanchor="middle",
    font=dict(size=14, color="#A84B2F"))
fig1.add_annotation(
    x=int(last["year"]), y=float(last["iat_ratio"]),
    text=f"  {last['iat_ratio']:.1f}x ",
    showarrow=False, xanchor="left", yanchor="middle",
    font=dict(size=14, color="#20808D"))

# NBER recession bands
recessions = [(1980.0, 1980.5), (1981.5, 1982.9), (1990.5, 1991.2),
              (2001.2, 2001.9), (2007.9, 2009.5), (2020.1, 2020.3)]
for s, e in recessions:
    fig1.add_vrect(x0=s, x1=e, fillcolor="lightgray",
                   opacity=0.35, layer="below", line_width=0)

fig1.update_layout(
    title=dict(
        text=("<b>Top-to-Bottom Quintile Income Ratio, 1979&#8211;2022</b><br>"
              "<span style='font-size:13px;color:#666'>"
              "Earned-income ratio rose from 24x to 96x; "
              "after-tax-and-transfer ratio rose from 2.3x to 4.4x</span>"),
        x=0.5, xanchor="center"),
    xaxis=dict(title="Year", range=[1979, 2026]),
    yaxis=dict(type="log", title="Top quintile / Bottom quintile (log scale)",
               range=[0.3, 2.1],
               tickvals=[2, 3, 5, 10, 20, 50, 100],
               ticktext=["2x", "3x", "5x", "10x", "20x", "50x", "100x"]),
    legend=dict(orientation="h", yanchor="bottom", y=-0.22,
                xanchor="center", x=0.5),
    width=1200, height=700,
    margin=dict(l=80, r=120, t=110, b=140),
)
fig1.add_annotation(
    text="Grey bands = NBER recessions  -  Sources: CBO, BLS CEX, IRS SOI, OMB, BEA, CPS ASEC",
    xref="paper", yref="paper", x=0.5, y=-0.32,
    xanchor="center", yanchor="top", showarrow=False,
    font=dict(size=10, color="#555"))

out1 = os.path.join(OUTPUT_DIR, "fig_inequality_ratio_before_after_fisc.png")
fig1.write_image(out1, scale=2)
print(f"Saved: {out1}")


# =============================================================================
# Figure 2 - Net fiscal position per HH per year, by quintile (2022)
# =============================================================================
y2022 = panel[panel["income_year"] == 2022].copy()
y2022 = (y2022.set_index("quintile")
              .loc[["Bottom", "Second", "Middle", "Fourth", "Top"]]
              .reset_index())
y2022["net"] = y2022["govt_transfers"] + y2022["priv_transfers"] - y2022["taxes"]

fig2 = go.Figure()
# Three flow bars (transfers in, taxes out) plus a fourth "net" total bar.
# Side-by-side grouping reads more cleanly than stacked here, since the
# Bottom-quintile inflows and the Top-quintile outflows are very different
# magnitudes.
fig2.add_trace(go.Bar(
    x=y2022["quintile"], y=y2022["govt_transfers"],
    name="Govt transfers received",
    marker_color="#20808D",
    text=[f"+${v/1000:.1f}k" for v in y2022["govt_transfers"]],
    textposition="outside",
    textfont=dict(size=11),
))
fig2.add_trace(go.Bar(
    x=y2022["quintile"], y=y2022["priv_transfers"],
    name="Private transfers received",
    marker_color="#BCE2E7",
    text=[f"+${v/1000:.1f}k" for v in y2022["priv_transfers"]],
    textposition="outside",
    textfont=dict(size=11),
))
fig2.add_trace(go.Bar(
    x=y2022["quintile"], y=-y2022["taxes"],
    name="Taxes paid",
    marker_color="#A84B2F",
    text=[f"-${v/1000:.0f}k" for v in y2022["taxes"]],
    textposition="outside",
    textfont=dict(size=11),
))
# Net fiscal position -- gold bar so the dark text labels stay readable
fig2.add_trace(go.Bar(
    x=y2022["quintile"], y=y2022["net"],
    name="Net fiscal position (total)",
    marker=dict(color="#FFC553", line=dict(color="#7A6020", width=1)),
    text=[(f"<b>+${v/1000:.1f}k</b>" if v >= 0 else f"<b>-${abs(v)/1000:.1f}k</b>")
          for v in y2022["net"]],
    textposition="outside",
    textfont=dict(size=12, color="black"),
))

fig2.add_hline(y=0, line=dict(color="black", width=1, dash="solid"))

fig2.update_layout(
    title=dict(
        text=("<b>Net Fiscal Position per Household by Quintile, 2022</b><br>"
              "<span style='font-size:13px;color:#666'>"
              "Bottom quintile: net receiver of 53k - "
              "Top quintile: net payer of 125k</span>"),
        x=0.5, xanchor="center"),
    xaxis_title="Income quintile (ranked by earned income)",
    yaxis_title="Dollars per household per year",
    barmode="group",
    bargap=0.25,
    bargroupgap=0.05,
    legend=dict(orientation="h", yanchor="bottom", y=-0.20,
                xanchor="center", x=0.5),
    width=1300, height=780,
    margin=dict(l=90, r=60, t=130, b=170),
)
fig2.update_yaxes(range=[-160000, 80000])
fig2.add_annotation(
    text="Net = govt transfers + private transfers - taxes. Sources: CBO, IRS, OMB, BEA, BLS, CPS ASEC, Giving USA",
    xref="paper", yref="paper", x=0.5, y=-0.30,
    xanchor="center", yanchor="top", showarrow=False,
    font=dict(size=10, color="#555"))

out2 = os.path.join(OUTPUT_DIR, "fig_net_fiscal_position_by_quintile_2022.png")
fig2.write_image(out2, scale=2)
print(f"Saved: {out2}")

print("\nDone.")
