#!/usr/bin/env python3
"""Create or update the external cron-job.org dispatcher for this repository.

Secrets are read from the process environment and are never written to disk.
"""

from __future__ import annotations

import argparse
import datetime as dt
import getpass
import json
import os
import sys
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


API_ROOT = "https://api.cron-job.org"
DEFAULT_REPO = "simondongxiao/us-market-daily-recap"
DEFAULT_TITLE = "US market daily recap external 07:03 BJT"
GITHUB_API_VERSION = "2022-11-28"


def fail(message: str) -> int:
    print(f"ERROR: {message}", file=sys.stderr)
    return 1


def api_request(method: str, path: str, api_key: str, payload: dict | None = None) -> dict:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8") if payload is not None else None
    request = Request(
        f"{API_ROOT}{path}",
        data=body,
        method=method,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
    )
    try:
        with urlopen(request, timeout=30) as response:
            raw = response.read().decode("utf-8")
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:500]
        raise RuntimeError(f"cron-job.org API HTTP {exc.code}: {detail}") from exc
    except URLError as exc:
        raise RuntimeError(f"cron-job.org API network error: {exc.reason}") from exc
    if not raw.strip():
        return {}
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError("cron-job.org returned a non-JSON response") from exc


def job_config(repo: str, title: str, github_pat: str, enabled: bool = True) -> dict:
    dispatch_url = f"https://api.github.com/repos/{repo}/actions/workflows/us-market-daily-recap.yml/dispatches"
    return {
        "job": {
            "enabled": enabled,
            "title": title,
            "url": dispatch_url,
            "saveResponses": True,
            "requestTimeout": 60,
            "redirectSuccess": False,
            "requestMethod": 1,
            "schedule": {
                "timezone": "Asia/Shanghai",
                "expiresAt": 0,
                "hours": [7],
                "mdays": [-1],
                "minutes": [3],
                "months": [-1],
                "wdays": [-1],
            },
            "notification": {
                "onFailure": True,
                "onFailureCount": 1,
                "onSuccess": True,
                "onDisable": True,
                "onSslCertExpiry": True,
                "onSslCertExpirySeconds": 604800,
                "mode": 1,
                "selectedChannels": [],
            },
            "extendedData": {
                "headers": {
                    "Authorization": f"Bearer {github_pat}",
                    "Accept": "application/vnd.github+json",
                    "Content-Type": "application/json",
                    "X-GitHub-Api-Version": GITHUB_API_VERSION,
                },
                "body": '{"ref":"main"}',
            },
        }
    }


def redact(payload: dict) -> dict:
    value = json.loads(json.dumps(payload))
    headers = value.get("job", {}).get("extendedData", {}).get("headers", {})
    if "Authorization" in headers:
        headers["Authorization"] = "Bearer <redacted>"
    return value


def iso_timestamp(value: int | None) -> str:
    if not value:
        return "never"
    return dt.datetime.fromtimestamp(value, dt.timezone.utc).isoformat()


def print_job(job: dict) -> None:
    schedule = job.get("schedule") or {}
    print(json.dumps({
        "job_id": job.get("jobId"),
        "title": job.get("title"),
        "enabled": job.get("enabled"),
        "timezone": schedule.get("timezone"),
        "hours": schedule.get("hours"),
        "minutes": schedule.get("minutes"),
        "next_execution_utc": iso_timestamp(job.get("nextExecution")),
        "last_execution_utc": iso_timestamp(job.get("lastExecution")),
        "last_status": job.get("lastStatus"),
    }, ensure_ascii=False))


def main() -> int:
    parser = argparse.ArgumentParser(description="Configure the cron-job.org 07:03 BJT dispatcher")
    parser.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY", DEFAULT_REPO))
    parser.add_argument("--title", default=DEFAULT_TITLE)
    parser.add_argument("--check", action="store_true", help="list the matching job without changing it")
    parser.add_argument("--disable", action="store_true", help="disable the matching job instead of enabling it")
    parser.add_argument("--dry-run", action="store_true", help="print the redacted request without calling the API")
    parser.add_argument("--interactive", action="store_true", help="read missing secrets without echoing them")
    args = parser.parse_args()

    api_key = os.environ.get("CRON_JOB_ORG_API_KEY", "")
    github_pat = os.environ.get("GITHUB_DISPATCH_PAT", "")
    if args.dry_run:
        print(json.dumps(redact(job_config(args.repo, args.title, github_pat or "missing", not args.disable)), ensure_ascii=False, indent=2))
        return 0
    if args.interactive and not api_key:
        api_key = getpass.getpass("cron-job.org API key: ").strip()
    if args.interactive and not github_pat and not args.check:
        github_pat = getpass.getpass("GitHub fine-grained PAT: ").strip()
    if not api_key:
        return fail("CRON_JOB_ORG_API_KEY is not set")
    if not args.check and not github_pat:
        return fail("GITHUB_DISPATCH_PAT is not set")

    try:
        listing = api_request("GET", "/jobs", api_key)
        matches = [job for job in listing.get("jobs", []) if job.get("title") == args.title]
        if len(matches) > 1:
            return fail(f"found {len(matches)} jobs with the same title; remove the duplicate in cron-job.org first")
        if args.check:
            if not matches:
                print(json.dumps({"found": False, "title": args.title}, ensure_ascii=False))
                return 0
            details = api_request("GET", f"/jobs/{matches[0]['jobId']}", api_key).get("jobDetails") or {}
            print_job(details)
            return 0

        payload = job_config(args.repo, args.title, github_pat, not args.disable)
        if matches:
            job_id = matches[0]["jobId"]
            api_request("PATCH", f"/jobs/{job_id}", api_key, payload)
            action = "updated"
        else:
            created = api_request("PUT", "/jobs", api_key, payload)
            job_id = created.get("jobId")
            action = "created"
        details = api_request("GET", f"/jobs/{job_id}", api_key).get("jobDetails") or {}
        print(f"cron-job.org job {action}: {job_id}")
        print_job(details)
        return 0
    except RuntimeError as exc:
        return fail(str(exc))


if __name__ == "__main__":
    raise SystemExit(main())
