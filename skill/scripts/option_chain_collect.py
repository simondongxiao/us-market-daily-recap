"""Collect free public US equity option-chain snapshots for the active index watchlist.

Primary automated source: Nasdaq's public option-chain endpoint used by its web page.
It supplies delayed/last-available bid, ask, last, volume, and open interest, but not
execution-side, sweeps, blocks, or a contractual real-time guarantee. The collector
therefore labels source timing and leaves those fields unresolved.
"""
from __future__ import annotations

import argparse
import json
import math
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

NASDAQ_ROOT = "https://api.nasdaq.com/api/quote/{ticker}/option-chain"
NASDAQ_PAGE = "https://www.nasdaq.com/market-activity/stocks/{ticker_lower}/option-chain"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json, text/plain, */*",
    "Origin": "https://www.nasdaq.com",
    "Referer": "https://www.nasdaq.com/",
}


def fetch_json(url: str, attempts: int = 3) -> dict:
    last_error = None
    for attempt in range(attempts):
        req = urllib.request.Request(url, headers=HEADERS)
        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                return json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, ConnectionResetError) as exc:
            last_error = exc
            if attempt + 1 >= attempts:
                raise
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"option-chain request failed without a response: {last_error}")


def num(value):
    if value is None:
        return None
    text = str(value).strip().replace(",", "").replace("$", "")
    if text in {"", "--", "N/A", "n/a", "null"}:
        return None
    try:
        return float(text.rstrip("%"))
    except ValueError:
        return None


def integer(value) -> int:
    result = num(value)
    return int(result) if result is not None else 0


def parse_expiry(value: str):
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None


def query_url(ticker: str, start: str | None = None, end: str | None = None) -> str:
    params = {"assetclass": "stocks"}
    if start and end:
        params["fromdate"] = start
        params["todate"] = end
    return NASDAQ_ROOT.format(ticker=urllib.parse.quote(ticker.upper())) + "?" + urllib.parse.urlencode(params)


def get_chain(ticker: str, start: str | None = None, end: str | None = None) -> tuple[dict, str]:
    url = query_url(ticker, start, end)
    return fetch_json(url), url


def available_expiries(payload: dict, report_date) -> list:
    options = []
    for item in (payload.get("data") or {}).get("filterlist", {}).get("fromdate", {}).get("filter", []):
        value = item.get("value", "")
        if "|" not in value or value == "all":
            continue
        left, right = value.split("|", 1)
        for candidate in (left, right):
            parsed = parse_expiry(candidate)
            if parsed and parsed >= report_date:
                options.append(parsed)
    return sorted(set(options))


def as_expiry_rows(payload: dict) -> list[dict]:
    rows = (payload.get("data") or {}).get("table", {}).get("rows", [])
    return [row for row in rows if row.get("strike") not in (None, "", "--")]


def mid_price(row: dict, prefix: str):
    last = num(row.get(f"{prefix}_Last"))
    bid = num(row.get(f"{prefix}_Bid"))
    ask = num(row.get(f"{prefix}_Ask"))
    if bid is not None and ask is not None and ask >= bid:
        return (bid + ask) / 2.0
    return last


def normal_cdf(value: float) -> float:
    return 0.5 * (1.0 + math.erf(value / math.sqrt(2.0)))


def bs_price(spot: float, strike: float, years: float, rate: float, vol: float, call: bool) -> float:
    if min(spot, strike, years, vol) <= 0:
        return 0.0
    root = vol * math.sqrt(years)
    d1 = (math.log(spot / strike) + (rate + 0.5 * vol * vol) * years) / root
    d2 = d1 - root
    discount = math.exp(-rate * years)
    if call:
        return spot * normal_cdf(d1) - strike * discount * normal_cdf(d2)
    return strike * discount * normal_cdf(-d2) - spot * normal_cdf(-d1)


def implied_vol(spot: float | None, strike: float, years: float, premium: float, call: bool) -> float | None:
    """Approximate IV from the displayed mid/last; absent dividends and American exercise."""
    if not spot or not premium or premium <= 0 or years <= 0:
        return None
    low, high = 0.0001, 5.0
    if bs_price(spot, strike, years, 0.05, high, call) < premium:
        return None
    for _ in range(60):
        mid = (low + high) / 2.0
        if bs_price(spot, strike, years, 0.05, mid, call) < premium:
            low = mid
        else:
            high = mid
    return (low + high) / 2.0


def extract_spot(ticker: str) -> float | None:
    url = f"https://api.nasdaq.com/api/quote/{urllib.parse.quote(ticker.upper())}/info?assetclass=stocks"
    data = fetch_json(url).get("data") or {}
    return num((data.get("primaryData") or {}).get("lastSalePrice"))


def summarize_expiry(ticker: str, expiry: str, payload: dict, spot: float | None, checked_at: str) -> dict:
    rows = as_expiry_rows(payload)
    call_volume = sum(integer(row.get("c_Volume")) for row in rows)
    put_volume = sum(integer(row.get("p_Volume")) for row in rows)
    call_oi = sum(integer(row.get("c_Openinterest")) for row in rows)
    put_oi = sum(integer(row.get("p_Openinterest")) for row in rows)
    strike_volume = {}
    call_premium = 0.0
    put_premium = 0.0
    iv_values = []
    for row in rows:
        strike = num(row.get("strike"))
        if strike is None:
            continue
        cv, pv = integer(row.get("c_Volume")), integer(row.get("p_Volume"))
        strike_volume[strike] = cv + pv
        years = max((parse_expiry(expiry) - datetime.now(ZoneInfo("America/New_York")).date()).days / 365.0, 1 / 365.0)
        for prefix, volume, is_call in (("c", cv, True), ("p", pv, False)):
            premium = mid_price(row, prefix)
            if premium is not None and volume:
                total = premium * volume * 100.0
                if is_call:
                    call_premium += total
                else:
                    put_premium += total
                iv = implied_vol(spot, strike, years, premium, is_call)
                if iv is not None and iv <= 5:
                    iv_values.append(iv * 100.0)
    total_volume = call_volume + put_volume
    max_strike_volume = max(strike_volume.values(), default=0)
    cp_ratio = call_volume / put_volume if put_volume else None
    alerts = []
    if call_oi and call_volume / call_oi >= 2:
        alerts.append("call-volume/OI>=2")
    if put_oi and put_volume / put_oi >= 2:
        alerts.append("put-volume/OI>=2")
    if cp_ratio is not None and cp_ratio >= 3:
        alerts.append("call-heavy")
    elif cp_ratio is not None and cp_ratio <= 0.33:
        alerts.append("put-heavy")
    if total_volume and max_strike_volume / total_volume >= 0.20:
        alerts.append("strike-concentration")
    return {
        "ticker": ticker,
        "as_of": checked_at,
        "expiry": expiry,
        "source": "Nasdaq public option-chain endpoint",
        "source_url": NASDAQ_PAGE.format(ticker_lower=ticker.lower()),
        "data_status": "available" if rows else "unavailable",
        "underlying_last_available": spot,
        "call_volume": call_volume,
        "put_volume": put_volume,
        "call_oi": call_oi,
        "put_oi": put_oi,
        "call_put_volume_ratio": cp_ratio,
        "call_premium_estimate": round(call_premium, 2),
        "put_premium_estimate": round(put_premium, 2),
        "max_strike_volume_share": round(max_strike_volume / total_volume, 4) if total_volume else None,
        "iv_mean_approx": round(sum(iv_values) / len(iv_values), 2) if iv_values else None,
        "execution_side_confirmed": False,
        "direction_label": None,
        "alerts": sorted(set(alerts)) or ["no_threshold_alert"],
        "limitations": ["Nasdaq chain does not provide execution side, sweep/block labels, or an IV history in this endpoint."]
    }


def active_entries(ledger: dict, tickers: list[str] | None):
    entries = ledger.get("entries", []) if isinstance(ledger, dict) else ledger
    if tickers:
        by_ticker = {e.get("ticker", "").upper(): e for e in entries}
        return [by_ticker.get(x.upper(), {"ticker": x.upper()}) for x in tickers]
    return [e for e in entries if e.get("status") in {"ANNOUNCED_PENDING", "EFFECTIVE_TODAY"}]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", required=True, help="Report date in YYYY-MM-DD")
    parser.add_argument("--ledger", default="D:/codex/outputs/us_market_daily_recaps/index_inclusion_watchlist.json")
    parser.add_argument("--out", default=None)
    parser.add_argument("--tickers", nargs="*", default=None)
    parser.add_argument("--no-update-ledger", action="store_true")
    args = parser.parse_args()
    ledger_path = Path(args.ledger)
    ledger = json.loads(ledger_path.read_text(encoding="utf-8")) if ledger_path.exists() else {"version": 1, "entries": []}
    target_date = datetime.strptime(args.date, "%Y-%m-%d").date()
    checked_at = datetime.now(ZoneInfo("America/New_York")).isoformat(timespec="seconds")
    results, errors = [], []
    for entry in active_entries(ledger, args.tickers):
        ticker = entry.get("ticker", "").upper()
        if not ticker:
            continue
        try:
            overview, _ = get_chain(ticker)
            expiries = available_expiries(overview, target_date)
            if not expiries:
                raise RuntimeError("no future expiry returned")
            near = expiries[0]
            far = next((x for x in expiries if (x - near).days >= 21), expiries[min(2, len(expiries) - 1)])
            spot = extract_spot(ticker)
            snapshots = []
            for expiry in sorted({near, far}):
                payload, _ = get_chain(ticker, expiry.isoformat(), expiry.isoformat())
                snapshots.append(summarize_expiry(ticker, expiry.isoformat(), payload, spot, checked_at))
            primary = snapshots[0]
            combined_alerts = sorted({alert for snap in snapshots for alert in snap["alerts"] if alert != "no_threshold_alert"})
            result = {
                "ticker": ticker,
                "company": entry.get("company"),
                "source": "Nasdaq public option-chain endpoint",
                "source_url": NASDAQ_PAGE.format(ticker_lower=ticker.lower()),
                "checked_at_et": checked_at,
                "data_status": "available",
                "last_trade_label": (overview.get("data") or {}).get("lastTrade"),
                "expiry_near": primary["expiry"],
                "expiry_far": snapshots[-1]["expiry"],
                "call_volume": primary["call_volume"],
                "put_volume": primary["put_volume"],
                "call_oi": primary["call_oi"],
                "put_oi": primary["put_oi"],
                "call_put_volume_ratio": primary["call_put_volume_ratio"],
                "call_premium_estimate": primary["call_premium_estimate"],
                "put_premium_estimate": primary["put_premium_estimate"],
                "iv_now": primary["iv_mean_approx"],
                "iv_prior": None,
                "max_strike_volume_share": primary["max_strike_volume_share"],
                "execution_side_confirmed": False,
                "direction_label": None,
                "option_alerts": combined_alerts or ["no_threshold_alert"],
                "expiries": snapshots,
                "limitations": primary["limitations"] + ["Last available underlying/option timestamps are retained; verify freshness before treating as target-session data."]
            }
            results.append(result)
            for e in ledger.get("entries", []):
                if e.get("ticker", "").upper() == ticker:
                    e["options_snapshot"] = result
                    e["last_options_check_date"] = args.date
        except Exception as exc:  # keep the daily run alive for the other names
            errors.append({"ticker": ticker, "error": str(exc), "source": NASDAQ_PAGE.format(ticker_lower=ticker.lower())})
            results.append({"ticker": ticker, "company": entry.get("company"), "source": "Nasdaq public option-chain endpoint", "data_status": "unavailable", "option_alerts": ["source unavailable"], "error": str(exc)})
    output = {"report_date": args.date, "checked_at_et": checked_at, "source_priority": ["Nasdaq public option-chain endpoint", "StockWe.com", "Yahoo Finance options"], "results": results, "errors": errors}
    destination = Path(args.out) if args.out else Path("D:/codex/outputs/us_market_daily_recaps") / args.date / "options_chain.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    if not args.no_update_ledger and ledger_path.exists():
        ledger["updated_at"] = checked_at
        ledger_path.write_text(json.dumps(ledger, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(output, ensure_ascii=False, indent=2))
    if errors and not results:
        sys.exit(1)


if __name__ == "__main__":
    main()
