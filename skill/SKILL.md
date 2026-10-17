---
name: us-market-daily-recap
description: Generate Chinese buy-side US market daily recaps after the US cash close, focusing on real capital concentration, sector rotation, stock-mover causes, new rumors and narratives, cross-asset context, factor/positioning stress, derivatives flow, meme/momentum stocks, and A/H-share mapping. Use when the user asks for 美股每日行情复盘, 收盘后复盘, 隔夜美股复盘, US market daily recap, sector rotation, 涨跌原因, 资金流向, 资金聚焦, or 今日美股更新.
---

# US Market Daily Recap

Use this skill in `D:\codex` only.

Final deliverables must be Word documents, not Markdown:

`D:\codex\outputs\us_market_daily_recaps\*.docx`

Markdown may be used only as an internal draft or rendering input. If an internal `.md` draft is saved, the final answer should still point to the `.docx` as the main deliverable.

Default date mapping: if the user says "today" in Beijing time after the US close, recap the latest completed US trading session and state both Beijing date and US Eastern trade date.

## Reference Style

For style and analytical habits, read the concise reference only when needed:

`references/style_learnings_from_20260729_pdfs.md`

For social/retail heat integration, read:

`references/social_heat_integration.md`

Key lessons from the user's two reference PDFs:

- Start with a precise trading tape snapshot, not a generic summary.
- Look for "wrong-way" price action: crowded long legs down while short/funding legs squeeze higher.
- Treat market structure as a first-class signal: breadth, new highs/lows, RSP versus SPY, Mag 7 versus the other 493 stocks, high beta versus low vol, momentum, and high-short-interest baskets.
- Explain factor pain beneath index calm: momentum, AI baskets, TMT momentum, SPX ex AI, realized vol, stock correlation, hedge-fund gross leverage, de-grossing, short covering, CTA/systematic thresholds, and prime-book flows when available.
- Separate real sponsorship from short-covering or gross-downs.
- Put useful charts into the Word document beside the relevant section, with captions and source lines.
- Visualize whenever the data has a natural shape: rankings, sector rotation, breadth, factor dispersion, AI-chain tiers, derivatives/flow proxies, intraday paths, and cross-market maps should be rendered as PNG charts, not only described in prose.

## Core Principle

The goal is not to list index moves. The goal is to explain where real money focused and why.

Explain the day's incremental change in expectations and trading conditions, not a recurring story imposed on every session. A policy event such as FCC action is one candidate catalyst, never the default cause of optical-stock moves.

When a stock or sub-sector moves, compare company news, sell-side research, management communication, industry read-throughs, policy, and market/factor structure without a fixed causal hierarchy. A broker report, conference Q&A, order commentary, or shift in risk appetite can be the main cause without a formal company announcement or new policy. Broad co-movement does not require a shared new headline. "Risk-off", "profit taking", or "crowding" need observable supporting evidence, just as a news-based explanation does.

## Priority Gate: Event Clock And Event Lifecycle

This gate has priority over company watchlists, sector checklists, AI tiers, optical lists, examples, and policy examples. Fixed lists are price/coverage universes, not daily news obligations. The operating rule is `MANDATORY PRICE SCAN != MANDATORY NARRATIVE`.

Before drafting the report, record `report_run_time_local`, `report_run_time_et`, `target_trade_date_et`, `target_session_open_et`, `target_session_close_et`, and `previous_session_close_et`. Resolve EDT/EST, weekends, US holidays, Beijing/ET date rollover, and whether the run is pre-market, intraday, or post-close. The report must state the completed US cash session it actually covers.

Every candidate event enters an event ledger with: `event_id`, `event_fingerprint`, `ticker_or_sector`, `event_type`, `event_date`, `first_public_at`, `last_material_update_at`, `source`, `source_url`, `target_trade_date`, `status`, `incremental_information`, `can_explain_cash_session`, and `notes`.

### Index Inclusion Watch And Option Risk

Maintain a separate persistent ledger at `D:\codex\outputs\us_market_daily_recaps\index_inclusion_watchlist.json` for publicly announced future additions to major US equity indexes. Check official S&P DJI, Nasdaq, Russell/FTSE, MSCI, and exchange notices before drafting each report; an index rumor or calendar estimate is not an announced inclusion. Each record must contain `ticker`, `company`, `index_family`, `index_name`, `announcement_date`, `first_public_at`, `effective_date`, `status`, `source`, `source_url`, `expected_passive_demand`, `last_reminder_date`, and `notes`.

- For every record with `status=ANNOUNCED_PENDING` and `report_date < effective_date`, add a daily `指数纳入提醒` row: ticker/company, index, announcement date, effective date, remaining US sessions, expected passive-flow direction, and the source. This reminder is mandatory on every daily recap until the effective session is complete.
- On the effective session, label `EFFECTIVE_TODAY` and keep the reminder in the report. On the first report after the effective date, write one `已完成纳入` close-out line and then set the record to `EFFECTIVE_COMPLETE`; do not keep repeating it. If an addition is cancelled, delayed, or removed from the notice, update the status and explain the changed effective date.
- Never confuse a scheduled rebalance date with an announcement date. Preserve both timestamps, distinguish preliminary/reconstitution notices from final changes, and use `POST_BELL_NEXT_SESSION` when the notice arrived after the completed cash session.
- Every active watchlist name must also enter the option-risk scan. Use `scripts/option_chain_collect.py --date YYYY-MM-DD` to automatically collect the nearest and farther Nasdaq public option chains, then check StockWe.com as the first flow source when accessible, especially its "美股期权异动实时订单", historical Call vs Put total-premium view, and per-ticker option order details. Use Yahoo Finance only as a fallback because it may rate-limit automated access; do not automate Cboe delayed quote tables where the site prohibits extraction. Record `source`, `checked_at_et`, whether the data is real-time or delayed, expiry, strike, call/put, contracts, premium/notional, volume, open interest, IV, call/put total premium, StockWe direction label, execution-side evidence, and sweep/block markers. Check the nearest liquid expiry and a farther benchmark expiry for option volume, open interest, implied volatility, IV change/percentile, call/put volume and OI, strike concentration, bid/ask execution side, block/sweep markers, and unusual trades. Flag only evidence-backed anomalies: volume/OI >= 2x, call/put volume ratio >= 3x or <= 0.33x, IV change >= 10 volatility points or >= 25% relative, or one strike contributing >= 20% of name option volume. A StockWe direction label is a sourced signal, not proof of opening or buying intent; a large trade without execution-side or multi-source confirmation is `unclassified`, not bullish or bearish.
- The report must include an `指数纳入与期权异常` subsection even when the result is “无已确认待纳入标的” or “未发现可验证期权异常”; do not silently omit the check. Run the automated Nasdaq collector first, then check StockWe.com for flow/direction labels and use a second public chain source when available. Use `source unavailable` only after recording the URL/path, checked timestamp, and the failed source or missing field. If StockWe is login-gated or subscription-gated, write `StockWe access unavailable` and do not infer that no abnormal flow occurred.
- Do not print option alerts as bare labels. In the Word report, every `put-heavy`, `call-heavy`, `volume/OI`, or `strike-concentration` flag must include the triggering value/expiry when available, a plain-language interpretation, and a limitation. In particular, strike concentration means one strike accounts for an unusually large share of volume for an expiry; it may reflect hedging, directional positioning, spreads, or dealer/Gamma concentration, and without execution-side/open-close evidence it must not be written as confirmed Put buying, Call buying, bullishness, or bearishness. If near and far expiries show opposite Call/Put signals, describe the expiry structure as split rather than aggregating it into one direction.
- Read [references/index_inclusion_and_options.md](references/index_inclusion_and_options.md) for the ledger schema, lifecycle, reminder wording, and option-anomaly evidence rules. Use `scripts/index_inclusion_watch.py` to validate the ledger and generate the daily reminder snapshot before authoring the Word report.

