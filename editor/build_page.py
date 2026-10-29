"""Build the Sunday review page (a Claude artifact) for one weekend.

  pip install markdown pillow
  python editor/build_page.py 2026-11-06   ->  build/2026-11-06.html

Reads drafts/<friday>.md, drafts/<friday>.review.md, runs/<friday>/enrich.json (photo
options) and runs/<friday>/weather.json (latest forecast). Photos are embedded, so
the page is self-contained.

Draft conventions:
  <!-- SUBJECT LINE: ... / PREVIEW TEXT: ... -->   at the top
  <!-- weather -->...<!-- /weather -->              forecast line (replaced with the latest)
  <!-- photos:<pick-key> -->  or  <!-- photos:<pick-key>:<n> -->   where a card's photo goes
                                                    (n = 1-based option to show first)
"""
from __future__ import annotations

import base64
import html
import json
import re
import sys
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import markdown

ROOT = Path(__file__).resolve().parent.parent
PT = ZoneInfo("America/Los_Angeles")


def weekend_label(friday: date) -> str:
    sun = date.fromordinal(friday.toordinal() + 2)
    if sun.month == friday.month:
        return f"{friday:%b} {friday.day}–{sun.day}"
    return f"{friday:%b} {friday.day}–{sun:%b} {sun.day}"


def data_uri(path: Path) -> str:
    return "data:image/jpeg;base64," + base64.b64encode(path.read_bytes()).decode()


def photo_block(key: str, first: int, enrich: dict, run: Path) -> str:
    photos = [p for p in (enrich.get(key, {}).get("photos") or []) if (run / p["file"]).exists()]
    if not photos:
        return '\n<p class="nophoto">No usable photo found on the event page. Add one in Substack.</p>\n'
    first = min(max(first, 1), len(photos)) - 1
    opts = []
    uris = [data_uri(run / p["file"]) for p in photos]
    for i, (p, uri) in enumerate(zip(photos, uris)):
        kind = f'{p["kind"]} · {p["w"]}×{p["h"]}'
        opts.append(
            f'<button class="opt" type="button" aria-pressed="{str(i == first).lower()}" '
            f'data-kind="{html.escape(kind)}" data-source="{html.escape(p["source"])}" '
            f'aria-label="Photo option {i + 1}: {html.escape(p["kind"])}"><img src="{uri}" alt=""></button>')
    chosen = photos[first]
    return (
        f'\n<figure class="photo" data-key="{html.escape(key)}">'
        f'<img class="main" src="{uris[first]}" alt="">'
        + (f'<div class="opts">{"".join(opts)}</div>' if len(photos) > 1 else "")
        + f'<figcaption><span class="kind">{html.escape(chosen["kind"])} · {chosen["w"]}×{chosen["h"]}</span>'
        f'<a class="src" href="{html.escape(chosen["source"])}" target="_blank" rel="noopener">source</a>'
        f'<button class="btn copy-photo" type="button">Copy photo</button></figcaption></figure>\n'
    )


def inline_md(text: str) -> str:
    out = markdown.markdown(text.strip())
    return re.sub(r"^<p>|</p>$", "", out)


def review_html(md: str) -> tuple[str, int]:
    """'## Heading' sections with '- ' items. Items get checkboxes; the
    'Check before sending' section is highlighted. Returns (html, items-to-check count)."""
    if not md.strip():
        return '<p>Nothing flagged this week.</p>', 0
    parts, n, must_count = [], 0, 0
    for block in re.split(r"(?m)^##\s+", md.strip()):
        if not block.strip():
            continue
        title, _, body = block.partition("\n")
        title = title.strip().strip("#").strip()
        if not body.strip() and not title:
            continue
        must = title.lower().startswith("check")
        items, paras = [], []
        for line in body.splitlines():
            m = re.match(r"^\s*[-*]\s+(.*)", line)
            if m:
                n += 1
                items.append(f'<li><input type="checkbox" id="r{n}" aria-label="Done"><span>{inline_md(m.group(1))}</span></li>')
                must_count += must
            elif line.strip():
                paras.append(f"<p>{inline_md(line)}</p>")
        inner = f"<h3>{html.escape(title)}</h3>{''.join(paras)}" + (f"<ul>{''.join(items)}</ul>" if items else "")
        parts.append(f'<div class="must">{inner}</div>' if must else f"<div>{inner}</div>")
    return "".join(parts), must_count


def main():
    friday = date.fromisoformat(sys.argv[1])
    f = friday.isoformat()
    run = ROOT / "runs" / f
    draft = (ROOT / "drafts" / f"{f}.md").read_text()
    review_path = ROOT / "drafts" / f"{f}.review.md"
    review_md = review_path.read_text() if review_path.exists() else ""
    enrich = json.loads((run / "enrich.json").read_text()) if (run / "enrich.json").exists() else {}
    wx = json.loads((run / "weather.json").read_text()) if (run / "weather.json").exists() else {}

    subject = re.search(r"SUBJECT LINE:\s*(.+)", draft)
    preview = re.search(r"PREVIEW TEXT:\s*(.+)", draft)
    body = re.sub(r"<!--\s*\n?\s*SUBJECT LINE:.*?-->", "", draft, count=1, flags=re.S)

    line = wx.get("line")
    def weather_sub(m):
        return f'\n<p class="weather">{html.escape(line or m.group(1))}</p>\n'
    body = re.sub(r"<!-- weather -->(.*?)<!-- /weather -->", weather_sub, body, flags=re.S)

    cards = 0
    def photos_sub(m):
        nonlocal cards
        cards += 1
        return photo_block(m.group(1), int(m.group(2) or 1), enrich, run)
    body = re.sub(r"<!--\s*photos:([\w-]+)(?::(\d+))?\s*-->", photos_sub, body)
    issue = markdown.markdown(body, extensions=["extra", "sane_lists", "nl2br"])

    rev, checks = review_html(review_md)
    asof = wx.get("fetched")
    asof_label = date.fromisoformat(asof).strftime("%a %b %-d") if asof else "unknown"

    page = (ROOT / "editor" / "page_template.html").read_text()
    repl = {
        "__WEEKEND__": weekend_label(friday),
        "__FRIDAY__": f,
        "__BUILT_AT__": datetime.now(PT).strftime("%a %b %-d, %-I:%M %p"),
        "__CHECK_COUNT__": f"{checks} to check" if checks else "Nothing to check",
        "__CHECK_CLASS__": "warn" if checks else "",
        "__CARD_COUNT__": f"{cards} lineup cards",
        "__FORECAST_ASOF__": asof_label,
        "__SUBJECT__": html.escape(subject.group(1).strip() if subject else ""),
        "__PREVIEW__": html.escape(preview.group(1).strip() if preview else ""),
        "__REVIEW_HTML__": rev,
        "__ISSUE_HTML__": issue,
    }
    for k, v in repl.items():
        page = page.replace(k, v)
    out = ROOT / "build" / f"{f}.html"
    out.parent.mkdir(exist_ok=True)
    out.write_text(page)
    print(f"{out}  ({out.stat().st_size / 1e6:.1f} MB, {cards} cards, {checks} to check)")


if __name__ == "__main__":
    main()
