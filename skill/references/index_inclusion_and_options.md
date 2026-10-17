# Index Inclusion And Option Risk

## Ledger Shape

Store persistent records in `D:\codex\outputs\us_market_daily_recaps\index_inclusion_watchlist.json`:

```json
{
  "version": 1,
  "updated_at": "2026-09-19T00:00:00Z",
  "entries": [
    {
      "ticker": "EXAMPLE",
      "company": "Example Corp",
      "index_family": "S&P DJI",
      "index_name": "S&P 500",
      "announcement_date": "2026-09-18",
      "first_public_at": "2026-09-18T17:00:00-04:00",
      "effective_date": "2026-09-22",
      "status": "ANNOUNCED_PENDING",
      "source": "Official index notice",
      "source_url": "https://example.com/notice",
      "expected_passive_demand": "positive",
      "last_reminder_date": null,
      "notes": "Final notice; effective after the close unless the source says otherwise."
    }
  ]
}
```

Allowed statuses: `ANNOUNCED_PENDING`, `EFFECTIVE_TODAY`, `EFFECTIVE_COMPLETE`, `CANCELLED`, `DELAYED`, `UNVERIFIED_RUMOR`.

The daily snapshot should include: `ticker`, `company`, `index_name`, `announcement_date`, `effective_date`, `sessions_remaining`, `status`, `expected_passive_demand`, `source_url`, and `option_alerts`.

## Preferred option-flow source

When access is available, check StockWe.com first for the active watchlist names:

- `https://stockwe.com/` — StockWe's "美股期权异动实时订单" and historical Call vs Put total-premium views.
- Capture `source`, `checked_at_et`, real-time/delayed status, contract/expiry/strike, call or put, contracts, premium/notional, volume, open interest, IV, Call vs Put total premium, the site's direction label, and sweep/block or bid/ask evidence when shown.
- A StockWe direction label is useful cross-confirmation, but it is not proof that a trade opened a new long position. Keep `opening/closing intent` as unknown unless the source provides explicit evidence.
- If the page is login-gated, subscription-gated, rate-limited, or inaccessible, record the URL/path, timestamp, and missing fields as `StockWe access unavailable`; do not convert the failure into "no unusual options activity".
- Use a public option chain or second flow source as a cross-check when available. If StockWe and the cross-check disagree, preserve both observations and label the interpretation unresolved.

## Free automated chain source

Use the Nasdaq option-chain page and its public web endpoint for the automated daily snapshot:

- Page: `https://www.nasdaq.com/market-activity/stocks/TICKER/option-chain`
- Endpoint used by the page: `https://api.nasdaq.com/api/quote/TICKER/option-chain?assetclass=stocks`
- The endpoint currently returns last, bid, ask, volume, and open interest by expiry and strike without an API key. It does not reliably provide execution side, sweep/block metadata, IV history, or a guaranteed real-time timestamp.
- Run `scripts/option_chain_collect.py --date YYYY-MM-DD` before `scripts/index_inclusion_watch.py`. The collector selects the nearest future expiry and a farther benchmark expiry, estimates call/put premium from displayed mid/last prices, computes volume/OI and strike concentration, and stores the full snapshot under `D:\codex\outputs\us_market_daily_recaps\YYYY-MM-DD\options_chain.json`.
- The collector must preserve `last_trade_label`, `checked_at_et`, `source_url`, and the source limitations. A non-empty Nasdaq response is not proof that the data matches the target cash-session close.
- Do not automate against Cboe delayed quote tables unless the license/terms explicitly permit it; the Cboe dashboard currently states that automated extraction is prohibited.

## Daily Reminder Rule

Count remaining US trading sessions from the report's target session to the effective date. A public notice after the cash close belongs to the next report's reminder. Keep `ANNOUNCED_PENDING` rows visible every day before effectiveness, including days when the stock did not move. On the effective session, mark `EFFECTIVE_TODAY`; after that session, close it once as `EFFECTIVE_COMPLETE`.

Use this wording pattern in Chinese:

`指数纳入提醒：TICKER（公司）将于 YYYY-MM-DD 纳入 INDEX；距离生效还有 N 个美股交易日。预期被动资金方向：正/负/不确定。来源：...`

Do not infer exact passive demand without index weight, float adjustment, rebalance volume, or a sourced estimate. Say “预期被动需求方向” rather than exact dollars when no estimate is available.

## Option Anomaly Evidence

For every active record, store a same-day snapshot when available:

```json
{
  "ticker": "EXAMPLE",
  "as_of": "2026-09-19T15:55:00-04:00",
  "expiry_near": "2026-09-25",
  "expiry_far": "2026-10-16",
  "call_volume": 12000,
  "put_volume": 3500,
  "call_oi": 18000,
  "put_oi": 21000,
  "iv_now": 62.4,
  "iv_prior": 48.1,
  "max_strike_volume_share": 0.27,
  "execution_side_confirmed": false,
  "source": "public option chain",
  "source_url": "https://example.com/options"
}
```

Flag `volume/OI >= 2`, call/put volume ratio `>= 3` or `<= 0.33`, IV change `>= 10` volatility points or `>= 25%` relative, or a single strike with `>= 20%` of name option volume. Classify the result as `call-heavy`, `put-heavy`, `IV-expansion`, `strike-concentration`, or `unclassified`. Do not call a trade “smart money buying” merely because it is large; require execution-side evidence, sweep/block metadata, a consistent multi-strike pattern, or confirmation from a second source.

When data is incomplete, report the missing field and source limitation. An absence of an alert is not evidence that no options activity occurred.