Use only these lifecycle statuses:

- `SESSION_NEW`: `previous_session_close_et < first_public_at <= target_session_close_et`; may explain the target cash session when timing and exposure fit.
- `POST_BELL_NEXT_SESSION`: `target_session_close_et < first_public_at <= report_run_time`; belongs only in “盘后 / 下一交易日观察” and cannot explain the finished cash session.
- `CONTINUING_REPRICING`: an older event has a new, verifiable analyst note, target/estimate revision, management comment, conference Q&A, order/pricing update, regulatory status change, industry read-through, peer confirmation, or clearly documented continuing price/volume repricing. State both the old event and today's incremental information.
- `HISTORICAL_BACKGROUND`: older information needed for context, at most one short background reference; never place it under “今日关键更新”, “今日新增催化”, or “今日新闻”.
- `EXPIRED_IRRELEVANT`: search-visible but with no current incremental information, price confirmation, or material read-through; remove it from the body.

Use stable fingerprints such as `AVGO|earnings|FY26Q3|2026-09-02` and `ORCL|earnings|FY27Q1|2026-09-10`. A repeated search result, media rewrite, aggregator push, webpage update, or retrieval timestamp does not make an old event new. Prefer the event's first-public timestamp over the search timestamp. A fixed company list may be scanned for price, relative strength, breadth, leadership, factor, and rotation, but a catalyst enters the narrative only after this gate. If there is no same-day company/industry information, abnormal relative move, or meaningful volume/breadth/factor signal, omit the name from the narrative.

For FCC, Commerce, telecom-security, bans, exemptions, and other policy items, verify issuer/submitter, original document, docket/document number, procedural status, scope, conditions, effective date, and first-public time. FCC enters the daily narrative only if there is a target-session filing or status change, new rule/order/notice/comment/ex parte, a same-day company/broker reference, documented renewed market trading with a credible source, or a changed scope/effective date/exemption/enforcement action. Otherwise omit it from the optical narrative. An FCC-hosted third-party filing is not FCC endorsement, and a router/robot exemption is not an optical-transceiver exemption.

The causal workflow is: `OBSERVED TAPE -> SAME-DAY EVIDENCE -> EXPECTATION DELTA -> CROSS-CONFIRMATION -> POSITIONING TEST -> CAUSAL RANKING`. Do not search a pre-written narrative and fit evidence to it. Examples below are a hypothesis menu only, not causal priors.

### Evidence-Led Attribution

- Start from the actual tape: absolute and industry/market-relative returns, leaders versus laggards, breadth, volume, and intraday timing when available. Look for evidence that distinguishes company alpha, industry repricing, and broad beta/factor moves.
- For material movers, check relevant earnings/filings and investor-relations events alongside timely broker research and credible industry reporting. Research inputs include initiation, rating/target changes, earnings-model revisions, channel checks, and shifts in conviction even with an unchanged rating. Conference inputs include fireside chats, analyst days, investor meetings, presentations, and Q&A about orders, demand, pricing, margins, capacity, and customer qualifications. A conference schedule alone proves neither positive guidance nor a catalyst.
- Identify the expectation delta: what changed versus prior management statements, documented consensus, or a clearly sourced market expectation? An upbeat report can disappoint a higher bar; a cautious meeting can beat feared downside. Do not invent whisper numbers or infer report content from the stock move. Distinguish formal guidance revisions, qualitative management tone, analyst interpretation, and unverified meeting snippets.
- Check first-public time, event date, publication/filing date, timezone, and recirculation. After-close information cannot explain an earlier cash-session move without evidence of earlier dissemination. Old FCC news or an old report is background unless new information or documented renewed attention makes it relevant today.
- Maintain a daily event ledger before drafting the mover section. Every earnings release, filing, guidance change, research note, conference, and rumor must have an event date, first-public timestamp, source, and status: `new today`, `continuing repricing`, `historical background`, or `not relevant today`. Do not place a historical earnings release in a section titled "today's key update". A prior result may be mentioned only to explain the market's current expectations or price reaction, and must be labeled as background; remove it entirely when it adds no incremental information.
- For companies with recent results, ask whether today's move contains a new estimate/target change, management comment, guidance update, order/customer disclosure, or fresh price/volume reaction. If none is documented, write the stock's current move under market/sector structure and state that the prior earnings are not a same-day catalyst. Do not keep a company on a daily tracking list merely because it is a large AI or cloud name.
- Do not create a standalone “today's key update” or “当日归因” subsection for a fixed-list company such as AVGO or ORCL unless its event ledger contains `SESSION_NEW` or `CONTINUING_REPRICING` with documented incremental information. Otherwise keep the ticker only in the relevant basket, rotation table, or sector paragraph; if even that adds no explanatory value, omit it.
- Rank explanations by timing, expectation change, affected-company exposure, relative price/volume response, peer confirmation, and counterevidence. Present the likely main driver, relevant amplifiers, confidence, and what remains unconfirmed; do not mechanically list every hypothesis or invent percentage contributions. Multiple causes can coexist, and insufficient evidence should remain unresolved.
- Absence of a discovered company catalyst is not proof of macro causation; absence of a policy document is not proof that no policy development occurred. Do not repeat a daily "no new FCC ban found" disclaimer when policy is not material to the day's move.
- For policy documents, verify the original text, issuer/submitter, document/docket number, release date, procedural status, product/company/geographic scope, conditions, and effective dates. Distinguish proposals, third-party comments/ex parte submissions, public notices, conditional exemptions, and final rules. A submission hosted on the FCC site is not FCC endorsement; an exemption for another equipment category is not an optical-transceiver exemption. Separate direct regulatory effects from inferred changes in market expectations.

### Company Expectation Reset And Claim Verification

Increase information density by going one layer below the headline. For the day's 3-6 most material companies or themes, use a compact expectation-reset card rather than adding more generic prose. Select names by abnormal absolute/relative move, volume, breadth impact, a verified same-day event, or a material forward catalyst; do not fill a fixed company quota.

Each selected card must answer, when data permits:

