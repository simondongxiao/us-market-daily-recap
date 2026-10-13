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
    sha = ""
    # `gh api -f` switches a request to POST unless the method is explicit.
    # The contents lookup must remain GET so an existing report can be updated.
    existing = subprocess.run(
        ["gh", "api", endpoint, "-X", "GET", "-f", f"ref={args.branch}", "--jq", ".sha"],
        capture_output=True,
        text=True,
    )
    if existing.returncode == 0:
        sha = existing.stdout.strip()
    payload = {
        "message": f"Store daily recap {report.stem}",
        "content": base64.b64encode(report.read_bytes()).decode("ascii"),
        "branch": args.branch,
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
    result = json.loads(response)
    html_url = result.get("content", {}).get("html_url") or f"https://github.com/{args.repo}/blob/{args.branch}/{path}"
    print(json.dumps({"repo": args.repo, "path": path, "html_url": html_url}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
