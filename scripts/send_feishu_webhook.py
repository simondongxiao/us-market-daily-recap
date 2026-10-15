#!/usr/bin/env python3
"""Send a compact daily-recap notification to a Feishu custom bot.

The webhook is read from FEISHU_WEBHOOK_URL and is never written to disk or
printed.  A custom bot webhook can deliver the notification and links, but it
does not upload a local .docx file; the workflow therefore includes the local
path and, when available, the GitHub Actions run URL.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--run-url", default="")
    parser.add_argument("--github-url", default="")
    parser.add_argument("--word-url", default="")
    parser.add_argument("--status", default="已生成")
    parser.add_argument("--webhook-env", default="FEISHU_WEBHOOK_URL")
    return parser.parse_args()


def report_date(report: Path) -> str:
    match = re.search(r"us_market_recap_(\d{4}-\d{2}-\d{2})_BJT", report.name)
    return match.group(1) if match else "未识别日期"


def read_excerpt(report: Path) -> str:
    """Read a short Markdown excerpt, or fall back to the generated Word text."""
    markdown = report.with_suffix(".md")
    text = ""
    if markdown.exists():
        try:
            text = markdown.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            text = ""
    if not text:
        try:
            from docx import Document

            paragraphs = Document(report).paragraphs
            text = "\n".join(p.text for p in paragraphs[:18] if p.text.strip())
        except Exception:
            text = ""
    text = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", text)
    text = re.sub(r"^#{1,6}\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:1200]


def build_text(args: argparse.Namespace) -> str:
    report = args.report.resolve()
    lines = [
        f"美股每日复盘｜北京时间 {report_date(report)}",
        f"状态：{args.status}",
    ]
    if args.run_url:
        lines.append(f"Actions运行记录：{args.run_url}")
    if args.github_url:
        lines.append(f"手机网页报告：{args.github_url}")
    if args.word_url:
        lines.append(f"GitHub Word归档：{args.word_url}")
    if not args.github_url or not args.word_url:
        raise RuntimeError("Feishu message requires both a public HTML URL and a GitHub Word URL")
    excerpt = read_excerpt(report)
    if excerpt:
        lines.extend(["", "摘要：", excerpt])
    # Feishu custom-bot requests have a 20 KB body limit. Keep margin for JSON.
    return "\n".join(lines)[:9000]


def send(webhook: str, text: str, attempts: int = 3) -> dict:
    body = json.dumps(
        {"msg_type": "text", "content": {"text": text}},
        ensure_ascii=False,
    ).encode("utf-8")
    request = urllib.request.Request(
        webhook,
        data=body,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    last_error = ""
    for attempt in range(1, attempts + 1):
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                raw = response.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as exc:
            last_error = f"Feishu webhook HTTP {exc.code}"
        except urllib.error.URLError as exc:
            last_error = f"Feishu webhook network error: {exc.reason}"
        else:
            try:
                result = json.loads(raw)
            except json.JSONDecodeError:
                last_error = "Feishu webhook returned non-JSON response"
            else:
                if "code" not in result:
                    last_error = "Feishu webhook response omitted code; delivery is unverified"
                elif result.get("code") != 0:
                    last_error = f"Feishu webhook rejected message: code={result.get('code')}"
                elif "StatusCode" in result and result.get("StatusCode") != 0:
                    last_error = f"Feishu webhook rejected message: StatusCode={result.get('StatusCode')}"
                else:
                    return result
        if attempt < attempts:
            time.sleep(2 ** attempt)
    raise RuntimeError(last_error)


def main() -> int:
    args = parse_args()
    webhook = os.environ.get(args.webhook_env, "").strip()
    if not webhook:
        raise RuntimeError(f"Missing environment variable: {args.webhook_env}")
    if not args.report.is_file():
        raise RuntimeError(f"Report does not exist: {args.report}")
    result = send(webhook, build_text(args))
    print(json.dumps({"sent": True, "response": result}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
