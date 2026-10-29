from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any


# These are coverage proxies or macro instruments, not single-stock movers.
NON_SINGLE_STOCKS = {
    "SPY", "QQQ", "RSP", "IWM", "DIA", "MAGS", "SOXX", "SMH", "IGV",
    "XLK", "XLC", "XLY", "XLP", "XLF", "XLI", "XLE", "XLB", "XLV",
    "XLRE", "XLU", "XBI", "IBB", "IHI", "XHE", "ARKG", "CIBR", "SKYY",
    "XME", "COPX", "GDX", "KRE", "XRT", "XHB", "ITA", "ARKK", "MTUM",
    "SPHB", "USMV", "MEME", "BUZZ", "^DJI", "^GSPC", "^IXIC", "^RUT",
    "^VIX", "^VVIX", "^SKEW", "^TNX", "DX-Y.NYB", "CL=F", "BZ=F", "GC=F",
    "HG=F", "BTC-USD",
}

INDUSTRY_HINTS = {
    "NVDA": "半导体/AI算力", "AMD": "半导体/CPU与GPU", "MU": "半导体/存储",
    "SNDK": "半导体/存储", "WDC": "半导体/存储", "STX": "半导体/存储",
    "LRCX": "半导体设备", "AMAT": "半导体设备", "TER": "半导体测试",
    "COHR": "光通信/光电子", "LITE": "光通信/光模块", "AAOI": "光通信/光模块",
    "CRDO": "网络互联/高速连接", "MRVL": "网络芯片/数据中心", "ANET": "网络交换",
    "VRT": "数据中心电力/散热", "PWR": "电力基础设施", "APLD": "AI数据中心",
    "IREN": "AI数据中心/算力", "ORCL": "云计算", "AVGO": "半导体/网络芯片",
    "META": "互联网平台/广告", "MSFT": "软件/云计算", "TWST": "生命科学工具/合成生物学",
    "FICO": "金融数据/软件", "HOOD": "金融科技/交易平台", "CRL": "生命科学工具",
    "LMT": "航空航天/国防", "HAS": "可选消费/玩具", "FFIV": "网络设备/应用交付",
}


