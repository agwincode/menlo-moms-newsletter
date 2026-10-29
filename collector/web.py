"""Shared page-fetching helpers for the collector and the enrich step.

Strategy: try a plain HTTP fetch first (fast, and it gets past the bot checks that
flag headless browsers), then fall back to a headless browser only when the page
is blocked or comes back too thin to use.
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass, field, asdict
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36"
)
HEADERS = {
    "User-Agent": UA,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

BLOCK_SIGNALS = [
    "access denied", "just a moment", "checking your browser",
    "cf-browser-verification", "attention required", "please verify you are a human",
    "verify you are human", "request unsuccessful", "incapsula", "403 forbidden",
]
BLOCK_STATUS = {401, 403, 405, 406, 429, 503}

THIN_CHARS = 800          # less readable text than this = not usable
MAX_TEXT_CHARS = 40000    # cap what we store per page
MAX_LINKS = 300

# Ticketing hosts render availability with JavaScript; always use the browser.
BROWSER_HOSTS = (
    "showare.com", "eventbrite.", "ticketmaster.", "universe.com", "tix.com",
    "ticketleap.", "brownpapertickets.", "perfectmind.com", "bibliocommons.com",
    "macaronikid.com", "axs.com", "seetickets.", "etix.com", "simpletix.",
)


@dataclass
class Page:
    url: str
    final_url: str = ""
    method: str = ""            # direct | browser
    status: str = "error"       # ok | thin | blocked | error
    http_status: int | None = None
    title: str = ""
    og_image: str = ""
    image_candidates: list = field(default_factory=list)
    text: str = ""
    links: list = field(default_factory=list)
    error: str = ""
    attempts: list = field(default_factory=list)

    def to_dict(self):
        return asdict(self)


def needs_browser(url: str) -> bool:
    host = urlparse(url).netloc.lower()
    return any(h in host for h in BROWSER_HOSTS)


def parse_html(html: str, base_url: str) -> dict:
    soup = BeautifulSoup(html, "lxml")

    def meta(*names):
        for n in names:
            tag = soup.find("meta", attrs={"property": n}) or soup.find("meta", attrs={"name": n})
            if tag and tag.get("content"):
                return urljoin(base_url, tag["content"].strip())
        return ""

    og_image = meta("og:image", "og:image:url", "twitter:image", "twitter:image:src")
    if re.search(r"(blank|spacer|pixel)\.(gif|png)", og_image, re.I):
        og_image = ""
    og_title = soup.find("meta", attrs={"property": "og:title"})
    title = (og_title.get("content") if og_title else "") or \
        (soup.title.string.strip() if soup.title and soup.title.string else "")

    for tag in soup(["script", "style", "noscript", "svg", "iframe", "template"]):
        tag.decompose()

    root = soup.find("main") or soup.find(attrs={"role": "main"}) or soup.body or soup

    images = []
    for img in root.find_all("img"):
        src = img.get("src") or img.get("data-src") or ""
        if not src or src.startswith("data:") or re.search(r"(logo|icon|sprite|avatar|pixel|blank\.gif|spacer)", src, re.I):
            continue
        images.append(urljoin(base_url, src))
        if len(images) >= 5:
            break

    links, seen = [], set()
    for a in (soup.body or soup).find_all("a", href=True):
        href = a["href"].strip()
        if href.startswith(("mailto:", "tel:", "javascript:", "#")):
            continue
        href = urljoin(base_url, href).split("#")[0]
        label = " ".join(a.get_text(" ").split())[:100]
        if not label or href in seen:
            continue
        seen.add(href)
        links.append({"text": label, "href": href})
        if len(links) >= MAX_LINKS:
            break

    text = root.get_text("\n")
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n", text).strip()

    return {
        "title": (title or "").strip()[:200],
        "og_image": og_image,
        "image_candidates": images,
        "text": text[:MAX_TEXT_CHARS],
        "links": links,
    }


def classify(http_status: int | None, text: str) -> str:
    low = text[:6000].lower()
    if http_status in BLOCK_STATUS:
        return "blocked"
    if len(text) < 5000 and any(s in low for s in BLOCK_SIGNALS):
        return "blocked"
    if http_status and http_status >= 400:
        return "error"
    if len(text) < THIN_CHARS:
        return "thin"
    return "ok"


def direct_fetch(url: str, retries: int = 2) -> Page:
    page = Page(url=url, method="direct")
    for attempt in range(retries + 1):
        try:
            r = requests.get(url, headers=HEADERS, timeout=30, allow_redirects=True)
            page.http_status = r.status_code
            page.final_url = r.url
            parsed = parse_html(r.text, r.url)
            for k, v in parsed.items():
                setattr(page, k, v)
            page.status = classify(r.status_code, page.text)
            page.error = ""
            if page.status in ("ok", "thin", "blocked") or r.status_code == 404:
                return page
        except Exception as e:  # network errors, timeouts
            page.status, page.error = "error", f"{type(e).__name__}: {e}"[:300]
        time.sleep(2 * (attempt + 1))
    return page


class Browser:
    """One headless Chromium shared across many pages."""

    def __enter__(self):
        from playwright.sync_api import sync_playwright
        self._pw = sync_playwright().start()
        self._browser = self._pw.chromium.launch(headless=True)
        self._ctx = self._browser.new_context(user_agent=UA, viewport={"width": 1440, "height": 1000},
                                              locale="en-US", timezone_id="America/Los_Angeles")
        self._ctx.add_init_script("Object.defineProperty(navigator,'webdriver',{get:()=>undefined})")
        return self

    def __exit__(self, *exc):
        try:
            self._browser.close()
        finally:
            self._pw.stop()

    def fetch(self, url: str) -> Page:
        page = Page(url=url, method="browser")
        tab = self._ctx.new_page()
        try:
            resp = None
            try:
                resp = tab.goto(url, wait_until="domcontentloaded", timeout=60000)
            except Exception:
                resp = tab.goto(url, wait_until="commit", timeout=45000)
            try:
                tab.wait_for_load_state("networkidle", timeout=15000)
            except Exception:
                pass
            tab.wait_for_timeout(3000)  # let ticket widgets and calendars hydrate
            page.http_status = resp.status if resp else None
            page.final_url = tab.url
            parsed = parse_html(tab.content(), tab.url)
            for k, v in parsed.items():
                setattr(page, k, v)
            page.status = classify(page.http_status, page.text)
        except Exception as e:
            page.status, page.error = "error", f"{type(e).__name__}: {e}"[:300]
        finally:
            tab.close()
        return page


LARGEST_IMAGES_JS = """
() => {
  const out = [];
  const seen = new Set();
  for (const el of document.querySelectorAll('img, picture, [style*="background-image"]')) {
    const r = el.getBoundingClientRect();
    if (r.width < 280 || r.height < 160) continue;
    const top = r.top + window.scrollY;
    if (top > 2600) continue;
    const src = el.currentSrc || el.src || getComputedStyle(el).backgroundImage || '';
    if (/logo|icon|sprite|avatar/i.test(src)) continue;
    const key = Math.round(r.left) + ':' + Math.round(top);
    if (seen.has(key)) continue;
    seen.add(key);
    out.push({i: out.length, area: r.width * r.height, top, src: src.slice(0, 500)});
    el.setAttribute('data-mm-photo', String(out.length - 1));
  }
  return out.sort((a, b) => b.area - a.area).slice(0, 3);
}
"""


def _save_jpeg(data: bytes, path, max_side: int = 1200) -> dict | None:
    """Normalize any image bytes to a reasonably sized JPEG. Returns size info or None."""
    import io
    from PIL import Image
    try:
        im = Image.open(io.BytesIO(data))
        im.load()
    except Exception:
        return None
    if im.width < 250 or im.height < 140:
        return None  # too small to use as a card photo
    if im.mode not in ("RGB", "L"):
        bg = Image.new("RGB", im.size, (255, 255, 255))
        im = im.convert("RGBA")
        bg.paste(im, mask=im.split()[-1])
        im = bg
    im = im.convert("RGB")
    im.thumbnail((max_side, max_side))
    path.parent.mkdir(parents=True, exist_ok=True)
    im.save(path, "JPEG", quality=80, optimize=True, progressive=True)
    return {"w": im.width, "h": im.height}


def capture_photos(browser: "Browser", url: str, outdir, og_image: str = "") -> list:
    """Up to 4 photo options for an event card, like the ones Angela picks by hand:
    the page's share image, its biggest images/flyers, and a screenshot of the top of the page."""
    from pathlib import Path
    outdir = Path(outdir)
    photos, n = [], 0

    def add(data, kind, source):
        nonlocal n
        n += 1
        f = outdir / f"{n}.jpg"
        info = _save_jpeg(data, f)
        if info:
            photos.append({"file": f.as_posix(), "kind": kind, "source": source, **info})
        else:
            n -= 1

    tab = browser._ctx.new_page()
    try:
        try:
            tab.goto(url, wait_until="domcontentloaded", timeout=60000)
        except Exception:
            tab.goto(url, wait_until="commit", timeout=45000)
        try:
            tab.wait_for_load_state("networkidle", timeout=15000)
        except Exception:
            pass
        tab.wait_for_timeout(2500)
        if og_image:
            try:
                r = tab.request.get(og_image, timeout=20000)
                if r.ok:
                    add(r.body(), "share image", og_image)
            except Exception:
                pass
        try:
            for item in tab.evaluate(LARGEST_IMAGES_JS):
                el = tab.query_selector(f'[data-mm-photo="{item["i"]}"]')
                if el:
                    try:
                        add(el.screenshot(timeout=10000), "image on page", item["src"][:300] if item["src"].startswith("http") else url)
                    except Exception:
                        pass
                if len(photos) >= 3:
                    break
        except Exception:
            pass
        try:
            add(tab.screenshot(clip={"x": 0, "y": 0, "width": 1440, "height": 900}), "top of page", url)
        except Exception:
            pass
    except Exception:
        pass
    finally:
        tab.close()
    return photos


def fetch(url: str, mode: str = "auto", browser: Browser | None = None) -> Page:
    """mode: auto | browser. Returns the best result, with every attempt recorded."""
    rank = {"ok": 3, "thin": 2, "blocked": 1, "error": 0}
    attempts, best = [], None
    if mode != "browser" and not needs_browser(url):
        best = direct_fetch(url)
        attempts.append(f"direct:{best.status}:{best.http_status or best.error[:60]}")
        if best.status == "ok" or browser is None:
            best.attempts = attempts
            return best
    if browser is None:
        return Page(url=url, status="error", error="browser required but not available", attempts=attempts)
    b = browser.fetch(url)
    attempts.append(f"browser:{b.status}:{b.http_status or b.error[:60]}")
    if best is None or rank[b.status] >= rank[best.status]:
        best = b
    best.attempts = attempts
    return best
