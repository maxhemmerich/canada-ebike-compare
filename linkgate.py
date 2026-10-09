"""Resolve every link a generated page carries - not only the ones that are href/src.

Found by hand on the live site 2026-10-09, not by the build: the range picker's result cards are built in
JavaScript from the "url" fields of their own JSON data block, and those fields were written as site-root
paths, so served from /how-far/ both links on every card were 404s. The first gate (added in build.py that
day) saw literal href/src and that one JSON block. It could not see the links that never appear as
href/src in the stripped HTML:

  * the content of <meta property="og:image"> / <meta name="twitter:image"> - the share card,
  * <link rel="canonical">,
  * any srcset candidate,
  * every "url" and "@id" inside a <script type="application/ld+json"> block.

A page whose only bad link is in its share card is still a page that shares a 404, so all of them are
swept here, and a canonical that does not name the page it sits on stops the build.

Internal targets - a relative reference, a srcset candidate, our own absolute site URL, a JSON-LD url/@id,
or a host-root path that really is this site's own path - must land on a file that exists in the tree.
Off-site absolute URLs (a maker's page, a government's page) are not this gate's business: they are not in
our tree, and whether they answer is checked in a browser, by hand, not here.

The whole sweep is a function so it can be run on its own against any tree:

    py -3.10 linkgate.py <root> <site-url>

which is exactly how it is shown to fail on a deliberately corrupted copy and pass on the real one.
"""
import html
import json
import os
import posixpath
import re
from urllib.parse import urlsplit

# A script body is code, not markup: an inline template like '<a href="' + m.url + '">' would otherwise be
# read as a link of its own. Strip every script element before the literal sweep; the JSON block check below
# covers the one data block whose values ARE links.
SCRIPT_RE = re.compile(r"<script\b[^>]*>.*?</script>", re.S)
HREF_SRC_RE = re.compile(r'(?<![\w-])(?:href|src)="([^"]*)"')
SRCSET_RE = re.compile(r'(?<![\w-])srcset="([^"]*)"')
# og:image / twitter:image are the share card; og:url is the page's own social URL. All three are absolute
# URLs our own site serves, and none of them is an href or a src.
META_URL_RE = re.compile(
    r'<meta\s+(?:property|name)="(?:og:image|twitter:image|og:url)"\s+content="([^"]*)"')
CANON_RE = re.compile(r'<link\s+rel="canonical"\s+href="([^"]*)"')
JSON_BLOCK_RE = re.compile(
    r'<script\b[^>]*\btype="application/(?:ld\+)?json"[^>]*>(.*?)</script>', re.S)
# Not ours to resolve: a fragment, a protocol-relative URL, or a scheme that is not a tree path.
SKIP_PREFIXES = ("#", "//", "mailto:", "tel:", "data:", "javascript:", "sms:")


def _tree_path(page, ref):
    """Where one reference lands inside the built tree, as a posix path ('' == the root)."""
    t = posixpath.normpath(posixpath.join(page, ref))
    return "" if t in (".", "/", "") else t.lstrip("/")


def _exists(root, target):
    full = os.path.join(root, *[x for x in target.split("/") if x])
    if os.path.isdir(full):
        full = os.path.join(full, "index.html")
    return os.path.isfile(full)


def _classify(site, site_path, ref):
    """('rel', ref) resolve from the page dir | ('abs', tree_path) our own site URL |
    ('problem', why) a reference that can only 404 here | None when it is not ours to resolve."""
    if not ref or ref.startswith(SKIP_PREFIXES):
        return None
    if ref.startswith(("http://", "https://")):
        if ref == site:
            return ("abs", "")
        if ref.startswith(site + "/"):
            return ("abs", ref[len(site) + 1:].split("#", 1)[0])
        return None
    if ref.startswith("/"):
        # A host-root path resolves against the host, not this site's own path. This site is served from a
        # subpath, so "/guide/" is a 404 live even though guide/index.html exists in the tree - the exact
        # shape of the bug this gate was built for. Only a path that really is this site's own path is kept.
        if ref == site_path or ref.startswith(site_path + "/"):
            return ("rel", ref[len(site_path):].split("#", 1)[0])
        return ("problem", "site-root path %r, but this site is served from %r" % (ref, site_path + "/"))
    return ("rel", ref.split("#", 1)[0])


