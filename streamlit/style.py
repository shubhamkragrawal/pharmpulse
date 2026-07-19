"""Shared Plotly theme/palette. Every page imports from here -- no per-page
color choices -- so the app reads as one system. Palette matches the
dataviz-skill reference instance (light mode) already used in the M4 notebook.
"""

import plotly.graph_objects as go
import plotly.io as pio

# Categorical hues, fixed order, never cycled.
BLUE = "#2a78d6"
GREEN = "#008300"
MAGENTA = "#e87ba4"
YELLOW = "#eda100"
AQUA = "#1baf7a"
ORANGE = "#eb6834"
VIOLET = "#4a3aa7"
RED = "#e34948"
CATEGORICAL = [BLUE, GREEN, MAGENTA, YELLOW, AQUA, ORANGE, VIOLET, RED]

SURFACE = "#fcfcfb"
PRIMARY_INK = "#0b0b0b"
SECONDARY_INK = "#52514e"
MUTED_INK = "#898781"
GRIDLINE = "#e1e0d9"
BASELINE = "#c3c2b7"

GOOD = "#0ca30c"
WARNING = "#fab219"
CRITICAL = "#d03b3b"

_template = go.layout.Template()
_template.layout = go.Layout(
    paper_bgcolor=SURFACE,
    plot_bgcolor=SURFACE,
    font=dict(color=PRIMARY_INK, size=13),
    colorway=CATEGORICAL,
    xaxis=dict(
        gridcolor=GRIDLINE,
        linecolor=BASELINE,
        tickfont=dict(color=MUTED_INK),
        title_font=dict(color=SECONDARY_INK),
        zeroline=False,
    ),
    yaxis=dict(
        gridcolor=GRIDLINE,
        linecolor=BASELINE,
        tickfont=dict(color=MUTED_INK),
        title_font=dict(color=SECONDARY_INK),
        zeroline=False,
    ),
    legend=dict(font=dict(color=SECONDARY_INK)),
    margin=dict(l=40, r=20, t=40, b=40),
)

pio.templates["pharmpulse"] = _template
pio.templates.default = "pharmpulse"


def traffic_light(value: float, good_max: float, warning_max: float) -> str:
    """Lower-is-better traffic light: <=good_max green, <=warning_max amber, else red."""
    if value <= good_max:
        return "🟢"
    if value <= warning_max:
        return "🟡"
    return "🔴"
