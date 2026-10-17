"""Collect social and retail heat snapshots for the US market daily recap.

The script is intentionally conservative:

- It saves raw JSON snapshots under D:\\codex.
- It does not require credentials for all sources.
- It labels unavailable sources instead of fabricating heat.
- It only uses official/low-risk paths by default.

Environment variables:

- X_BEARER_TOKEN: X API bearer token for recent counts.
- STOCKTWITS_USER / STOCKTWITS_PASS: optional Firestream sentiment credentials.
- REDDIT_CLIENT_ID / REDDIT_CLIENT_SECRET / REDDIT_USER_AGENT: optional OAuth path.

Usage:

python collect_social_heat.py --date 2026-07-30 --symbols MEME BUZZ ARKK NVDA MU META MSFT --out D:\\codex\\outputs\\us_market_daily_recaps\\social_heat\\2026-07-30
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


DEFAULT_SUBREDDITS = ["wallstreetbets", "stocks", "investing", "options", "SecurityAnalysis"]


def now_utc() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def request_json(url: str, headers: dict[str, str] | None = None, timeout: int = 20) -> tuple[dict[str, Any] | list[Any] | None, str | None]:
    req = urllib.request.Request(url, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = resp.read().decode("utf-8", errors="replace")
        return json.loads(data), None
    except urllib.error.HTTPError as exc:
        return None, f"HTTP {exc.code}: {exc.reason}"
    except Exception as exc:  # noqa: BLE001 - snapshot scripts should report, not crash.
        return None, repr(exc)


def stocktwits_public_trending() -> dict[str, Any]:
    url = "https://api.stocktwits.com/api/2/trending/symbols/equities.json"
    data, err = request_json(url, {"User-Agent": "codex-us-market-daily-recap/1.0"})
    if err:
        fallback = "https://stocktwits.com/sentiment"
        page, page_err = request_text(fallback)
        if page_err:
            return unavailable("stocktwits", f"public API failed: {err}; sentiment page failed: {page_err}")
        symbols = sorted(set(re.findall(r"\b[A-Z]{1,5}(?:\.\w+)?(?=[+-]?\d+\.\d+%)", page)))
        return {
            "source": "stocktwits",
            "captured_at": now_utc(),
            "method": "public_sentiment_page_parse",
            "evidence_url": fallback,
            "items": [{"symbol": s, "rank": i + 1} for i, s in enumerate(symbols[:30])],
            "limitations": "Parsed public page text; no message counts or sentiment detail.",
        }
    symbols = data.get("symbols", []) if isinstance(data, dict) else []
    return {
        "source": "stocktwits",
        "captured_at": now_utc(),
        "method": "public_trending_symbols_endpoint",
        "evidence_url": url,
        "items": [
            {
                "symbol": item.get("symbol"),
                "title": item.get("title"),
                "rank": idx + 1,
                "watchlist_count": item.get("watchlist_count"),
                "trending_score": item.get("trending_score"),
            }
            for idx, item in enumerate(symbols)
        ],
        "limitations": "Public endpoint/page can change; use as retail attention only.",
    }


def request_text(url: str, headers: dict[str, str] | None = None, timeout: int = 20) -> tuple[str | None, str | None]:
    req = urllib.request.Request(url, headers=headers or {"User-Agent": "codex-us-market-daily-recap/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8", errors="replace"), None
    except urllib.error.HTTPError as exc:
        return None, f"HTTP {exc.code}: {exc.reason}"
    except Exception as exc:  # noqa: BLE001
        return None, repr(exc)


def reddit_public(symbols: list[str], subreddits: list[str]) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    ok_count = 0
    headers = {"User-Agent": os.getenv("REDDIT_USER_AGENT", "codex-us-market-daily-recap/1.0")}
    for symbol in symbols:
        query = urllib.parse.quote(f"${symbol} OR {symbol}")
        for sr in subreddits:
            url = f"https://www.reddit.com/r/{sr}/search.json?q={query}&restrict_sr=1&sort=new&t=day&limit=25&raw_json=1"
            data, err = request_json(url, headers)
            if err:
                rows.append({"symbol": symbol, "subreddit": sr, "error": err})
                continue
            children = (((data or {}).get("data") or {}).get("children") or []) if isinstance(data, dict) else []
            ok_count += 1
            posts = []
            for child in children:
                p = child.get("data", {})
                posts.append(
                    {
                        "title": p.get("title"),
                        "created_utc": p.get("created_utc"),
                        "score": p.get("score"),
                        "num_comments": p.get("num_comments"),
                        "permalink": "https://www.reddit.com" + p.get("permalink", ""),
                    }
                )
            rows.append(
                {
                    "symbol": symbol,
                    "subreddit": sr,
                    "mentions_24h": len(posts),
                    "score_sum": sum((p.get("score") or 0) for p in posts),
                    "comment_sum": sum((p.get("num_comments") or 0) for p in posts),
                    "top_posts": posts[:5],
                    "evidence_url": url,
                }
            )
            time.sleep(0.8)
    block = {
        "source": "reddit",
        "captured_at": now_utc(),
        "method": "public_subreddit_search_json",
        "items": rows,
        "limitations": "Anonymous public JSON may be rate-limited or blocked; OAuth/PRAW is more stable.",
    }
    if ok_count == 0:
        block["status"] = "unavailable"
        block["reason"] = "all public Reddit subreddit search requests failed; configure Reddit OAuth/PRAW or provide exported Reddit data"
    return block


def x_recent_counts(symbols: list[str]) -> dict[str, Any]:
    token = os.getenv("X_BEARER_TOKEN")
    if not token:
        return unavailable("x", "missing X_BEARER_TOKEN; recent counts/search require approved X developer access")
    rows = []
    headers = {"Authorization": f"Bearer {token}", "User-Agent": "codex-us-market-daily-recap/1.0"}
    for symbol in symbols:
        q = urllib.parse.quote(f"({symbol} OR ${symbol}) lang:en -is:retweet")
        url = f"https://api.x.com/2/tweets/counts/recent?query={q}&granularity=hour"
        data, err = request_json(url, headers)
        if err:
            rows.append({"symbol": symbol, "error": err})
        else:
            meta = (data or {}).get("meta", {}) if isinstance(data, dict) else {}
            rows.append({"symbol": symbol, "tweet_count_7d": meta.get("total_tweet_count"), "evidence_url": url})
        time.sleep(0.5)
    return {
        "source": "x",
        "captured_at": now_utc(),
        "method": "recent_counts",
        "items": rows,
        "limitations": "Counts are public-post volume, not verified sentiment; rumor content needs manual cross-check.",
    }


def unavailable(source: str, reason: str) -> dict[str, Any]:
    return {"source": source, "captured_at": now_utc(), "status": "unavailable", "reason": reason, "items": []}


def summarize(payload: dict[str, Any]) -> dict[str, Any]:
    summary: dict[str, Any] = {"captured_at": now_utc(), "sources": {}, "symbols": {}}
    for source, block in payload.items():
        summary["sources"][source] = block.get("status", "ok")
        for item in block.get("items", []):
            if item.get("error"):
                continue
            symbol = item.get("symbol")
            if not symbol:
                continue
            bucket = summary["symbols"].setdefault(symbol, {"sources": [], "signals": []})
            bucket["sources"].append(source)
            signal = {k: v for k, v in item.items() if k not in {"top_posts"}}
            bucket["signals"].append(signal)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", required=True, help="Snapshot date, e.g. 2026-07-30")
    parser.add_argument("--symbols", nargs="+", required=True)
    parser.add_argument("--subreddits", nargs="*", default=DEFAULT_SUBREDDITS)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    out_dir = Path(args.out)
    if not str(out_dir.resolve()).lower().startswith(str(Path(r"D:\codex").resolve()).lower()):
        raise SystemExit("Output directory must be under D:\\codex")
    out_dir.mkdir(parents=True, exist_ok=True)

    payload = {
        "stocktwits": stocktwits_public_trending(),
        "reddit": reddit_public(args.symbols, args.subreddits),
        "x": x_recent_counts(args.symbols),
        "futu": unavailable("futu", "requires local Futu OpenD + futu package; use for quote/news/hot lists, not community discussion by default"),
        "tiger": unavailable("tiger", "no stable official community heat API configured; use official export/hot-list only"),
        "xueqiu": unavailable("xueqiu", "unofficial/cookie-dependent; use user-provided export or explicit logged-in browser workflow"),
    }

    raw_path = out_dir / f"social_heat_raw_{args.date}.json"
    summary_path = out_dir / f"social_heat_summary_{args.date}.json"
    raw_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    summary_path.write_text(json.dumps(summarize(payload), ensure_ascii=False, indent=2), encoding="utf-8")
    print(raw_path)
    print(summary_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
