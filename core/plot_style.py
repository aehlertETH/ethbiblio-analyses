# core/plot_style.py
from pathlib import Path

import plotly.graph_objects as go
import plotly.io as pio

DEFAULT_TEMPLATE_NAME = "ethreports"
DEFAULT_FONT_SIZE = 12
DEFAULT_TEXT_COLOR = "#222222"
DEFAULT_FONT_FAMILY = "Arial, Helvetica, sans-serif"

_MATHJAX_CONFIGURED = False

DEFAULT_LAYOUT = dict(
    margin=dict(l=40, r=20, t=20, b=40),
    font=dict(
        family=DEFAULT_FONT_FAMILY,
        size=DEFAULT_FONT_SIZE,
        color=DEFAULT_TEXT_COLOR,
    ),
)

_AXIS_COLOR = "#B0B0B0"
_GRID_COLOR = "rgba(0,0,0,0.12)"
_BG = "white"


def _register_template() -> None:
    layout = dict(
        font=dict(
            family=DEFAULT_FONT_FAMILY,
            size=DEFAULT_FONT_SIZE,
            color=DEFAULT_TEXT_COLOR,
        ),
        paper_bgcolor=_BG,
        plot_bgcolor=_BG,
        xaxis=dict(
            showline=True,
            linecolor=_AXIS_COLOR,
            tickcolor=_AXIS_COLOR,
            gridcolor=_GRID_COLOR,
            zerolinecolor=_GRID_COLOR,
            mirror=True,
        ),
        yaxis=dict(
            showline=True,
            linecolor=_AXIS_COLOR,
            tickcolor=_AXIS_COLOR,
            gridcolor=_GRID_COLOR,
            zerolinecolor=_GRID_COLOR,
            mirror=True,
        ),
    )

    tmpl = go.layout.Template(pio.templates["simple_white"])
    tmpl.layout.update(layout)
    pio.templates[DEFAULT_TEMPLATE_NAME] = tmpl


# register once on import
_register_template()


def _configure_mathjax_for_static_export() -> None:
    global _MATHJAX_CONFIGURED
    if _MATHJAX_CONFIGURED:
        return
    _MATHJAX_CONFIGURED = True

    # Keep user-defined mathjax settings if already configured.
    if getattr(pio.defaults, "mathjax", None):
        return

    try:
        import kaleido  # type: ignore
    except Exception:
        return

    mathjax_js = Path(kaleido.__file__).resolve().parent / "executable" / "etc" / "mathjax" / "MathJax.js"
    if mathjax_js.exists():
        pio.defaults.mathjax = f"{mathjax_js.as_uri()}?config=TeX-AMS-MML_SVG"


def apply_style(fig: go.Figure) -> go.Figure:
    """
    Apply only what is shared for all charts:
    - template
    - margins
    - font
    - axis/grid look (via template)
    """
    _configure_mathjax_for_static_export()
    fig.update_layout(template=DEFAULT_TEMPLATE_NAME, **DEFAULT_LAYOUT)
    return fig
