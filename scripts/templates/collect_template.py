from __future__ import annotations

import concurrent.futures
import json
import time
from pathlib import Path

import numpy as np
import pandas as pd
import requests


DAY = pd.Timestamp("2026-10-12")
ROOT = Path(r"D:\codex\outputs\us_market_daily_recaps\2026-10-13")
ROOT.mkdir(parents=True, exist_ok=True)
API = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
HEADERS = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}

SYMBOLS = """
^DJI ^GSPC ^IXIC ^RUT SPY QQQ RSP IWM DIA
XLK XLC XLY XLP XLF XLI XLE XLB XLV XLRE XLU
SOXX SMH IGV CIBR SKYY XBI IBB IHI XHE ARKG XME COPX GDX KRE XRT XHB ITA ARKK
MTUM SPHB USMV MEME BUZZ MAGS
NVDA AVGO AMD MU MRVL QCOM ADI TXN INTC AMAT LRCX KLAC
MSFT ORCL CRM NOW ADBE SNOW DDOG MDB WDAY CRWD PANW ZS
AAPL AMZN GOOGL GOOG META TSLA
ANET CRDO ALAB HPE DELL SMCI VRT ETN PWR CEG NRG VST APLD IREN DLR EQIX
COHR LITE AAOI CIEN GLW NOK SNDK WDC STX ARM TSM
VZ T TMUS CCI AMT SBAC SHOP SNAP CMCSA MDT FICO FIGS IONQ LCID
JPM WFC C GS BAC C XOM CVX CVX JNJ PEP WMT CAT DAL RCL CCL
COIN MSTR HOOD BTC-USD
^VIX ^VVIX ^SKEW ^TNX DX-Y.NYB CL=F BZ=F GC=F HG=F
""".split()


def fetch_chart(symbol: str, start: str = "2025-01-01", end: str = "2026-10-14", interval: str = "1d") -> pd.DataFrame:
    start_ts = int(pd.Timestamp(start, tz="UTC").timestamp())
    end_ts = int(pd.Timestamp(end, tz="UTC").timestamp())
    params = {
        "period1": start_ts,
        "period2": end_ts,
        "interval": interval,
        "events": "history",
        "includePrePost": "false",
        "includeAdjustedClose": "true",
    }
    last_error = None
    for attempt in range(4):
        try:
            response = requests.get(API.format(symbol=symbol), params=params, headers=HEADERS, timeout=30)
            response.raise_for_status()
            payload = response.json()
            result = (payload.get("chart") or {}).get("result") or []
            if not result:
                raise RuntimeError((payload.get("chart") or {}).get("error"))
            result = result[0]
            timestamps = result.get("timestamp") or []
            quote = (result.get("indicators") or {}).get("quote", [{}])[0]
            frame = pd.DataFrame({k: quote.get(k, []) for k in ["open", "high", "low", "close", "volume"]}, index=pd.to_datetime(timestamps, unit="s", utc=True))
            tz = (result.get("meta") or {}).get("exchangeTimezoneName", "America/New_York")
            frame.index = frame.index.tz_convert(tz).tz_localize(None).normalize()
            frame = frame[~frame.index.duplicated(keep="last")].sort_index()
            return frame.dropna(subset=["close"])
        except Exception as exc:  # Yahoo may transiently return 429/empty results.
            last_error = exc
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"{symbol}: {last_error}")


def save_symbol(symbol: str) -> dict:
    try:
        frame = fetch_chart(symbol)
        out = frame.rename(columns={"close": "Close", "open": "Open", "high": "High", "low": "Low", "volume": "Volume"})
        out.index.name = "Date"
        out.to_csv(ROOT / (symbol.replace("^", "idx_").replace("=", "_") + "_daily.csv"))
        if DAY not in out.index:
            raise RuntimeError(f"target date missing; last={out.index[-1]}")
        close = pd.to_numeric(out["Close"], errors="coerce").dropna()
        volume = pd.to_numeric(out["Volume"], errors="coerce").fillna(0)
        pos = close.index.get_loc(DAY)
        cur = float(close.loc[DAY])
        prev = float(close.iloc[pos - 1])
        base5 = float(close.iloc[pos - 5]) if pos >= 5 else float("nan")
        prior = close.iloc[:pos]
        month_base = float(prior.iloc[-1]) if DAY.month == 1 else float(prior.loc[prior.index.month != DAY.month].iloc[-1])
        year_base = float(prior.loc[prior.index.year < DAY.year].iloc[-1])
        prior_vol = volume.iloc[:pos].tail(30).mean()
        row = {
            "symbol": symbol,
            "close": cur,
            "day": (cur / prev - 1) * 100,
            "5d": (cur / base5 - 1) * 100,
            "WTD": (cur / prev - 1) * 100,
            "MTD": (cur / month_base - 1) * 100,
            "YTD": (cur / year_base - 1) * 100,
            "volume": float(volume.loc[DAY]),
            "volume_ratio": float(volume.loc[DAY] / prior_vol) if prior_vol else None,
            "ma20": float(close.iloc[max(0, pos - 19):pos + 1].mean()),
            "ma50": float(close.iloc[max(0, pos - 49):pos + 1].mean()),
            "ma200": float(close.iloc[max(0, pos - 199):pos + 1].mean()),
            "prev_close": prev,
            "rv20": float(close.iloc[:pos + 1].pct_change().tail(20).std() * np.sqrt(252) * 100),
            "basis": "Yahoo Chart API daily OHLCV",
        }
        return row
    except Exception as exc:
        return {"symbol": symbol, "error": str(exc)}