1. `Price fact`: absolute return, sector/index-relative return, volume confirmation, and intraday timing.
2. `Incremental evidence`: the new filing, earnings item, analyst work, conference comment, management change, product release, capital-allocation decision, industry datum, attributed rumor, or third-party calculation.
3. `Expectation delta`: what the market previously expected and which assumption moved. A positive headline can still disappoint a higher bar.
4. `Valuation or capital-allocation anchor`: consensus or sourced EPS/revenue/FCF, multiple, implied price, buyback size, CapEx, financing capacity, or another relevant anchor. Distinguish a new authorization, total authorization, remaining authorization, and actual repurchases.
5. `Debate and counterevidence`: the strongest alternative interpretation, contradictory peer/tape evidence, and whether the move may be positioning rather than fundamentals.
6. `Next verification`: the next order, customer, user, revenue, margin, product, regulatory, conference, or reporting milestone that would confirm or reject the thesis.

Proactively search for calculations, channel checks, social-media threads, meeting snippets, rumors, and market relays when they plausibly explain the tape. They are admissible evidence, not forbidden material, but their provenance and verification status must remain visible. Never sanitize an unattributed claim into a fact.

Use these claim statuses:

- `PRIMARY_VERIFIED`: confirmed in a company filing, official release, regulator/exchange document, prepared remarks, or attributable management transcript.
- `SECONDARY_CORROBORATED`: reported by a reliable secondary source and independently corroborated where practical.
- `ATTRIBUTED_CALCULATION`: a named analyst, investor, account, institution, or publication produced a calculation whose inputs and arithmetic can be summarized or reproduced; this remains the originator's estimate, not a company fact.
- `UNVERIFIED_RUMOR`: an attributed but unconfirmed market relay, meeting snippet, social post, or channel check. State who circulated it, when, and what remains unverified.
- `ORIGIN_UNKNOWN`: the claim is circulating but the original author, timestamp, or source cannot be established. Do not use it as the main causal explanation.
- `CONTRADICTED_OR_NOT_REPRODUCIBLE`: primary evidence conflicts with the claim, or the calculation cannot be reproduced from stated assumptions. Keep only if explaining why the market narrative is unreliable.

For every non-primary claim retained in the Word report, record the originator or institution, source URL or capture path, first-public timestamp when available, claim type, key inputs, units, arithmetic or methodology, sensitivity to assumptions, current status, tape confirmation, and the missing evidence needed for verification. Prefix the prose with visible wording such as `第三方测算：`, `卖方测算：`, `社交媒体测算：`, `会议转述/待验：`, or `市场传闻/待验：`. If the originator cannot be identified, write `原始出处未确认` rather than “市场认为”.

An attributed calculation may be useful even when unverified. Reproduce the bridge when feasible, check unit consistency and order of magnitude, and show which assumptions drive the conclusion. For example, a user-to-compute estimate should separate active users, concurrency or utilization, inference/training mix, compute per user, CPU/GPU split, memory content, hardware pricing, and the comparison supply base. Present a sensitivity range instead of one false-precision point estimate when the inputs are uncertain.

Rumors or third-party calculations may explain price only when timing fits the cash session and the relevant stocks/peers show confirming relative price, breadth, volume, or options behavior. Otherwise place them in `待验叙事` or `盘后/下一交易日观察`, not as the main cause. Read [references/company_expectation_and_claims.md](references/company_expectation_and_claims.md) when a report contains a material company expectation reset, valuation bridge, rumor, channel check, meeting relay, or third-party calculation.

Examples:

- Memory stocks moving together may reflect Samsung/SK hynix long-term supply deals, lock-volume-for-price concerns, CXMT/China substitution, HBM allocation, or pricing-cycle changes.
- AI hardware moving together may reflect hyperscaler CapEx guidance, vendor financing, data-center lease/financing risk, power bottlenecks, export controls, or China substitution.
- Optical networking or optical module stocks moving together may reflect fresh research or management commentary, hyperscaler qualification changes, co-packaged optics timelines, 800G/1.6T ramps, DSP/networking supply-chain read-throughs, China competition, policy, or broad factor rotation. This is a hypothesis menu only; FCC/Commerce is not a default explanation.
- Consumer staples leaders making new highs, such as Coca-Cola, may reflect company news, pricing power, or defensive rotation; test breadth and relative performance before concluding that market risk appetite cooled.

## Required Structure

Default Word order is: (1) Executive Tape Snapshot, (2) Rotation & Leadership Dashboard, (3) Rotation Matrix, (4) Factor, Microstructure & HF Positioning, (5) Today's Company Expectation Resets, (6) Technology Sector Scan, (7) Non-Tech Sector Scan, (8) Decliners & Kill Reasons, (9) Where Capital Focused, (10) Index Inclusion & Option Risk, (11) Derivatives, Gamma & Flows, (12) Post-Bell / Next Session, (13) A-Share & Hong Kong Mapping, (14) Data Appendix, (15) Sources. The expectation-reset section is mandatory, but include only names that pass the Event Gate; when no company has material incremental information, state that briefly and keep the section short. Preserve the existing sections below; move or summarize repeated material rather than deleting research depth.

### Rotation & Leadership Dashboard

Run the Rotation Engine on every completed session, including quiet semiconductor or software days. It diagnoses price leadership and relative preference; it does not prove fund flow. Put `Today's Leadership`, `Semi vs Software`, `Mag7 Internal Rotation`, `Mag7 vs Tech ex-Mag7`, `Tech vs Non-Tech`, and `Growth / Cyclical / Defensive Rotation` before the factor and technology narrative.

### Chart-First Observation Gate

Do not write the rotation narrative from a prewritten market view and then place charts underneath it. The mandatory order is: `COLLECT DATA -> CALCULATE METRICS -> RENDER CHARTS -> INSPECT EACH CHART AND ITS SOURCE DATA -> WRITE OBSERVATION RECORD -> WRITE INTERPRETATION`. Previous-day prose, chart titles, or a fixed “risk-on/risk-off” template cannot be used as the observation source.

For every chart, create an observation record before drafting the paragraph: chart id, date, series and sign convention, absolute returns, relative returns, median and breadth, volume confirmation or absence, visible concentration, and what remains unclear. The paragraph must be generated from or traceable to that record. Direction words such as `跑赢/跑输`, `强/弱`, `流入/流出`, and `承压/承接` must be chosen after comparing the current values; never hard-code them into a reusable daily template.

For spread charts, inspect both the sign and the underlying absolute returns. A positive `Semi - Software` spread means Semi outperformed Software; it does not mean Semi rose in absolute terms. If the chart, data table, caption, and prose disagree on sign, breadth, or direction, stop the export, correct the observation record, and regenerate the Word file. A chart may support a price-preference proxy, but it cannot by itself prove net fund flow or a causal news explanation.

At the very top of this dashboard, before the detailed chart/table discussion, write a short chart-led conclusion answering: which baskets show relative strength, which show relative weakness, whether the pattern is broad or concentrated, and what direction of capital preference the prices imply. Then comment on each required chart in order: (1) SOXX versus IGV, (2) the Semi-Software daily spread, (3) Mag7 internal heatmap, (4) leadership heatmap, and (5) sector rotation map when available. For each, state the observed direction, breadth/median confirmation or divergence, volume confirmation or absence, and the resulting interpretation: likely price preference/inflow proxy, likely price pressure/outflow proxy, short-covering possibility, or unclear. Use “资金偏好/价格流向代理” when there is no direct flow evidence; reserve “净流入/净流出” for sourced ETF, fund-flow, prime-broker, 13F, options, dealer, or other direct evidence.