def _urls_from(obj):
    """Every string under a "url" or "@id" key, anywhere in a parsed JSON block."""
    out = []
    if isinstance(obj, dict):
        for key, val in obj.items():
            if key in ("url", "@id") and isinstance(val, str):
                out.append(val)
            else:
                out.extend(_urls_from(val))
    elif isinstance(obj, list):
        for val in obj:
            out.extend(_urls_from(val))
    return out


def check(root, pages, site):
    """Sweep every page. Raise AssertionError listing every bad reference, else return (links, pages)."""
    site = site.rstrip("/")
    site_path = urlsplit(site).path.rstrip("/")
    links = 0
    problems = []

    for page in pages:
        page = (page or "").strip("/")
        fpath = os.path.join(root, page, "index.html")
        text = open(fpath, encoding="utf-8").read()
        stem = (page + "/index.html") if page else "index.html"
        body = SCRIPT_RE.sub("", text)  # markup only; a script body is code

        def land(ref, kind=""):
            nonlocal links
            if not isinstance(ref, str):
                return
            ref = html.unescape(ref)
            cls = _classify(site, site_path, ref)
            if cls is None:
                return
            if cls[0] == "problem":
                problems.append("%s: %s%s" % (stem, kind, cls[1]))
                return
            target = cls[1] if cls[0] == "abs" else _tree_path(page, cls[1])
            links += 1
            if not _exists(root, target):
                problems.append("%s: %s%r lands on %r, which is not in the tree" % (stem, kind, ref, target))

        # 1. literal href / src
        for ref in HREF_SRC_RE.findall(body):
            land(ref)
        # 2. every srcset candidate (the URL is the first token before the width/density descriptor)
        for attr in SRCSET_RE.findall(body):
            for cand in attr.split(","):
                cand = cand.strip()
                if cand:
                    land(cand.split(" ")[0], "srcset ")
        # 3. the share card and social URL
        for ref in META_URL_RE.findall(text):
            land(ref, "meta url ")
        # 4. canonical - and it must be this page's own URL, exactly
        want = "%s/%s" % (site, (page + "/") if page else "")
        for ref in CANON_RE.findall(text):
            ref_u = html.unescape(ref)
            if ref_u != want:
                problems.append("%s: canonical %r is not this page's own URL %r" % (stem, ref_u, want))
            land(ref_u, "canonical ")
        # 5. every url/@id inside a JSON data block (the picker's data, or JSON-LD)
        for block in JSON_BLOCK_RE.findall(text):
            try:
                data = json.loads(block)
            except ValueError:
                problems.append("%s: a JSON data block does not parse" % stem)
                continue
            for ref in _urls_from(data):
                land(ref, "JSON ")

    if problems:
        raise AssertionError("link gate: %d bad reference(s)\n  %s"
                             % (len(problems), "\n  ".join(problems)))
    return links, len(pages)


def discover_pages(root):
    """Every page in a tree: the root if it holds index.html, plus every subdir that does."""
    pages = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d != ".git"]
        if "index.html" in filenames:
            rel = os.path.relpath(dirpath, root).replace("\\", "/")
            pages.append("" if rel == "." else rel)
    return sorted(pages)


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 3:
        print("usage: py -3.10 linkgate.py <root> <site-url>")
        raise SystemExit(2)
    _root, _site = sys.argv[1], sys.argv[2]
    _pages = discover_pages(_root)
    _links, _n = check(_root, _pages, _site)
    print("linkgate: %d references over %d pages, all landing inside the tree" % (_links, _n))
