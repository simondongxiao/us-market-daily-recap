from __future__ import annotations

import argparse
import base64
import json
import os
import subprocess
import tempfile
from pathlib import Path


def gh(args: list[str], *, input_path: Path | None = None) -> str:
    command = ["gh", "api", *args]
    if input_path is not None:
        command += ["--input", str(input_path)]
    result = subprocess.run(command, check=True, capture_output=True, text=True)
    return result.stdout


def upload_file(local_file: Path, endpoint: str, branch: str, message: str) -> dict:
    sha = ""
    existing = subprocess.run(
        ["gh", "api", endpoint, "-X", "GET", "-f", f"ref={branch}", "--jq", ".sha"],
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
    print(json.dumps({"repo": args.repo, "path": path, "html_url": html_url, "word_url": word_url}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