#### Sector Map Exception Gate

The 11-sector ETF heatmap is an index-level overview, not a complete account of sector leadership. Immediately below every sector rotation map, add either (a) a sub-sector proxy chart/table or (b) a named single-stock exception note; in practice use both whenever data is available. At minimum scan relevant sub-sector proxies such as `SOXX/SMH（半导体）`, `IGV（软件）`, `CIBR（网络安全）`, `SKYY（云计算）`, `XBI/IBB（生物医药）`, `IHI/XHE（医疗器械）`, `ARKG（基因组学）`, `XME（金属与矿业）`, `COPX（铜矿）`, and `GDX（黄金矿业）`, extending the list when the day's tape makes another basket relevant. The rotation engine should render `rotation_subsector_heatmap.png` when the required price history exists and label every row with an industry keyword.

The report must also create a `Sector Map Exception Notes` record after reading the chart. List material movers that the broad ETF can hide: a practical trigger is absolute single-stock return of at least 3%, at least 2x the sector ETF move, a 30-day volume ratio of at least 2x, or a same-day event/rumor/research/management communication. Each note must contain the ticker, industry, return, volume or relative-performance evidence, event-lifecycle status, source, and the best-supported explanation plus what remains unconfirmed. Example: `TWST（生命科学工具/合成生物学）大涨` must be separated from `XLV（医疗保健）` and checked against `XBI/IBB`, because a company-specific AI-drug-discovery partnership or analyst reset can lift TWST while large-cap healthcare weights determine XLV. Never conclude “healthcare is weak/strong” from XLV alone when a relevant sub-sector or single-stock dispersion is available. If neither a sub-sector proxy nor an explainable exception can be obtained, state the missing data and do not hide the limitation behind the ETF average.

For every spread chart, state the sign convention immediately before interpreting it: `Semi - Software > 0` means Semi outperformed Software, while `< 0` means Software outperformed Semi. Reconcile the spread with both baskets' absolute equal-weight and median returns. A positive spread must not be described as semiconductor underperformance; if both baskets fall, describe relative outperformance separately from absolute weakness. Run a final contradiction check between chart sign, table values, breadth, and prose before exporting the Word file.

At minimum calculate 1D, 5D cumulative, and 20D cumulative relative performance, plus 20D percentile or z-score when history permits, breadth differential, relative volume, and rank/rank change for the main pairs. Use `SOXX` cross-checked with `SMH` versus `IGV`; `MAGS` versus `QQQ`, `RSP`, and a transparent Tech ex-Mag7 basket; 11 sector ETFs versus `SPY` and `RSP`; and transparent proxies for Growth/Defensive, Cyclical/Defensive, AI CapEx/AI Applications, High Beta/Low Vol, Momentum/Market, Most-shorted or MEME/Momentum, and Small Cap/Large Cap.

Semi and Software baskets must report equal-weight return, median return, advancing percentage, percentage outperforming SPY, relative volume, and counts above +2% or below -2%. Keep the core universe editable and add dynamically relevant names; do not treat the examples as a permanent news list. If SOXX is weak but equal-weight/median breadth is strong, call out `ETF vs breadth divergence` and possible heavyweight drag. If all are weak, sector-wide weakness is better supported. Apply the same test to IGV and Software breadth.

Mag7 price tracking is fixed, not fixed-news tracking. Calculate each name's 1D/5D/20D and relative performance versus SPY/QQQ, Mag7 equal-weight return, cap-weight proxy, breadth, and cross-sectional dispersion. Use regimes `COMPUTE_LED`, `PLATFORM_LED`, `CONSUMER_DEVICE_LED`, `HIGH_BETA_LED`, `BROAD_MAG7`, or `FRAGMENTED_MAG7`; do not describe three winners and four losers as “Mag7 broadly strong”.

Use rotation states `EMERGING`, `CONFIRMED`, `EXTENDED`, `REVERSING`, `NOISE`, or `UNCLEAR/MIXED`. Do not force a state from one day's spread. A one-day reversal against a still-positive 20D trend is normally `EMERGING` or `REVERSING`, not automatically confirmed. Label the result `price-based rotation proxy` unless direct ETF flow, prime-broker, 13F, options, dealer, or fund-flow evidence supports stronger wording. Do not equate relative performance with confirmed net fund flow.

### Rotation Matrix

Place one compact matrix immediately after the Rotation Dashboard and before Factor/Microstructure. Columns: `Rotation Pair | 1D | 5D | 20D | Breadth | Volume | Regime | Interpretation`. At minimum include Semi-Software, Mag7-Tech ex-Mag7, Mag7-RSP, QQQ-RSP, Growth-Defensive, Cyclical-Defensive, AI CapEx-AI Applications, High Beta-Low Vol, and Small Cap-Large Cap. Link its interpretation to the HF checks: crowded AI long unwind, software short covering, de-grossing, rates/duration, gamma, ETF flow, estimate revisions, research upgrades, and real order confirmation. These are hypotheses to test, not a mechanical score.

