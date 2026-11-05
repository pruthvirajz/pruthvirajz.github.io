"""Add new Substack posts to the Blog list in index.html.

Substack blocks GitHub's servers, so if the direct feed is refused the
script fetches it through public feed relays instead.
"""
import html
import json
import re
import sys
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

FEED = "https://lifeofthelaw.substack.com/feed"
PAGE = "index.html"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"
LIST_RE = re.compile(r'(<ul class="posts">)(.*?)(\n(\s*)</ul>)', re.S)
LINK_RE = re.compile(r'<li><a href="([^"]+)"')


def clean(url):
    return url.split("?")[0].rstrip("/")


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read()


def parse_rss(data):
    posts = []
    for item in ET.fromstring(data).iter("item"):
        t, l = (item.findtext("title") or "").strip(), (item.findtext("link") or "").strip()
        if t and l:
            posts.append((clean(l), t))
    return posts


def via_direct():
    return parse_rss(get(FEED))


def via_rss2json():
    data = json.loads(get("https://api.rss2json.com/v1/api.json?rss_url=" + urllib.parse.quote(FEED, safe="")))
    if data.get("status") != "ok":
        raise RuntimeError(data.get("message", "rss2json error"))
    return [(clean(i["link"]), i["title"].strip()) for i in data["items"] if i.get("title") and i.get("link")]


def via_allorigins():
    return parse_rss(get("https://api.allorigins.win/raw?url=" + urllib.parse.quote(FEED, safe="")))


def fetch_posts(source=None):
    if source:  # local test file
        with open(source, "rb") as f:
            return parse_rss(f.read())
    errors = []
    for fn in (via_direct, via_rss2json, via_allorigins):
        try:
            posts = fn()
            if posts:
                print(f"Feed read via {fn.__name__} ({len(posts)} posts)")
                return posts
            errors.append(f"{fn.__name__}: empty")
        except Exception as e:
            errors.append(f"{fn.__name__}: {e}")
    sys.exit("Could not read the Substack feed:\n  " + "\n  ".join(errors))


def main(source=None):
    posts = fetch_posts(source)
    with open(PAGE, encoding="utf-8") as f:
        page = f.read()
    m = LIST_RE.search(page)
    if not m:
        sys.exit('Could not find <ul class="posts"> in index.html')
    body = m.group(2)
    existing = {clean(u) for u in LINK_RE.findall(body)}
    new = [(u, t) for u, t in posts if u not in existing]
    if not new:
        print("No new posts.")
        return
    indent = m.group(4) + "  "
    lines = "".join(
        f'\n{indent}<li><a href="{html.escape(u)}" target="_blank" rel="noopener">{html.escape(t, quote=False)}</a></li>'
        for u, t in new
    )
    c = re.search(r"\n\s*<!--.*?-->", body, re.S)
    cut = c.end() if c else 0
    body = body[:cut] + lines + body[cut:]
    with open(PAGE, "w", encoding="utf-8") as f:
        f.write(page[: m.start(2)] + body + page[m.end(2):])
    for u, t in new:
        print("Added:", t)


if __name__ == "__main__":
    main(*sys.argv[1:])
