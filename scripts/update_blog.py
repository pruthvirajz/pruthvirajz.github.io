"""Add new Substack posts to the Blog list in index.html.

Substack blocks GitHub's servers, so the script tries several routes to read
the feed and uses the first one that works.
"""
import html
import json
import re
import subprocess
import sys
import time
import urllib.parse
import urllib.request

FEED = "https://lifeofthelaw.substack.com/feed"
PAGE = "index.html"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"
Q = urllib.parse.quote(FEED, safe="")
LIST_RE = re.compile(r'(<ul class="posts">)(.*?)(\n(\s*)</ul>)', re.S)
LINK_RE = re.compile(r'<li><a href="([^"]+)"')
ITEM_RE = re.compile(r"<item>(.*?)</item>", re.S)


def clean(url):
    return url.split("?")[0].rstrip("/")


def strip_cdata(s):
    s = s.strip()
    if s.startswith("<![CDATA["):
        s = s[9:-3]
    return html.unescape(s.strip())


def parse_rss(text):
    """Pull (link, title) pairs out of RSS text, newest first."""
    if isinstance(text, bytes):
        text = text.decode("utf-8", "replace")
    posts = []
    for item in ITEM_RE.findall(text):
        t = re.search(r"<title>(.*?)</title>", item, re.S)
        l = re.search(r"<link>(.*?)</link>", item, re.S)
        if t and l:
            link = strip_cdata(l.group(1))
            if "substack.com/p/" in link:
                posts.append((clean(link), strip_cdata(t.group(1))))
    return posts


def get(url, headers=None):
    h = {"User-Agent": UA, "Accept": "application/rss+xml, application/xml, text/xml, */*"}
    h.update(headers or {})
    with urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=40) as r:
        return r.read()


def direct():
    return parse_rss(get(FEED))


def curl():
    out = subprocess.run(
        ["curl", "-sSL", "--fail", "--compressed", "-A", UA, "-H", "Accept-Language: en-GB,en;q=0.9", FEED],
        capture_output=True, timeout=60,
    )
    if out.returncode:
        raise RuntimeError(out.stderr.decode()[-200:])
    return parse_rss(out.stdout)


def rss2json():
    data = json.loads(get(f"https://api.rss2json.com/v1/api.json?rss_url={Q}"))
    if data.get("status") != "ok":
        raise RuntimeError(data.get("message", "error"))
    return [(clean(i["link"]), i["title"].strip()) for i in data["items"]]


def jina():
    return parse_rss(get(f"https://r.jina.ai/{FEED}", {"X-Return-Format": "html"}))


def codetabs():
    return parse_rss(get(f"https://api.codetabs.com/v1/proxy/?quest={FEED}"))


def corsproxy():
    return parse_rss(get(f"https://corsproxy.io/?url={Q}"))


def allorigins():
    return parse_rss(json.loads(get(f"https://api.allorigins.win/get?url={Q}"))["contents"])


ROUTES = [direct, curl, rss2json, jina, codetabs, corsproxy, allorigins]


def fetch_posts(source=None):
    if source:  # local test file
        with open(source, "rb") as f:
            return parse_rss(f.read())
    errors = []
    for attempt in range(2):
        for fn in ROUTES:
            try:
                posts = fn()
                if posts:
                    print(f"Feed read via {fn.__name__} ({len(posts)} posts)")
                    return posts
                errors.append(f"{fn.__name__}: no posts found")
            except Exception as e:
                errors.append(f"{fn.__name__}: {e}")
        time.sleep(20)
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
