"""Deterministic event-clock helpers used before daily narrative drafting."""
from datetime import datetime

STATUSES = {"SESSION_NEW", "POST_BELL_NEXT_SESSION", "CONTINUING_REPRICING", "HISTORICAL_BACKGROUND", "EXPIRED_IRRELEVANT"}

def classify_event(first_public_at: datetime, previous_close_et: datetime,
                   session_close_et: datetime, report_run_et: datetime,
                   has_incremental_update: bool = False) -> str:
    if previous_close_et < first_public_at <= session_close_et:
        return "SESSION_NEW"
    if session_close_et < first_public_at <= report_run_et:
        return "POST_BELL_NEXT_SESSION"
    if first_public_at <= previous_close_et and has_incremental_update:
        return "CONTINUING_REPRICING"
    if first_public_at <= previous_close_et:
        return "HISTORICAL_BACKGROUND"
    return "EXPIRED_IRRELEVANT"

def event_fingerprint(ticker_or_sector: str, event_type: str,
                      event_key: str, event_date: str) -> str:
    return "|".join(str(x).strip().upper() for x in
                    (ticker_or_sector, event_type, event_key, event_date))

if __name__ == "__main__":
    print("event_gate: import classify_event and event_fingerprint")