Use a lightweight history cache at `D:\codex\outputs\us_market_daily_recaps\rotation_cache\`, updating only new sessions when possible. Store date, ticker/basket, close, daily return, volume, relative volume, and basket membership; backfill only missing history. Record basket construction in the report or generated JSON.

### Rotation Engine Internal Checks

Run these checks in the background and do not clutter the final report with them:

- Confirm target session clock and reject any event with `first_public_at > target_session_close_et` as a cash-session explanation.
- Reject an old earnings fingerprint marked `SESSION_NEW`; fixed-universe membership without same-day evidence is a warning, not a catalyst.
- Warn if FCC is used as the optical-sector main cause without a qualifying same-day document, status change, company/broker reference, or credible renewed trading evidence.
- Reconcile Rotation Matrix 1D/5D/20D signs with the underlying close series. If ETF signal conflicts with equal-weight or median breadth, write `ETF vs breadth divergence`.
- If no direct flow evidence exists, downgrade `funds flowed/net inflow/net outflow` to `price-based rotation`, `relative preference`, or `rotation proxy`.
- Run a final consistency pass for date, source, event fingerprint, basket membership, chart labels, and price/return units before authoring the Word file.

Do not turn Rotation Engine into a second mechanical bullish/bearish score. Use its numbers to identify leadership, breadth, dispersion, persistence, and reversal, then apply evidence-led judgment.

### 1. Executive Tape Snapshot

Start the report with a compact first-page dashboard:

- One-sentence thesis. Format the thesis as a highlighted or underlined key point in Word.
- Dow Jones, S&P 500, Nasdaq Composite or NDX, Russell 2000.
- Equal-weight S&P 500 or RSP when available.
- Breadth and participation: advance/decline ratio, percent of S&P 500 or Nasdaq components up, new highs/new lows, and whether RSP outperformed or underperformed SPY.
- Concentration and mega-cap effect: whether Mag 7/mega-cap tech carried the index, whether the other 493 stocks diverged, and whether index calm hid factor or sector damage.
- Total volume versus YTD or 30-day average when available.
- MOC buy/sell imbalance when available.
- VIX.
- US Treasury yields, especially 10Y and 2Y when relevant.
- DXY or broad dollar direction.
- Oil, gold, copper, and BTC.
- A short read-through for risk appetite, duration, cyclicals, commodities, and growth style.

When rates, inflation, central-bank policy, fiscal policy, or liquidity expectations materially affect the session, add a compact `Macro Pricing Board`. It must include the 2Y and 10Y Treasury yield levels and basis-point changes, the 2s10s curve move, a named futures/OIS source plus timestamp for the next-meeting outcome probability and cumulative expected policy path, the transmission into affected sectors or factors, and at least one piece of counterevidence. Distinguish the probability of the next meeting decision from the cumulative path priced over later meetings. If a required public series cannot be obtained, name the source checked and the missing field rather than inventing a value. Follow [references/company_expectation_and_claims.md](references/company_expectation_and_claims.md).

Clearly label unavailable or uncertain data. Do not invent exact numbers.

Crypto unit check: when the source BTC quote is in USD, display `万美元` as `USD price / 10,000` with two decimals. Never divide a USD BTC quote by 1,000 and label it `万美元`; reconcile the displayed value against the raw snapshot before export, so `$86,000` displays as `8.60万美元`.

### 12. Data Appendix: Index And Sector Performance Matrix

Place this matrix near the end of the report, immediately before the source list. Do not place it near the top where it interrupts the narrative.

Include a compact performance matrix for core indices and key sectors/sub-sectors. The table should include:

- Day change.
- Week-to-date or trailing 5 trading day change.
- Month-to-date or trailing 1 month change.
- Year-to-date change.

Do not leave many cells as unavailable just because a ready-made return table is missing. Compute returns from point levels whenever possible:

- Week return = current close / prior week-end close or close 5 trading days ago - 1.
- Month return = current close / prior month-end close, current close / first trading day of month close, or close about 21 trading days ago - 1; state which basis is used.
- YTD return = current close / prior year-end close - 1.
- Use ETF proxies for sectors/sub-sectors when official sector index point levels are unavailable, and label the proxy.
- Every sector/index/ETF proxy label shown in a chart, heatmap, table, or ranking must include an industry keyword, not only the ticker. Use the format `XLK（科技）`, `XLC（通信服务）`, `XLV（医疗保健）`, `XBI（生物医药）`, etc.; the ticker may remain in English, but the Chinese industry keyword is mandatory. For sector rotation maps, the y-axis is invalid if it contains bare codes such as `XLK`, `XLC`, or `XLV` without an industry label.
- Maintain a reusable label map for core proxies: `XLK（科技）`, `XLC（通信服务）`, `XLY（可选消费）`, `XLP（必选消费）`, `XLF（金融）`, `XLI（工业）`, `XLE（能源）`, `XLB（材料）`, `XLV（医疗保健）`, `XLRE（房地产）`, `XLU（公用事业）`, `SOXX/SMH（半导体）`, `IGV（软件）`, `XBI（生物医药）`, `XME（金属与矿业）`, `COPX（铜矿）`, `GDX（黄金矿业）`, `ARKK（创新成长）`, `MEME（高空头/迷因）`, and `BUZZ（社交情绪）`. Extend the map for any additional proxy used.
- The Rotation Engine `rotation_sector_heatmap.png` is an integrated sector-and-industry map, not an 11-sector-only chart. It must include the 11 SPDR sectors plus, when history is available, `SOXX/SMH（半导体）`, `IGV（软件）`, `CIBR（网络安全）`, `SKYY（云计算）`, `XBI/IBB（生物医药）`, `IHI/XHE（医疗器械）`, `ARKG（基因组学/生命科学）`, `XME（金属与矿业）`, `COPX（铜矿）`, `GDX（黄金矿业）`, `KRE（区域银行）`, `XRT（零售）`, `XHB（住宅建筑）`, `ITA（航空航天/国防）`, and `ARKK（创新成长）`. These additions are the default high-value industry coverage; add a company or a more relevant proxy when the day's tape requires it.
- This label rule applies specifically to the Rotation Engine `rotation_sector_heatmap.png`: its y-axis must display labels such as `XLK（科技）`, `XLV（医疗保健）`, and `XBI（生物医药）`, while the underlying JSON/CSV may retain the ticker as the machine-readable key. Keep a separate sub-sector chart only when the integrated map would be unreadable or when a focused industry drill-down adds explanatory value.
- Only write "暂不可得" after checking that neither point levels nor a reasonable ETF proxy can be obtained.
- If the primary market-data provider is rate-limited or returns an incomplete target-session bar, switch to a second public chart/data endpoint before declaring a field unavailable. For a completed cash session, a missing daily close may be reconstructed from the target date's 5-minute regular-session OHLCV bars; label the field as `public 5-minute cash-session aggregate`, keep the source URL, and never silently reuse the prior session's value. Do not export a daily report when core index/ETF coverage or the breadth universe is incomplete; record the failed source and fallback basis in the data log.

At minimum cover:

- Core indices: Dow Jones, S&P 500, Nasdaq Composite or NDX, Russell 2000, equal-weight S&P 500 or RSP.
- Core sectors: XLK/Technology, XLC/Communication Services, XLY/Consumer Discretionary, XLP/Consumer Staples, XLF/Financials, XLI/Industrials, XLE/Energy, XLB/Materials, XLV/Healthcare, XLRE/Real Estate, XLU/Utilities.
- Key sub-sectors when relevant: SOX/SOXX semiconductors, IGV software, cybersecurity ETF or leading basket, cloud/software basket, SMH, AI hardware basket, data-center REITs, XBI/IBB biotech, IHI/XHE medical devices, ARKG genomics/life-science tools, XME/metals, COPX/copper miners, gold miners, KRE/regional banks, XRT/retail, XHB/homebuilders, ITA/aerospace-defense, luxury consumption proxy, meme/high-short-interest basket, MEME ETF, BUZZ/social-sentiment ETF, ARKK/speculative growth. When a company-specific move is much larger than its broad-sector ETF, add the company to the exception scan even if its sub-sector proxy is unavailable.
- The daily price collector's symbol universe must request the default integrated-map tickers (`SOXX SMH IGV CIBR SKYY XBI IBB IHI XHE ARKG XME COPX GDX KRE XRT XHB ITA ARKK`) alongside the 11 core sectors. If an ETF is unavailable or has no target-session bar after primary and fallback retrieval, keep the row as `暂不可得` and record the failed source rather than silently dropping the industry.

If a week/month/YTD number is unavailable, write "暂不可得" instead of omitting the row.

### 4. Factor, Microstructure & HF Positioning

This section is mandatory. Diagnose market structure before moving into sector narrative.

#### Market Structure & Microstructure

- Breadth & participation: advance/decline ratio, percent of S&P 500 or Nasdaq components up, new highs/new lows, sector participation, and whether RSP beat or lagged SPY.
- Keep the breadth vocabulary separate: `Advancing/Declining` means the stock rose/fell versus the previous close in the target session; `New highs/New lows` means the stock reached a defined lookback extreme (default 252 sessions). Never translate `Declining` as `New lows`, and never describe the relationship from a chart without checking the actual counts. State the lookback window beside new-high/new-low counts.
- Concentration & mega-cap effect: distinguish "index flat but internal damage" from "Mag 7 carrying the index while the other 493 stocks are weak" or "broad participation with no single mega-cap sponsor."
- Factor multi-speed: momentum, high beta versus low vol, high-short-interest baskets, meme/high-short names, AI baskets, defensives, cyclicals, and rate-sensitive groups.
- Intraday structure: morning gap, midday fade, 3:40pm ET last-20-minute move, closing auction pressure, and whether volume confirmed the price move when reliable data is available.

#### Price vs. News Divergence

Explicitly identify sectors or stocks that moved against the obvious headline:

- Bad news but stock/sector rises: possible short covering, de-grossing, bottom fishing, earnings clearing, or supply/demand bottleneck sponsorship.
- Good news but stock/sector falls: possible crowded long unwind, sell-the-news, guidance bar too high, valuation derating, or gamma/positioning pressure.
- Macro risk-off day but high-short or previously hated names rally: treat as potential short squeeze or long/short book de-grossing, not automatically as fundamental sponsorship.

#### Positioning & De-grossing Decision Tree

For major wrong-way moves, compare these positioning hypotheses with the company, research/conference, industry, and market evidence above. They are alternatives to test, not required diagnoses or a fixed ranking. A positive expectation revision can explain strength on a macro-negative day without a squeeze. State confidence and retain an unresolved conclusion when necessary:

1. Short squeeze / short covering: prior high short interest, crowded negative narrative, sharp upside on heavy volume, weak or absent fundamental news, high borrow/short-interest screens, or high-short ETF/basket outperformance.
2. Hedge-fund de-grossing / de-leveraging: macro shock triggers selling of longs and covering of shorts at the same time; crowded longs fall while funding shorts/high-short names rise.
3. Net buyers overwhelmed / bottom fishing: long-only or strategic buyers absorb bad news; sector breadth and volume improve without classic squeeze markers.
4. Earnings clearing / position reset: stock rallies after results because feared downside did not materialize, or falls after a beat because the bar was too high.
5. CTA/systematic or vol-control flow: price crosses moving averages, prior highs/lows, realized-vol thresholds, or volatility regimes that can force trend funds or vol-target funds to cut/add exposure.
6. Dealer/gamma effect: use VIX/VVIX/SKEW, put/call ratio, intraday realized vol, large strike magnets, and last-hour price behavior to infer whether options hedging likely amplified or pinned moves. Label as inference unless sourced.

#### HF Mechanics And Flow Read-through

When available, use Goldman/Morgan Stanley/JPM prime-brokerage notes, 13F changes, short-interest data, ETF flow data, and dealer/option dashboards. If proprietary data is not available, use public proxies and label them clearly:

- Long-selling proxy: crowded momentum/AI leaders down on heavy volume, XLK/QQQ/SMH/IGV outflows or relative weakness, or mega-cap underperformance.
- Short-covering proxy: high-short-interest/meme basket, most-shorted basket, weak balance-sheet names, or prior funding shorts rallying on a macro risk-off day.
- De-grossing proxy: simultaneous long-book losers and short-book winners, falling gross-risk proxies, rising correlation, and broad factor compression.
- CTA/systematic proxy: SPY/QQQ/IWM/RSP and key sector ETFs crossing 20/50/200-day moving averages, breaking prior range highs/lows, or realized volatility moving through a regime threshold.

Do not call a move "real sponsorship" until it survives this check. If evidence is mixed, write "price sponsorship plus possible short covering" or "short-covering-led, fundamentals not yet confirmed."

Always check whether the day contains:

- Index strength hiding factor damage.
- AI down while ex-AI is at or near highs.
- Momentum longs being sold and shorts/funding legs squeezing.
- Software/internet rally caused by short-covering rather than fundamental sponsorship.
- Staples, healthcare, utilities, or low-vol defensives rallying as former funding shorts.
- Hedge-fund gross-downs, prime-book long selling, or systematic/fundamental L/S pain.
- Index realized vol low while single-stock/factor vol is high.
- High-short-interest or most-shorted baskets rallying on a down tape.
- RSP versus SPY divergence and Mag 7 versus S&P 493 divergence.

If the market had a visible intraday selloff, reversal, or "跳水", add a standalone subsection named:

`盘中跳水/反转原因`

This subsection must distinguish:

- Macro trigger: rates, oil, dollar, Fed, jobs/inflation, geopolitics.
- Sector trigger: semiconductors, AI CapEx, optical, software, energy, financials, healthcare, etc.
- Single-stock trigger that became index/factor pressure: for example SpaceX/AMD/Nvidia/Apple/Amazon/Meta.
- Positioning trigger: crowded longs, short-covering reversal, gamma/option dealer flow, ETF de-risking, lockup/unlock supply, or post-earnings sell-the-news.
- Whether the selloff was broad-market risk-off or narrow cap-weight/factor repricing.

Do not only report the closing result if there was a meaningful intraday reversal.

If data is available, include factor/positioning charts or screenshots in the Word document.

### 5. Technology Sector Scan

Do not treat technology as one block. Scan these sub-sectors:

For the Technology Sector Scan, delete any standalone recurring-ticker rule section such as “AVGO/ORCL处理规则”. A ticker is not a daily section. Instead, create a compact `科技股异动归因` table or paragraph block only for technology names that meet the day's anomaly threshold: typically absolute move >= 3%, sector-relative move >= 2 percentage points, volume >= 1.5x 30-day average, a verified same-day event, or a material options/positioning alert. For each selected name, state:

- Price fact: return, sector/ETF-relative return, volume, and whether the move was isolated or part of a basket.
- Cause search: same-day filing/release, broker research or target/estimate change, conference/management communication, product/order/customer evidence, industry read-through, policy/security development, or factor/positioning rotation.
- Expectation delta: what the market had priced before and what changed today; distinguish primary evidence, secondary reporting, attributed calculation, rumor, and unresolved cause.
- Counterevidence and next verification: peer divergence, lack of confirmation, and the next order, price, margin, customer, filing, conference, or trading-session signal that would validate the explanation.

Do not write “technology was weak/strong” as the cause of an individual move. If no credible catalyst is found, say so explicitly and attribute only to the observable structure (for example: rate-sensitive de-grossing, profit-taking after an extended run, high-beta/factor rotation, or company-specific supply) with a confidence level. Do not use a historical AVGO or ORCL earnings release to fill an empty causal slot; if either name is not anomalous and has no incremental event, omit it from the technology narrative rather than repeating its history.

- Semiconductors: GPU, CPU, ASIC, analog, EDA, equipment, foundry, memory, HBM, storage.
- AI infrastructure: data centers, servers, networking, power, cooling, leasing, REITs, AI cloud, financing chain.
- Software: enterprise SaaS, AI agents, workflow software, databases, observability, cybersecurity software when relevant.
- Internet platforms: search, ads, social, streaming, marketplaces, cloud platforms.
- Cybersecurity.
- Cloud and IT services.
- Optical communication and hardware: optical modules, coherent, copper interconnect, switches, PCB, storage, servers.
  - Use COHR, LITE, AAOI, GLW, MRVL, AVGO, ALAB, CIEN, NOK and related optical/DSP names as a price/coverage universe when relevant; do not force every name into the narrative or search each one for news.
  - If they move as a group, compare fresh research/conference takeaways, AI data-center demand, orders/pricing, 800G/1.6T ramps, CPO timelines, hyperscaler qualifications, China competition, policy/security developments, and broad risk/factor rotation. No automatic FCC-first ordering. Select the day's main explanation using the Event Gate and Evidence-Led Attribution checks.
- Consumer electronics: Apple chain, PCs, smartphones, wearables, EV/robotics when relevant.
- Meme, high-short-interest, retail momentum, and speculative growth stocks: scan separately as a risk-appetite thermometer, especially when they move as a group. Use a basket/index proxy when possible instead of only listing single names:
  - First check live Roundhill Meme Stock ETF `MEME` as the direct meme-stock basket proxy.
  - Also check `BUZZ` as a broader social-sentiment ETF proxy.
  - Use `ARKK` only as speculative-growth proxy, not as a pure meme-stock proxy.
  - Do not use the old Solactive Roundhill Meme Stock Index as a current index because Solactive announced termination effective 2024-04-11. If referenced historically, label it as discontinued.

#### AI Chain Basket Ladder

Split AI and hard-tech exposure into institution-style market-structure baskets when relevant, not one generic "AI" bucket. These are price-analysis universes, not daily news obligations:

- Tier 1 Cash Flow Winners: NVDA, AVGO, MSFT, META, AMZN, GOOGL, ORCL and other cash-flow leaders with direct AI revenue, platform control, or balance-sheet capacity; scan price daily, include news only after the Event Gate.
- Tier 2 Infrastructure & Networking: MU, SNDK, WDC, STX, COHR, LITE, AAOI, GLW, MRVL, CRDO, ALAB, CIEN, NOK, ANET, HPE, DELL, SMCI and related compute/network/storage beneficiaries.
- Tier 3 Power & Data Center Utilities: VRT, ETN, PWR, CEG, NRG, VST, APLD, IREN, DLR, EQIX, nuclear/uranium, power, cooling, grid, and data-center financing beneficiaries.

For each tier, evaluate relevant explanations, allowing overlap rather than forcing one bucket:

- Tier-1 spillover into Tier 2/3.
- Over-shorted Tier 2/3 mean reversion.
- Real order/revenue confirmation.
- Broker research or management-conference expectations being raised or disappointed.
- Policy/security/China substitution read-through.
- Financing/rate sensitivity.
- Broad risk-appetite, momentum, or valuation rotation without a new industry headline.

When Tier 2 or Tier 3 rallies on a macro-negative day, test short covering/de-grossing alongside new fundamental expectations and relative-value rotation. Price divergence alone proves neither covering nor fresh long-only sponsorship.

Add AI CapEx versus AI Applications when data permits. AI CapEx may include compute, networking, memory, power, cooling, and data-center infrastructure; AI Applications may include software, agents, workflow, databases, and application beneficiaries. State basket membership and treat both as proxies.

For each material move, explain:

- Which stocks led.
- Whether the move was backed by volume, options activity, earnings, guidance, order news, supply-chain rumors, policy, or industry read-through.
- The incremental catalyst or expectation change if supported; otherwise the observed market/factor structure, without inventing a new narrative or rumor to fill a slot.
- Whether the move has real sponsorship or looks like short-covering/gross-down.

### 6. Non-Tech Sector Scan

Use US market sector categories first, then expand into important sub-sectors. At minimum scan:

- Consumer staples.
- Consumer discretionary.
- Luxury consumption: LVMH, Hermes, Richemont, Tapestry, Ralph Lauren, Estee Lauder, Capri, high-end travel/beauty/jewelry read-throughs.
- Financials: banks, brokers, cards/payments, insurers, asset managers, private equity.
- Industrials: machinery, aerospace/defense, rails, logistics, electrical equipment, infrastructure.
- Energy: E&P, majors, oilfield services, refiners, LNG, uranium when relevant.
- Materials and metals: copper, aluminum, steel, gold miners, lithium, chemicals, packaging, paper.
- Healthcare: pharma, biotech, medtech, life-science tools, hospitals, managed care.
- Real estate: REITs, data-center REITs, housing, builders.
- Utilities: regulated utilities, power, nuclear, grid, AI electricity beneficiaries.
- Communication services: telecom, cable, media, entertainment, platforms if not already covered.
- Airlines, defense, and transport when they are major movers.

Do not omit a sector just because it was not the strongest. Briefly mark "not a main line today" if needed.

### 7. Decliners And Kill Reasons

Separate:

- Earnings/guidance misses.
- Research or company-conference takeaways below the market's documented expectations, including insufficient upside despite positive headline language.
- Rates/duration pressure.
- Regulation/policy.
- Oil or commodity shocks.
- Valuation derating.
- Crowded-trade unwind.
- New sub-sector narrative or rumor.
- Pair-trade/funding-short reversal.
- Pure technical pullback.

If multiple stocks in one niche fall together, distinguish a shared incremental catalyst from broad market/factor pressure and company-specific disappointments. Do not assume a shared policy narrative from co-movement alone.

### 8. Where Capital Focused

Rank:

- Highest priority.
- Second priority.
- Watch list.
- Lower priority / avoid for now.

Use cross-confirmation from sector returns, leading stock moves, volume, ETF action, options/news heat, factor/prime flow, and social/retail discussion if available. If Stocktwits, Reddit, X, Futubull, Tiger, or Xueqiu overseas data is unavailable, explicitly say so and do not treat it as evidence.

Before writing this section, check whether a same-day social heat snapshot exists under:

`D:\codex\outputs\us_market_daily_recaps\social_heat\YYYY-MM-DD\social_heat_summary_YYYY-MM-DD.json`

If it does not exist, run the helper when feasible:

`python scripts/collect_social_heat.py --date YYYY-MM-DD --symbols NVDA MU META MSFT TSLA AAPL AMZN GME COIN MSTR --out D:\codex\outputs\us_market_daily_recaps\social_heat\YYYY-MM-DD`

Use symbols relevant to that day's market movers, not only the default example.

Source rules:

- Stocktwits: use public trending/page data when available; use Firestream sentiment only if `STOCKTWITS_USER` and `STOCKTWITS_PASS` are configured. Treat as retail attention, not institutional flow.
- Reddit: scan WSB, stocks, investing, options and relevant sector subreddits. Prefer OAuth/PRAW if configured; public JSON is acceptable only with source limitations saved in the snapshot.
- X: use recent counts/search only if `X_BEARER_TOKEN` is configured. Counts indicate narrative velocity, not truth.
- Futubull/Moomoo: use official Futu OpenD only when available; treat as quote/news/hot-list data unless a supported community endpoint is confirmed.
- Tiger: do not claim community heat unless an official hot-list/export/logged-in workflow is provided.
- Xueqiu: do not blind-scrape unofficial endpoints by default. Use user-provided exports, screenshots, or explicit logged-in browser capture only.

Only write "social heat confirms" when at least two social/retail sources agree and the move is also supported by price/volume/news. Otherwise label it as "retail-only heat", "news-only heat", or "source unavailable".

### 9. Derivatives, Gamma & Flows

This section is mandatory. If proprietary flow data is unavailable, use public proxies and explicitly label the inference. Do not stop at "data unavailable" unless both direct data and reasonable proxies are unavailable.

- Realized vol versus implied vol: VIX, VVIX, SKEW, index realized move, and whether vol was bought or sold.
- Put/call and protection demand: Cboe total/equity/index put-call ratios when available; if not, infer from VIX/SKEW and sector selloff breadth.
- 0DTE and gamma behavior: whether the tape looked negative gamma (moves extend in the same direction, late-day acceleration, high realized vol) or positive gamma/pinning (range-bound, repeated mean reversion, big-strike magnets). Label this as inferred unless using a sourced GEX dashboard.
- MOC / closing-flow estimate: check the final 20 minutes after 3:40pm ET in SPY/QQQ/IWM/RSP and leading sector ETFs. Rising price plus volume into close suggests buy imbalance; falling price plus volume suggests sell imbalance. Call it "MOC proxy" unless an official imbalance source is cited.
- ETF and factor flow proxies: SPY/QQQ/IWM/RSP/SMH/IGV/XLE/XLV/XLF/ARKK/MEME/BUZZ relative moves, volume spikes, and sector breadth.
- Prime-book and hedge-fund mechanics: if GS/MS/JPM PB notes are available, summarize net buying, gross activity, long sales and short covers. If not, infer possible de-grossing or short covering from price structure and label confidence.
- CTA/systematic flow: note whether SPY/QQQ/IWM/RSP or major sector ETFs crossed important 20/50/200-day moving averages or prior range levels.
- Post-bell movers relevant to the next trading day.

Post-bell items must be clearly labeled and should not be used to explain the cash-session move unless timing supports it.

### 10. Post-Bell / Next Session

Keep after-close events in a separate section. Apply the Event Gate: post-bell results, filings, guidance, research, conferences, or rumors can inform the next session but cannot explain the completed cash session unless they were publicly available before that session closed.

Add a compact `Forward Event Radar` for material scheduled events and known catalysts. For each item, state the exact date, time, and timezone; directly exposed companies or baskets; public consensus or clearly attributed market expectation; the variables that would constitute an upside or downside surprise; and evidence of what may already be priced through price, volume, options, or positioning. Include credible pending rumors or third-party calculations only with the visible status and provenance rules in `Company Expectation Reset And Claim Verification`; never present the event outcome as certain. Follow [references/company_expectation_and_claims.md](references/company_expectation_and_claims.md).

### 11. A-Share And Hong Kong Mapping

Map US after-close narratives into A-share/HK sectors and tickers as inference only. State clearly:

`以下为映射推演，不等于 A/H 事实涨跌。`

Separate:

- Direct read-through.
- Sentiment read-through.
- Contradictory or non-transferable factors such as policy, localization, pricing, or market-structure differences.

## Word And Chart Requirements

- Final output must be `.docx`.
- Save the Word file under `D:\codex\outputs\us_market_daily_recaps\`.
- Use charts by default whenever a section contains comparable numeric data, ranked movers, baskets, breadth, relative performance, intraday paths, or flow proxies. Do not leave a chart-worthy section as text only.
- Each daily Word report must include these Rotation Engine PNG visuals when price history is available: SOXX and IGV normalized to 100 over the last 20 sessions; 20-session SOXX minus IGV daily-spread bars; a Mag7 internal heatmap with 1D/5D/20D/vs SPY; a leadership heatmap covering Mag7, Tech ex-Mag7, Semi, Software, AI CapEx, AI Applications, Cyclicals, Defensives, and Small Cap; and the integrated sector-and-industry rotation map containing XBI and the default high-value industry proxies above. Label these as price-based proxies.
- At minimum, each daily Word report should include PNG visuals for: executive rotation map, sector/ETF performance, market-structure/factor proxy, AI-chain tier ladder when AI is relevant, and derivatives/flow proxy when data or proxies are available.
- Put each chart near the section it supports. Do not push all visuals into an appendix unless there are many charts.
- Use PNG for generated visuals. Do not embed SVG in Word because it may render blank.
- Each chart must have a short caption and source/data-basis line. If a chart is based on proxies, label it as proxy/inference.
- Make core takeaways easy to scan: use yellow highlight or underline for the most important one-sentence thesis, each highest-priority capital-focus item, and the main sector-narrative conclusion.
- Do not over-highlight. Usually 5-8 highlighted/underlined points are enough for one daily report.
- In the Word body, format individual stock/company names and single-stock ticker symbols with light gray shading so readers can quickly scan the trading anchors. This applies to names such as Coca-Cola, Nvidia, Micron, Salesforce, KO, NVDA, MU, CRM, and similar single-stock anchors.
- Do not gray-shade tables. Tables are data areas and should remain clean.
- Do not gray-shade index names, index codes, ETF codes, sector names, or basket codes such as S&P 500, SPX, Dow Jones, Nasdaq, Russell 2000, SOX, SOXX, SMH, IGV, XLP, XLK, RSP, or similar.
- Do not gray-shade generic market words such as AI, EPS, CapEx, revenue, guidance, valuation, or risk-off unless they are part of an individual company name.
- Use more readable spacing than a dense Markdown page: normal body paragraphs should use expanded line spacing and some after-paragraph spacing.
- Include charts, factor screenshots, PDF screenshots, or generated plots in the Word file when they materially support the narrative; for sector rotation, market structure, AI tiers, and flow proxies this is mandatory.
- Every inserted chart/image needs a short caption and source line.
- Put charts near the section that discusses them; use an appendix only when there are many charts.
- The Word report should use compact tables for tape snapshot, sector scan, biggest movers, and capital-focus ranking.
- Cite key sources at the end with links.
- Mark time basis and data basis.
- Prefer primary sources for company earnings and official announcements; use reliable media for market recaps and rumors.
- Preserve uncertainty. Never fabricate unavailable prices, volumes, rumors, factor data, options flow, or social sentiment.

If no Word library is available, use the bundled helper script:

`scripts/render_recap_docx.py`

The helper can render a Markdown draft into `.docx` and embed local image paths written as Markdown image tags.