def collect_intraday() -> list[dict]:
    rows = []
    for symbol in ["SPY", "QQQ", "RSP", "IWM", "SOXX", "IGV", "XLE", "XLC", "XLK"]:
        try:
            frame = fetch_chart(symbol, "2026-10-12", "2026-10-13", "5m")
            frame = frame.between_time("09:30", "16:00")
            frame.rename(columns={"close": "Close", "open": "Open", "high": "High", "low": "Low", "volume": "Volume"}, inplace=True)
            frame.to_csv(ROOT / f"{symbol}_intraday.csv")
            late = frame.between_time("15:40", "16:00")
            rows.append({
                "symbol": symbol,
                "open_return": float((frame.Close.iloc[-1] / frame.Open.iloc[0] - 1) * 100),
                "late_return": float((late.Close.iloc[-1] / late.Open.iloc[0] - 1) * 100),
                "volume_share": float(late.Volume.sum() / frame.Volume.sum() * 100) if frame.Volume.sum() else None,
                "bars": int(len(frame)),
            })
        except Exception as exc:
            rows.append({"symbol": symbol, "error": str(exc)})
    (ROOT / "intraday.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")
    return rows


def collect_breadth() -> None:
    source = Path(r"D:\codex\outputs\us_market_daily_recaps\2026-10-10\sp500_members.csv")
    if not source.exists():
        return
    members = pd.read_csv(source)
    symbols = [str(x).replace(".", "-") for x in members["Symbol"].dropna()]
    def one(symbol: str) -> dict:
        try:
            frame = fetch_chart(symbol, "2025-09-01", "2026-10-13")
            close = frame["close"].dropna()
            high = frame["high"].dropna()
            low = frame["low"].dropna()
            pos = close.index.get_loc(DAY)
            before = close.iloc[:pos]
            return {"symbol": symbol, "return": float((close.iloc[pos] / close.iloc[pos - 1] - 1) * 100), "high252": bool(high.iloc[pos] > high.iloc[max(0, pos - 251):pos].max()), "low252": bool(low.iloc[pos] < low.iloc[max(0, pos - 251):pos].min()), "observations": int(len(before))}
        except Exception as exc:
            return {"symbol": symbol, "error": str(exc)}
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as pool:
        rows = list(pool.map(one, symbols))
    pd.DataFrame(rows).to_csv(ROOT / "sp500_breadth_detail.csv", index=False)
    valid = [x for x in rows if "return" in x]
    adv = sum(x["return"] > 0 for x in valid)
    dec = sum(x["return"] < 0 for x in valid)
    payload = {
        "n": len(valid),
        "universe": len(rows),
        "advancers": adv,
        "decliners": dec,
        "unchanged": len(valid) - adv - dec,
        "ad_ratio": adv / dec if dec else None,
        "up_pct": adv / len(valid) * 100 if valid else None,
        "highs_252": sum(x["high252"] for x in valid if x["observations"] >= 250),
        "lows_252": sum(x["low252"] for x in valid if x["observations"] >= 250),
        "errors": len(rows) - len(valid),
    }
    (ROOT / "breadth.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")


def main() -> None:
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        rows = list(pool.map(save_symbol, SYMBOLS))
    (ROOT / "quotes.json").write_text(json.dumps({x["symbol"]: x for x in rows}, indent=2), encoding="utf-8")
    pd.DataFrame(rows).to_csv(ROOT / "matrix.csv", index=False)
    collect_intraday()
    collect_breadth()
    print(json.dumps({"ok": sum("error" not in x for x in rows), "errors": [x for x in rows if "error" in x]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
