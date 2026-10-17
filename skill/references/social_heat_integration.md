# Social And Retail Heat Integration

Use social/retail heat only as corroborating evidence, never as the sole reason for a market call.

## Recommended Source Priority

1. Stocktwits
   - Best use: retail equity attention, trending tickers, bullish/bearish community skew.
   - Current access reality: Stocktwits developer app registration page says new registrations are paused while APIs/docs/terms are under review. Public pages such as `/sentiment` expose top trending symbols. Firestream sentiment endpoints exist for credentialed users via basic auth.
   - Practical path:
     - First try public trending endpoint/page for top equities.
     - If the user has Stocktwits Firestream credentials, use `STOCKTWITS_USER` and `STOCKTWITS_PASS` to query sentiment detail for watchlist tickers.
   - Evidence rank: medium for retail attention; low for institutional capital.

2. Meme and social-sentiment basket proxies
   - Best use: transform scattered retail names into a monitorable price basket.
   - Direct meme proxy: Roundhill Meme Stock ETF `MEME`. Roundhill's current fund page describes it as an actively managed ETF targeting retail-driven, viral meme stocks and lists launch date 2025-10-08.
   - Historical caveat: the old Solactive Roundhill Meme Stock Index was terminated effective 2024-04-11, so do not use `.MEME`/`.MEMEP`/`.MEMEN` as current index data.
   - Broader social-sentiment proxy: VanEck Social Sentiment ETF `BUZZ`, which tracks the BUZZ NextGen AI US Sentiment Leaders Index and selects U.S. stocks with high positive investor sentiment from online sources.
   - Speculative-growth proxy: `ARKK` can be shown as a separate high-beta/spec-growth line, but it is not a meme index.
   - Report rule: in the performance matrix, include `MEME` when quote/performance data is available; include `BUZZ` when social-sentiment breadth matters; keep `ARKK` separate.

3. Reddit
   - Best use: WSB/high-beta/meme ticker attention, narrative keywords in titles/comments.
   - Current access reality: official Reddit API supports search/listing endpoints; hosted/server IPs may require OAuth. PRAW or OAuth is more stable than anonymous `.json` calls.
   - Practical path:
     - Scan `wallstreetbets`, `stocks`, `investing`, `options`, `SecurityAnalysis`, and targeted sector subreddits.
     - Count posts in the last 24h, sum score/comments, and extract top tickers.
     - Use `REDDIT_CLIENT_ID`, `REDDIT_CLIENT_SECRET`, `REDDIT_USER_AGENT` when available; otherwise try public JSON with conservative rate limiting.
   - Evidence rank: high for meme/retail heat; low for institutional flow.

4. X
   - Best use: breaking narrative velocity, real-time rumor diffusion, ticker/keyword post counts.
   - Current access reality: X API recent search and recent counts require an approved developer app and bearer token. Recent search covers last 7 days; counts endpoint is enough for heat scoring.
   - Practical path:
     - Use `X_BEARER_TOKEN`.
     - Query `(NVDA OR $NVDA) lang:en -is:retweet` for watchlist tickers and sector keywords.
     - Prefer counts over text ingestion for daily recap unless a specific rumor needs source inspection.
   - Evidence rank: medium-high for narrative velocity; rumor content must be cross-checked.

5. Futu / Moomoo
   - Best use: market movers, hot lists, quotes, options, news, short-term retail trading attention if exposed by OpenD.
   - Current access reality: Futu OpenAPI uses a local OpenD gateway; login and quote rights/quotas apply. Official docs cover quote, market snapshot, search, news/announcements/ratings and options analytics. It is not a clean public social-discussion API.
   - Practical path:
     - Use only if OpenD is running and the `futu` Python package is installed.
     - Treat Futu data as trading/quote/news heat, not community discussion, unless a supported community endpoint is explicitly available.
   - Evidence rank: high for China-speaking retail trading attention if sourced from official hot lists; otherwise medium.

6. Tiger Brokers
   - Best use: Chinese-speaking retail attention if a logged-in terminal/export/hot-list source is available.
   - Current access reality: public, stable community heat API is not clearly available from official sources.
   - Practical path:
     - Do not scrape private app content automatically without explicit user-approved logged-in workflow.
     - Prefer manual export/screenshot or official market/news APIs if available.
   - Evidence rank: medium if sourced from official hot list/export; otherwise do not use.

7. Xueqiu
   - Best use: Chinese investor attention and overseas-stock discussion.
   - Current access reality: commonly used endpoints are unofficial and cookie/session dependent; anti-scraping and terms risk are high.
   - Practical path:
     - Avoid blind scraping as default.
     - Accept user-provided exported page text, screenshots, or logged-in browser capture if the user explicitly requests it.
   - Evidence rank: medium for China-speaking narrative; must be labeled as discussion heat.

## Heat Score

Normalize each source into:

- `symbol`
- `source`
- `rank`
- `mentions_24h`
- `mentions_1h`
- `score_or_engagement`
- `sentiment_bullish`
- `sentiment_bearish`
- `top_keywords`
- `evidence_url`
- `captured_at`
- `limitations`

Suggested composite:

`heat_score = z(mentions_24h) * 0.40 + z(acceleration_1h_vs_24h) * 0.25 + z(engagement) * 0.20 + sentiment_extreme * 0.15`

For daily recaps, classify:

- `Confirmed heat`: appears in at least 2 sources and matches price/volume/news.
- `Retail-only heat`: appears in social but not price/volume.
- `News-only heat`: appears in news/price but not social.
- `Unavailable`: source not configured, blocked, or no reliable endpoint.

## Report Rule

Never write "Stocktwits/Reddit/X confirms" unless the raw snapshot is saved under:

`D:\codex\outputs\us_market_daily_recaps\social_heat\YYYY-MM-DD\`

If a source is unavailable, say exactly which credential or connector is missing.
