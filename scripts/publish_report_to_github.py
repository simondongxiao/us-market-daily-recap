from __future__ import annotations

import argparse
import base64
import json
import os
import re
import subprocess
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


def gh(args: list[str], *, input_path: Path | None = None) -> str:
    command = ["gh", "api", *args]
    if input_path is not None:
        command += ["--input", str(input_path)]
    result = subprocess.run(command, check=True, capture_output=True, text=True)
    return result.stdout


def upload_file(local_file: Path, endpoint: str, branch: str, message: str) -> dict:
    sha = ""
    lookup_endpoint = f"{endpoint}?ref={urllib.parse.quote(branch, safe='')}"
    existing = subprocess.run(
        ["gh", "api", lookup_endpoint, "--jq", ".sha"],
        capture_output=True,
        text=True,
    )
    if existing.returncode == 0:
        sha = existing.stdout.strip()
    payload = {
        "message": message,
        "content": base64.b64encode(local_file.read_bytes()).decode("ascii"),
        "branch": branch,
    }
    if sha:
        payload["sha"] = sha
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".json", delete=False) as handle:
        json.dump(payload, handle)
        payload_path = Path(handle.name)
    try:
        response = gh(["-X", "PUT", endpoint], input_path=payload_path)
    finally:
        payload_path.unlink(missing_ok=True)
    return json.loads(response)


def request_json(args: list[str]) -> dict | list:
    return json.loads(gh(args))


def trigger_pages_build(repo: str) -> dict:
    """Explicitly request a legacy Pages rebuild after the HTML commit."""
    return request_json([f"repos/{repo}/pages/builds", "-X", "POST"])


def wait_for_pages(
    repo: str,
    html_url: str,
    expected_date: str,
    expected_commit: str,
    timeout_seconds: int = 180,
) -> dict:
    """Wait for Pages and verify the public HTML is the current report."""
    started = time.monotonic()
    last_build: dict = {}
    last_error = ""
    while time.monotonic() - started <= timeout_seconds:
        try:
            last_build = request_json([f"repos/{repo}/pages/builds/latest"])
        except subprocess.CalledProcessError as exc:
            last_error = exc.stderr or str(exc)
        status = str(last_build.get("status", "")).lower() if isinstance(last_build, dict) else ""
        if status == "errored":
            last_error = str(last_build)
        elif status == "built" and (not expected_commit or last_build.get("commit") == expected_commit):
            parsed = urllib.parse.urlparse(html_url)
            if parsed.scheme != "https" or not parsed.netloc:
                raise RuntimeError(f"Invalid Pages URL: {html_url}")
            probe = f"{html_url}?codex_verify={int(time.time())}"
            request = urllib.request.Request(probe, headers={"Cache-Control": "no-cache"})
            try:
                with urllib.request.urlopen(request, timeout=30) as response:
                    content_type = response.headers.get("Content-Type", "")
                    body = response.read().decode("utf-8", errors="replace")
                if response.status == 200 and "text/html" in content_type.lower() and expected_date in body and len(body) > 1000:
                    return {
                        "verified": True,
                        "build": last_build,
                        "http_status": response.status,
                        "content_type": content_type,
                        "content_length": len(body),
                    }
                last_error = f"Pages returned status={response.status}, type={content_type}, length={len(body)}"
            except (urllib.error.HTTPError, urllib.error.URLError) as exc:
                last_error = str(exc)
        time.sleep(5)
    raise RuntimeError(f"Pages did not publish {html_url} within {timeout_seconds}s; last_build={last_build}; last_error={last_error}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY", "simondongxiao/us-market-daily-recap"))
    parser.add_argument("--branch", default=os.environ.get("GITHUB_BRANCH", "main"))
    args = parser.parse_args()
    report = args.report.resolve()
    if not report.is_file():
        raise FileNotFoundError(report)
    path = f"reports/{report.name}"
    endpoint = f"repos/{args.repo}/contents/{path}"
    word_result = upload_file(report, endpoint, args.branch, f"Store daily recap Word {report.stem}")
    html_report = report.with_suffix('.html')
    html_result = None
    if html_report.is_file():
        html_path = f"reports/{html_report.name}"
        html_endpoint = f"repos/{args.repo}/contents/{html_path}"
        html_result = upload_file(html_report, html_endpoint, args.branch, f"Store mobile HTML recap {html_report.stem}")
    word_url = word_result.get("content", {}).get("html_url") or f"https://github.com/{args.repo}/blob/{args.branch}/{path}"
    html_url = (html_result or {}).get("content", {}).get("html_url") if html_result else ""
    if not html_url and html_report.is_file():
        html_url = f"https://github.com/{args.repo}/blob/{args.branch}/reports/{html_report.name}"
    if html_report.is_file():
        owner, repo_name = args.repo.split('/', 1)
        # GitHub Pages is enabled for the public delivery repository, so this
        # is the browser-rendered URL rather than the source/blob URL.
        html_url = f"https://{owner}.github.io/{repo_name}/reports/{html_report.name}"
    pages = None
    if html_report.is_file():
        trigger_pages_build(args.repo)
        match = re.search(r"us_market_recap_(\d{4}-\d{2}-\d{2})_BJT", report.name)
        if not match:
            raise RuntimeError(f"Could not parse report date from {report.name}")
        expected_date = match.group(1)
        expected_commit = (html_result or {}).get("commit", {}).get("sha", "")
        pages = wait_for_pages(args.repo, html_url, expected_date, expected_commit)
    print(json.dumps({
        "repo": args.repo,
        "path": path,
        "html_url": html_url,
        "word_url": word_url,
        "pages_verified": bool(pages and pages.get("verified")),
        "pages": pages,
        "html_commit": (html_result or {}).get("commit", {}).get("sha", ""),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
