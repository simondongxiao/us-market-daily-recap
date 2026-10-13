"""Validate the persistent index-inclusion ledger and emit daily reminders."""
from __future__ import annotations
import argparse, json
from pathlib import Path
import pandas as pd

ACTIVE = {"ANNOUNCED_PENDING", "EFFECTIVE_TODAY"}
REQUIRED = {"ticker", "company", "index_family", "index_name", "announcement_date", "first_public_at", "effective_date", "status", "source", "source_url", "expected_passive_demand", "last_reminder_date", "notes"}

def option_alerts(s: dict) -> list[str]:
    out=[]
    for label in (s.get('option_alerts') or s.get('alerts') or []):
        if label and label != 'no_threshold_alert': out.append(str(label))
    for expiry in s.get('expiries') or []:
        for label in (expiry.get('alerts') or []):
            if label and label != 'no_threshold_alert': out.append(str(label))
    try:
        if s.get("call_oi") and s.get("put_oi") and float(s["call_volume"])/max(float(s["call_oi"]),1) >= 2: out.append("call-volume/OI>=2")
        if s.get("put_oi") and float(s["put_volume"])/max(float(s["put_oi"]),1) >= 2: out.append("put-volume/OI>=2")
        ratio=float(s["call_volume"])/max(float(s["put_volume"]),1)
        if ratio>=3: out.append("call-heavy")
        if ratio<=0.33: out.append("put-heavy")
        if s.get("iv_now") is not None and s.get("iv_prior") is not None:
            diff=float(s["iv_now"])-float(s["iv_prior"])
            if diff>=10 or diff/max(abs(float(s["iv_prior"])),1)>=.25: out.append("IV-expansion")
        if float(s.get("max_strike_volume_share",0))>=.20: out.append("strike-concentration")
    except (KeyError, TypeError, ValueError, ZeroDivisionError):
        out.append("unclassified")
    return sorted(set(out))

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--date',required=True); ap.add_argument('--ledger',default='D:/codex/outputs/us_market_daily_recaps/index_inclusion_watchlist.json'); ap.add_argument('--out',default=None); a=ap.parse_args()
    payload=json.loads(Path(a.ledger).read_text(encoding='utf-8'))
    entries=payload.get('entries',payload) if isinstance(payload,dict) else payload
    report=pd.Timestamp(a.date); reminders=[]; errors=[]; closeouts=[]
    for e in entries:
        missing=sorted(REQUIRED-set(e))
        if missing: errors.append({'ticker':e.get('ticker'),'missing':missing}); continue
        eff=pd.Timestamp(e['effective_date'])
        if e['status'] in ACTIVE and report <= eff:
            # Count US business sessions after the report date through the effective date.
            # This keeps a Saturday report ahead of a Monday rebalance at 1 session remaining.
            sessions=max(len(pd.bdate_range(report + pd.Timedelta(days=1),eff,inclusive='both')),0)
            snap=e.get('options_snapshot') or {}
            reminders.append({'ticker':e['ticker'],'company':e['company'],'index_name':e['index_name'],'announcement_date':e['announcement_date'],'effective_date':e['effective_date'],'sessions_remaining':sessions,'status':'EFFECTIVE_TODAY' if report==eff else e['status'],'expected_passive_demand':e['expected_passive_demand'],'source_url':e['source_url'],'option_source':snap.get('source','source unavailable'),'option_checked_at_et':snap.get('checked_at_et'),'option_data_status':snap.get('data_status','unavailable' if not snap else 'available'),'option_direction_label':snap.get('direction_label'),'option_alerts':option_alerts(snap) if snap else ['source unavailable']})
        elif e['status'] in ACTIVE and report > eff:
            closeouts.append({'ticker':e['ticker'],'company':e['company'],'index_name':e['index_name'],'effective_date':e['effective_date'],'action':'close after one completion note'})
    out={'report_date':a.date,'reminders':reminders,'closeouts':closeouts,'validation_errors':errors}
    dest=Path(a.out) if a.out else Path('D:/codex/outputs/us_market_daily_recaps')/a.date/'index_inclusion_watch.json'; dest.parent.mkdir(parents=True,exist_ok=True); dest.write_text(json.dumps(out,indent=2,ensure_ascii=False),encoding='utf-8'); print(json.dumps(out,ensure_ascii=False,indent=2))
if __name__=='__main__': main()
