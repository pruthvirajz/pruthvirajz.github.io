"""Pull the latest posts from the Substack RSS feed into the Blog list in index.html.

New posts are added at the top. Posts already on the page stay where they are,
even if they have dropped out of the feed (Substack's feed only lists recent posts).
"""
import html
import re
import sys
import urllib.request
import xml.etree.ElementTree as ET

FEED_URL = "https://lifeofthelaw.substack.com/feed"
PAGE = "index.html"
LIST_RE = re.compile(r'(<ul class="posts">)(.*?)(\n(\s*)</ul>)', re.S)
LINK_RE = re.compile(r'<li><a href="([^"]+)"')


def clean(url):
    return url.split("?")[0].rstrip("/")


def fetch_feed(source):
    if source.startswith("http"):
        req = urllib.request.Request(source, headers={"User-Agent": "Mozilla/5.0 (blog-sync)"})
        with urllib.request.urlopen(req, timeout=30) as r:
            data = r.read()
    else:
        with open(source, "rb") as f:
            data = f.read()
    posts = []
    for item in ET.fromstring(data).iter("item"):
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        if title and link:
            posts.append((clean(link), title))
    return posts  # newest first, as Substack lists them


def main(source=FEED_URL):
    posts = fetch_feed(source)
    with open(PAGE, encoding="utf-8") as f:
        page = f.read()

    m = LIST_RE.search(page)
    if not m:
        sys.exit("Could not find <ul class=\"posts\"> in index.html")
    body = m.group(2)
    existing = {clean(u) for u in LINK_RE.findall(body)}

    new = [(u, t) for u, t in posts if u not in existing]
    if not new:
        print("No new posts.")
        return

    indent = m.group(4) + "  "
    new_lines = "".join(
        f'\n{indent}<li><a href="{html.escape(u)}" target="_blank" rel="noopener">{html.escape(t, quote=False)}</a></li>'
        for u, t in new
    )
    # Insert new posts after the "TO ADD A POST" comment if present, else at the top.
    comment = re.search(r"\n\s*<!--.*?-->", body, re.S)
    cut = comment.end() if comment else 0
    body = body[:cut] + new_lines + body[cut:]

    page = page[: m.start(2)] + body + page[m.end(2):]
    with open(PAGE, "w", encoding="utf-8") as f:
        f.write(page)
    for u, t in new:
        print("Added:", t)


if __name__ == "__main__":
    main(*sys.argv[1:])
