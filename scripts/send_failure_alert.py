#!/usr/bin/env python3
"""Send a failure-only Feishu alert from a separate process/job."""

from __future__ import annotations

import argparse
import json
import os
import sys

from send_feishu_webhook import send


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", required=True)
    parser.add_argument("--reason", required=True)
    parser.add_argument("--report-date-bjt", required=True)
    parser.add_argument("--run-url", default="")
    parser.add_argument("--webhook-env", default="FEISHU_WEBHOOK_URL")
    args = parser.parse_args()
    webhook = os.environ.get(args.webhook_env, "").strip()
    if not webhook:
        raise RuntimeError(f"Missing environment variable: {args.webhook_env}")
    lines = [
        f"美股每日复盘自动化失败｜北京时间 {args.report_date_bjt}",
        f"失败阶段：{args.phase}",
        f"原因：{args.reason[:1800]}",
    ]
    if args.run_url:
        lines.append(f"Actions运行记录：{args.run_url}")
    result = send(webhook, "\n".join(lines), attempts=3)
    print(json.dumps({"alert_sent": True, "response": result}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RuntimeError as exc:
        print(f"ERROR: failure alert was not sent: {exc}", file=sys.stderr)
        raise SystemExit(1)