def _float(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _is_stock(symbol: str) -> bool:
    return bool(symbol) and symbol not in NON_SINGLE_STOCKS and not symbol.startswith("^") and "=" not in symbol


def _add_reason(row: dict[str, Any], reason: str) -> None:
    reasons = row.setdefault("selection_reasons", [])
    if reason not in reasons:
        reasons.append(reason)


def select_daily_movers(root: Path, side_limit: int = 4, max_selected: int = 10) -> dict[str, Any]:
    """Select the day's actual single-stock outliers from all available cross-sectional data."""
    quotes_path = root / "quotes.json"
    quotes = json.loads(quotes_path.read_text(encoding="utf-8")) if quotes_path.exists() else {}
    spy_day = _float((quotes.get("SPY") or {}).get("day"))
    candidates: dict[str, dict[str, Any]] = {}

    # Yahoo quote coverage supplies volume and relative-to-SPY evidence.
    for symbol, raw in quotes.items():
        if not _is_stock(symbol):
            continue
        day = _float(raw.get("day"))
        if day is None:
            continue
        volume_ratio = _float(raw.get("volume_ratio"))
        candidates[symbol] = {
            "ticker": symbol,
            "industry": INDUSTRY_HINTS.get(symbol, "单股异动（行业标签待核）"),
            "day": day,
            "volume_ratio": volume_ratio,
            "relative_vs_spy": day - spy_day if spy_day is not None else None,
            "source": "Yahoo Finance Chart API quote universe",
            "new_high_252": None,
            "new_low_252": None,
            "selection_reasons": [],
        }

    # S&P 500 breadth is the wider daily cross-section. It prevents the fixed
    # AI/optical watchlists from becoming the report's anomaly list.
    breadth_path = root / "sp500_breadth_detail.csv"
    if breadth_path.exists():
        with breadth_path.open(newline="", encoding="utf-8-sig") as handle:
            for raw in csv.DictReader(handle):
                symbol = str(raw.get("symbol") or "").strip().upper()
                day = _float(raw.get("return"))
                if not _is_stock(symbol) or day is None:
                    continue
                if symbol not in candidates:
                    candidates[symbol] = {
                        "ticker": symbol,
                        "industry": INDUSTRY_HINTS.get(symbol, "S&P 500成分股（行业标签待核）"),
                        "day": day,
                        "volume_ratio": None,
                        "relative_vs_spy": day - spy_day if spy_day is not None else None,
                        "source": "S&P 500 breadth cross-section",
                        "new_high_252": str(raw.get("high252", "")).lower() == "true",
                        "new_low_252": str(raw.get("low252", "")).lower() == "true",
                        "selection_reasons": [],
                    }
                else:
                    candidates[symbol]["new_high_252"] = str(raw.get("high252", "")).lower() == "true"
                    candidates[symbol]["new_low_252"] = str(raw.get("low252", "")).lower() == "true"
                    if "S&P 500 breadth cross-section" not in candidates[symbol]["source"]:
                        candidates[symbol]["source"] += "; S&P 500 breadth cross-section"

    valid = list(candidates.values())
    if not valid:
        return {
            "report_date_bjt": root.name,
            "selection_method": "no valid single-stock daily data",
            "universe_count": 0,
            "selected_count": 0,
            "selected": [],
            "coverage": {"quotes": 0, "sp500_breadth": 0},
        }

    def qualified(row: dict[str, Any]) -> bool:
        day = abs(row["day"])
        rel = abs(row["relative_vs_spy"]) if row.get("relative_vs_spy") is not None else 0
        volume = row.get("volume_ratio") or 0
        return day >= 2 or rel >= 2 or volume >= 1.5 or row.get("new_high_252") or row.get("new_low_252")

    qualified_rows = [row for row in valid if qualified(row)]
    pool = qualified_rows or valid
    gainers = sorted((row for row in pool if row["day"] > 0), key=lambda row: row["day"], reverse=True)
    decliners = sorted((row for row in pool if row["day"] < 0), key=lambda row: row["day"])
    by_volume = sorted(pool, key=lambda row: row.get("volume_ratio") or 0, reverse=True)
    selected: dict[str, dict[str, Any]] = {}

    def add(row: dict[str, Any], reason: str) -> None:
        _add_reason(row, reason)
        selected[row["ticker"]] = row

    for row in gainers[:side_limit]:
        add(row, "top_gainer" if row["day"] > 0 else "top_decliner")
    for row in decliners[:side_limit]:
        add(row, "top_decliner")
    for row in by_volume[: max(2, side_limit // 2)]:
        if (row.get("volume_ratio") or 0) >= 1.5:
            add(row, "relative_volume_outlier")

    if len(selected) < min(max_selected, 4):
        for row in sorted(pool, key=lambda row: abs(row["day"]), reverse=True):
            add(row, "absolute_move_outlier")
            if len(selected) >= min(max_selected, 4):
                break

    ordered = sorted(selected.values(), key=lambda row: abs(row["day"]), reverse=True)[:max_selected]
    for row in ordered:
        row["selection_rank"] = ordered.index(row) + 1
        row["selection_reasons"] = sorted(row.get("selection_reasons", []))
    return {
        "report_date_bjt": root.name,
        "selection_method": "S&P 500 daily cross-section plus Yahoo quote universe; fixed lists are scan-only",
        "universe_count": len(valid),
        "qualified_count": len(qualified_rows),
        "selected_count": len(ordered),
        "spy_day": spy_day,
        "coverage": {
            "quotes": sum(1 for symbol in quotes if _is_stock(symbol)),
            "sp500_breadth": sum(1 for row in valid if "S&P 500 breadth cross-section" in row.get("source", "")),
        },
        "selected": ordered,
    }


def write_daily_movers(root: Path) -> dict[str, Any]:
    payload = select_daily_movers(root)
    (root / "daily_movers.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload

