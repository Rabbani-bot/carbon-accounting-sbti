"""Shared, consistent figure style for all portfolio projects."""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

PALETTE = ["#1D4E89", "#00A6A6", "#F6AE2D", "#E4572E", "#6A4C93", "#8AC926", "#5C677D"]
NEUTRAL = "#5C677D"
GRID = "#E6E8EC"
CREDIT = "Mohammad Rabbani | github.com/Rabbani-bot"


def apply():
    plt.rcParams.update({
        "font.family": ["Inter", "DejaVu Sans"],
        "font.size": 10.5,
        "axes.titlesize": 12.5, "axes.titleweight": "semibold", "axes.titlelocation": "left",
        "axes.labelsize": 10.5, "axes.labelcolor": "#222",
        "axes.spines.top": False, "axes.spines.right": False,
        "axes.edgecolor": "#9AA0A6", "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.8,
        "axes.axisbelow": True, "axes.prop_cycle": plt.cycler(color=PALETTE),
        "xtick.color": "#444", "ytick.color": "#444",
        "legend.frameon": False, "figure.dpi": 110, "savefig.dpi": 160,
        "savefig.bbox": "tight", "figure.facecolor": "white",
    })


def footnote(fig, text=CREDIT):
    fig.text(0.995, 0.005, text, ha="right", va="bottom", fontsize=8, color="#777")
