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
    if not labels or not values:
        ax.text(.5, .5, "Source unavailable", ha="center", va="center", transform=ax.transAxes, fontsize=13, color="#666")
        ax.set_axis_off()
        ax.set_title(title, loc="left", fontweight="bold", pad=10)
        save(fig, name)
        return
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

    # Keep the richer visual layer used by the earlier buy-side recap. The
    # compact charts above are useful for the first page; these drill-downs
    # prevent ETF averages from hiding industry and single-name dispersion.
    labels = {
        "XLK": "XLK（科技）", "XLC": "XLC（通信服务）", "XLY": "XLY（可选消费）", "XLP": "XLP（必选消费）",
        "XLF": "XLF（金融）", "XLI": "XLI（工业）", "XLE": "XLE（能源）", "XLB": "XLB（材料）",
        "XLV": "XLV（医疗保健）", "XLRE": "XLRE（房地产）", "XLU": "XLU（公用事业）",
        "SOXX": "SOXX（半导体）", "SMH": "SMH（半导体）", "IGV": "IGV（软件）",
        "XBI": "XBI（生物医药）", "IBB": "IBB（生物医药）", "IHI": "IHI（医疗器械）", "XHE": "XHE（医疗设备）",
        "ARKG": "ARKG（基因组学）", "CIBR": "CIBR（网络安全）", "SKYY": "SKYY（云计算）",
        "XME": "XME（金属与矿业）", "COPX": "COPX（铜矿）", "GDX": "GDX（黄金矿业）",
        "KRE": "KRE（区域银行）", "XRT": "XRT（零售）", "XHB": "XHB（住宅建筑）",
        "ITA": "ITA（航空航天/国防）", "ARKK": "ARKK（创新成长）", "MEME": "MEME（高空头/迷因）",
        "BUZZ": "BUZZ（社交情绪）",
    }

    def present(names: list[str]) -> list[str]:
        return [s for s in names if s in q and q[s].get("day") is not None]

    def labeled(names: list[str]) -> list[str]:
        return [labels.get(s, s) for s in names]

    broad = present(["XLE", "XLP", "XLC", "RSP", "SPY", "IWM", "XLK", "SOXX", "IGV", "XBI", "XLF", "XLV"])
    broad = sorted(broad, key=lambda s: q[s]["day"], reverse=True)
    bar("rotation.png", f"Price preference map | {ROOT.name} cash session", labeled(broad), [q[s]["day"] for s in broad], height=4.6)

    sectors = sorted(present(list(labels)[:11]), key=lambda s: q[s]["day"], reverse=True)
    bar("sectors.png", "11-sector ETF map | industry-labelled daily returns", labeled(sectors), [q[s]["day"] for s in sectors], height=4.3)

    subsector_names = present(["SOXX", "SMH", "IGV", "CIBR", "SKYY", "XBI", "IBB", "IHI", "XHE", "ARKG", "XME", "COPX", "GDX", "KRE", "XRT", "XHB", "ITA", "ARKK"])
    subsector_names = sorted(subsector_names, key=lambda s: q[s]["day"], reverse=True)
    bar("subsectors.png", "Sub-sector dispersion | industry proxies", labeled(subsector_names), [q[s]["day"] for s in subsector_names], height=max(5.2, .28 * len(subsector_names) + 1.8))

    factor_names = present(["MAGS", "IGV", "QQQ", "SPY", "RSP", "SPHB", "MTUM", "ARKK", "USMV", "IWM", "MEME", "BUZZ"])
    bar("factors.png", "Factor multi-speed | momentum, beta, low-vol and small cap", factor_names, [q[s]["day"] for s in factor_names], height=4.4)

    optical_names = present("AAOI COHR ALAB GLW LITE CIEN CRDO MRVL MU SNDK WDC STX".split())
    optical_names = sorted(optical_names, key=lambda s: q[s]["day"], reverse=True)
    bar("optical.png", "Optical / AI networking / semiconductor exceptions", optical_names, [q[s]["day"] for s in optical_names], height=max(4.0, .30 * len(optical_names) + 1.3))

    memory_names = present("MU SNDK WDC STX HPE DELL SMCI".split())
    memory_names = sorted(memory_names, key=lambda s: q[s]["day"], reverse=True)
    bar("memory.png", "Memory and server chain | storage versus server dispersion", memory_names, [q[s]["day"] for s in memory_names], height=3.8)

    mag7 = present("META NVDA MSFT AMZN GOOGL AAPL TSLA".split())
    bar("mag7.png", "Mag 7 internal rotation | not a single basket", mag7, [q[s]["day"] for s in mag7], height=3.8)

    pressure = sorted(present("LITE COHR CIEN AAOI ALAB CRDO SNDK MU MRVL NVDA AVGO ORCL".split()), key=lambda s: q[s]["day"])
    bar("losers.png", "Pressure points | largest negative moves", pressure[:8], [q[s]["day"] for s in pressure[:8]], height=4.2)

    company_names = sorted(present("META FICO FIGS MDT LITE COHR CIEN AAOI MU SNDK NVDA AVGO MRVL CRDO IONQ LCID TWST".split()), key=lambda s: abs(q[s]["day"]), reverse=True)
    bar("company_movers.png", "Company exceptions | absolute move and volume context", [f"{s} {q[s].get('volume_ratio', 0):.2f}x" for s in company_names[:12]], [q[s]["day"] for s in company_names[:12]], height=5.0)

    cross_names = present(["DX-Y.NYB", "CL=F", "BZ=F", "HG=F", "GC=F", "BTC-USD"])
    cross_labels = {"DX-Y.NYB": "DXY 美元", "CL=F": "WTI 原油", "BZ=F": "Brent 原油", "HG=F": "铜", "GC=F": "黄金", "BTC-USD": "BTC"}
    bar("crossasset.png", "Cross-asset tape | macro confirmation and counterevidence", [cross_labels[s] for s in cross_names], [q[s]["day"] for s in cross_names], height=3.2)

    vol_names = [s for s in ["^VIX", "^VVIX", "^SKEW"] if s in q and q[s].get("day") is not None]
    bar("volatility.png", "Volatility and tail-protection proxies", ["VIX" if s == "^VIX" else "VVIX" if s == "^VVIX" else "SKEW" for s in vol_names], [q[s]["day"] for s in vol_names], xlabel="Daily index change (%)", height=2.8)

    intraday_path = ROOT / "intraday.json"
    if intraday_path.exists():
        intraday = json.loads(intraday_path.read_text(encoding="utf-8"))
        if intraday:
            late_names = [x["symbol"] for x in intraday]
            late_values = [x.get("late_return", 0.0) for x in intraday]
            bar("moc.png", "Last 20-minute price proxy | not official MOC imbalance", late_names, late_values, xlabel="15:40-16:00 ET return (%)", height=3.4)

    intraday_files = [s for s in ["SPY", "QQQ", "RSP", "IWM", "SOXX", "IGV", "XLE", "XLC", "XLK"] if (ROOT / f"{s}_intraday.csv").exists()]
    if intraday_files:
        fig, ax = plt.subplots(figsize=(10, 3.7))
        for s in intraday_files:
            d = pd.read_csv(ROOT / f"{s}_intraday.csv")
            close = pd.to_numeric(d.get("Close"), errors="coerce").dropna()
            if close.empty:
                continue
            ax.plot(np.arange(len(close)), close / close.iloc[0] * 100, label=s, lw=1.25)
        ax.axhline(100, color="#777", lw=.6)
        ax.axvspan(max(0, 74), 79, color="#eeeeee", alpha=.8)
        ax.set_title("Regular-session path | closing auction proxy", loc="left", fontweight="bold")
        ax.set_ylabel("09:30 = 100")
        ax.legend(frameon=False, ncol=5, fontsize=8)
        ax.grid(alpha=.15)
        save(fig, "intraday.png")

    tier_groups = {
        "Tier 1 cash-flow leaders": "NVDA AVGO MSFT META AMZN GOOGL ORCL".split(),
        "Tier 2 infra / networking": "MU SNDK WDC STX COHR LITE AAOI GLW MRVL CRDO ALAB CIEN ANET HPE DELL SMCI".split(),
        "Tier 3 power / data centers": "VRT ETN PWR CEG NRG VST APLD IREN DLR EQIX".split(),
        "AI applications": "MSFT GOOGL AMZN META ORCL CRM NOW ADBE SNOW DDOG MDB CRWD".split(),
    }
    tier_values = []
    tier_labels = []
    for name, names in tier_groups.items():
        vals = [q[s]["day"] for s in names if s in q and q[s].get("day") is not None]
        if vals:
            tier_labels.append(name)
            tier_values.append(float(np.mean(vals)))
    bar("tiers.png", "AI chain tiers | cash-flow leaders, infrastructure and applications", tier_labels, tier_values, height=3.5)

    tn = q.get("^TNX", {})
    if tn.get("close") is not None and tn.get("prev_close") is not None:
        fig, ax = plt.subplots(figsize=(8.5, 2.8))
        vals = [tn["prev_close"], tn["close"]]
        ax.bar(["previous close", "target close"], vals, color=["#929eab", "#197f9d"])
        ax.set_ylabel("10Y yield proxy (%)")
        ax.set_title("10Y Treasury yield proxy | duration transmission", loc="left", fontweight="bold")
        ax.grid(axis="y", alpha=.15)
        ax.text(1, vals[1], f"{(vals[1] - vals[0]) * 100:+.1f}bp", ha="center", va="bottom", fontsize=9)
        save(fig, "macro_curve.png")

    option_rows = [x for x in options if x.get("data_status") == "available" and x.get("call_put_volume_ratio") is not None]
    if option_rows:
        option_rows = sorted(option_rows, key=lambda x: abs((x.get("call_put_volume_ratio") or 1) - 1), reverse=True)
        bar("options.png", "Near-expiry option structure | Call/Put volume ratio", [x["ticker"] for x in option_rows], [x.get("call_put_volume_ratio") or 0 for x in option_rows], xlabel="Call volume / Put volume", height=max(3.3, .25 * len(option_rows) + 1.5))

    fig, ax = plt.subplots(figsize=(10, 3.5))
    ax.axis("off")
    leaders = ", ".join(s for s in broad[:3]) or "unavailable"
    laggards = ", ".join(s for s in broad[-3:]) or "unavailable"
    ax.text(.03, .78, f"Relative strength\n{leaders}", transform=ax.transAxes, fontsize=12, color="#17836d", fontweight="bold", va="center")
    ax.annotate("", xy=(.48, .78), xytext=(.31, .78), xycoords="axes fraction", arrowprops={"arrowstyle": "->", "color": "#17836d", "lw": 1.8})
    ax.text(.53, .78, "price preference proxy\nnot direct fund flow", transform=ax.transAxes, fontsize=11, va="center")
    ax.text(.03, .35, f"Relative weakness\n{laggards}", transform=ax.transAxes, fontsize=12, color="#c84d58", fontweight="bold", va="center")
    ax.annotate("", xy=(.48, .35), xytext=(.31, .35), xycoords="axes fraction", arrowprops={"arrowstyle": "->", "color": "#c84d58", "lw": 1.8})
    ax.text(.53, .35, "pressure proxy\ncheck breadth, volume and catalysts", transform=ax.transAxes, fontsize=11, va="center")
    ax.set_title("Market-to-industry read-through | observed tape, not causal proof", loc="left", fontweight="bold")
    save(fig, "mapping.png")


if __name__ == "__main__":
    main()
