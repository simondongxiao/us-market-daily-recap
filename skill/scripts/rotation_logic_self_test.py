"""Small deterministic tests for event gating and rotation wording."""
from datetime import datetime, timedelta, timezone
from rotation_engine import regime
from event_gate import classify_event, event_fingerprint

ET = timezone(timedelta(hours=-4))
prev = datetime(2026, 9, 10, 16, 0, tzinfo=ET)
close = datetime(2026, 9, 11, 16, 0, tzinfo=ET)

assert classify_event(datetime(2026, 9, 1, 8, tzinfo=ET), prev, close, close, False) == "HISTORICAL_BACKGROUND"  # old AVGO result
assert classify_event(datetime(2026, 9, 11, 9, tzinfo=ET), prev, close, close, False) == "SESSION_NEW"                 # new ORCL note
assert classify_event(datetime(2026, 9, 11, 17, tzinfo=ET), prev, close, datetime(2026, 9, 11, 18, tzinfo=ET), False) == "POST_BELL_NEXT_SESSION"      # cannot explain cash session
assert classify_event(datetime(2026, 9, 1, 8, tzinfo=ET), prev, close, close, True) == "CONTINUING_REPRICING"
assert event_fingerprint("AVGO", "earnings", "FY26Q3", "2026-09-02") == "AVGO|EARNINGS|FY26Q3|2026-09-02"
assert regime(-0.04, 0.06, 0.18, None, True) in {"REVERSING", "EXTENDED"}
assert regime(0.03, 0.005, 0.01, None, False) in {"EMERGING", "UNCLEAR"}
print("rotation_logic_self_test: PASS")
