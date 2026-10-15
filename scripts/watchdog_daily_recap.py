#!/usr/bin/env python3
"""Detect a missed delivery and request one compensating workflow run."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import subprocess
import sys
from pathlib import Path


REPO_DIR = Path(__file__).resolve().parents[1]
STATE_SCRIPT = REPO_DIR / "scripts" / "delivery_state.py"
ALERT_SCRIPT = REPO_DIR / "scripts" / "send_failure_alert.py"


def bjt_date() -> str:
    try:
        from zoneinfo import ZoneInfo

        return dt.datetime.now(ZoneInfo("Asia/Shanghai")).date().isoformat()
    except Exception:
        return (dt.datetime.utcnow() + dt.timedelta(hours=8)).date().isoformat()


def run(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, capture_output=True, text=True)


def send_alert(repo: str, date: str, phase: str, reason: str) -> None:
    run_url = f"{os.environ.get('GITHUB_SERVER_URL', 'https://github.com')}/{repo}/actions/runs/{os.environ.get('GITHUB_RUN_ID', '')}"
    result = run([sys.executable, str(ALERT_SCRIPT), "--phase", phase, "--reason", reason, "--report-date-bjt", date, "--run-url", run_url])
    print(result.stdout, end="")
    if result.returncode != 0:
        print(result.stderr, file=sys.stderr, end="")
        print("ERROR: watchdog failure alert could not be sent", file=sys.stderr)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY", "simondongxiao/us-market-daily-recap"))
    parser.add_argument("--report-date-bjt", default="")
    args = parser.parse_args()
    date = args.report_date_bjt or bjt_date()
    check = run([sys.executable, str(STATE_SCRIPT), "check", "--repo", args.repo, "--report-date-bjt", date])
    print(check.stdout, end="")
    if check.returncode != 0:
        reason = check.stderr.strip() or "delivery state lookup failed"
        send_alert(args.repo, date, "watchdog_state_check", reason)
        return 1
    try:
        state = json.loads(check.stdout.splitlines()[-1])
    except (json.JSONDecodeError, IndexError) as exc:
        send_alert(args.repo, date, "watchdog_state_check", f"invalid state response: {exc}")
        return 1
    if state.get("has_success_for_report_date"):
        print(f"Delivery already recorded for report_date_bjt={date}; no compensation run needed.")
        return 0
    dispatch = run([
        "gh", "workflow", "run", "us-market-daily-recap.yml", "--repo", args.repo,
        "--ref", "main", "-f", f"report_date_bjt={date}",
    ])
    print(dispatch.stdout, end="")
    if dispatch.returncode != 0:
        reason = dispatch.stderr.strip() or "workflow_dispatch compensation request failed"
        send_alert(args.repo, date, "watchdog_compensation", reason)
        return 1
    print(f"No successful delivery found for {date}; compensation workflow_dispatch requested.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
