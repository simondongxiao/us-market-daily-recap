from __future__ import annotations

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


ROOT = Path(r"D:\codex\outputs\us_market_daily_recaps\2026-10-13")
plt.rcParams.update({"font.family": ["Microsoft YaHei", "DejaVu Sans"], "font.size": 9, "axes.spines.top": False, "axes.spines.right": False})


def save(fig: plt.Figure, name: str) -> None:
    fig.tight_layout()
    fig.savefig(ROOT / name, dpi=190, facecolor="white", bbox_inches="tight")
    plt.close(fig)


def quote(symbol: str) -> dict:
    return json.loads((ROOT / "quotes.json").read_text(encoding="utf-8"))[symbol]


def bar(name: str, title: str, labels: list[str], values: list[float], xlabel: str = "1D price return (%)", height: float = 4.0) -> None:
    fig, ax = plt.subplots(figsize=(9.5, height))
    y = np.arange(len(labels))
    colors = ["#17836d" if x >= 0 else "#c84d58" for x in values]
    ax.barh(y, values, color=colors, height=.64)
    ax.set_yticks(y, labels)
    ax.invert_yaxis()
    ax.axvline(0, color="#555", lw=.7)
    ax.grid(axis="x", alpha=.18)
    ax.set_axisbelow(True)
    ax.set_title(title, loc="left", fontweight="bold", pad=10)
    ax.set_xlabel(xlabel)
    span = max(max(values) - min(values), .2)
    ax.set_xlim(min(0, min(values)) - span * .18, max(0, max(values)) + span * .18)
    for i, value in enumerate(values):
        ax.text(value + (span * .025 if value >= 0 else -span * .025), i, f"{value:+.2f}", va="center", ha="left" if value >= 0 else "right", fontsize=8)
    save(fig, name)


def main() -> None:
    q = json.loads((ROOT / "quotes.json").read_text(encoding="utf-8"))
    sector_labels = {"XLK": "XLK 科技", "XLC": "XLC 通信服务", "XLY": "XLY 可选消费", "XLP": "XLP 必选消费", "XLF": "XLF 金融", "XLI": "XLI 工业", "XLE": "XLE 能源", "XLB": "XLB 材料", "XLV": "XLV 医疗保健", "XLRE": "XLRE 房地产", "XLU": "XLU 公用事业"}
    sectors = sorted(sector_labels, key=lambda s: q[s]["day"], reverse=True)
    bar("sector_bar.png", "Sector rotation | Energy, staples and communication led", [sector_labels[s] for s in sectors], [q[s]["day"] for s in sectors], height=4.6)

    breadth = json.loads((ROOT / "breadth.json").read_text(encoding="utf-8"))
    fig, axes = plt.subplots(1, 2, figsize=(9.5, 3.0), gridspec_kw={"width_ratios": [1.3, 1]})
    for ax, labels, values, title in [
        (axes[0], ["Advancing", "Declining", "Unchanged"], [breadth["advancers"], breadth["decliners"], breadth["unchanged"]], "503 current S&P constituents"),
        (axes[1], ["252-session highs", "252-session lows"], [breadth["highs_252"], breadth["lows_252"]], "Historical extremes"),
    ]:
        y = np.arange(len(labels))
        ax.barh(y, values, color=["#17836d", "#c84d58", "#aaa"][:len(labels)])
        ax.set_yticks(y, labels)
        ax.invert_yaxis()
        ax.set_title(title, loc="left", fontsize=9, fontweight="bold")
        ax.grid(axis="x", alpha=.18)
        ax.set_axisbelow(True)
        for i, v in enumerate(values): ax.text(v + max(values) * .025, i, str(v), va="center", fontsize=8)
    fig.suptitle(f"Breadth | {breadth['up_pct']:.1f}% advanced; highs still exceed lows", x=.02, ha="left", fontweight="bold")
    save(fig, "breadth.png")

    factor_symbols = ["XLE", "XLP", "XLC", "RSP", "SPY", "IWM", "QQQ", "IGV", "XLK", "SOXX", "SPHB", "USMV"]
    bar("factor_proxy.png", "Factor and style proxies | defensives/energy versus high-beta tech", factor_symbols, [q[s]["day"] for s in factor_symbols], height=4.5)

    tiers = {
        "Tier 1 cash-flow leaders": "NVDA AVGO MSFT META AMZN GOOGL ORCL".split(),
        "Tier 2 infrastructure / networking": "MU SNDK WDC STX COHR LITE AAOI GLW MRVL CRDO ALAB CIEN NOK ANET HPE DELL SMCI".split(),
        "Tier 3 power / data centers": "VRT ETN PWR CEG NRG VST APLD IREN DLR EQIX".split(),
        "AI applications": "MSFT GOOGL AMZN META ORCL CRM NOW ADBE SNOW DDOG MDB CRWD".split(),
    }
    tier_values = [float(np.mean([q[s]["day"] for s in names if s in q])) for names in tiers.values()]
    bar("ai_ladder.png", "AI chain ladder | hardware drawdown exceeds applications", list(tiers), tier_values, height=3.1)

    options = json.loads((ROOT / "options_chain.json").read_text(encoding="utf-8"))["results"]
    flagged = []
    for row in options:
        alerts = [x for x in row.get("option_alerts", []) if x != "no_threshold_alert"]
        if alerts:
            flagged.append((row["ticker"], row.get("call_put_volume_ratio") or 0, row.get("max_strike_volume_share") or 0, ", ".join(alerts)))
    if flagged:
        flagged.sort(key=lambda x: max(abs(x[1] - 1), x[2]), reverse=True)
        labels = [f"{x[0]} | {x[3]}" for x in flagged]
        values = [x[2] * 100 if x[2] >= .2 else (x[1] - 1) * 10 for x in flagged]
        bar("options_alerts.png", "Option-chain threshold alerts | structure, not confirmed direction", labels, values, xlabel="Strike share (%) or 10x Call/Put deviation", height=max(3.2, .38 * len(labels) + 1.4))

    movers = sorted([(s, q[s]["day"], q[s].get("volume_ratio") or 0) for s in "META FICO FIGS MDT LITE COHR CIEN AAOI MU SNDK NVDA AVGO MRVL CRDO IONQ LCID".split()], key=lambda x: x[1], reverse=True)
    bar("movers.png", "Material single-stock exceptions | 1D return", [f"{s}  {vratio:.2f}x vol" for s, _, vratio in movers], [v for _, v, _ in movers], height=5.5)


if __name__ == "__main__":
    main()
