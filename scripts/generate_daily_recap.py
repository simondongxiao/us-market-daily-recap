from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import subprocess
import sys
import urllib.parse
import urllib.request
from pathlib import Path


REPO_DIR = Path(__file__).resolve().parents[1]
SKILL_DIR = Path(os.environ.get("US_MARKET_SKILL_DIR", r"D:\codex\skills\us-market-daily-recap"))
if not SKILL_DIR.exists():
    SKILL_DIR = REPO_DIR / "scripts/vendor"
TOOLS_DIR = SKILL_DIR / "scripts" if (SKILL_DIR / "scripts").exists() else SKILL_DIR
OUTPUT_ROOT = Path(os.environ.get("RECAP_OUTPUT_ROOT", r"D:\codex\outputs\us_market_daily_recaps"))
PYTHON = Path(sys.executable)


def run(args: list[str]) -> None:
    print("+", " ".join(str(x) for x in args), flush=True)
    subprocess.run(args, check=True)


def latest_us_session(report_date: dt.date) -> dt.date:
    """Resolve the latest completed SPY cash session before the Beijing date."""
    start = dt.datetime.combine(report_date - dt.timedelta(days=15), dt.time(), tzinfo=dt.timezone.utc)
    end = dt.datetime.combine(report_date + dt.timedelta(days=1), dt.time(), tzinfo=dt.timezone.utc)
    query = urllib.parse.urlencode({"period1": int(start.timestamp()), "period2": int(end.timestamp()), "interval": "1d", "events": "history"})
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/SPY?{query}"
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = json.loads(response.read().decode("utf-8"))
        timestamps = ((payload.get("chart") or {}).get("result") or [{}])[0].get("timestamp") or []
        dates = [dt.datetime.fromtimestamp(x, dt.timezone.utc).date() for x in timestamps]
        dates = [x for x in dates if x < report_date]
        if dates:
            return max(dates)
    except Exception as exc:
        print(f"WARN: session lookup failed: {exc}", file=sys.stderr)
    candidate = report_date - dt.timedelta(days=1)
    while candidate.weekday() >= 5:
        candidate -= dt.timedelta(days=1)
    return candidate


def materialize(template: Path, destination: Path, replacements: dict[str, str]) -> None:
    text = template.read_text(encoding="utf-8")
    # Protect replacement values from later date substitutions. For example,
    # an output path containing the template date must not be rewritten again
    # when the generic template date is replaced below.
    tokens: dict[str, str] = {}
    for index, (old, new) in enumerate(replacements.items()):
        token = f"__CODEX_REPLACEMENT_{index}__"
        text = text.replace(old, token)
        tokens[token] = new
    for token, new in tokens.items():
        text = text.replace(token, new)
    destination.write_text(text, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report-date-bjt", default=os.environ.get("REPORT_DATE_BJT"))
    parser.add_argument("--task-dir", default=os.environ.get("CODEX_TASK_DIR", str(REPO_DIR)))
    args = parser.parse_args()
    report_date = dt.date.fromisoformat(args.report_date_bjt or dt.date.today().isoformat())
    us_date = latest_us_session(report_date)
    report = report_date.isoformat()
    us = us_date.isoformat()
    root = OUTPUT_ROOT / report
    root.mkdir(parents=True, exist_ok=True)
    runtime = root / "_runtime"
    runtime.mkdir(parents=True, exist_ok=True)
    tomorrow = (report_date + dt.timedelta(days=1)).isoformat()

    materialize(REPO_DIR / "scripts/templates/collect_template.py", runtime / "collect.py", {
        'pd.Timestamp("2026-10-12")': f'pd.Timestamp("{us}")',
        'Path(r"D:\\codex\\outputs\\us_market_daily_recaps\\2026-10-13")': f'Path(r"{root}")',
        '"2026-10-12", "2026-10-13", "5m"': f'"{us}", "{report}", "5m"',
        '"2025-09-01", "2026-10-13"': f'"2025-09-01", "{report}"',
        'end: str = "2026-10-14"': f'end: str = "{tomorrow}"',
        'Path(r"D:\\codex\\outputs\\us_market_daily_recaps\\2026-10-10\\sp500_members.csv")': f'Path(r"{REPO_DIR / "data/sp500_members.csv"}")',
    })
    materialize(REPO_DIR / "scripts/templates/make_assets_template.py", runtime / "make_assets.py", {
        'Path(r"D:\\codex\\outputs\\us_market_daily_recaps\\2026-10-13")': f'Path(r"{root}")',
    })
    out_docx = OUTPUT_ROOT / f"us_market_recap_{report}_BJT_us_{us}_final.docx"
    materialize(REPO_DIR / "scripts/templates/build_recap_template.py", runtime / "build.py", {
        'Path(r"D:\\codex\\outputs\\us_market_daily_recaps\\2026-10-13")': f'Path(r"{root}")',
        'Path(r"D:\\codex\\outputs\\us_market_daily_recaps\\us_market_recap_2026-10-13_BJT_us_2026-10-12_final.docx")': f'Path(r"{out_docx}")',
        "2026-10-13": report,
        "2026-10-12": us,
    })

    run([str(PYTHON), str(runtime / "collect.py")])
    run([str(PYTHON), str(TOOLS_DIR / "rotation_engine.py"), "--date", report, "--root", str(root)])
    tickers = "LITE COHR CIEN AAOI MU SNDK NVDA AVGO META FICO MRNA TWST CRDO MRVL GME".split()
    run([str(PYTHON), str(TOOLS_DIR / "option_chain_collect.py"), "--date", report, "--out", str(root / "options_chain.json"), "--tickers", *tickers])
    ledger = Path(os.environ.get("INDEX_INCLUSION_LEDGER", str(OUTPUT_ROOT / "index_inclusion_watchlist.json")))
    if not ledger.exists():
        ledger = REPO_DIR / "data/index_inclusion_watchlist.json"
    run([str(PYTHON), str(TOOLS_DIR / "index_inclusion_watch.py"), "--date", report, "--ledger", str(ledger), "--out", str(root / "index_inclusion_watch.json")])
    run([str(PYTHON), str(runtime / "make_assets.py")])
    run([str(PYTHON), str(runtime / "build.py")])

    if not out_docx.is_file():
        raise RuntimeError(f"Word report was not created: {out_docx}")
    out_html = out_docx.with_suffix('.html')
    run([str(PYTHON), str(REPO_DIR / 'scripts/convert_docx_to_mobile_html.py'), '--input', str(out_docx), '--output', str(out_html)])
    if not out_html.is_file():
        raise RuntimeError(f"HTML report was not created: {out_html}")
    manifest = {
        "report_date_bjt": report,
        "us_trade_date": us,
        "report_path": str(out_docx),
        "report_name": out_docx.name,
        "html_path": str(out_html),
        "html_name": out_html.name,
        "task_dir": str(Path(args.task_dir).resolve()),
        "generated_by": str(Path(__file__).resolve()),
    }
    (root / "generation_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
