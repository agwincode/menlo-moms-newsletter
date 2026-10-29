"""Friday-morning collector.

Pulls every source in sources.yaml and saves a text snapshot per source, plus the
target weekend's forecast, to runs/<target-friday>/. The editor reads these at noon.

  python collector/collect.py                      # normal Friday run
  python collector/collect.py --friday 2026-11-06  # pick the weekend explicitly
  python collector/collect.py --smoke              # test every source, incl. retired ones
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

import feedparser
import yaml

sys.path.insert(0, str(Path(__file__).parent))
import weather  # noqa: E402
from web import Browser, Page, fetch  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
KEEP_WEEKS = 8


def target_friday(today: date) -> date:
    """The weekend after this one: a Friday run targets the Friday 7 days later."""
    ahead = (4 - today.weekday()) % 7 or 7
    return today + timedelta(days=ahead)


def fetch_rss(src) -> Page:
    p = Page(url=src["url"], final_url=src["url"], method="rss")
    try:
        feed = feedparser.parse(src["url"], agent="Mozilla/5.0 MenloMoms")
        entries = []
        for e in feed.entries[:60]:
            summary = re.sub(r"<[^>]+>", " ", e.get("summary", ""))
            summary = " ".join(summary.split())[:800]
            entries.append(f"{e.get('title','')}\nPublished: {e.get('published','')}\nURL: {e.get('link','')}\n{summary}")
            p.links.append({"text": e.get("title", ""), "href": e.get("link", "")})
        p.text = "\n\n---\n\n".join(entries)
        p.status = "ok" if entries else "thin"
        p.http_status = getattr(feed, "status", None)
    except Exception as ex:
        p.status, p.error = "error", str(ex)[:300]
    return p


def prune(runs_dir: Path):
    cutoff = date.today() - timedelta(weeks=KEEP_WEEKS)
    for d in runs_dir.iterdir() if runs_dir.exists() else []:
        try:
            if d.is_dir() and date.fromisoformat(d.name) < cutoff:
                shutil.rmtree(d)
        except ValueError:
            continue


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--friday")
    ap.add_argument("--smoke", action="store_true")
    args = ap.parse_args()

    cfg = yaml.safe_load((ROOT / "sources.yaml").read_text())
    sources = list(cfg["sources"])
    if args.smoke:
        sources += [dict(s, retired=True) for s in cfg.get("retired", [])]
        out = ROOT / "runs" / f"_smoke-{datetime.now():%Y%m%d-%H%M}"
        friday = target_friday(date.today())
    else:
        friday = date.fromisoformat(args.friday) if args.friday else target_friday(date.today())
        out = ROOT / "runs" / friday.isoformat()
        prune(ROOT / "runs")

    (out / "sources").mkdir(parents=True, exist_ok=True)
    print(f"Collecting for weekend of {friday} -> {out.relative_to(ROOT)}")

    rows = []
    with Browser() as browser:
        for src in sources:
            mode = src.get("mode", "auto")
            started = datetime.now()
            page = fetch_rss(src) if mode == "rss" else fetch(src["url"], mode, browser)
            secs = (datetime.now() - started).seconds
            rec = {"id": src["id"], "watchlist": src.get("watchlist", False),
                   "retired": src.get("retired", False), "note": src.get("note", ""),
                   "collected_at": datetime.now().isoformat(timespec="seconds"), **page.to_dict()}
            (out / "sources" / f"{src['id']}.json").write_text(json.dumps(rec, indent=1, ensure_ascii=False))
            rows.append({"id": src["id"], "url": src["url"], "status": page.status, "method": page.method,
                         "http": page.http_status, "chars": len(page.text), "links": len(page.links),
                         "secs": secs, "attempts": page.attempts, "error": page.error,
                         "retired": src.get("retired", False)})
            print(f"  {page.status:7} {page.method:7} {len(page.text):6}ch  {src['id']}  {' '.join(page.attempts)}")

    wx = weather.forecast(friday)
    (out / "weather.json").write_text(json.dumps(wx, indent=1))
    print("Weather:", wx["line"])

    ok = sum(r["status"] == "ok" for r in rows if not r["retired"])
    total = sum(not r["retired"] for r in rows)
    summary = {"friday": friday.isoformat(), "run_at": datetime.now().isoformat(timespec="seconds"),
               "ok": ok, "total": total, "sources": rows, "weather": wx["line"]}
    (out / "summary.json").write_text(json.dumps(summary, indent=1))

    md = [f"# Collector run for weekend of {friday}", "",
          f"{ok} of {total} sources OK. Weather: {wx['line']}", "",
          "| Source | Status | Method | Chars | Attempts |", "|---|---|---|---|---|"]
    for r in rows:
        name = r["id"] + (" (retired)" if r["retired"] else "")
        md.append(f"| [{name}]({r['url']}) | {r['status']} | {r['method']} | {r['chars']} | {' / '.join(r['attempts']) or r['error'][:60]} |")
    (out / "summary.md").write_text("\n".join(md) + "\n")
    if os.getenv("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a") as f:
            f.write("\n".join(md) + "\n")

    print(f"{ok}/{total} sources OK")
    # Fail the workflow (GitHub emails you) if most sources failed, e.g. a network outage.
    if not args.smoke and ok < total * 0.5:
        sys.exit(1)


if __name__ == "__main__":
    main()
