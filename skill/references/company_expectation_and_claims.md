# Company Expectation And Claim Verification

Read this reference when a daily recap contains a material company expectation reset, valuation bridge, capital-allocation event, rumor, channel check, meeting relay, social-media calculation, or other non-primary claim.

## Compact Company Card

Keep the finished prose concise. Gather the detail in the working record, then publish only the decision-relevant fields.

| Field | Required content |
|---|---|
| Price fact | Absolute return, sector/index-relative return, volume ratio, intraday timing |
| New information | What became public in or before the target cash session |
| Prior expectation | Consensus, management's prior statement, attributed investor expectation, or clearly labeled market bar |
| Expectation delta | Which assumption changed and why the price reaction is rational or surprising |
| Valuation/capital anchor | EPS/revenue/FCF and multiple, implied price, buyback authorization versus execution, CapEx or financing bridge |
| Debate | Base interpretation, strongest counter-thesis, positioning alternative |
| Verification | Status, primary/secondary sources, missing evidence, next milestone |

Suggested finished form:

`Ticker move and relative performance. New information and timing. Expectation delta. Valuation or capital-allocation anchor. Counter-thesis and next verification.`

Do not write all fields when they add no value. Do not omit the expectation delta for a material event simply to save space.

## Claim Record

Maintain these fields in the event or research ledger:

- `claim_id`
- `ticker_or_theme`
- `claim_text`
- `claim_type`
- `originator_name`
- `originator_affiliation`
- `source_url_or_capture_path`
- `first_public_at`
- `retrieved_at`
- `status`
- `inputs`
- `units`
- `method`
- `reproduced_result`
- `sensitivity`
- `primary_source_check`
- `secondary_corroboration`
- `tape_confirmation`
- `cash_session_eligible`
- `missing_evidence`
- `notes`

## Verification Workflow

1. Find the earliest attributable version, not only reposts or screenshots.
2. Identify the author/account/institution and whether it is a company representative, analyst, investor, journalist, expert, or anonymous relay.
3. Check first-public time against the target cash-session close.
4. Search for a primary document or direct transcript that confirms or contradicts the claim.
5. Reproduce the arithmetic when it is a calculation. Check currency, percentages, billions/millions, annual versus daily rates, utilization, market-share assumptions, and double counting.
6. Run a sensitivity range around the assumptions that dominate the result.
7. Compare the claim with the affected stock, peer basket, volume, breadth, intraday timing, and options structure.
8. Assign one status from the parent skill and state what evidence would upgrade or reject it.

## Valuation And Capital Allocation

- State whether earnings are reported, consensus, management guidance, or an attributed forecast.
- Show the bridge explicitly: `EPS x P/E = implied price`, `revenue x margin = operating profit`, or the relevant model.
- A valuation anchor is not a price target unless the assumptions are defended.
- Distinguish a newly approved repurchase authorization from total authorization, remaining capacity, executed purchases, and actual daily buyback demand.
- For buybacks, compare authorization with market capitalization, free cash flow, cash/debt, historical execution, expiry, and stated conditions.

## Industry And Supply-Chain Calculations

For compute, memory, optical, power, networking, or data-center claims, decompose the bridge into physical and financial assumptions. Examples include:

- Users, queries, tokens, concurrency, utilization, inference versus training, compute per workload.
- GPU/accelerator, CPU, memory, storage, networking, optical, power, cooling, and facility content.
- Installed capacity versus annual shipments; nameplate capacity versus usable capacity.
- Unit price, bill of materials, depreciation period, replacement cycle, and supplier share.
- Global supply or addressable market used as the comparison denominator.

Do not describe a shift in bill of materials or value pool as confirmed unless vendor data, customer commentary, shipment/order evidence, or multiple credible channel checks support it. Otherwise write it as an attributed thesis and specify the verification path.

## Macro Pricing Board

The macro section should explain what the market prices, not only give a narrative label.

Include when material:

- 2Y and 10Y Treasury level and daily basis-point change.
- Curve change such as 2s10s steepening/flattening.
- Next meeting probability and expected policy-path change from a named futures/OIS source with timestamp.
- Inflation, labor, oil, dollar, term-premium, and supply/auction inputs that changed the path.
- Transmission to duration equities, banks, housing/REITs, utilities, commodities, and leveraged/high-beta groups.
- Counterevidence: sectors or stocks that moved against the apparent macro impulse.

Do not repeat an options-implied probability without naming the contract/source and observation time. Distinguish a probability of one meeting outcome from the expected cumulative path.

## Forward Event Radar

For each material next-session event record:

- Event and exact scheduled time/timezone.
- Directly exposed companies or baskets.
- Public consensus or attributable market expectation.
- Upside and downside surprise variables.
- Whether positioning already appears elevated in price, volume, options, or social attention.

Keep future events out of the completed cash-session explanation unless information was public before that session closed.
