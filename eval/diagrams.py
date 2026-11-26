"""Workflow and architecture diagrams for the report and deck.  python -m eval.diagrams"""
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

from cov.common import RESULTS

INK, INK2, LINE = "#191919", "#555555", "#9a9a9a"
C = {"det": "#257de0", "model": "#f47230", "verify": "#00b894", "human": "#6a4ce2", "manual": "#8a8a8a"}
FIG = RESULTS / "figures"


def box(ax, x, y, w, h, text, color, fill_alpha=0.12, fs=8.2, bold=False):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.008,rounding_size=0.012",
                                fc=matplotlib.colors.to_rgba(color, fill_alpha), ec=color, lw=1.4))
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=fs, color=INK,
            fontweight="bold" if bold else "normal", wrap=True)


def arrow(ax, x1, y1, x2, y2, color=LINE, style="-|>", ls="-"):
    ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2), arrowstyle=style, mutation_scale=10, color=color, lw=1.2,
                                 linestyle=ls, shrinkA=0, shrinkB=0))


def current_state():
    fig, ax = plt.subplots(figsize=(10, 5.0), dpi=200)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    lanes = ["Borrower CFO", "Portfolio operations", "Credit analyst", "Portfolio manager", "Credit committee / counsel"]
    lh = 0.17
    for i, name in enumerate(lanes):
        y = 0.9 - (i + 1) * lh
        ax.add_patch(plt.Rectangle((0, y), 1, lh, fc="#f6f6f6" if i % 2 == 0 else "white", ec="#e0e0e0", lw=0.6))
        ax.text(0.01, y + lh / 2, name, va="center", fontsize=8.5, color=INK2, fontweight="bold")
    Y = lambda i: 0.9 - (i + 1) * lh + 0.03
    h = lh - 0.06
    steps = [(0, 0.17, "Deliver statements\n+ certificate\n(45 days)"), (1, 0.17, "Log receipt,\nchase late\npackages"),
             (2, 0.31, "Re-key PDFs\ninto spreading\nmodel"), (2, 0.45, "Re-read agreement\n+ amendments;\nrebuild EBITDA"),
             (2, 0.59, "Recompute ratios;\nreconcile to\ncertificate (Excel)"), (3, 0.59, "Review;\nwatchlist /\nrisk rating"),
             (4, 0.73, "Breach / waiver /\namendment\ndecision"), (2, 0.87, "File memo,\nupdate tracker")]
    w = 0.12
    for lane, x, t in steps:
        box(ax, x, Y(lane), w, h, t, C["manual"], fs=6.6)
    pairs = [(0, 1), (1, 2), (2, 3), (3, 4), (4, 5), (5, 6), (6, 7)]
    for a, b in pairs:
        la, xa, _ = steps[a]
        lb, xb, _ = steps[b]
        if la == lb:
            arrow(ax, xa + w, Y(la) + h / 2, xb, Y(lb) + h / 2)
        else:
            arrow(ax, xa + w / 2 if xa == xb else xa + w, Y(la) + (0 if lb > la else h) if xa == xb else Y(la) + h / 2,
                  xb + w / 2 if xa == xb else xb, Y(lb) + (h if lb > la else 0) if xa == xb else Y(lb) + h / 2)
    pains = [(0.31, "P1 manual\nre-keying"), (0.45, "P2 definitions\ndrift"),
             (0.59, "P3 weak clause link\nP5 add-back variance"), (0.73, "P4 reactive\nmonitoring")]
    for x, t in pains:
        ax.text(x + w / 2, 0.91, t, ha="center", va="bottom", fontsize=6.8, color="#c0392b")
    ax.text(0.0, 1.03, "Current state: quarterly covenant monitoring cycle (assumed from EDGAR documents; not observed at a lender)",
            fontsize=10, color=INK, va="top", fontweight="bold")
    fig.savefig(FIG / "current_state.png", bbox_inches="tight")
    plt.close(fig)


