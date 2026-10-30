from typing import Any

import plotly.graph_objects as go
import plotly.io as pio

# Plotly theme tokens (edit here to update all assets)
PLOTLY_FONT_FAMILY = "Arial"  # placeholder; set the final font here later
PLOTLY_FONT_SIZE = 12
PLOTLY_TEXT_COLOR = "#222222"
PLOTLY_AXIS_COLOR = "#B0B0B0"
PLOTLY_GRID_COLOR = "rgba(0,0,0,0.12)"
PLOTLY_BG = "white"
PLOTLY_TEMPLATE = "simple_white"

COLOR_OA_STATUS = {'closed':'#e65100', 'open':'#215CAF'}

# Quick-start institution colors (adjust later if needed)
INSTITUTION_COLORS = {
    "empa": "#00838F",
    "epfl": "#FF0000",
    "psi": "#F28E2B",
    "wsl": "#00695C",
    "ethz": "#003A70",
    "eawag": "#00A6D6",
    "ethdomain": "#4D4D4D",
}

PLOTLY_PRIMARY = INSTITUTION_COLORS["ethz"]
PLOTLY_SECONDARY = "#6e6e6e"
PLOTLY_ACCENT = INSTITUTION_COLORS["epfl"]

# Default categorical palette for multi-series plots
PLOTLY_PALETTE = [
    INSTITUTION_COLORS["ethz"],
    INSTITUTION_COLORS["epfl"],
    INSTITUTION_COLORS["psi"],
    INSTITUTION_COLORS["wsl"],
    INSTITUTION_COLORS["empa"],
    INSTITUTION_COLORS["eawag"],
    INSTITUTION_COLORS["ethdomain"],
]

COLOR_SCHEME = {
    "primary": PLOTLY_PRIMARY,
    "secondary": PLOTLY_SECONDARY,
    "accent": PLOTLY_ACCENT,
    "palette": PLOTLY_PALETTE,
    "institutions": INSTITUTION_COLORS,
}

def palette_color(index: int) -> str:
    return PLOTLY_PALETTE[index % len(PLOTLY_PALETTE)]

def institution_color(inst: str) -> str:
    return INSTITUTION_COLORS.get(inst, PLOTLY_SECONDARY)

def plotly_base_layout() -> dict[str, Any]:
    # Build a layout dict for direct fig.update_layout(...) usage.
    return dict(
        template="ethreports",
        font=dict(
            family=PLOTLY_FONT_FAMILY,
            size=PLOTLY_FONT_SIZE,
            color=PLOTLY_TEXT_COLOR,
        ),
        paper_bgcolor=PLOTLY_BG,
        plot_bgcolor=PLOTLY_BG,
    )


# Register the named template so it can be used as template="ethreports".
_ethreports_layout = dict(
    font=dict(
        family=PLOTLY_FONT_FAMILY,
        size=PLOTLY_FONT_SIZE,
        color=PLOTLY_TEXT_COLOR,
    ),
    paper_bgcolor=PLOTLY_BG,
    plot_bgcolor=PLOTLY_BG,
    xaxis=dict(
        showline=True,
        linecolor=PLOTLY_AXIS_COLOR,
        tickcolor=PLOTLY_AXIS_COLOR,
        gridcolor=PLOTLY_GRID_COLOR,
        zerolinecolor=PLOTLY_GRID_COLOR,
    ),
    yaxis=dict(
        showline=True,
        linecolor=PLOTLY_AXIS_COLOR,
        tickcolor=PLOTLY_AXIS_COLOR,
        gridcolor=PLOTLY_GRID_COLOR,
        zerolinecolor=PLOTLY_GRID_COLOR,
    ),
)
ETHREPORTS_TEMPLATE = go.layout.Template(pio.templates["simple_white"])
ETHREPORTS_TEMPLATE.layout.update(_ethreports_layout)
pio.templates["ethreports"] = ETHREPORTS_TEMPLATE


def apply_plotly_theme(
    fig: go.Figure,
    *,
    title: str | None = None,
    xaxis_title: str | None = None,
    yaxis_title: str | None = None,
    legend_inside: bool = True,
) -> go.Figure:
    # Apply the named theme plus common legend/title helpers.
    layout = plotly_base_layout()
    if title:
        layout["title"] = dict(text=title, x=0.5, xanchor="center")
    if legend_inside:
        layout["legend"] = dict(
            x=0.02,
            y=0.98,
            xanchor="left",
            yanchor="top",
            bgcolor="rgba(255,255,255,0.6)",
            bordercolor="rgba(0,0,0,0.1)",
            borderwidth=1,
        )
    fig.update_layout(**layout)
    if xaxis_title is not None:
        fig.update_xaxes(title=xaxis_title)
    if yaxis_title is not None:
        fig.update_yaxes(title=yaxis_title)
    return fig
