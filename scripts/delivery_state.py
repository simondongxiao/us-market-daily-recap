#!/usr/bin/env python3
"""Persist and query delivery state for schedule/manual-run de-duplication."""

from __future__ import annotations

import argparse
import base64
import json
import os
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path


STATE_PATH = "state/daily_delivery_state.json"


def gh(args: list[str], *, input_path: Path | None = None) -> str:
    command = ["gh", "api", *args]
    if input_path is not None:
        command += ["--input", str(input_path)]
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or f"gh api failed with exit code {result.returncode}")
    return result.stdout


def load_state(repo: str, branch: str) -> tuple[dict, str]:
    endpoint = f"repos/{repo}/contents/{STATE_PATH}?ref={branch}"
    result = subprocess.run(["gh", "api", endpoint], capture_output=True, text=True)
    if result.returncode != 0:
        if "404" in result.stderr or '"status": 404' in result.stdout:
            return {"version": 1, "deliveries": []}, ""
        raise RuntimeError(result.stderr.strip() or "Unable to read delivery state")
    payload = json.loads(result.stdout)
    content = base64.b64decode(payload["content"].replace("\n", "")).decode("utf-8")
    state = json.loads(content)
    state.setdefault("version", 1)
    state.setdefault("deliveries", [])
    return state, payload.get("sha", "")


def matching_success(state: dict, report_date_bjt: str, us_trade_date: str, content_version: str = "") -> dict | None:
    matches = [
        item for item in state.get("deliveries", [])
        if item.get("status") == "sent"
        and item.get("report_date_bjt") == report_date_bjt
        and (not us_trade_date or item.get("us_trade_date") == us_trade_date)
        and (not content_version or item.get("content_version") == content_version)
    ]
    return max(matches, key=lambda item: item.get("sent_at_utc", ""), default=None)


def do_check(args: argparse.Namespace) -> int:
    state, _ = load_state(args.repo, args.branch)
    matched = matching_success(state, args.report_date_bjt, args.us_trade_date, args.content_version)
    date_success = any(
        item.get("status") == "sent" and item.get("report_date_bjt") == args.report_date_bjt
        for item in state.get("deliveries", [])
    )
    print(json.dumps({
        "duplicate": matched is not None,
        "has_success_for_report_date": date_success,
        "matched": matched,
        "state_path": STATE_PATH,
    }, ensure_ascii=False))
    return 0


def do_record(args: argparse.Namespace) -> int:
    state, sha = load_state(args.repo, args.branch)
    item = {
        "status": args.status,
        "report_date_bjt": args.report_date_bjt,
        "us_trade_date": args.us_trade_date,
        "content_version": args.content_version,
        "html_url": args.html_url,
        "word_url": args.word_url,
        "run_url": args.run_url,
        "sent_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    deliveries = [
        x for x in state.get("deliveries", [])
        if not (
            x.get("report_date_bjt") == args.report_date_bjt
            and x.get("us_trade_date") == args.us_trade_date
            and x.get("content_version") == args.content_version
        )
    ]
    deliveries.append(item)
    state["deliveries"] = deliveries[-120:]
    state["updated_at_utc"] = datetime.now(timezone.utc).isoformat()
    payload = {
        "message": f"Record daily recap delivery {args.report_date_bjt} {args.us_trade_date}",
        "content": base64.b64encode(json.dumps(state, ensure_ascii=False, indent=2).encode("utf-8")).decode("ascii"),
        "branch": args.branch,
    }
    if sha:
        payload["sha"] = sha
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".json", delete=False) as handle:
        json.dump(payload, handle)
        payload_path = Path(handle.name)
    try:
        gh(["-X", "PUT", f"repos/{args.repo}/contents/{STATE_PATH}"], input_path=payload_path)
    finally:
        payload_path.unlink(missing_ok=True)
    print(json.dumps({"recorded": True, "state_path": STATE_PATH, "status": args.status}, ensure_ascii=False))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["check", "record"])
    parser.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY", "simondongxiao/us-market-daily-recap"))
    parser.add_argument("--branch", default=os.environ.get("GITHUB_BRANCH", "main"))
    parser.add_argument("--report-date-bjt", required=True)
    parser.add_argument("--us-trade-date", default="")
    parser.add_argument("--content-version", default="")
    parser.add_argument("--html-url", default="")
    parser.add_argument("--word-url", default="")
    parser.add_argument("--run-url", default="")
    parser.add_argument("--status", default="sent")
    args = parser.parse_args()
    return do_check(args) if args.command == "check" else do_record(args)


if __name__ == "__main__":
    raise SystemExit(main())