def future_state():
    fig, ax = plt.subplots(figsize=(10, 5.6), dpi=200)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    h = 0.12
    # row 1: inputs and proposal
    box(ax, 0.00, 0.78, 0.13, h, "Borrower package\n(PDF, untrusted)", C["manual"], fs=7.5)
    box(ax, 0.00, 0.56, 0.13, h, "Credit agreement\n+ amendments", C["manual"], fs=7.5)
    box(ax, 0.17, 0.78, 0.15, h, "Extraction -> typed\nfields + page cites\n(rule x2 | LLM)", C["model"], fs=7.3)
    box(ax, 0.17, 0.56, 0.15, h, "Knowledge graph\n(rule | LLM + team\nreview)", C["model"], fs=7.3)
    box(ax, 0.36, 0.78, 0.17, h, "Verify: XBRL tie-out,\n2nd independent read,\nprior package, arithmetic", C["verify"], fs=7.2)
    box(ax, 0.36, 0.56, 0.17, h, "Governing version by\neffective date\n(halt if undeterminable)", C["det"], fs=7.2)
    box(ax, 0.57, 0.67, 0.16, h, "Covenant engine:\ncaps, ratios, headroom,\nsensitivity, trend", C["det"], fs=7.3)
    box(ax, 0.77, 0.78, 0.22, h, "Gap > tolerance? Investigator:\nread-only tools, closed-set\ncauses, 12-step budget", C["model"], fs=7.2)
    box(ax, 0.77, 0.56, 0.22, h, "Provisional status +\ndraft memo (numeric guard)", C["det"], fs=7.3)
    # row 2: humans
    box(ax, 0.17, 0.27, 0.20, h, "Analyst: accept / reject\nfindings and re-read values", C["human"], fs=7.4)
    box(ax, 0.42, 0.27, 0.20, h, "PM: sign COMPLIANT/TIGHT,\nrelease HALT, rating", C["human"], fs=7.4)
    box(ax, 0.67, 0.27, 0.20, h, "Credit committee: declare\nbreach, waiver, amendment", C["human"], fs=7.4)
    box(ax, 0.17, 0.06, 0.70, 0.10, "Append-only audit log (SHA-256 hash chain): input hashes, code commit, terms + evidence,\n"
                                  "every field + page, agent trace, tolerances, each decision with user / role / time", C["det"], fs=7.4)
    for (x1, y1, x2, y2) in [(0.13, 0.84, 0.17, 0.84), (0.13, 0.62, 0.17, 0.62), (0.32, 0.84, 0.36, 0.84), (0.32, 0.62, 0.36, 0.62),
                             (0.53, 0.84, 0.57, 0.76), (0.53, 0.62, 0.57, 0.70), (0.73, 0.75, 0.77, 0.84), (0.73, 0.71, 0.77, 0.62),
                             (0.88, 0.78, 0.88, 0.68), (0.88, 0.56, 0.77, 0.39), (0.27, 0.27, 0.27, 0.16), (0.52, 0.27, 0.52, 0.16),
                             (0.77, 0.27, 0.77, 0.16), (0.37, 0.33, 0.42, 0.33), (0.62, 0.33, 0.67, 0.33)]:
        arrow(ax, x1, y1, x2, y2)
    ax.text(0.0, 0.47, "AUTHORITY LINE: nothing above this line can set a status, accept a figure, or contact the borrower",
            fontsize=7.6, color=C["human"], fontweight="bold")
    ax.plot([0, 1], [0.455, 0.455], color=C["human"], lw=1, ls="--")
    leg = [("Model may propose", C["model"]), ("Deterministic", C["det"]), ("Independent verification", C["verify"]),
           ("Human authority", C["human"]), ("Input", C["manual"])]
    for i, (t, c) in enumerate(leg):
        ax.add_patch(plt.Rectangle((0.0 + i * 0.2, 0.955), 0.018, 0.025, fc=matplotlib.colors.to_rgba(c, 0.25), ec=c))
        ax.text(0.024 + i * 0.2, 0.967, t, fontsize=7.6, va="center", color=INK)
    fig.savefig(FIG / "future_state.png", bbox_inches="tight")
    plt.close(fig)


if __name__ == "__main__":
    FIG.mkdir(parents=True, exist_ok=True)
    current_state()
    future_state()
