"""Check every event the editor picked, on the organizer's own page.

Input:  runs/<friday>/picks.json   {"events": [{"key": "pumpkin-drop", "url": "https://..."}]}
Output: runs/<friday>/enrich.json  per key: page status, share image, price/date/ticket clues

The editor reads enrich.json to confirm each card (dates incl. multi-day, price,
registration, sold out / not yet on sale) and to pull the card's photo.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from web import Browser, fetch  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent

SIGNALS = {
    "sold_out": r"sold[\s-]?out|no (?:tickets|seats|spots) (?:left|available|remaining)|fully booked|at capacity",
    "waitlist": r"wait[\s-]?list",
    "registration_closed": r"registration (?:is )?(?:now )?closed|registration has closed|reservations? (?:are |is )?closed|sign[\s-]?ups? (?:are |is )?closed",
    "sales_ended": r"sales? (?:have |has )?ended|no longer (?:on sale|available)|event (?:has )?ended|this event has passed",
    "not_on_sale": r"(?:tickets?|registration) (?:go|goes|will go) on sale|on sale (?:on|starting|beginning)|registration opens|coming soon",
    "cancelled": r"cancell?ed|postponed",
    "registration_required": r"registration required|reservations? required|rsvp required|advance (?:registration|reservation)|must register",
    "age_limit": r"ages? \d+\s?(?:\+|and up|or older|-\s?\d+)|\d+\s?\+ only|adults only|18\+|21\+",
}
PRICE = r"\$\s?\d+(?:\.\d{2})?|\bfree\b"
DATE = (r"(?:(?:mon|tue|wed|thu|fri|sat|sun)[a-z]*,?\s+)?(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+\d{1,2}"
        r"(?:\s*[-–]\s*(?:(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+)?\d{1,2})?(?:,?\s+\d{4})?")


def snippets(pattern: str, text: str, limit=4, width=90):
    out = []
    for m in re.finditer(pattern, text, re.I):
        s = text[max(0, m.start() - width): m.end() + width].replace("\n", " ")
        out.append(" ".join(s.split()))
        if len(out) >= limit:
            break
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("friday")
    args = ap.parse_args()
    run = ROOT / "runs" / args.friday
    picks = json.loads((run / "picks.json").read_text())["events"]

    results = {}
    with Browser() as browser:
        for ev in picks:
            page = fetch(ev["url"], ev.get("mode", "auto"), browser)
            text = page.text
            results[ev["key"]] = {
                "url": ev["url"], "final_url": page.final_url, "status": page.status,
                "method": page.method, "attempts": page.attempts, "http": page.http_status,
                "title": page.title, "og_image": page.og_image, "image_candidates": page.image_candidates,
                "signals": {k: snippets(p, text) for k, p in SIGNALS.items()},
                "prices": sorted(set(m.group(0).strip().lower() for m in re.finditer(PRICE, text, re.I)))[:12],
                "dates": list(dict.fromkeys(m.group(0).strip() for m in re.finditer(DATE, text, re.I)))[:15],
                "text": text[:15000],
                "error": page.error,
            }
            print(f"{page.status:7} {page.method:7} img={'y' if page.og_image else 'n'}  {ev['key']}")

    (run / "enrich.json").write_text(json.dumps(results, indent=1, ensure_ascii=False))
    ok = sum(r["status"] == "ok" for r in results.values())
    print(f"{ok}/{len(results)} pick pages loaded")


if __name__ == "__main__":
    main()
