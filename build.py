#!/usr/bin/env python
# build.py — generates index.html and the decision-guide PDF from data/products.json.
# Render with:  py -3.10 build.py
import json, os, html, re

ROOT = os.path.dirname(os.path.abspath(__file__))
DATA = json.load(open(os.path.join(ROOT, "data", "products.json"), encoding="utf-8"))
PRODUCTS = DATA["products"]
BY_ID = {p["id"]: p for p in PRODUCTS}
CHECKED = DATA["checked_on"]

# ---------------------------------------------------------------- counting (no account, no vendor SDK, no cookie)
# This lane lives on organic search traffic and had no way to tell whether it gets any. It is measured
# with one free counter that needs no account, no signup and no API key — Abacus
# (https://abacus.jasoncameron.dev, "Integer as a Service"; every response is CORS-enabled):
#   GET /hit/<namespace>/<key>  -> increment by one, answer {"value": N} (creates the key on first hit)
#   GET /get/<namespace>/<key>  -> read only, never increments; 404 {"error":"Key not found"} if absent
# Measured live before this was wired (2026-10-08): 404 -> hit x3 -> {1,2,3} -> get {3} -> get {3}
# (a read does not move the number) -> hit -> {4}; /info said is_genuine true, TTL 4031h59m59s.
# Rejected on measurement, not assumption: counterapi.dev v1 -> 410 Gone, its v2 -> 404 "Workspace not
# found" (it wants a registered workspace), countapi.xyz -> no response at all, visitorbadge -> 403.
#
# What is sent: one anonymous GET per page load, naming the PAGE. No cookie (credentials: omit), no
# referring page (referrerPolicy: no-referrer), no visitor id, no fingerprint — nothing that identifies
# a person. As with any HTTP request, the counter service necessarily sees the requesting IP address.
# What is counted: page loads that ran JavaScript. A load with scripting off is not counted; software
# that renders pages and runs scripts — including a crawler that does — is. So the number is a floor,
# never a census, and /stats/ says so in those words.
# Keys expire after 6 months of no access; the /stats/ page reads every key, which resets that clock.
METRIC_HOST = "abacus.jasoncameron.dev"
METRIC_BASE = "https://" + METRIC_HOST
METRIC_NS = "maxhemmerich.github.io"    # the service's own advice: use the site's domain as namespace
METRIC_PREFIX = "canada-ebike-compare"  # this repo's slug, so no other site on this host can collide

def metric_key(segment):
    """One counter key per generated page. The service allows ^[A-Za-z0-9_-.]{3,64}$; asserted here."""
    key = "%s-%s" % (METRIC_PREFIX, segment)
    assert re.match(r"^[A-Za-z0-9_.-]{3,64}$", key), "counter key outside the service's charset: %r" % key
    return key

def track_js(segment):
    """The beacon, as one string. Invisible by construction: no element, no class, no styles — nothing
    that can appear in the page's layout or disturb its one theme. One fire-and-forget GET per load."""
    return (
        '<script>\n'
        '/* Page-view count. One anonymous increment, read back on the stats page. */\n'
        '(function(){\n'
        '  try{\n'
        '    fetch("%s/hit/%s/%s", {mode:"no-cors", cache:"no-store", credentials:"omit",\n'
        '      referrerPolicy:"no-referrer", keepalive:true});\n'
        '  }catch(e){}\n'
        '})();\n'
        '</script>\n' % (METRIC_BASE, METRIC_NS, metric_key(segment)))

def write_page(path, html_text, segment):
    """THE one write path for every generated HTML page. A page cannot be written without its beacon,
    and a page with no </body> cannot be written either: both are asserted before the file is touched."""
    assert html_text.count("</body>") == 1, "%s: not exactly one </body> (found %d)" % (
        path, html_text.count("</body>"))
    out = html_text.replace("</body>", track_js(segment) + "</body>")
    beacon = "%s/hit/%s/%s" % (METRIC_BASE, METRIC_NS, metric_key(segment))
    assert out.count(beacon) == 1, "%s: beacon not inserted exactly once" % path
    os.makedirs(os.path.dirname(path), exist_ok=True)
    open(path, "w", encoding="utf-8").write(out)
    print("wrote %s" % os.path.relpath(path, ROOT).replace(os.sep, "/"))

# ---------------------------------------------------------------- order
# ONE deterministic order for every list of the bikes, on the page and in the PDF.
# The table caption promises cheapest-to-dearest, so sort by price ascending. Three models
# tie at CA$2,699, so ties break by model name A-Z and then by id: the same data always
# builds the identical page (no reliance on the order rows happen to sit in products.json).
ORDER = sorted(PRODUCTS, key=lambda p: (p["price_cad"], p["model"].lower(), p["id"]))
TIE_NOTE = "equal-price bikes A-Z"

# ---------------------------------------------------------------- catalog size + price span (derived, never typed)
# The copy names how many bikes are on the page and the price span they cover. Both are DERIVED from
# data/products.json, so adding or removing a model cannot leave "five" or "CA$1,899 to CA$2,699"
# stranded in the page as a false statement. A row in the data is the only edit an addition needs.
N = len(PRODUCTS)
_N_WORDS = {1: "one", 2: "two", 3: "three", 4: "four", 5: "five", 6: "six",
            7: "seven", 8: "eight", 9: "nine", 10: "ten", 11: "eleven", 12: "twelve"}
assert N in _N_WORDS, "add a word for %d models to _N_WORDS" % N
N_WORD = _N_WORDS[N]
N_WORD_CAP = N_WORD.capitalize()

def _cad(n):
    return "CA$%s" % format(n, ",d")

_PRICE_LO = _cad(min(p["price_cad"] for p in PRODUCTS))
_PRICE_HI = _cad(max(p["price_cad"] for p in PRODUCTS))
PRICE_SPAN = "%s to %s" % (_PRICE_LO, _PRICE_HI)
PRICE_SPAN_DASH = "%s-%s" % (_PRICE_LO, _PRICE_HI)

# ---------------------------------------------------------------- published-range table
# Used by the "how far will it go" picker. This is the only hand-made table in the build, so it is
# guarded twice, and it is checked HERE - before a single file is written - so a drifted figure stops
# the build instead of leaving a half-written site behind:
#   1. it must cover exactly the models in products.json, and
#   2. every number in it must appear literally in that model's published `range` string.
# There is no derating factor and no "hills cost you 20%" rule anywhere: where a maker publishes a
# single figure, the picker says exactly that rather than inventing a lower one.
RANGE_PARSE = {
    "radster-road": dict(
        high=104, low=40, low_label="bottom of the maker's range",
        high_from='the top of the maker\'s published range "40-104 km (maker estimate)"',
        low_from='the bottom of the maker\'s published range "40-104 km (maker estimate)"'),
    "radkick-7speed": dict(
        high=56, low=24, low_label="bottom of the maker's range",
        high_from='the top of the maker\'s published range "24-56 km (maker estimate)"',
        low_from='the bottom of the maker\'s published range "24-56 km (maker estimate)"'),
    "velotric-tempo": dict(
        high=97, low=None, low_label=None,
        high_from='the maker\'s single published figure "up to 97 km (maker estimate)"',
        low_from=None),
    "velotric-discover-3": dict(
        high=129, low=105, low_label="throttle only, from the maker's 105 km figure",
        high_from='the maker\'s published pedal-assist figure "129 km PAS / 105 km throttle (maker)"',
        low_from='the maker\'s published throttle-only figure "105 km"'),
    "surface604-rook": dict(
        high=150, low=None, low_label=None,
        high_from='the maker\'s single published figure "up to 150 km (maker, eco mode)"',
        low_from=None),
    "aventon-soltera-2-5": dict(
        high=74, low=None, low_label=None,
        high_from='the maker\'s published "Up to 46 Miles", converted to km (1 mi = 1.609344 km); their footnote names Eco mode and a 75 kg rider',
        low_from=None),
    "ohm-cruise-3": dict(
        high=150, low=None, low_label=None,
        high_from='the maker\'s own product-page feature tile "150km Freedom"; the specification table publishes no range figure',
        low_from=None),
}
_RANGE_TOKENS = {"radster-road": ("104", "40"), "radkick-7speed": ("56", "24"),
                 "velotric-tempo": ("97",), "velotric-discover-3": ("129", "105"),
                 "surface604-rook": ("150",), "aventon-soltera-2-5": ("74", "46"),
                 "ohm-cruise-3": ("150",)}
assert set(RANGE_PARSE) == {q["id"] for q in PRODUCTS} == set(_RANGE_TOKENS), \
    "the range table is out of step with data/products.json"
for _pid, _toks in _RANGE_TOKENS.items():
    _src = BY_ID[_pid]["range"]
    for _t in _toks:
        assert _t in _src, "figure %s is not in the published range string for %s: %r" % (_t, _pid, _src)

def esc(s):
    return html.escape(str(s), quote=True)

# ---------------------------------------------------------------- head-to-head pairs
# The buyer queries this site has no page for yet: a shopper weighing up two specific bikes. A pair is
# just two ids already in data/products.json; each pair becomes ONE page at vs/<slug-a>-vs-<slug-b>/,
# two columns, every cell a field already published on those models' own pages. The URL slug is
# derived from each model's own name, so it cannot be hand-typed out of step with the data and two
# models cannot share a segment. Some pairs cover the closest calls on the comparison table.
def _slug(name):
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", name.lower())).strip("-")

MODEL_SLUG = {p["id"]: _slug(p["model"]) for p in ORDER}
assert len(set(MODEL_SLUG.values())) == len(ORDER), \
    "two models slug to the same URL segment: %s" % sorted(MODEL_SLUG.values())

# Ordered: this order is the page order and the sitemap order.
PAIRS = [
    ("velotric-discover-3", "surface604-rook"),   # "Discover 3 vs Rook" - the two CA$2,699 commuters
    ("velotric-tempo", "radkick-7speed"),         # "Tempo vs RadKick 7-Speed" - the two lightest here
    ("aventon-soltera-2-5", "velotric-tempo"),    # "Soltera 2.5 vs Tempo" - the two light, cheap city bikes
    ("ohm-cruise-3", "velotric-discover-3"),      # "Cruise 3 vs Discover 3" - premium mid-drive vs the all-rounder
]

def pair_slug(a, b):
    return "%s-vs-%s" % (MODEL_SLUG[a], MODEL_SLUG[b])

_PAIR_SEEN = set()
for _pa, _pb in PAIRS:
    assert _pa in BY_ID and _pb in BY_ID, "a pair names a model not in products.json: %s" % ((_pa, _pb),)
    assert _pa != _pb, "a pair compares a model with itself: %s" % _pa
    _s = pair_slug(_pa, _pb)
    assert _s not in _PAIR_SEEN, "two pairs share one URL: %s" % _s
    _PAIR_SEEN.add(_s)
PAIR_SLUGS = [pair_slug(a, b) for a, b in PAIRS]

def pair_label(a, b):
    pa, pb = BY_ID[a], BY_ID[b]
    return "%s %s vs %s %s" % (pa["maker"], pa["model"], pb["maker"], pb["model"])

def pair_availability(a, b):
    """Availability exactly as observed in data/products.json; nothing where none was observed."""
    return ["%s %s: %s" % (BY_ID[q]["maker"], BY_ID[q]["model"], BY_ID[q]["availability"])
            for q in (a, b) if BY_ID[q].get("availability")]

def pair_card(a, b):
    # Deliberately no price in the card: the price belongs on the comparison table and on the pair's
    # own page, and repeating it here would add another "CA$1,899" token to the landing page for no
    # reader benefit. The card names the two bikes, the pair's link, and any observed availability.
    notes = "".join('<p class="pickstock">%s</p>' % esc(n) for n in pair_availability(a, b))
    return ('<article class="pick"><h3><a href="vs/%s/">%s</a></h3>%s'
            '<p>Column by column, on the same published figures as the table above.</p></article>'
            % (esc(pair_slug(a, b)), esc(pair_label(a, b)), notes))

PAIR_CARDS = "\n".join(pair_card(a, b) for a, b in PAIRS)

# ---------------------------------------------------------------- decisions
PICKS = [
    ("Apartment, stairs, or carrying it onto transit",
     "velotric-tempo",
     "At 39 lb the Tempo is the lightest bike here - 7 lb under the next lightest - and light enough to ride with the motor off. The 374 Wh battery is the trade-off."),
    ("The cheapest way in, without buying a toy",
     "aventon-soltera-2-5",
     "At CA$1,699 the Soltera 2.5 is the lowest price here and still a real bike: Tektro hydraulic disc brakes, a torque sensor and lights front and rear, UL 2849 / UL 2271 certified. Its 345.6 Wh battery is the honest limit: short, light trips."),
    ("The longest commute on one charge",
     "surface604-rook",
     "The Rook carries the biggest battery here (960 Wh) and, at up to 150 km in eco, claims the joint-longest range on this page - the same figure OHM publishes for the Cruise 3. It is also the only bike here that ships at Class 3."),
    ("The best all-round daily commuter",
     "velotric-discover-3",
     "750 W is the highest motor rating in this set, and its 730 Wh battery is the second biggest - behind only the Rook's 960 Wh - with lights, fenders and a rack included."),
    ("The lowest-priced Rad Power bike here",
     "radkick-7speed",
     "At CA$1,899 the RadKick 7-Speed still has hydraulic brakes and a rear rack included, and it is the lightest Rad on this page. Its 40 Nm is the least torque here and its 360 Wh battery is the honest limit: short trips only."),
    ("A bike that feels like a bike, on a long mixed commute",
     "radster-road",
     "The Radster Road pairs a torque sensor with a 100 Nm motor, so the assist follows your pedalling instead of pushing you. It is the heaviest bike here."),
    ("The premium step-through commuter",
     "ohm-cruise-3",
     "CA$3,499 buys a Shimano E7000 system with 60 Nm, a 504 Wh in-tube battery, a 2-year warranty and 30-day returns, from a maker that has designed in North Vancouver since 2005. The dearest bike here; the maker sells it on comfort rather than speed."),
]

# ---------------------------------------------------------------- HTML
def stock_badge(p):
    """Availability as observed on the maker's page. Rendered only where it was seen:
    a maker whose stock we did not observe gets no badge, never an invented "in stock"."""
    a = p.get("availability")
    return f'<span class="stock">{esc(a)}</span>' if a else ""

def model_cell(p):
    return ('<th scope="row" class="model">'
            f'<a class="mname" href="bikes/{esc(p["id"])}/">{esc(p["model"])}</a>'
            f'<span class="mmaker">{esc(p["maker"])}</span>'
            + stock_badge(p) +
            f'<a class="spec-link" href="{esc(p["source_url"])}" target="_blank" rel="noopener nofollow">maker specs \u2197</a>'
            '</th>')

def row_html(p):
    return (
        "<tr>"
        + model_cell(p)
        + f'<td class="price">{esc(p["price_display"])}'
          f'<span class="aff" data-aff="{esc(p["id"])}"></span></td>'
        + f'<td>{esc(p["motor"])}</td>'
        + f'<td>{esc(p["torque"])}</td>'
        + f'<td>{esc(p["battery"])}</td>'
        + f'<td>{esc(p["range"])}</td>'
        + f'<td>{esc(p["weight"])}</td>'
        + f'<td>{esc(p["brakes"])}</td>'
        + f'<td>{esc(p["eclass"])}</td>'
        + f'<td>{esc(p["warranty"])}</td>'
        + "</tr>"
    )

ROWS = "\n".join(row_html(p) for p in ORDER)

def pick_html(title, pid, body):
    p = BY_ID[pid]
    return (f'<article class="pick"><h3>{esc(title)}</h3>'
            f'<p class="pickwho">{esc(p["maker"])} {esc(p["model"])} &middot; {esc(p["price_display"])}</p>'
            + (f'<p class="pickstock">{esc(p["availability"])}</p>' if p.get("availability") else "") +
            f'<p>{esc(body)}</p></article>')

PICKS_HTML = "\n".join(pick_html(*pk) for pk in PICKS)

def source_html(p):
    return (f'<li><strong>{esc(p["maker"])} {esc(p["model"])}</strong> &mdash; '
            f'<a href="{esc(p["source_url"])}" target="_blank" rel="noopener nofollow">{esc(p["source_url"])}</a>'
            f'<br><span class="fn">{esc(p["source_note"])}</span></li>')

SOURCES_HTML = "\n".join(source_html(p) for p in ORDER)

def detail_html(p):
    return (f'<article class="detail"><h3>{esc(p["maker"])} {esc(p["model"])} <span class="dprice">{esc(p["price_display"])}</span></h3>'
            + (f'<p class="pickstock">{esc(p["availability"])}</p>' if p.get("availability") else "") +
            f'<p>{esc(p["best_for"])}</p>'
            f'<p class="src">Source: <a href="{esc(p["source_url"])}" target="_blank" rel="noopener nofollow">{esc(p["maker"])} product page</a>, checked {esc(CHECKED)}.</p></article>')

DETAILS_HTML = "\n".join(detail_html(p) for p in ORDER)

PAGE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="impact-site-verification" value="12512726-8e95-419c-8747-523f99ebd94b">
<title>Canadian Commuter E-Bike Comparison (CAD, 2026)</title>
<meta name="description" content="__N_WORD_CAP__ commuter e-bikes you can buy in Canada for __PRICE_SPAN_DASH__, compared on price, motor, battery, range, weight and warranty, with every spec traced to the maker's own product page.">
<style>
  :root{
    --paper:#faf8f4; --ink:#16181d; --muted:#5d6270; --line:#e3ddd1;
    --accent:#0e6b53; --accent-ink:#0a5340; --amber:#a6550c; --card:#ffffff;
  }
  *{box-sizing:border-box}
  html{-webkit-text-size-adjust:100%}
  body{margin:0;background:var(--paper);color:var(--ink);
    font:16px/1.6 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif}
  a{color:var(--accent-ink)}
  a:focus-visible,button:focus-visible{outline:3px solid var(--amber);outline-offset:2px}
  .wrap{max-width:1040px;margin:0 auto;padding:0 20px}
  header.top{border-bottom:1px solid var(--line);background:var(--paper)}
  .top .wrap{display:flex;justify-content:space-between;align-items:baseline;gap:12px;padding-top:14px;padding-bottom:14px}
  .brand{font:700 15px/1 -apple-system,"Segoe UI",sans-serif;letter-spacing:.14em;text-transform:uppercase}
  .stamp{font-size:13px;color:var(--muted)}
  h1,h2,h3{font-family:Georgia,"Iowan Old Style","Times New Roman",serif;font-weight:700;letter-spacing:-.01em}
  .hero{padding:44px 0 8px}
  .hero h1{font-size:clamp(30px,5vw,46px);line-height:1.1;margin:0 0 14px;max-width:20ch}
  .deck{font-size:19px;color:#333842;max-width:62ch;margin:0 0 22px}
  .cta{display:flex;flex-wrap:wrap;gap:12px;align-items:center;margin:0 0 26px}
  .btn{display:inline-block;background:var(--accent);color:#fff;text-decoration:none;
    font-weight:600;padding:13px 20px;border-radius:8px}
  .btn:hover{background:var(--accent-ink)}
  .btn.ghost{background:transparent;color:var(--accent-ink);border:1px solid var(--accent)}
  .disclosure{background:#fff;border:1px solid var(--line);border-left:4px solid var(--amber);
    padding:14px 16px;border-radius:6px;font-size:15px;color:#3a3f49;max-width:70ch}
  .disclosure strong{color:var(--ink)}
  section{padding:40px 0;border-top:1px solid var(--line)}
  section h2{font-size:clamp(22px,3vw,30px);margin:0 0 6px}
  .sub{color:var(--muted);margin:0 0 24px;max-width:66ch}
  .picks{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:20px 28px}
  .pick h3{font-size:17px;margin:0 0 4px;font-family:-apple-system,"Segoe UI",sans-serif;font-weight:700}
  .pick .pickwho{margin:0 0 8px;font-size:14px;color:var(--accent-ink);font-weight:600}
  .pick p{margin:0;color:#333842;font-size:15px}
  .tablewrap{overflow-x:auto;border:1px solid var(--line);border-radius:10px;background:var(--card)}
  table{border-collapse:collapse;width:100%;min-width:880px;font-size:13.4px}
  caption{text-align:left;padding:14px 16px;color:var(--muted);font-size:13px}
  th,td{text-align:left;padding:11px 10px;border-bottom:1px solid var(--line);vertical-align:top}
  thead th{position:sticky;top:0;background:#f3efe7;font-size:12px;letter-spacing:.05em;
    text-transform:uppercase;color:#4a4f59;white-space:nowrap;z-index:1}
  tbody tr:last-child td,tbody tr:last-child th{border-bottom:none}
  th.model{white-space:normal;min-width:150px}
  .mname{display:block;font-weight:700;font-size:15px}
  .mmaker{display:block;color:var(--muted);font-size:13px;margin:2px 0 6px}
  .spec-link{font-size:12.5px;text-decoration:none;border-bottom:1px solid var(--accent)}
  a.mname{color:inherit;text-decoration:none;border-bottom:1px solid var(--line)}
  a.mname:hover{border-bottom-color:var(--accent)}
  td.price{font-variant-numeric:tabular-nums;font-weight:700;white-space:nowrap}
  .aff{display:block;font-size:11px;color:var(--muted);margin-top:4px;font-weight:400}
  .stock{display:inline-block;margin:1px 0 2px;font-size:11px;font-weight:700;color:#fff;
    background:var(--amber);padding:1px 6px;border-radius:4px;letter-spacing:.02em}
  .pickstock{margin:0 0 6px;font-size:12.5px;font-weight:700;color:var(--amber)}
  .details{display:grid;gap:20px}
  .detail{border-left:3px solid var(--accent);padding:2px 0 2px 16px}
  .detail h3{margin:0 0 6px;font-size:18px}
  .detail .dprice{color:var(--muted);font-family:-apple-system,sans-serif;font-size:15px;font-weight:600}
  .detail p{margin:0 0 8px;color:#333842;max-width:72ch}
  .src,.fn{font-size:13px;color:var(--muted)}
  ul.sources{list-style:none;padding:0;margin:0;display:grid;gap:14px}
  ul.sources li{border-bottom:1px dashed var(--line);padding-bottom:12px;max-width:78ch}
  .note{font-size:14px;color:var(--muted);max-width:72ch}
  footer{border-top:1px solid var(--line);padding:28px 0 50px;color:var(--muted);font-size:13.5px}
  footer p{margin:0 0 8px;max-width:78ch}
</style>
</head>
<body>
<header class="top"><div class="wrap">
  <span class="brand">Commuter E-Bikes CA</span>
  <span class="stamp">Prices and specs checked <strong>__CHECKED__</strong></span>
</div></header>

<main class="wrap">
  <section class="hero" style="border-top:none">
    <h1>__N_WORD_CAP__ commuter e-bikes you can buy in Canada, sorted out</h1>
    <p class="deck">__PRICE_SPAN__. Real specs from each maker's own product page, so you can tell which bike fits a real commute instead of a spec sheet.</p>
    <div class="cta">
      <a class="btn" href="guide/canada-commuter-ebike-guide.pdf" download>Download the free PDF guide</a>
      <a class="btn ghost" href="guide/">Read the guide as a page</a>
      <a class="btn ghost" href="#compare">Compare the __N_WORD__</a>
      <a class="btn ghost" href="how-far/">How far will it go?</a>
      <a class="btn ghost" href="commute-costs/">What a commute costs</a>
      <a class="btn ghost" href="gear/">Gear: helmets, locks and lights</a>
      <a class="btn ghost" href="rules/">Classes and rules: what the law says where you ride</a>
      <a class="btn ghost" href="trails/">Where you may ride: trails, parks and paths</a>
    </div>
    <p class="disclosure" role="note">__DISCLOSURE__</p>
  </section>

  <section id="picks">
    <h2>Which one, in one line each</h2>
    <p class="sub">Match the bike to your ride, not to the biggest number on the box.</p>
    <div class="picks">__PICKS__</div>
  </section>

  <section id="compare">
    <h2>The comparison</h2>
    <p class="sub">Every price is in Canadian dollars as published by the maker, and every spec links to the page it was read from. "Claimed range" is the maker's own estimate, not a test result. Scroll the table sideways on a phone.</p>
    <div class="tablewrap">
      <table>
        <caption>Bikes listed cheapest to dearest; __TIE_NOTE__. Specs read __CHECKED__; prices move, so confirm on the maker's page before you buy.</caption>
        <thead><tr>
          <th scope="col">Model</th><th scope="col">Price (CAD)</th><th scope="col">Motor</th>
          <th scope="col">Torque</th><th scope="col">Battery</th><th scope="col">Claimed range</th>
          <th scope="col">Weight</th><th scope="col">Brakes</th><th scope="col">Class</th><th scope="col">Warranty</th>
        </tr></thead>
        <tbody>
__ROWS__
        </tbody>
      </table>
    </div>
  </section>

  <section id="headtohead">
    <h2>Head to head</h2>
    <p class="sub">The closest calls in this set, compared column by column on the same published figures as the table above &mdash; two columns, one row per field, and nothing that is not on the makers' own pages.</p>
    <div class="picks">__PAIRS__</div>
  </section>

  <section id="guide">
    <h2>Which one for which household</h2>
    <p class="sub">The decision guide, in full &mdash; also as <a href="guide/">a page you can read or link to</a>, and as <a href="guide/canada-commuter-ebike-guide.pdf" download>a free PDF</a>.</p>
    <div class="details">__DETAILS__</div>
  </section>

  <section id="sources">
    <h2>Where every number comes from</h2>
    <p class="sub">No remembered specs. Each figure above was read from the maker's own page on the date shown, and the exact page is below.</p>
    <ul class="sources">__SOURCES__</ul>
    <p class="note" style="margin-top:18px">Two caveats worth naming. <strong>Claimed range</strong> is the maker's figure and depends on rider weight, hills and assist level. <strong>Weight</strong> is the maker's figure too. Where a maker does not publish a figure on the page we read, the table says so rather than guessing.</p>
  </section>
</main>

<footer><div class="wrap">
  <p><strong>Disclosure (repeated):</strong> this site carries no live affiliate links. Links marked "maker specs" go to the manufacturer's own page, unmonetised. If paid partner links are added later, they will be labelled as such here and on the button itself.</p>
  <p>This is general product information, not advice about your particular riding, health or local by-laws. Check your province's e-bike rules before buying. Prices and stock change daily.</p>
  <p>Built __CHECKED__ by the GAMMA project. Data: <a href="data/products.json">products.json</a> &middot; classes and rules: <a href="rules/">what Class 1/2/3 mean in Canada</a> &middot; page views: <a href="stats/">the counts</a>.</p>
</div></footer>

<script src="config.js"></script>
<script>
(function(){
  var cfg = window.GAMMA_CONFIG || { products:{} };
  var affMap = {
    "radster-road":"AFFILIATE_RADSTER_ROAD","radkick-7speed":"AFFILIATE_RADKICK_7SPEED",
    "velotric-tempo":"AFFILIATE_VELOTRIC_TEMPO","velotric-discover-3":"AFFILIATE_VELOTRIC_DISCOVER_3",
    "surface604-rook":"AFFILIATE_SURFACE604_ROOK"
  };
  document.querySelectorAll(".aff").forEach(function(el){
    var id = el.getAttribute("data-aff");
    // A row says "affiliate link" only when a real tracking link is configured for it.
    // While the constant is null the row says nothing: the disclosure above the fold
    // already covers the absence, and no claim is made about any application's status.
    var live = cfg[affMap[id]];
    el.textContent = live ? "affiliate link" : "";
  });
})();
</script>
</body>
</html>
"""

out = (PAGE
       .replace("__CHECKED__", esc(CHECKED))
       .replace("__TIE_NOTE__", esc(TIE_NOTE))
       .replace("__N_WORD_CAP__", esc(N_WORD_CAP))
       .replace("__N_WORD__", esc(N_WORD))
       .replace("__PRICE_SPAN_DASH__", esc(PRICE_SPAN_DASH))
       .replace("__PRICE_SPAN__", esc(PRICE_SPAN))
       .replace("__DISCLOSURE__", esc(json.load(open(os.path.join(ROOT,"data","products.json"), encoding="utf-8"))["currency_note"]) + " " + "<strong>Disclosure:</strong> no live affiliate links yet; every product link goes to the maker's own site.")
       .replace("__PICKS__", PICKS_HTML)
       .replace("__ROWS__", ROWS)
       .replace("__DETAILS__", DETAILS_HTML)
       .replace("__PAIRS__", PAIR_CARDS)
       .replace("__SOURCES__", SOURCES_HTML))
write_page(os.path.join(ROOT, "index.html"), out, "index")

# ================================================================ per-bike pages, sitemap, robots.txt
# One indexable URL per model, generated from the same dataset as the comparison page so a rebuild
# cannot drop them. Nothing here is written by hand: every field comes from data/products.json, and a
# figure the maker did not publish is absent rather than guessed.
SITE = "https://maxhemmerich.github.io/canada-ebike-compare"
# The comparison page's stylesheet is this site's one theme; the bike pages reuse it verbatim, so a
# bike page cannot drift into a second look.
CSS = PAGE.split("<style>", 1)[1].split("</style>", 1)[0]

BIKE_FIELDS = [
    ("type", "Type"), ("motor", "Motor"), ("torque", "Torque"), ("battery", "Battery"),
    ("range", "Claimed range"), ("weight", "Weight"), ("brakes", "Brakes"),
    ("eclass", "Class"), ("sensor", "Sensor"), ("warranty", "Warranty"), ("payload", "Max load"),
]

# The affiliate rule, unchanged from the comparison page: a bike page offers a partner link only when
# its own constant in config.js holds a real tracking URL. While the constant is null the element is
# removed, so the page carries no link and says nothing about the status of any application.
BIKE_AFF_JS = """<script src="../../config.js"></script>
<script>
(function(){
  var cfg = window.GAMMA_CONFIG || { products:{} };
  var affMap = {
    "radster-road":"AFFILIATE_RADSTER_ROAD","radkick-7speed":"AFFILIATE_RADKICK_7SPEED",
    "velotric-tempo":"AFFILIATE_VELOTRIC_TEMPO","velotric-discover-3":"AFFILIATE_VELOTRIC_DISCOVER_3",
    "surface604-rook":"AFFILIATE_SURFACE604_ROOK"
  };
  var el = document.querySelector(".buyaff");
  if (!el) return;
  var live = cfg[affMap[el.getAttribute("data-aff")]];
  if (live) {
    el.href = live;
    el.textContent = "Go to the maker (affiliate link)";
    el.setAttribute("rel", "sponsored nofollow noopener");
    el.target = "_blank";
    el.hidden = false;
  } else {
    el.remove();
  }
})();
</script>"""

BIKE_PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="impact-site-verification" value="12512726-8e95-419c-8747-523f99ebd94b">
<title>__TITLE__</title>
<meta name="description" content="__DESC__">
<link rel="canonical" href="__CANONICAL__">
<style>__CSS__
  .crumb{font-size:13px;color:var(--muted);margin:0 0 8px}
  .bikehero{padding:34px 0 8px}
  .bikehero h1{font-size:clamp(26px,4.4vw,40px);line-height:1.12;margin:0 0 10px;max-width:26ch}
  .pricebig{font:700 22px/1.2 Georgia,serif;margin:0 0 14px;font-variant-numeric:tabular-nums}
  .pricebig .stock{display:inline-block;margin-left:10px;vertical-align:2px}
  .specs{margin:0 0 6px;border:1px solid var(--line);border-radius:10px;background:var(--card);overflow:hidden}
  .specs div{display:flex;gap:16px;padding:10px 14px;border-bottom:1px solid var(--line)}
  .specs div:last-child{border-bottom:none}
  .specs dt{flex:0 0 148px;margin:0;color:var(--muted);font-size:13.5px}
  .specs dd{margin:0;font-weight:600;font-size:14.5px}
  .buyrow{margin:18px 0 6px}
  ul.otherbikes{list-style:none;padding:0;margin:0;display:grid;gap:8px}
  ul.otherbikes a{font-size:14.5px}
</style>
</head>
<body>
<header class="top"><div class="wrap">
  <a class="brand" href="../../" style="color:inherit;text-decoration:none">Commuter E-Bikes CA</a>
  <span class="stamp">Prices and specs checked <strong>__CHECKED__</strong></span>
</div></header>

<main class="wrap">
  <section class="bikehero" style="border-top:none">
    <p class="crumb"><a href="../../">All __N_WORD__ commuter e-bikes, compared</a> &rsaquo; __MAKER__</p>
    <h1>__MAKER__ __MODEL__ in Canada</h1>
    <p class="pricebig">__PRICE____STOCK__</p>
    <p class="buyrow"><a class="buyaff" data-aff="__ID__" hidden></a></p>
    <p class="deck">__DECK__</p>
  </section>

  <section id="specs">
    <h2>Specifications</h2>
    <p class="sub">Every figure below was read from __MAKER__'s own product page on __CHECKED__, and that exact page is linked at the bottom of this one. Where a maker publishes no figure, the field is absent rather than guessed.</p>
    <dl class="specs">
      __SPECS__
    </dl>
  </section>

  <section id="who">
    <h2>Who it suits</h2>
    <div class="details"><article class="detail"><h3>__MAKER__ __MODEL__ <span class="dprice">__PRICE__</span></h3><p>__BESTFOR__</p></article></div>
  </section>

  <section id="next">
    <h2>The other bikes</h2>
    <ul class="otherbikes">__OTHERS__</ul>
    <p class="cta" style="margin-top:20px">
      <a class="btn" href="../../#compare">Compare all __N_WORD__ side by side</a>
      <a class="btn ghost" href="../../guide/canada-commuter-ebike-guide.pdf" download>Download the free PDF guide</a>
      <a class="btn ghost" href="../../gear/">Gear: helmets, locks and lights</a>
      <a class="btn ghost" href="../../rules/">Classes and rules: is it legal where you ride?</a>
    </p>
  </section>
__VSSECTION__
  <section id="source">
    <h2>Where these numbers come from</h2>
    <ul class="sources"><li><strong>__MAKER__ __MODEL__</strong> &mdash; <a href="__SOURCEURL__" target="_blank" rel="noopener nofollow">__SOURCEURL__</a><br><span class="fn">__SOURCENOTE__</span></li></ul>
  </section>
</main>

<footer><div class="wrap">
  <p><strong>Disclosure:</strong> this page has no live affiliate link for the __MODEL__. Nothing here is paid for and no purchase through this page earns anyone a commission today; the only product link above goes to __MAKER__'s own page. If a paid partner link is ever added, it will be labelled as one.</p>
  <p>This is general product information, not advice about your particular riding, health or local by-laws. Check your province's e-bike rules before buying. Prices and stock change daily.</p>
  <p>Built __CHECKED__ by the GAMMA project. Data: <a href="../../data/products.json">products.json</a> &middot; <a href="../../">the comparison</a> &middot; <a href="../../rules/">is it legal where you ride?</a>.</p>
</div></footer>

__AFFJS__
</body>
</html>
"""

def bike_vs_section(p):
    """Links from this bike's own page to every head-to-head page it appears on, so no vs page is an
    orphan. A bike in no pair gets no section at all - never an empty heading."""
    rows = [(a, b) for a, b in PAIRS if p["id"] in (a, b)]
    if not rows:
        return ""
    items = "\n      ".join(
        '<li><a href="../../vs/%s/">%s</a></li>' % (esc(pair_slug(a, b)), esc(pair_label(a, b)))
        for a, b in rows)
    return ('\n  <section id="headtohead">\n'
            '    <h2>Head to head</h2>\n'
            '    <p class="sub">This bike in a direct comparison, on the same published figures.</p>\n'
            '    <ul class="otherbikes">\n      %s\n    </ul>\n'
            '  </section>\n' % items)

def bike_html(p):
    specs = "\n      ".join(
        ['<div><dt>Price (CAD)</dt><dd>%s</dd></div>' % esc(p["price_display"])] +
        ['<div><dt>%s</dt><dd>%s</dd></div>' % (label, esc(p[key]))
         for key, label in BIKE_FIELDS if p.get(key)])
    others = "\n      ".join(
        '<li><a href="../%s/">%s %s &mdash; %s</a></li>'
        % (esc(q["id"]), esc(q["maker"]), esc(q["model"]), esc(q["price_display"]))
        for q in ORDER if q["id"] != p["id"])
    stock = ('<span class="stock">%s</span>' % esc(p["availability"])) if p.get("availability") else ""
    stock_word = (" (%s)" % p["availability"]) if p.get("availability") else ""
    title = "%s %s \u2014 %s in Canada | Commuter E-Bikes CA" % (p["maker"], p["model"], p["price_display"])
    desc = ("%s %s for %s in Canada: %s, %s, %s battery, %s claimed range, %s. "
            "Specs read from the maker's own product page, checked %s."
            % (p["maker"], p["model"], p["price_display"], p["motor"], p["torque"],
               p["battery"], p["range"], p["weight"], CHECKED))
    deck = ("%s from %s's own Canadian storefront%s. The figures below were read from %s's product "
            "page, not from memory, and that page is linked at the bottom."
            % (p["price_display"], p["maker"], stock_word, p["maker"]))
    return (BIKE_PAGE
            .replace("__CSS__", CSS)
            .replace("__N_WORD__", esc(N_WORD))
            .replace("__TITLE__", esc(title))
            .replace("__DESC__", esc(desc))
            .replace("__CANONICAL__", "%s/bikes/%s/" % (SITE, p["id"]))
            .replace("__CHECKED__", esc(CHECKED))
            .replace("__MAKER__", esc(p["maker"]))
            .replace("__MODEL__", esc(p["model"]))
            .replace("__ID__", esc(p["id"]))
            .replace("__PRICE__", esc(p["price_display"]))
            .replace("__STOCK__", stock)
            .replace("__DECK__", esc(deck))
            .replace("__SPECS__", specs)
            .replace("__BESTFOR__", esc(p["best_for"]))
            .replace("__OTHERS__", others)
            .replace("__SOURCEURL__", esc(p["source_url"]))
            .replace("__SOURCENOTE__", esc(p["source_note"]))
            .replace("__VSSECTION__", bike_vs_section(p))
            .replace("__AFFJS__", BIKE_AFF_JS))

for p in ORDER:
    write_page(os.path.join(ROOT, "bikes", p["id"], "index.html"), bike_html(p), "bikes-%s" % p["id"])

# ================================================================ "how far will it go" range picker
# The one page here that answers a question instead of listing a spec sheet: a buyer types a round-trip
# distance and sees which of the bikes claims to cover it, from the sourced figures already in
# data/products.json. Generated here so a rebuild cannot drop it, and linked from sitemap.xml.
# RANGE_PARSE (defined and guarded at the top of this file, before anything is written) supplies the
# two figures per model.

# The browser gets exactly what the table above says: published strings, and the two figures derived
# from them. No affiliate constant is read or written here; there is nothing on this page to point at.
PICKER_DATA = json.dumps([
    {"id": q["id"], "maker": q["maker"], "model": q["model"], "price": q["price_display"],
     "battery": q["battery"], "range": q["range"], "url": "bikes/%s/" % q["id"],
     "high": RANGE_PARSE[q["id"]]["high"], "low": RANGE_PARSE[q["id"]]["low"],
     "highFrom": RANGE_PARSE[q["id"]]["high_from"], "lowLabel": RANGE_PARSE[q["id"]]["low_label"]}
    for q in ORDER], ensure_ascii=False).replace("<", "\\u003c")

def _low_cell(pid):
    r = RANGE_PARSE[pid]
    if r["low"] is None:
        return '<span class="onefig">one figure only</span>'
    return '%d km<br><span class="fn">%s</span>' % (r["low"], esc(r["low_label"]))

FIG_ROWS = "\n".join(
    '<tr><th scope="row" class="model"><a class="mname" href="../bikes/%s/">%s</a>'
    '<span class="mmaker">%s</span></th>'
    '<td class="price">%s</td><td>%s</td><td>%s</td><td class="num">%d km</td><td>%s</td>'
    '<td><a class="spec-link" href="%s" target="_blank" rel="noopener nofollow">maker specs \u2197</a></td></tr>'
    % (esc(q["id"]), esc(q["model"]), esc(q["maker"]), esc(q["price_display"]), esc(q["battery"]),
       esc(q["range"]), RANGE_PARSE[q["id"]]["high"], _low_cell(q["id"]), esc(q["source_url"]))
    for q in ORDER)

BIKE_LINKS = "\n      ".join(
    '<li><a href="../bikes/%s/">%s %s &mdash; %s, claimed range %s</a></li>'
    % (esc(q["id"]), esc(q["maker"]), esc(q["model"]), esc(q["price_display"]), esc(q["range"]))
    for q in ORDER)

PICKER_PAGE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="impact-site-verification" value="12512726-8e95-419c-8747-523f99ebd94b">
<title>How far will an e-bike go? Range vs. your commute (Canada)</title>
<meta name="description" content="How big a battery do you need for a 14 km commute? Enter your round-trip distance and see which of __N_WORD__ Canadian commuter e-bikes claims to cover it, using each maker's own published range figure.">
<link rel="canonical" href="__CANONICAL__">
<style>__CSS__
  .crumb{font-size:13px;color:var(--muted);margin:0 0 8px}
  .pickerbox{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:18px 18px 14px;max-width:640px}
  .pickerbox label{display:block;font-weight:600;font-size:14.5px;margin:0 0 6px}
  .inputrow{display:flex;flex-wrap:wrap;gap:10px;align-items:center}
  input#dist{font:700 22px/1.1 Georgia,serif;font-variant-numeric:tabular-nums;width:120px;
    padding:9px 12px;border:1px solid var(--line);border-radius:8px;background:#fff;color:var(--ink)}
  .quick{display:flex;flex-wrap:wrap;gap:6px}
  .quick button{border:1px solid var(--line);background:#fff;color:var(--accent-ink);
    border-radius:999px;padding:6px 13px;font-size:13.5px;font-weight:600;cursor:pointer}
  .quick button:hover{border-color:var(--accent)}
  label.hills{display:flex;gap:9px;align-items:flex-start;font-weight:400;margin:14px 0 0}
  label.hills input{width:17px;height:17px;margin:2px 0 0}
  .methodline{font-size:13px;color:var(--muted);margin:12px 0 0;max-width:70ch}
  .summary{font-weight:700;font-size:16px;margin:20px 0 0}
  #results h3{font-family:-apple-system,"Segoe UI",sans-serif;font-size:13px;letter-spacing:.06em;
    text-transform:uppercase;color:var(--muted);margin:22px 0 8px}
  ul.rt{list-style:none;padding:0;margin:0;display:grid;gap:10px}
  ul.rt li{border:1px solid var(--line);border-left:4px solid var(--line);border-radius:8px;
    background:var(--card);padding:12px 14px}
  ul.rt li.cover{border-left-color:var(--accent)}
  ul.rt li.partial{border-left-color:var(--amber)}
  ul.rt li.short{opacity:.9}
  .rowhead{display:flex;flex-wrap:wrap;gap:10px;justify-content:space-between;align-items:baseline}
  .rowhead b{font-size:16px}
  .rowhead a{color:inherit;text-decoration:none;border-bottom:1px solid var(--line)}
  .rowhead a:hover{border-bottom-color:var(--accent)}
  .rprice{font-variant-numeric:tabular-nums;font-weight:700;font-size:14.5px}
  .rt,.rfacts{margin:6px 0 0;font-size:14.5px;color:#333842;max-width:78ch}
  .rfacts{font-size:13px;color:var(--muted)}
  td.num{font-variant-numeric:tabular-nums;font-weight:600;white-space:nowrap}
  .onefig{color:var(--muted);font-size:12.5px}
  ol.method{margin:0;padding-left:22px;max-width:80ch}
  ol.method li{margin:0 0 10px;color:#333842}
  ul.otherbikes{list-style:none;padding:0;margin:0;display:grid;gap:8px}
  ul.otherbikes a{font-size:14.5px}
</style>
</head>
<body>
<header class="top"><div class="wrap">
  <a class="brand" href="../" style="color:inherit;text-decoration:none">Commuter E-Bikes CA</a>
  <span class="stamp">Prices and specs checked <strong>__CHECKED__</strong></span>
</div></header>

<main class="wrap">
  <section class="hero" style="border-top:none">
    <p class="crumb"><a href="../">All __N_WORD__ commuter e-bikes, compared</a> &rsaquo; Range picker</p>
    <h1>How far will it actually go?</h1>
    <p class="deck">"How big a battery do I need for a 14 km commute?" Put your round-trip distance in below. This page compares it with the range figure each maker publishes on its own product page &mdash; not a test we ran, and not a number we bent to fit.</p>
    <p class="disclosure" role="note"><strong>Disclosure:</strong> this page has no live affiliate links. Nothing here is paid for and no purchase through this page earns anyone a commission today; every link goes to a maker's own page or to another page on this site.</p>
  </section>

  <section id="picker">
    <h2>Your round trip</h2>
    <p class="sub">Round-trip distance in kilometres. The decision is made only against figures quoted in full in the table below.</p>
    <div class="pickerbox">
      <label for="dist">Round-trip distance (km)</label>
      <div class="inputrow">
        <input id="dist" type="number" min="1" max="500" step="1" value="14" inputmode="numeric" aria-describedby="methodline">
        <span class="quick">
          <button type="button" data-km="5">5 km</button>
          <button type="button" data-km="10">10 km</button>
          <button type="button" data-km="14">14 km</button>
          <button type="button" data-km="25">25 km</button>
          <button type="button" data-km="40">40 km</button>
        </span>
      </div>
      <label class="hills"><input id="hills" type="checkbox"> My route is hilly, or I ride with a load</label>
      <p class="methodline" id="methodline">With the hills box clear, your distance is compared with each maker's highest published figure. With it ticked, the comparison moves to the lowest figure that maker publishes; a maker who publishes only one figure is labelled as such, not adjusted by a rule of ours.</p>
    </div>
    <p class="summary" id="summary" role="status" aria-live="polite"></p>
    <div id="results"></div>
    <noscript><p class="note">This picker needs JavaScript to sort the bikes. The table below lists every published figure it works from, so nothing on this page depends on scripts to be readable.</p></noscript>
  </section>

  <section id="figures">
    <h2>Every figure this page uses, as published</h2>
    <p class="sub">No test-ride number and no remembered number is used anywhere on this page. The "top figure" and "lowest published figure" columns are the maker's own published range, read exactly as written; where a maker publishes a single figure, the lowest column says so.</p>
    <div class="tablewrap">
      <table>
        <caption>Claimed range as published by each maker, read __CHECKED__. Claimed range is the maker's own estimate and depends on rider weight, hills, temperature and assist level &mdash; none of that is modelled on this page.</caption>
        <thead><tr>
          <th scope="col">Model</th><th scope="col">Price (CAD)</th><th scope="col">Battery</th>
          <th scope="col">Maker's published claimed range</th><th scope="col">Top figure</th>
          <th scope="col">Lowest published figure</th><th scope="col">Source</th>
        </tr></thead>
        <tbody>
__FIGROWS__
        </tbody>
      </table>
    </div>
  </section>

  <section id="method">
    <h2>How this page decides</h2>
    <ol class="method">
      <li><strong>It only ever quotes the maker.</strong> Each top figure and each lowest published figure above is a number the maker itself published, quoted in full in the table, with a link to the page it was read from.</li>
      <li><strong>Hills are not modelled.</strong> No maker here publishes a hills figure, so this page will not invent a percentage for you. The hills box changes which published figure you are measured against &mdash; the maker's own low end, where one exists.</li>
      <li><strong>A caveat on the Rook.</strong> Surface 604 describes its published figure as eco mode, so that top figure is the maker's best case, not a worst case.</li>
      <li><strong>Conversions, named.</strong> Only the Soltera 2.5's range is published in miles (46 mi); it is shown here converted to kilometres at 1 mi = 1.609344 km. The Discover 3 publishes both its pedal-assist and its throttle range in kilometres.</li>
      <li><strong>Where two of these figures come from.</strong> The Soltera 2.5's figure carries Aventon's own footnote &mdash; Eco mode, a 75 kg rider, flat paved road &mdash; so it is a best case as well. The Cruise 3's 150 km is stated on OHM's own product page in its feature grid rather than in its specification table, and no assist level is named with it.</li>
      <li><strong>Battery size is the whole story only sometimes.</strong> The Wh figure above is the maker's published capacity; two bikes can post the same miles from different Wh once weight and assist level are counted in.</li>
    </ol>
  </section>

  <section id="next">
    <h2>Read the rest</h2>
    <ul class="otherbikes">
      <li><a href="../">All __N_WORD__ commuter e-bikes, compared side by side</a></li>
      __BIKELINKS__
      <li><a href="../guide/">The decision guide &mdash; the free front-door page</a></li>
      <li><a href="../guide/canada-commuter-ebike-guide.pdf" download>The free decision-guide PDF</a></li>
    </ul>
  </section>
</main>

<footer><div class="wrap">
  <p><strong>Disclosure:</strong> this page has no live affiliate links. Nothing here is paid for and no purchase through this page earns anyone a commission today. Links go to the makers' own pages and to other pages on this site. If a paid partner link is ever added, it will be labelled as one, here and on the button itself.</p>
  <p>This is general product information, not advice about your particular riding, health or local by-laws. Check your province's e-bike rules before buying. Prices and stock change daily.</p>
  <p>Built __CHECKED__ by the GAMMA project. Data: <a href="../data/products.json">products.json</a> &middot; <a href="../">the comparison</a> &middot; <a href="#picker">this picker</a>.</p>
</div></footer>

<script type="application/json" id="rangeData">__PICKERDATA__</script>
<script>
(function(){
  var DATA = JSON.parse(document.getElementById("rangeData").textContent);
  var dist = document.getElementById("dist");
  var hills = document.getElementById("hills");
  var out = document.getElementById("results");
  var sum = document.getElementById("summary");
  if (!DATA || !DATA.length) return;

  Array.prototype.forEach.call(document.querySelectorAll(".quick button"), function(b){
    b.addEventListener("click", function(){ dist.value = b.getAttribute("data-km"); render(); });
  });
  dist.addEventListener("input", render);
  hills.addEventListener("change", render);

  function card(m, cls, text){
    return '<li class="row ' + cls + '">'
      + '<div class="rowhead"><b><a href="' + m.url + '">' + m.maker + ' ' + m.model + '</a></b>'
      + '<span class="rprice">' + m.price + '</span></div>'
      + '<p class="rt">' + text + '</p>'
      + '<p class="rfacts">Battery: ' + m.battery + ' &middot; maker\u2019s claimed range: ' + m.range
      + ' &middot; <a href="' + m.url + '">full specs</a></p></li>';
  }

  function group(title, items){
    if (!items.length) return "";
    return '<h3>' + title + '</h3><ul class="rt">' + items.join("") + '</ul>';
  }

  function render(){
    var d = parseFloat(dist.value);
    if (!(d > 0) || d > 500) {
      sum.textContent = "Enter a round-trip distance in kilometres (1 to 500).";
      out.innerHTML = "";
      return;
    }
    var dShow = (Math.round(d * 10) / 10);
    var hilly = hills.checked;
    var cover = [], partial = [], short = [];
    DATA.forEach(function(m){
      if (!hilly) {
        if (d <= m.high) cover.push(card(m, "cover",
          "Covers a " + dShow + " km round trip. " + m.maker + " publishes up to " + m.high + " km."));
        else short.push(card(m, "short",
          "Does not reach your round trip: " + m.maker + " publishes up to " + m.high + " km, "
          + (Math.round((d - m.high) * 10) / 10) + " km short."));
      } else if (m.low !== null && m.low !== undefined) {
        if (d <= m.low) cover.push(card(m, "cover",
          "Covers it even against the lowest figure " + m.maker + " publishes: " + m.low + " km (" + m.lowLabel + ")."));
        else if (d <= m.high) partial.push(card(m, "partial",
          "Covers it only on the best case: " + m.maker + " publishes up to " + m.high + " km. Their lowest published figure is "
          + m.low + " km (" + m.lowLabel + "), and that does not reach " + dShow + " km."));
        else short.push(card(m, "short",
          "Does not reach your round trip: " + m.maker + " publishes up to " + m.high + " km."));
      } else {
        if (d <= m.high) partial.push(card(m, "partial",
          "One published figure only: " + m.maker + " publishes " + m.high + " km and no lower figure, so a hilly route cannot be checked against the maker\u2019s own numbers. Treat " + m.high + " km as the best case."));
        else short.push(card(m, "short",
          "Does not reach your round trip: " + m.maker + " publishes one figure, " + m.high + " km."));
      }
    });
    out.innerHTML = group("Covers your round trip", cover)
                  + group("Covers it only on the maker\u2019s best-case figure", partial)
                  + group("Does not reach", short);
    if (!hilly) {
      sum.textContent = (short.length === 0)
        ? "All " + DATA.length + " bikes claim to cover a " + dShow + " km round trip on the highest figure their maker publishes."
        : cover.length + " of the " + DATA.length + " bikes claim to cover a " + dShow + " km round trip on the highest figure their maker publishes; "
          + short.length + (short.length === 1 ? " does not." : " do not.");
    } else {
      sum.textContent = "Hills on: " + cover.length + " of the " + DATA.length + " claim to cover a " + dShow
        + " km round trip even against the lowest figure their maker publishes; " + partial.length
        + " only on the maker\u2019s best case; " + short.length + " do not reach it.";
    }
  }
  render();
})();
</script>
</body>
</html>
"""

_picker_out = (PICKER_PAGE
               .replace("__CSS__", CSS)
               .replace("__N_WORD__", esc(N_WORD))
               .replace("__CANONICAL__", "%s/how-far/" % SITE)
               .replace("__CHECKED__", esc(CHECKED))
               .replace("__FIGROWS__", FIG_ROWS)
               .replace("__BIKELINKS__", BIKE_LINKS)
               .replace("__PICKERDATA__", PICKER_DATA))
write_page(os.path.join(ROOT, "how-far", "index.html"), _picker_out, "how-far")

# ================================================================ the free decision guide, as a real page
# The guide ships twice: the printable PDF, and /guide/ — the version a stranger can link to, with its own
# title, description, canonical and social card. The PDF is not a link target: a writer cannot cite it and
# a crawler cannot index it. BOTH artefacts are generated from the SAME source objects defined here and
# consumed again by the PDF further down this file, so the page cannot drift from the PDF. Nothing on the
# page is hand-written a second time: the one-line verdicts are the PICKS list, "which one for which
# household" is DETAILS_HTML, "where every number comes from" is SOURCES_HTML, and the comparison table is
# built from GUIDE_TABLE. What is asserted, not promised: the build reads this page and the finished PDF
# back and compares them (see the end of this file).

# ---- the guide's own source: ONE definition, used by this page and by the PDF
GUIDE_TITLE = "Canadian commuter e-bikes, sorted out"
GUIDE_INTRO = ("%s bikes you can buy in Canada for %s. Every figure in this guide was read from the maker's "
               "own product page on %s - no remembered specs. Prices move, so confirm before you buy."
               % (N_WORD_CAP, PRICE_SPAN, CHECKED))
GUIDE_DISCLOSURE = ("this guide was not paid for and carries no live affiliate links. Product names link "
                    "to the makers' own pages. If paid partner links are ever added, they will be labelled "
                    "as such.")
GUIDE_PICKS_HEAD = "Which one, in one line each"
GUIDE_COMPARE_HEAD = "The comparison"
GUIDE_COMPARE_NOTE = ("Cheapest to dearest; %s. Claimed range is the maker's estimate, not a test. Weight "
                      "is the maker's figure. Where a maker does not publish a figure, the cell says so."
                      % TIE_NOTE)
GUIDE_COMPARE_NOTE2 = ("Cheapest is not the same as best value: the Soltera 2.5 costs the least but carries "
                       "the smallest battery here. Match the battery to your round-trip distance, not the "
                       "price tag.")
GUIDE_HOUSEHOLD_HEAD = "Which one for which household"
GUIDE_SOURCES_HEAD = "Where every number comes from"
GUIDE_SOURCES_NOTE = ("Each bike below links to the exact page the figures were read from, on %s."
                      % CHECKED)
GUIDE_CAVEATS = ("Two caveats worth naming. Claimed range is the maker's figure and depends on rider weight, "
                 "hills, temperature and assist level. Weight is the maker's figure too. Where a maker does "
                 "not publish a figure on the page we read, this guide says so rather than guessing. This is "
                 "general product information, not advice about your riding or your province's e-bike rules "
                 "- check those before you buy.")

# The guide's comparison table, once: (column heading, the products.json field it prints). None = the model
# cell, which carries the model, its maker, any observed availability and the link to the maker's own page.
# The heading holds a newline the PDF uses to wrap a narrow column; the page prints it as a space.
GUIDE_TABLE = [
    ("Model", None),
    ("Price\n(CAD)", "price_display"),
    ("Motor", "motor"),
    ("Torque", "torque"),
    ("Battery", "battery"),
    ("Claimed\nrange", "range"),
    ("Weight", "weight"),
    ("Brakes", "brakes"),
    ("Class", "eclass"),
    ("Warranty", "warranty"),
]

def guide_row(p):
    """One table row, every cell the published field itself. No .aff element and no config.js is emitted
    on this page at all, so there is nothing here that could pay or that claims a link pays."""
    cells = []
    for _label, _field in GUIDE_TABLE:
        if _field is None:
            cells.append('<th scope="row" class="model">'
                         '<a class="mname" href="../bikes/%s/">%s</a><span class="mmaker">%s</span>%s'
                         '<a class="spec-link" href="%s" target="_blank" rel="noopener nofollow">maker specs \u2197</a>'
                         '</th>' % (esc(p["id"]), esc(p["model"]), esc(p["maker"]), stock_badge(p),
                                    esc(p["source_url"])))
        elif _field == "price_display":
            cells.append('<td class="price">%s</td>' % esc(p[_field]))
        else:
            cells.append('<td>%s</td>' % esc(p[_field]))
    return "<tr>%s</tr>" % "".join(cells)

GUIDE_ROWS = "\n".join(guide_row(p) for p in ORDER)
GUIDE_COLS = "\n            ".join('<th scope="col">%s</th>' % esc(l.replace("\n", " "))
                                  for l, _f in GUIDE_TABLE)

GUIDE_PAGE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="impact-site-verification" value="12512726-8e95-419c-8747-523f99ebd94b">
<title>__TITLE__</title>
<meta name="description" content="__DESC__">
<link rel="canonical" href="__CANONICAL__">
<meta property="og:type" content="article">
<meta property="og:site_name" content="Commuter E-Bikes CA">
<meta property="og:title" content="__OGTITLE__">
<meta property="og:description" content="__DESC__">
<meta property="og:url" content="__CANONICAL__">
<meta name="twitter:card" content="summary">
<meta name="twitter:title" content="__OGTITLE__">
<meta name="twitter:description" content="__DESC__">
<style>__CSS__
  .crumb{font-size:13px;color:var(--muted);margin:0 0 8px}
  .guidehero{padding:34px 0 8px}
  .guidehero h1{font-size:clamp(27px,4.6vw,42px);line-height:1.12;margin:0 0 12px;max-width:26ch}
  .cta{margin:0 0 22px}
  ul.otherbikes{list-style:none;padding:0;margin:0;display:grid;gap:8px}
  ul.otherbikes a{font-size:14.5px}
</style>
</head>
<body>
<header class="top"><div class="wrap">
  <a class="brand" href="../" style="color:inherit;text-decoration:none">Commuter E-Bikes CA</a>
  <span class="stamp">Prices and specs checked <strong>__CHECKED__</strong></span>
</div></header>

<main class="wrap">
  <section class="guidehero" style="border-top:none">
    <p class="crumb"><a href="../">All __N_WORD__ commuter e-bikes, compared</a> &rsaquo; The decision guide</p>
    <h1>The commuter e-bike decision guide</h1>
    <p class="deck">__INTRO__</p>
    <p class="cta">
      <a class="btn" href="canada-commuter-ebike-guide.pdf" download>Download the free PDF</a>
      <a class="btn ghost" href="../#compare">Compare all __N_WORD__ side by side</a>
      <a class="btn ghost" href="../how-far/">How far will it go?</a>
    </p>
    <p class="disclosure" role="note"><strong>Disclosure:</strong> __DISC__</p>
  </section>

  <section id="picks">
    <h2>__PICKSHEAD__</h2>
    <p class="sub">Match the bike to your ride, not to the biggest number on the box. These are the same one-line verdicts the comparison page and the PDF carry, from the same list.</p>
    <div class="picks">__PICKS__</div>
  </section>

  <section id="compare">
    <h2>__COMPAREHEAD__</h2>
    <p class="sub">Every price is in Canadian dollars as the maker publishes it, and every spec links to the page it was read from. Scroll the table sideways on a phone.</p>
    <div class="tablewrap">
      <table>
        <caption>__COMPARENOTE__</caption>
        <thead><tr>
            __COLS__
        </tr></thead>
        <tbody>
__ROWS__
        </tbody>
      </table>
    </div>
    <p class="note" style="margin-top:14px">__COMPARENOTE2__</p>
  </section>

  <section id="household">
    <h2>__HOUSEHOLDHEAD__</h2>
    <p class="sub">Which bike suits which rider, one paragraph each, the same text the PDF carries.</p>
    <div class="details">__DETAILS__</div>
  </section>

  <section id="sources">
    <h2>__SOURCESHEAD__</h2>
    <p class="sub">__SOURCESNOTE__</p>
    <ul class="sources">__SOURCES__</ul>
    <p class="note" style="margin-top:18px">__CAVEATS__</p>
  </section>

  <section id="next">
    <h2>Read the rest</h2>
    <ul class="otherbikes">
      <li><a href="../">All __N_WORD__ commuter e-bikes, compared side by side</a></li>
      <li><a href="../commute-costs/">What a commute costs: e-bike vs car vs transit, per year</a></li>
      <li><a href="../how-far/">How far will it go? Range against your commute</a></li>
      <li><a href="../stats/">Page views on this site &mdash; the counts, read live</a></li>
    </ul>
  </section>
</main>

<footer><div class="wrap">
  <p><strong>Disclosure:</strong> __DISC__</p>
  <p>This is general product information, not advice about your particular riding, health or local by-laws. Check your province's e-bike rules before buying. Prices and stock change daily.</p>
  <p>Built __CHECKED__ by the GAMMA project. Data: <a href="../data/products.json">products.json</a> &middot; <a href="../">the comparison</a> &middot; <a href="../how-far/">the range picker</a>.</p>
</div></footer>
</body>
</html>
"""

_guide_title = "The free commuter e-bike decision guide (Canada) | Commuter E-Bikes CA"
_guide_desc = ("%s commuter e-bikes you can buy in Canada, sorted into which one suits which rider, with the "
               "full comparison table and every figure traced to the maker's own product page. Free, no "
               "signup." % N_WORD_CAP)
_guide_out = (GUIDE_PAGE
              .replace("__CSS__", CSS)
              .replace("__N_WORD__", esc(N_WORD))
              .replace("__TITLE__", esc(_guide_title))
              .replace("__OGTITLE__", esc(_guide_title))
              .replace("__DESC__", esc(_guide_desc))
              .replace("__CANONICAL__", "%s/guide/" % SITE)
              .replace("__CHECKED__", esc(CHECKED))
              .replace("__INTRO__", esc(GUIDE_INTRO))
              .replace("__DISC__", esc(GUIDE_DISCLOSURE))
              .replace("__PICKSHEAD__", esc(GUIDE_PICKS_HEAD))
              .replace("__COMPAREHEAD__", esc(GUIDE_COMPARE_HEAD))
              .replace("__COMPARENOTE__", esc(GUIDE_COMPARE_NOTE))
              .replace("__COMPARENOTE2__", esc(GUIDE_COMPARE_NOTE2))
              .replace("__COLS__", GUIDE_COLS)
              .replace("__ROWS__", GUIDE_ROWS)
              .replace("__HOUSEHOLDHEAD__", esc(GUIDE_HOUSEHOLD_HEAD))
              .replace("__DETAILS__", DETAILS_HTML)
              .replace("__SOURCESHEAD__", esc(GUIDE_SOURCES_HEAD))
              .replace("__SOURCESNOTE__", esc(GUIDE_SOURCES_NOTE))
              .replace("__SOURCES__", SOURCES_HTML)
              .replace("__CAVEATS__", esc(GUIDE_CAVEATS))
              .replace("__PICKS__", PICKS_HTML))
write_page(os.path.join(ROOT, "guide", "index.html"), _guide_out, "guide")

# ---- the page is checked against its own source before the sitemap is written
GUIDE_FILE = os.path.join(ROOT, "guide", "index.html")
GUIDE_TEXT = open(GUIDE_FILE, encoding="utf-8").read()

# 1. every published field of every model is PRINTED here: an omission stops the build, so the page
#    cannot quietly become a partial copy of the guide.
for _p in ORDER:
    for _lbl, _f in GUIDE_TABLE:
        if _f and _p.get(_f):
            assert esc(_p[_f]) in GUIDE_TEXT, \
                "guide page omits %s of %s: %r" % (_f, _p["id"], _p[_f])
    for _f in ("best_for", "source_url", "source_note", "maker", "model"):
        assert esc(_p[_f]) in GUIDE_TEXT, "guide page omits %s of %s" % (_f, _p["id"])

# 2. nothing on this page can pay, and it says nothing about the status of any program.
for _bad in ("config.js", "AFFILIATE_", 'data-aff=', 'class="buyaff"'):
    assert _bad not in GUIDE_TEXT, "affiliate element on the guide page: %r" % _bad

# 3. its own head: title, description, canonical and the social card.
assert "<link rel=\"canonical\" href=\"%s/guide/\">" % SITE in GUIDE_TEXT
for _head in ('<title>', 'name="description"', 'property="og:type"', 'property="og:site_name"',
              'property="og:title"', 'property="og:description"', 'property="og:url"',
              'name="twitter:card"', 'name="twitter:title"', 'name="twitter:description"'):
    assert _head in GUIDE_TEXT, "guide page is missing %s" % _head
print("guide page: %d bytes, every published field present, no affiliate element" % len(GUIDE_TEXT))

# ================================================================ head-to-head "vs" pages
# One page per pair in the PAIRS list at the top of this file: two columns, every cell a field already
# published on that model's own page in data/products.json, and nothing else. No config.js and no
# affiliate element is emitted here at all, so a page in this directory has nothing that could pay and
# says nothing about the status of any program. Each page carries its own title, meta description and
# canonical, is listed in sitemap.xml, and is linked from the landing page and from both models' pages.
VS_FIELDS = [("price_display", "Price (CAD)")] + BIKE_FIELDS

def vs_rows(a, b):
    """One row per published field, both columns from products.json. A field only one maker publishes
    is left out rather than half-filled: the page omits what is not in the data."""
    pa, pb = BY_ID[a], BY_ID[b]
    rows = []
    for key, label in VS_FIELDS:
        va, vb = pa.get(key), pb.get(key)
        if va and vb:
            rows.append('<tr><th scope="row">%s</th><td>%s</td><td>%s</td></tr>'
                        % (esc(label), esc(va), esc(vb)))
    return "\n        ".join(rows)

def vs_col(p):
    """A column head: the model's own bikes/<id>/ page, its maker's source page, and availability only
    where products.json observed one."""
    stock = (' <span class="stock">%s</span>' % esc(p["availability"])) if p.get("availability") else ""
    return ('<a class="mname" href="../../bikes/%s/">%s %s</a>%s'
            '<span class="mmaker">%s</span>'
            '<a class="spec-link" href="%s" target="_blank" rel="noopener nofollow">maker specs \u2197</a>'
            % (esc(p["id"]), esc(p["maker"]), esc(p["model"]), stock,
               esc(p["maker"]), esc(p["source_url"])))

VS_PAGE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="impact-site-verification" value="12512726-8e95-419c-8747-523f99ebd94b">
<title>__TITLE__</title>
<meta name="description" content="__DESC__">
<link rel="canonical" href="__CANONICAL__">
<style>__CSS__
  .crumb{font-size:13px;color:var(--muted);margin:0 0 8px}
  .vshero{padding:34px 0 8px}
  .vshero h1{font-size:clamp(25px,4.4vw,40px);line-height:1.12;margin:0 0 10px;max-width:30ch}
  .vshero .disclosure{margin-top:16px}
  table.vs{min-width:620px}
  table.vs thead th{white-space:normal}
  table.vs th[scope="row"]{color:var(--muted);font-weight:600;width:180px}
  table.vs tbody td{font-weight:600;font-size:14px}
  table.vs .mmaker{margin:2px 0 6px}
  ul.otherbikes{list-style:none;padding:0;margin:0;display:grid;gap:8px}
  ul.otherbikes a{font-size:14.5px}
</style>
</head>
<body>
<header class="top"><div class="wrap">
  <a class="brand" href="../../" style="color:inherit;text-decoration:none">Commuter E-Bikes CA</a>
  <span class="stamp">Prices and specs checked <strong>__CHECKED__</strong></span>
</div></header>

<main class="wrap">
  <section class="vshero" style="border-top:none">
    <p class="crumb"><a href="../../">All __N_WORD__ commuter e-bikes, compared</a> &rsaquo; Head to head</p>
    <h1>__H1__</h1>
    <p class="deck">__DECK__</p>
    <p class="disclosure" role="note"><strong>Disclosure:</strong> this page has no live affiliate links. Nothing here is paid for and no purchase through this page earns anyone a commission today; every link goes to a maker's own page or to another page on this site.</p>
  </section>

  <section id="table">
    <h2>Side by side</h2>
    <p class="sub">Two columns, one row per published field. Each cell is the figure the maker publishes on its own product page, read __CHECKED__; where a maker publishes no figure for a field, the row is absent rather than filled in.</p>
    <div class="tablewrap">
      <table class="vs">
        <caption>Specifications as published by each maker, read __CHECKED__. Prices are in Canadian dollars. Claimed range is the maker's own estimate, not a test result.</caption>
        <thead><tr>
          <th scope="col">Specification</th>
          <th scope="col">__COLA__</th>
          <th scope="col">__COLB__</th>
        </tr></thead>
        <tbody>
        __ROWS__
        </tbody>
      </table>
    </div>
  </section>

  <section id="who">
    <h2>Who each one suits</h2>
    <p class="sub">Each summary below is the one this site already publishes on that model's own page &mdash; not a new verdict written for this comparison.</p>
    <div class="details">
      __WHO__
    </div>
  </section>

  <section id="next">
    <h2>Read the rest</h2>
    <ul class="otherbikes">
      __NEXT__
    </ul>
  </section>

  <section id="source">
    <h2>Where these numbers come from</h2>
    <ul class="sources">
      __SOURCES__
    </ul>
  </section>
</main>

<footer><div class="wrap">
  <p><strong>Disclosure:</strong> this page has no live affiliate links for either bike. Nothing here is paid for and no purchase through this page earns anyone a commission today; the only product links above go to the makers' own pages. If a paid partner link is ever added, it will be labelled as one.</p>
  <p>This is general product information, not advice about your particular riding, health or local by-laws. Check your province's e-bike rules before buying. Prices and stock change daily.</p>
  <p>Built __CHECKED__ by the GAMMA project. Data: <a href="../../data/products.json">products.json</a> &middot; <a href="../../">the comparison</a> &middot; <a href="../../how-far/">the range picker</a>.</p>
</div></footer>
</body>
</html>
"""

def vs_page(a, b):
    pa, pb = BY_ID[a], BY_ID[b]
    slug = pair_slug(a, b)
    mn_a, mn_b = "%s %s" % (pa["maker"], pa["model"]), "%s %s" % (pb["maker"], pb["model"])
    title = "%s vs %s in Canada \u2014 specs compared | Commuter E-Bikes CA" % (mn_a, mn_b)
    desc = ("%s (%s) vs %s (%s): motor, torque, battery, claimed range, weight, brakes, class and "
            "warranty side by side, from each maker's own product page, checked %s."
            % (mn_a, pa["price_display"], mn_b, pb["price_display"], CHECKED))
    deck = ("%s and %s both sell in Canada. Every figure below was read from the two makers' own product "
            "pages on %s \u2014 not from memory, and not a test result." % (mn_a, mn_b, CHECKED))
    who = "\n      ".join(
        '<article class="detail"><h3>%s %s <span class="dprice">%s</span></h3>'
        '<p><a href="../../bikes/%s/">Full %s %s specifications</a></p><p>%s</p></article>'
        % (esc(q["maker"]), esc(q["model"]), esc(q["price_display"]), esc(q["id"]),
           esc(q["maker"]), esc(q["model"]), esc(q["best_for"]))
        for q in (pa, pb))
    links = ['<li><a href="../../">All %s commuter e-bikes, compared side by side</a></li>' % esc(N_WORD)]
    for q in (pa, pb):
        links.append('<li><a href="../../bikes/%s/">%s %s &mdash; %s, full specifications</a></li>'
                     % (esc(q["id"]), esc(q["maker"]), esc(q["model"]), esc(q["price_display"])))
    links.append('<li><a href="../../how-far/">How far will it go? Range against your commute</a></li>')
    links.append('<li><a href="../../guide/canada-commuter-ebike-guide.pdf" download>The free decision-guide PDF</a></li>')
    for c, d in PAIRS:
        if (c, d) != (a, b):
            links.append('<li><a href="../%s/">%s</a></li>' % (esc(pair_slug(c, d)), esc(pair_label(c, d))))
    out = (VS_PAGE
           .replace("__CSS__", CSS)
           .replace("__N_WORD__", esc(N_WORD))
           .replace("__TITLE__", esc(title))
           .replace("__DESC__", esc(desc))
           .replace("__CANONICAL__", "%s/vs/%s/" % (SITE, slug))
           .replace("__CHECKED__", esc(CHECKED))
           .replace("__H1__", esc(pair_label(a, b)))
           .replace("__DECK__", esc(deck))
           .replace("__COLA__", vs_col(pa))
           .replace("__COLB__", vs_col(pb))
           .replace("__ROWS__", vs_rows(a, b))
           .replace("__WHO__", who)
           .replace("__NEXT__", "\n      ".join(links))
           .replace("__SOURCES__", "\n      ".join(source_html(q) for q in (pa, pb))))
    write_page(os.path.join(ROOT, "vs", slug, "index.html"), out, "vs-%s" % slug)

for _pa, _pb in PAIRS:
    vs_page(_pa, _pb)

# ================================================================ "what a commute costs" (the linkable asset)
# The one page on this site a third party would cite: what it actually costs, per year, to move a
# Canadian commuter by e-bike, by car and by transit. Built ONLY from published, dated figures, every
# one named in the sources block below - the CAA Driving Costs Calculator (per province: fuel cost per
# year, fuel price, electricity price), the Canada Revenue Agency (its 2026 reasonable per-kilometre
# rate), each city's own transit agency, and this site's own published battery and range figures. No
# config.js and no affiliate element is emitted here at all; every field comes from the data blocks.
COST_DISTANCE_KM = 12500
COST_HEADLINE_MODEL = "velotric-discover-3"
COST_READ = "2026-10-09"
CAA_VEHICLE = "2025 Nissan Sentra (mainstream gas passenger car)"
_CAA_BASE = "https://carcosts.caa.ca/results/%s/passenger_mainstream/ice"
CRA_URL = ("https://www.canada.ca/en/revenue-agency/services/tax/businesses/topics/payroll/"
           "benefits-allowances/automobile/automobile-motor-vehicle-allowances/"
           "reasonable-kilometre-allowance.html")
CRA_YEAR = "2026"
CRA_FIRST_5000, CRA_AFTER = 0.73, 0.67

# CAA Driving Costs Calculator, passenger_mainstream/ice, read 2026-10-09. Every province carries the
# SAME vehicle (the 2025 Nissan Sentra, its best-in-class mainstream gas car) at 12,500 km/year, 55%
# city / 45% highway, so the provinces differ only by fuel price, electricity price and registration.
# fuel = fuel cost per year (CA$); litre = fuel price (cents/L); kwh = electricity price (cents/kWh);
# reg = licence and registration (CA$). Depreciation and maintenance are national in CAA's figures.
CAA_PROVINCES = {
    "Ontario":          dict(slug="ontario",          fuel=1506.11, litre=181.87, kwh=20.2, reg=0.00),
    "Quebec":           dict(slug="quebec",           fuel=1635.88, litre=197.54, kwh=14.1, reg=186.97),
    "British Columbia": dict(slug="british-columbia", fuel=1746.10, litre=210.85, kwh=16.8, reg=94.00),
    "Alberta":          dict(slug="alberta",          fuel=1242.52, litre=150.04, kwh=26.3, reg=200.00),
    "Manitoba":         dict(slug="manitoba",         fuel=1276.14, litre=154.10, kwh=16.5, reg=129.00),
}
CAA_DEPRECIATION, CAA_MAINTENANCE = 2747.00, 296.50
CAA_FUEL_ECONOMY = 6.55
COST_PROVINCE_ORDER = ["Ontario", "Quebec", "British Columbia", "Alberta", "Manitoba"]

# Each city's own transit agency, read 2026-10-09. pass_price = the adult monthly (or month-equivalent)
# figure the agency publishes; single = the adult single fare it publishes.
COST_CITIES = [
    dict(city="Toronto", province="Ontario", agency="TTC",
         single=3.30, single_label="adult single fare, PRESTO",
         pass_price=143.00, pass_label="adult 12-month pass",
         source="https://www.ttc.ca/Fares-and-passes",
         note="The TTC discontinued its adult monthly pass on 31 August 2026; pay-as-you-go fares are now capped after 47 paid trips in a calendar month, and the adult 12-month pass is CA$143.00 a month."),
    dict(city="Ottawa", province="Ontario", agency="OC Transpo",
         single=4.10, single_label="adult fare, Presto",
         pass_price=138.50, pass_label="adult monthly pass",
         source="https://www.octranspo.com/en/fares/",
         note="OC Transpo caps a month of fares at the price of an adult monthly pass, CA$138.50."),
    dict(city="Montreal", province="Quebec", agency="STM",
         single=3.75, single_label="1 trip, All modes A",
         pass_price=110.00, pass_label="Monthly, All Modes A",
         source="https://stm.info/en/info/fares/transit-fares/monthly-all-modes",
         note="The STM's Monthly, All Modes A pass is CA$110.00; a single All modes A trip is CA$3.75."),
    dict(city="Calgary", province="Alberta", agency="Calgary Transit",
         single=4.00, single_label="adult cash fare",
         pass_price=126.00, pass_label="adult monthly pass",
         source="https://www.calgarytransit.com/fares---passes.html",
         note="Calgary Transit's 2026 adult fares: CA$4.00 single, CA$126.00 adult monthly pass."),
    dict(city="Edmonton", province="Alberta", agency="ETS",
         single=3.00, single_label="adult Arc, 90-minute",
         pass_price=102.00, pass_label="adult Arc monthly fare cap",
         source="https://www.edmonton.ca/ets/fares-passes",
         note="Edmonton's ETS charges CA$3.00 for a 90-minute adult Arc trip and caps a month of adult Arc fares at CA$102."),
    dict(city="Vancouver", province="British Columbia", agency="TransLink",
         single=2.85, single_label="adult stored-value, 1 zone",
         pass_price=117.20, pass_label="adult 1-zone monthly pass",
         source="https://www.translink.ca/transit-fares/pricing-and-fare-zones",
         note="TransLink's adult 1-zone monthly pass is CA$117.20; a 1-zone stored-value single fare is CA$2.85."),
    dict(city="Winnipeg", province="Manitoba", agency="Winnipeg Transit",
         single=3.10, single_label="full fare, e-cash",
         pass_price=119.35, pass_label="monthly e-pass",
         source="https://winnipegtransit.com/fares",
         note="Winnipeg Transit's 2026 fares: CA$3.10 full fare on e-cash, CA$119.35 monthly e-pass."),
]

# Battery capacity per model, in Wh, taken from the maker's own published battery string in
# data/products.json (guarded below). The maker's claimed range in km is RANGE_PARSE[...]["high"],
# already read from the maker's product page and used by the range picker. Wh/km is this page's own
# arithmetic on those two published inputs.
BATTERY_WH = {"radster-road": 720.0, "radkick-7speed": 360.0, "velotric-tempo": 374.0,
              "velotric-discover-3": 730.0, "surface604-rook": 960.0,
              "aventon-soltera-2-5": 345.6, "ohm-cruise-3": 504.0}
assert set(BATTERY_WH) == {q["id"] for q in PRODUCTS}, "BATTERY_WH is out of step with products.json"
for _pid, _wh in BATTERY_WH.items():
    assert ("%g" % _wh) in BY_ID[_pid]["battery"], \
        "battery %g is not in the published battery string for %s: %r" % (_wh, _pid, BY_ID[_pid]["battery"])
assert COST_HEADLINE_MODEL in BATTERY_WH, "the headline model is not in the catalogue"


def _wh_per_km(pid):
    return BATTERY_WH[pid] / RANGE_PARSE[pid]["high"]


def _kwh_per_year(pid):
    return _wh_per_km(pid) * COST_DISTANCE_KM / 1000.0


def _ca(x):
    return "CA$%s" % format(x, ",.2f")


CRA_ANNUAL = CRA_FIRST_5000 * 5000 + CRA_AFTER * (COST_DISTANCE_KM - 5000)

# ---- the rows, every cell derived here from the data above (nothing typed by hand)
def _cost_city_row(c):
    p = CAA_PROVINCES[c["province"]]
    charge = _kwh_per_year(COST_HEADLINE_MODEL) * (p["kwh"] / 100.0)
    return ('<tr><th scope="row" class="model">%s<span class="prov">%s</span></th>'
            '<td class="prov">%s</td>'
            '<td class="num">%s</td><td class="num">%s</td><td class="num">%s</td></tr>'
            % (esc(c["city"]), esc(c["agency"]), esc(c["province"]),
               _ca(charge), _ca(p["fuel"]), _ca(c["pass_price"] * 12)))


COST_BILL_ROWS = "\n        ".join(_cost_city_row(c) for c in COST_CITIES)


def _cost_ebike_row(q):
    return ('<tr><th scope="row" class="model"><a class="mname" href="../bikes/%s/">%s</a>'
            '<span class="mmaker">%s</span></th>'
            '<td>%s</td><td class="num">%s km</td><td class="num">%s</td><td class="num">%s</td></tr>'
            % (esc(q["id"]), esc(q["model"]), esc(q["maker"]), esc(q["battery"]),
               format(RANGE_PARSE[q["id"]]["high"], ",d"), format(_wh_per_km(q["id"]), ",.2f"),
               format(_kwh_per_year(q["id"]), ",.2f")))


COST_EBIKE_ROWS = "\n        ".join(_cost_ebike_row(q) for q in ORDER)


def _cost_car_row(pname):
    p = CAA_PROVINCES[pname]
    allin = p["fuel"] + CAA_DEPRECIATION + CAA_MAINTENANCE + p["reg"]
    return ('<tr><th scope="row" class="model">%s</th>'
            '<td class="num">%s</td><td class="num">%s</td><td class="num">%s</td>'
            '<td class="num">%s</td><td class="num">%s</td></tr>'
            % (esc(pname), "$%.2f" % (p["litre"] / 100.0), "$%.3f" % (p["kwh"] / 100.0),
               _ca(p["fuel"]), _ca(p["reg"]), _ca(allin)))


COST_CAR_ROWS = "\n        ".join(_cost_car_row(p) for p in COST_PROVINCE_ORDER)

# ---- prose and the sources block (all text with figures lives here, never in the template)
COST_TITLE = "What a Canadian commuter actually pays: e-bike vs car vs transit, per year | Commuter E-Bikes CA"
COST_DESC = ("A commuter's yearly bill for the same distance, three ways - charging an e-bike, fuelling a "
             "small car, or a transit pass - in seven Canadian cities. Every figure from a named, dated "
             "source; nothing from memory.")
COST_INTRO = ("A commuter's yearly bill for the same distance, three ways: charging an e-bike, fuelling a "
              "small car, or buying a transit pass. Every figure below is published and dated - the CAA "
              "Driving Costs Calculator, the Canada Revenue Agency, and each city's own transit agency - "
              "and every one is named at the bottom of this page. Nothing here is remembered or guessed; "
              "where a figure does not exist, the page says so instead of filling the gap.")
COST_DISCLOSURE = ("this page has no live affiliate links and nothing to buy. It carries no partner link "
                   "and no commission, and every source is a public one, named in full below.")
COST_BILL_SUB = ("Seven cities, one commuter each. The car figures are the province's, because that is how "
                 "the CAA publishes them; the transit figure is the city's own pass. Electricity and fuel "
                 "prices come from the same CAA province records.")
COST_BILL_NOTE = ("E-bike, to charge: the Velotric Discover 3 - this site's all-round pick - using the "
                  "maker's claimed range and the province's published electricity price, for %s km a year. "
                  "Car, fuel only: CAA's yearly fuel cost for a %s at the same distance. Transit, pass: "
                  "the city's adult monthly (or month-equivalent) pass, times twelve - a pass is unlimited "
                  "travel, so transit is compared as an annual bill, not per kilometre."
                  % (format(COST_DISTANCE_KM, ",d"), CAA_VEHICLE))
COST_BILL_CAVEAT = ("This is the running bill, not the whole cost of ownership: it leaves out insurance, "
                    "the price of the vehicle itself, and any transit trips beyond the commute. What each "
                    "figure can and cannot tell you is set out under \u201cWhat is not in these numbers\u201d.")
COST_CRA_SUB = ("Canada's tax system publishes its own idea of what it costs to run a car, per kilometre: "
                "the CRA reasonable per-kilometre rate that an employer may reimburse tax-free. For %s it "
                "is $%.2f for the first %s km and $%.2f for every kilometre after (provinces; the "
                "territories add four cents)." % (CRA_YEAR, CRA_FIRST_5000, format(5000, ",d"), CRA_AFTER))
COST_CRA_ANNUAL = _ca(CRA_ANNUAL)
COST_CRA_LINE = ("$%.2f \u00d7 %s km, plus $%.2f \u00d7 %s km, at %s km a year = %s. One federal, "
                 "per-province number that already folds in fuel, maintenance, depreciation, insurance "
                 "and finance - the closest thing Canada has to an official cost of driving."
                 % (CRA_FIRST_5000, format(5000, ",d"), CRA_AFTER, format(COST_DISTANCE_KM - 5000, ",d"),
                    format(COST_DISTANCE_KM, ",d"), _ca(CRA_ANNUAL)))
COST_CRA_NOTE = ("The rate is set for business use of a personal vehicle and is identical in every "
                 "province; only the territories add four cents. It is not a consumer price list, but it "
                 "is the government's own published per-kilometre cost - and at %s km it comes to %s a year."
                 % (format(COST_DISTANCE_KM, ",d"), _ca(CRA_ANNUAL)))
COST_EBIKE_SUB = ("Energy per kilometre is this page's own arithmetic: each model's published battery "
                  "capacity divided by the maker's own claimed range. Both inputs come from the maker's "
                  "product page (read %s); the ratio is derived here and stated nowhere else." % COST_READ)
COST_EBIKE_NOTE = ("Battery and range are the maker's published figures, the same ones on this site's "
                   "model pages; Wh/km and the yearly kWh are derived from them. A lower Wh/km is a more "
                   "efficient bike - but only against each maker's own claim.")
COST_EBIKE_CAVEAT = ("Two honest limits. The maker's claimed range is a best case, so these Wh/km figures "
                     "are a floor - a real rider uses more energy per kilometre. And a charger is not "
                     "lossless: the battery stores the watt-hours shown, while the wall draws somewhat "
                     "more, and no maker here publishes charger efficiency, so it is not modelled.")
COST_CAR_SUB = ("The same CAA province record the e-bike price comes from, for a %s at %s km a year (55%% "
                "city, 45%% highway). All-in is fuel plus registration plus CAA's depreciation and "
                "maintenance; it leaves out insurance, which CAA asks the driver to enter."
                % (CAA_VEHICLE, format(COST_DISTANCE_KM, ",d")))
COST_CAR_NOTE = ("CAA publishes a province's fuel price and electricity price with the same vehicle, so "
                 "the provinces differ only by price and by registration. Depreciation (%s) and "
                 "maintenance (%s) are national figures; the fuel price is not."
                 % (_ca(CAA_DEPRECIATION), _ca(CAA_MAINTENANCE)))
COST_CAR_CAVEAT = ("All-in is not a sticker price: depreciation is CAA's average for the category, and "
                   "insurance is left out because CAA does not publish it. The fuel column is the one "
                   "figure that does not depend on how the car was bought.")
COST_SOURCES_SUB = ("Every number on this page traces to one of these, each read on the date shown. Where "
                    "a figure does not exist, it is admitted above rather than filled in. Read %s." % COST_READ)
COST_CAVEATS = ("Claimed range is the maker's own estimate. Transit fares are set by each agency and change "
                "most years; the CRA rate is set annually and may differ after the year shown. Prices were "
                "read on the dates above and may since have moved. This page is general cost information, "
                "not financial or tax advice.")

COST_MISSING = "\n      ".join(
    "<li>%s</li>" % t for t in [
        "<strong>Insurance.</strong> Not published by the sources used here. The CAA calculator asks the "
        "driver to enter their own premium, and the CRA per-kilometre rate folds insurance in - so no "
        "insurance number appears anywhere on this page rather than a guess.",
        "<strong>The price of the vehicle.</strong> An e-bike, a car and a transit pass are bought very "
        "differently. This page compares what it costs to keep moving, not what it costs to acquire.",
        "<strong>Charger losses and battery wear.</strong> No maker here publishes charger efficiency or a "
        "battery-degradation curve, so neither is modelled.",
        "<strong>The maker's claimed range is optimistic.</strong> The e-bike energy figures use it, which "
        "makes them the lowest honest estimate - a floor, not a measured result.",
        "<strong>Transit is not distance-matched.</strong> A pass is unlimited travel, so it is compared as "
        "an annual bill rather than per kilometre. Each city's single fare is in the sources below.",
        "<strong>One rate, two tiers.</strong> The CRA figure uses the first-5,000-km rate and the rate "
        "after it; a longer year averages lower, a shorter one higher.",
    ])


def _cost_src(text):
    return "<li>%s</li>" % text


COST_SOURCES = "\n        ".join(
    [_cost_src("<strong>CAA Driving Costs Calculator</strong> \u2014 carcosts.caa.ca, the per-province "
               "results for the %s at %s km a year (55%% city, 45%% highway). Gives the fuel cost per "
               "year, the fuel price ($/L) and the electricity price ($/kWh) for each province. Read %s. "
               "Source pages: %s"
               % (esc(CAA_VEHICLE), format(COST_DISTANCE_KM, ",d"), esc(COST_READ),
                  " \u00b7 ".join('<a href="%s" target="_blank" rel="noopener nofollow">%s</a>'
                                  % (esc(_CAA_BASE % CAA_PROVINCES[p]["slug"]), esc(p))
                                  for p in COST_PROVINCE_ORDER))),
     _cost_src("<strong>Canada Revenue Agency</strong>, \u201cMotor vehicle provided by the employer\u201d "
               "\u2014 the %s reasonable per-kilometre rate: $%.2f for the first %s km and $%.2f after "
               "(provinces; the territories add four cents). Read %s. "
               "<a href=\"%s\" target=\"_blank\" rel=\"noopener nofollow\">canada.ca</a>"
               % (esc(CRA_YEAR), CRA_FIRST_5000, format(5000, ",d"), CRA_AFTER, esc(COST_READ), esc(CRA_URL))),
     _cost_src("<strong>E-bike energy</strong> \u2014 this site's own "
               "<a href=\"../data/products.json\">data/products.json</a>: each model's published battery "
               "capacity (Wh) and the maker's own claimed range, both read from the maker's product page "
               "(checked %s). Wh/km and the yearly kWh are this page's arithmetic on those two figures."
               % esc(CHECKED))]
    + [_cost_src("<strong>%s</strong> \u2014 %s, %s. %s Read %s. "
                 "<a href=\"%s\" target=\"_blank\" rel=\"noopener nofollow\">%s fares</a>"
                 % (esc(c["city"]), esc(c["agency"]), esc(c["province"]), esc(c["note"]), esc(COST_READ),
                    esc(c["source"]), esc(c["agency"])))
       for c in COST_CITIES])

COST_PAGE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__</title>
<meta name="description" content="__DESC__">
<link rel="canonical" href="__CANONICAL__">
<meta property="og:type" content="article">
<meta property="og:site_name" content="Commuter E-Bikes CA">
<meta property="og:title" content="__OGTITLE__">
<meta property="og:description" content="__DESC__">
<meta property="og:url" content="__CANONICAL__">
<meta name="twitter:card" content="summary">
<meta name="twitter:title" content="__OGTITLE__">
<meta name="twitter:description" content="__DESC__">
<style>__CSS__
  .crumb{font-size:13px;color:var(--muted);margin:0 0 8px}
  .costhero{padding:34px 0 8px}
  .costhero h1{font-size:clamp(27px,4.6vw,42px);line-height:1.12;margin:0 0 12px;max-width:28ch}
  table.cost td.num,table.cost th.num{text-align:right;font-variant-numeric:tabular-nums;font-weight:700;white-space:nowrap}
  table.cost .model{font-weight:700}
  table.cost .prov{display:block;color:var(--muted);font-size:12.5px;font-weight:400;margin-top:2px}
  table.cost td.prov{font-weight:400;color:var(--muted);white-space:nowrap}
  .big{font-size:clamp(30px,6vw,54px);font-weight:700;font-family:Georgia,"Iowan Old Style","Times New Roman",serif;line-height:1;margin:0 0 8px}
  .callout{background:var(--card);border:1px solid var(--line);border-left:4px solid var(--accent);border-radius:8px;padding:18px 20px;margin:18px 0;max-width:74ch}
  ol.method{margin:0;padding-left:22px}
  ol.method li{margin:0 0 10px;max-width:78ch;color:#333842}
  ul.otherbikes{list-style:none;padding:0;margin:0;display:grid;gap:8px}
  ul.otherbikes a{font-size:14.5px}
  code{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;font-size:13px}
  p.mta{margin-top:14px}
  p.mtb{margin-top:18px}
</style>
</head>
<body>
<header class="top"><div class="wrap">
  <a class="brand" href="../" style="color:inherit;text-decoration:none">Commuter E-Bikes CA</a>
  <span class="stamp">Figures checked <strong>__CHECKED__</strong></span>
</div></header>

<main class="wrap">
  <section class="costhero" style="border-top:none">
    <p class="crumb"><a href="../">All __N_WORD__ commuter e-bikes, compared</a> &rsaquo; What a commute costs</p>
    <h1>What a Canadian commuter actually pays: e-bike vs car vs transit</h1>
    <p class="deck">__INTRO__</p>
    <p class="disclosure" role="note"><strong>Disclosure:</strong> __DISC__</p>
  </section>

  <section id="bill">
    <h2>The bill, per year, in seven cities</h2>
    <p class="sub">__BILL_SUB__</p>
    <div class="tablewrap">
      <table class="cost">
        <caption>__BILL_NOTE__</caption>
        <thead><tr>
          <th scope="col">City</th><th scope="col">Province</th>
          <th scope="col" class="num">E-bike, to charge</th>
          <th scope="col" class="num">Car, fuel only</th>
          <th scope="col" class="num">Transit, pass</th>
        </tr></thead>
        <tbody>
        __BILL_ROWS__
        </tbody>
      </table>
    </div>
    <p class="note mta">__BILL_CAVEAT__</p>
  </section>

  <section id="cra">
    <h2>The tax system's own number for a car</h2>
    <p class="sub">__CRA_SUB__</p>
    <div class="callout">
      <p class="big">__CRA_ANNUAL__</p>
      <p>__CRA_LINE__</p>
    </div>
    <p class="note">__CRA_NOTE__</p>
  </section>

  <section id="ebike">
    <h2>The e-bike's own energy, model by model</h2>
    <p class="sub">__EBIKE_SUB__</p>
    <div class="tablewrap">
      <table class="cost">
        <caption>__EBIKE_NOTE__</caption>
        <thead><tr>
          <th scope="col">Model</th><th scope="col">Battery</th>
          <th scope="col" class="num">Maker range</th>
          <th scope="col" class="num">Wh/km</th>
          <th scope="col" class="num">kWh / year</th>
        </tr></thead>
        <tbody>
        __EBIKE_ROWS__
        </tbody>
      </table>
    </div>
    <p class="note mta">__EBIKE_CAVEAT__</p>
  </section>

  <section id="car">
    <h2>The car, province by province</h2>
    <p class="sub">__CAR_SUB__</p>
    <div class="tablewrap">
      <table class="cost">
        <caption>__CAR_NOTE__</caption>
        <thead><tr>
          <th scope="col">Province</th>
          <th scope="col" class="num">Fuel $/L</th>
          <th scope="col" class="num">Electricity $/kWh</th>
          <th scope="col" class="num">Fuel $/yr</th>
          <th scope="col" class="num">Registration $/yr</th>
          <th scope="col" class="num">All-in $/yr</th>
        </tr></thead>
        <tbody>
        __CAR_ROWS__
        </tbody>
      </table>
    </div>
    <p class="note mta">__CAR_CAVEAT__</p>
  </section>

  <section id="missing">
    <h2>What is not in these numbers</h2>
    <ol class="method">
      __MISSING__
    </ol>
  </section>

  <section id="sources">
    <h2>Every figure and where it comes from</h2>
    <p class="sub">__SOURCES_SUB__</p>
    <ul class="sources">__SOURCES__</ul>
    <p class="note mtb">__CAVEATS__</p>
  </section>

  <section id="next">
    <h2>Read the rest</h2>
    <ul class="otherbikes">
      <li><a href="../">All __N_WORD__ commuter e-bikes, compared side by side</a></li>
      <li><a href="../guide/">The free decision guide</a></li>
      <li><a href="../how-far/">How far will it go? Range against your commute</a></li>
      <li><a href="../stats/">Page views on this site &mdash; the counts, read live</a></li>
    </ul>
  </section>
</main>

<footer><div class="wrap">
  <p><strong>Disclosure:</strong> __DISC__</p>
  <p>This is general cost information, not financial or tax advice, and not advice about your particular riding, health or local by-laws. Check your province's e-bike rules before buying.</p>
  <p>Built __CHECKED__ by the GAMMA project. Sources: the CAA Driving Costs Calculator, the Canada Revenue Agency, and each city's own transit agency &mdash; all named above. Data: <a href="../data/products.json">products.json</a> &middot; <a href="../">the comparison</a>.</p>
</div></footer>
</body>
</html>
"""

# The template may carry no figure of its own: every digit in the output must come from a substitution,
# or a hand-typed number could go live on a page whose whole point is that nothing is typed by hand.
# Style, script and tags are dropped first - h1/h2 tag names carry digits of their own, which are not
# page content - leaving only visible copy, where any digit must be a substituted figure.
_tmpl_probe = re.sub(r"(?s)<(style|script).*?</\1>", " ", COST_PAGE)
_tmpl_probe = re.sub(r"(?s)<[^>]+>", " ", _tmpl_probe)
_tmpl_probe = re.sub(r"__[A-Z_0-9]*__", "", _tmpl_probe)
assert not re.search(r"\d", _tmpl_probe), \
    "a figure is typed into the commute-costs template instead of being substituted"

_COST_SUBST = {
    "__CSS__": CSS,
    "__N_WORD__": esc(N_WORD),
    "__CHECKED__": esc(CHECKED),
    "__TITLE__": esc(COST_TITLE),
    "__OGTITLE__": esc(COST_TITLE),
    "__DESC__": esc(COST_DESC),
    "__CANONICAL__": "%s/commute-costs/" % SITE,
    "__INTRO__": esc(COST_INTRO),
    "__DISC__": esc(COST_DISCLOSURE),
    "__BILL_SUB__": esc(COST_BILL_SUB),
    "__BILL_NOTE__": esc(COST_BILL_NOTE),
    "__BILL_ROWS__": COST_BILL_ROWS,
    "__BILL_CAVEAT__": esc(COST_BILL_CAVEAT),
    "__CRA_SUB__": esc(COST_CRA_SUB),
    "__CRA_ANNUAL__": esc(COST_CRA_ANNUAL),
    "__CRA_LINE__": esc(COST_CRA_LINE),
    "__CRA_NOTE__": esc(COST_CRA_NOTE),
    "__EBIKE_SUB__": esc(COST_EBIKE_SUB),
    "__EBIKE_NOTE__": esc(COST_EBIKE_NOTE),
    "__EBIKE_ROWS__": COST_EBIKE_ROWS,
    "__EBIKE_CAVEAT__": esc(COST_EBIKE_CAVEAT),
    "__CAR_SUB__": esc(COST_CAR_SUB),
    "__CAR_NOTE__": esc(COST_CAR_NOTE),
    "__CAR_ROWS__": COST_CAR_ROWS,
    "__CAR_CAVEAT__": esc(COST_CAR_CAVEAT),
    "__MISSING__": COST_MISSING,
    "__SOURCES_SUB__": esc(COST_SOURCES_SUB),
    "__SOURCES__": COST_SOURCES,
    "__CAVEATS__": esc(COST_CAVEATS),
}
_cost_out = COST_PAGE
for _k, _v in _COST_SUBST.items():
    _cost_out = _cost_out.replace(_k, _v)
write_page(os.path.join(ROOT, "commute-costs", "index.html"), _cost_out, "commute-costs")

# ---- the page is read back and checked before the sitemap is written
COST_FILE = os.path.join(ROOT, "commute-costs", "index.html")
COST_TEXT = open(COST_FILE, encoding="utf-8").read()

# 1. nothing here can pay, and it says nothing about the status of any program.
for _bad in ("config.js", "AFFILIATE_", 'data-aff=', 'class="buyaff"'):
    assert _bad not in COST_TEXT, "affiliate element on the commute-costs page: %r" % _bad

# 2. its own head: title, description, canonical and the social card.
assert "<link rel=\"canonical\" href=\"%s/commute-costs/\">" % SITE in COST_TEXT
for _head in ('<title>', 'name="description"', 'property="og:type"', 'property="og:site_name"',
              'property="og:title"', 'property="og:description"', 'property="og:url"',
              'name="twitter:card"', 'name="twitter:title"', 'name="twitter:description"'):
    assert _head in COST_TEXT, "commute-costs page is missing %s" % _head

# 3. every number that reached the page must come from a substitution, precomputed above - the guard a
#    hand-typed figure would trip.
_allowed_nums = set()
for _v in _COST_SUBST.values():
    _allowed_nums |= set(re.findall(r"\d[\d,.]*", str(_v)))
_body_text = re.sub(r"(?s)<(style|script).*?</\1>", " ", COST_TEXT.split("<body>", 1)[1])
_body_text = html.unescape(re.sub(r"(?s)<[^>]+>", " ", _body_text))
_page_nums = set(re.findall(r"\d[\d,.]*", _body_text))
assert _page_nums <= _allowed_nums, \
    "number on the commute-costs page with no published source: %r" % sorted(_page_nums - _allowed_nums)
print("commute-costs page: %d bytes, %d figures, every one substituted from a named source, no affiliate element"
      % (len(COST_TEXT), len(_page_nums)))

# ================================================================ gear: helmets, locks and lights
# Every other page here is a bike spec sheet. This is the one page aimed at the reader who already has
# a bike and needs gear - a helmet, a lock, a set of lights - and it is deliberately crew-owned: it
# loads NO config.js and emits NO .aff element, and it links to no product at all, so it earns nothing
# today and can be pointed at a program later without a rebuild. Every figure on it is the makers' own
# published figure for a bike already on this site, substituted from data/products.json; the template
# carries no digit of its own and the build aborts on any number that is not one of those substitutions.
GEAR_READ = COST_READ  # the same re-verification date the catalogue figures were read on
GEAR_TITLE = ("E-bike gear in Canada: helmets, locks and lights, and what each bike here is rated to "
              "carry | Commuter E-Bikes CA")
GEAR_DESC = ("What to check on a helmet, a lock and a set of lights for a Canadian e-bike commute, plus "
             "the maker's own maximum-load figure for each of the %s bikes on this site. No product "
             "links and nothing paid for." % N_WORD)
GEAR_INTRO = ("A helmet, a lock and a set of lights are the three things a commuter ends up buying in "
              "the first month, and the three where the wrong buy is worthless or dangerous. This page "
              "is what to check on each of them. It recommends no particular product: there is no "
              "product link on it, nothing on it is paid for, and the only figures on it are the "
              "makers' own published figures for the bikes on this site.")
GEAR_DISCLOSURE = ("this page carries no affiliate link and no product link at all, and nothing on it "
                   "earns a commission. It is general buying guidance, not legal, medical or safety "
                   "advice for your particular riding or your province's rules.")

GEAR_HELMET_HEAD = "Helmets: fit before features"
GEAR_HELMET = [
    ("In Canada a bicycle helmet must carry a certification mark from a recognised standards body, and "
     "the label inside the shell is where you check it. What an e-bike changes is not the helmet's job "
     "but the speed: the faster the motor can assist you, the more a helmet built and tested for that "
     "speed matters. A bargain leisure-cycling shell and a lid rated for motor-assisted speeds are not "
     "the same product even when they look alike."),
    ("Fit does more than price. A helmet that shifts on your head is not protecting you: it should sit "
     "level and low enough to cover your forehead, the straps should meet just under your ear, and it "
     "should not rock when you shake your head with the buckle done up."),
    ("Rotational-impact systems, of which MIPS is the best known, add a sliding layer between the shell "
     "and your head. They are worth knowing about, but a certified helmet that fits properly beats an "
     "expensive one that does not."),
]
GEAR_LOCK_HEAD = "Locks: two beats one"
GEAR_LOCK = [
    ("Two locks are better than one good lock. On a commuter e-bike the parts that walk away first are "
     "the wheels, the battery and the seatpost, so a heavy lock through the frame plus a second lock or "
     "cable through a wheel covers more than one heavier lock on its own."),
    ("Look for an independent security rating rather than the maker's own claim. Sold Secure and ART "
     "are the two scales you will see on locks sold in Canada; both test a lock by trying to cut, pick "
     "and lever it. A bike worth a few thousand dollars deserves a lock at the top of one of them."),
    ("Match the lock to the bike. Lock to an immovable object, fill the shackle so a jack cannot get "
     "in, and take a removable battery with you. The dearer the bike, the shorter the life of a cheap "
     "cable."),
]
GEAR_LIGHT_HEAD = "Lights: to see by, and to be seen"
GEAR_LIGHT = [
    ("A commuter's lights do two jobs: to see the road, and to be seen. In a city the second matters "
     "more, and it is the one a bargain light fails at - a dim front lamp and a barely-there rear "
     "blinky disappear at dusk beside car headlights."),
    ("Front: bright enough to be seen by a driver in daylight, and aimed low so you do not dazzle "
     "oncoming traffic. Rear: the light that keeps you alive after dark - a steady red on the bike, "
     "and if you can, a second on your helmet or bag, because one rear light can be hidden by a "
     "pannier or a passing car."),
    ("Reflectors are required in most of Canada and most bikes ship with them. Check what is already "
     "in the box before buying anything."),
]

def _gear_para(text):
    return '<p class="gearsec">%s</p>' % esc(text)

GEAR_HELMET_HTML = "\n    ".join(_gear_para(t) for t in GEAR_HELMET)
GEAR_LOCK_HTML = "\n    ".join(_gear_para(t) for t in GEAR_LOCK)
GEAR_LIGHT_HTML = "\n    ".join(_gear_para(t) for t in GEAR_LIGHT)

GEAR_FIT_HEAD = "What each bike here is rated to carry"
GEAR_FIT_SUB = ("The maximum total load each maker publishes for the whole bike - rider and cargo "
                "together. It is the ceiling to stay under when you add a rack bag, a basket or a "
                "child seat; where a maker publishes no such figure, the cell says so rather than "
                "being filled in with a guess.")
GEAR_FIT_CAPTION = ("Each load, weight, class and price below is the maker's own published figure, "
                    "read from its product page on the date shown on that bike's own page.")

def _gear_fit_row(q):
    """One row per bike, every cell the published field itself. No affiliate element is emitted on this
    page at all, so there is nothing here that could pay or that claims a link pays."""
    return ('<tr><th scope="row" class="model"><a class="mname" href="../bikes/%s/">%s</a>'
            '<span class="mmaker">%s</span></th>'
            '<td>%s</td><td>%s</td><td>%s</td><td class="price">%s</td></tr>'
            % (esc(q["id"]), esc(q["model"]), esc(q["maker"]), esc(q.get("payload") or "not published"),
               esc(q["weight"]), esc(q["eclass"]), esc(q["price_display"])))

GEAR_FIT_ROWS = "\n        ".join(_gear_fit_row(q) for q in ORDER)

_GEAR_CHEAP = min(ORDER, key=lambda p: p["price_cad"])
_GEAR_DEAR = max(ORDER, key=lambda p: p["price_cad"])
GEAR_SPECIFIC = ("The bikes on this site run from %s, and the gear is not the same buy at each end. "
                 "The cheapest here is the %s %s at %s; the dearest is the %s %s at %s. Gear is also "
                 "the one purchase that follows you to the next bike, so it is the wrong place to cut "
                 "to the price of the cheapest bike on the page."
                 % (PRICE_SPAN, _GEAR_CHEAP["maker"], _GEAR_CHEAP["model"], _GEAR_CHEAP["price_display"],
                    _GEAR_DEAR["maker"], _GEAR_DEAR["model"], _GEAR_DEAR["price_display"]))

GEAR_SOURCES = "\n        ".join(
    '<li><strong>%s %s</strong> &mdash; the maker\'s own product page, read %s: '
    '<a href="%s" target="_blank" rel="noopener nofollow">%s</a></li>'
    % (esc(q["maker"]), esc(q["model"]), esc(GEAR_READ), esc(q["source_url"]), esc(q["source_url"]))
    for q in ORDER)

GEAR_PAGE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__</title>
<meta name="description" content="__DESC__">
<link rel="canonical" href="__CANONICAL__">
<meta property="og:type" content="article">
<meta property="og:site_name" content="Commuter E-Bikes CA">
<meta property="og:title" content="__OGTITLE__">
<meta property="og:description" content="__DESC__">
<meta property="og:url" content="__CANONICAL__">
<meta name="twitter:card" content="summary">
<meta name="twitter:title" content="__OGTITLE__">
<meta name="twitter:description" content="__DESC__">
<style>__CSS__
  .crumb{font-size:13px;color:var(--muted);margin:0 0 8px}
  .gearhero{padding:34px 0 8px}
  .gearhero h1{font-size:clamp(27px,4.6vw,42px);line-height:1.12;margin:0 0 12px;max-width:28ch}
  p.gearsec{margin:0 0 14px;color:#333842;max-width:74ch}
  table.gear .model{font-weight:700}
  ul.otherbikes{list-style:none;padding:0;margin:0;display:grid;gap:8px}
  ul.otherbikes a{font-size:14.5px}
</style>
</head>
<body>
<header class="top"><div class="wrap">
  <a class="brand" href="../" style="color:inherit;text-decoration:none">Commuter E-Bikes CA</a>
  <span class="stamp">Guidance written <strong>__CHECKED__</strong></span>
</div></header>

<main class="wrap">
  <section class="gearhero" style="border-top:none">
    <p class="crumb"><a href="../">All __N_WORD__ commuter e-bikes, compared</a> &rsaquo; Gear</p>
    <h1>Gear for a Canadian e-bike commute: helmets, locks and lights</h1>
    <p class="deck">__INTRO__</p>
    <p class="disclosure" role="note"><strong>Disclosure:</strong> __DISC__</p>
  </section>

  <section id="helmet">
    <h2>__HELMET_HEAD__</h2>
    __HELMET__
  </section>

  <section id="lock">
    <h2>__LOCK_HEAD__</h2>
    __LOCK__
  </section>

  <section id="lights">
    <h2>__LIGHT_HEAD__</h2>
    __LIGHT__
  </section>

  <section id="load">
    <h2>__FIT_HEAD__</h2>
    <p class="sub">__FIT_SUB__</p>
    <div class="tablewrap">
      <table class="gear">
        <caption>__FIT_CAPTION__</caption>
        <thead><tr>
          <th scope="col">Model</th><th scope="col">Max total load (maker's figure)</th>
          <th scope="col">Weight (maker's figure)</th><th scope="col">Class</th>
          <th scope="col">Price (CAD)</th>
        </tr></thead>
        <tbody>
        __FIT_ROWS__
        </tbody>
      </table>
    </div>
    <p class="note">__SPECIFIC__</p>
  </section>

  <section id="sources">
    <h2>Where the figures come from</h2>
    <p class="sub">The load, weight, class and price in the table above are the makers' own published figures, read from their own product pages on __READ__ &mdash; the same date each bike page carries.</p>
    <ul class="sources">__SOURCES__</ul>
  </section>

  <section id="next">
    <h2>Read the rest</h2>
    <ul class="otherbikes">
      <li><a href="../">All __N_WORD__ commuter e-bikes, compared side by side</a></li>
      <li><a href="../how-far/">How far will it go? Range against your commute</a></li>
      <li><a href="../commute-costs/">What a commute actually costs, e-bike vs car vs transit</a></li>
      <li><a href="../guide/">The free decision guide</a></li>
      <li><a href="../stats/">Page views on this site &mdash; the counts, read live</a></li>
    </ul>
  </section>
</main>

<footer><div class="wrap">
  <p><strong>Disclosure:</strong> __DISC__</p>
  <p>This is general product information, not advice about your particular riding, health or local by-laws. Check your province's e-bike rules before buying.</p>
  <p>Built __CHECKED__ by the GAMMA project. Data: <a href="../data/products.json">products.json</a> &middot; <a href="../">the comparison</a> &middot; <a href="../commute-costs/">what a commute costs</a>.</p>
</div></footer>
</body>
</html>
"""

# The template may carry no figure of its own: every digit in the output must come from a substitution,
# or a hand-typed number could go live on a page whose whole point is that nothing is typed by hand.
_tmpl_probe = re.sub(r"(?s)<(style|script).*?</\1>", " ", GEAR_PAGE)
_tmpl_probe = re.sub(r"(?s)<[^>]+>", " ", _tmpl_probe)
_tmpl_probe = re.sub(r"__[A-Z_0-9]*__", "", _tmpl_probe)
assert not re.search(r"\d", _tmpl_probe), \
    "a figure is typed into the gear template instead of being substituted"

_GEAR_SUBST = {
    "__CSS__": CSS,
    "__N_WORD__": esc(N_WORD),
    "__CHECKED__": esc(CHECKED),
    "__READ__": esc(GEAR_READ),
    "__TITLE__": esc(GEAR_TITLE),
    "__OGTITLE__": esc(GEAR_TITLE),
    "__DESC__": esc(GEAR_DESC),
    "__CANONICAL__": "%s/gear/" % SITE,
    "__INTRO__": esc(GEAR_INTRO),
    "__DISC__": esc(GEAR_DISCLOSURE),
    "__HELMET_HEAD__": esc(GEAR_HELMET_HEAD),
    "__HELMET__": GEAR_HELMET_HTML,
    "__LOCK_HEAD__": esc(GEAR_LOCK_HEAD),
    "__LOCK__": GEAR_LOCK_HTML,
    "__LIGHT_HEAD__": esc(GEAR_LIGHT_HEAD),
    "__LIGHT__": GEAR_LIGHT_HTML,
    "__FIT_HEAD__": esc(GEAR_FIT_HEAD),
    "__FIT_SUB__": esc(GEAR_FIT_SUB),
    "__FIT_CAPTION__": esc(GEAR_FIT_CAPTION),
    "__FIT_ROWS__": GEAR_FIT_ROWS,
    "__SPECIFIC__": esc(GEAR_SPECIFIC),
    "__SOURCES__": GEAR_SOURCES,
}
_gear_out = GEAR_PAGE
for _k, _v in _GEAR_SUBST.items():
    _gear_out = _gear_out.replace(_k, _v)
write_page(os.path.join(ROOT, "gear", "index.html"), _gear_out, "gear")

# ---- the page is read back and checked before the sitemap is written
GEAR_FILE = os.path.join(ROOT, "gear", "index.html")
GEAR_TEXT = open(GEAR_FILE, encoding="utf-8").read()

# 1. nothing here can pay, and it says nothing about the status of any program.
for _bad in ("config.js", "AFFILIATE_", 'data-aff=', 'class="buyaff"'):
    assert _bad not in GEAR_TEXT, "affiliate element on the gear page: %r" % _bad

# 2. its own head: title, description, canonical and the social card.
assert '<link rel="canonical" href="%s/gear/">' % SITE in GEAR_TEXT
for _head in ('<title>', 'name="description"', 'property="og:type"', 'property="og:site_name"',
              'property="og:title"', 'property="og:description"', 'property="og:url"',
              'name="twitter:card"', 'name="twitter:title"', 'name="twitter:description"'):
    assert _head in GEAR_TEXT, "gear page is missing %s" % _head

# 3. no product link: every absolute link on the page is a maker's own product page, never a shop bag.
_hrefs = re.findall(r'href="([^"]+)"', GEAR_TEXT)
_ext = sorted(h for h in _hrefs if h.startswith("http") and not h.startswith(SITE))
assert set(_ext) <= {q["source_url"] for q in ORDER}, \
    "the gear page links off to a non-maker, non-site URL: %r" % [h for h in _ext if h not in {q["source_url"] for q in ORDER}]

# 4. every number that reached the page must come from a substitution, precomputed above - the guard a
#    hand-typed figure would trip.
_allowed_nums = set()
for _v in _GEAR_SUBST.values():
    _allowed_nums |= set(re.findall(r"\d[\d,.]*", str(_v)))
_body_text = re.sub(r"(?s)<(style|script).*?</\1>", " ", GEAR_TEXT.split("<body>", 1)[1])
_body_text = html.unescape(re.sub(r"(?s)<[^>]+>", " ", _body_text))
_page_nums = set(re.findall(r"\d[\d,.]*", _body_text))
assert _page_nums <= _allowed_nums, \
    "number on the gear page with no published source: %r" % sorted(_page_nums - _allowed_nums)
print("gear page: %d bytes, %d figures, every one substituted from the makers' own data, no affiliate "
      "element, no product link" % (len(GEAR_TEXT), len(_page_nums)))

# ================================================================ classes and rules: what Class 1/2/3 mean in Canada
# Every other page here sells a bike; this is the page a rider needs before any of them - what the class
# number on a spec sheet actually means, where a class may ride, what helmet is required, and how the
# provinces differ. Crew-owned like /gear/: it loads NO config.js, emits NO .aff element and links to NO
# product - every off-site link on it is a GOVERNMENT page, asserted below. Nothing on it is typed from
# memory: each rule is stored with the government page it was read from, that page's own date, and a
# verbatim quote, and the build checks that the figures in a province's row really are in its quote. The
# template carries no digit of its own.
RULES_READ = COST_READ  # the same date the catalogue and the cost page were last read on

# ---- the three classes, in the words of a federal agency (Parks Canada) and of a province's own policy
# (Recreation Sites and Trails BC). The honest headline of this page: Canada has no national Class 1/2/3
# law. The three classes are a labelling convention federal land managers and makers use; the rule that
# binds a rider on a public road is provincial and is written in watts and km/h, never as a class number.
RULES_CLASS_SOURCES = [
    dict(name="Parks Canada \u2014 Pacific Rim National Park Reserve",
         url="https://parks.canada.ca/pn-np/bc/pacificrim/activ/cyclisme-cycling",
         date="read 2026-10-09",
         quote=("The three classes of e-bikes are defined as follows: Class 1: e-bikes that are pedal-assist "
                "only, with no throttle, and have a maximum assisted speed of 32 kilometers per hour. "
                "Class 2: e-bikes that also have a maximum speed of 32 kilometers per hour, but are "
                "throttle-assisted. Class 3: e-bikes that are pedal-assist only, with no throttle, and have "
                "a maximum assisted speed of 45 kilometers per hour.")),
    dict(name="Recreation Sites and Trails BC \u2014 e-bike policy",
         url=("https://www2.gov.bc.ca/assets/gov/sports-recreation-arts-and-culture/outdoor-recreation/"
              "camping-and-hiking/recreation-sites-and-trails/ebike_policy_final_04-25-2019.pdf"),
         date="policy dated 2019, read 2026-10-09",
         quote=("A Class 1 e-bike means a bicycle equipped with a motor that provides assistance only when the "
                "rider is pedaling (pedal assist) and that ceases to provide assistance when the bicycle "
                "reaches 32 kilometers per hour and has a maximum continuous wattage output of 500 watts. "
                "[...] A Class 2 e-bike means a bicycle equipped with a motor that can be used exclusively to "
                "propel the bicycle (throttle equipped) and that ceases to provide assistance when the bicycle "
                "reaches 32 kilometers per hour. [...] Class 3 e-bike means a bicycle equipped with a motor "
                "that provides assistance only when the rider is pedaling (pedal assist) and that ceases to "
                "provide assistance when the bicycle reaches 45 kilometers per hour.")),
]
RULES_CLASS_QUOTES = " ".join(s["quote"] for s in RULES_CLASS_SOURCES)

RULES_CLASSES = [
    dict(cls="Class 1", assist="Pedal-assist only: the motor helps while you pedal, and stops when you stop.",
         speed="32 km/h", throttle="No throttle",
         where=("This is the class Parks Canada permits on its designated trails and beaches. Its own rule: "
                "only pedal-assist Class 1 e-bikes are allowed on the multi-use pathway in Pacific Rim "
                "National Park Reserve, and Class 2 or 3 machines are not.")),
    dict(cls="Class 2", assist="Pedal-assist or a throttle: the motor can drive the bike with no pedalling.",
         speed="32 km/h", throttle="Throttle",
         where=("The same ceiling as Class 1; the throttle is the whole difference. BC's own trails policy "
                "goes further than Parks Canada and treats a Class 2 machine as a motor vehicle as well as a "
                "cycle.")),
    dict(cls="Class 3", assist="Pedal-assist only, no throttle, with a higher ceiling.",
         speed="45 km/h", throttle="No throttle",
         where=("45 km/h is above every assist ceiling written into provincial law in Canada (32 km/h, or "
                "25 km/h for a light e-bike in British Columbia), so a Class 3 bike is a bicycle on a public "
                "road only where it is ridden to the provincial limit.")),
]


def _rules_class_row(c):
    return ('<tr><th scope="row" class="model">%s</th><td>%s</td><td class="num">%s</td>'
            '<td>%s</td><td>%s</td></tr>'
            % (esc(c["cls"]), esc(c["assist"]), esc(c["speed"]), esc(c["throttle"]), esc(c["where"])))


RULES_CLASS_ROWS = "\n        ".join(_rules_class_row(c) for c in RULES_CLASSES)

RULES_CLASSES_HEAD = "The three classes, in a government's own words"
RULES_CLASSES_SUB = (u"Class 1, 2 and 3 are not a Canadian statute. They are the labelling convention "
                     u"manufacturers print on a spec sheet and federal land managers use to decide which "
                     u"machines may use a trail - the two sources below are where they are written down. "
                     u"What actually binds you on a public road is provincial, and no province writes its "
                     u"rules as a class number.")
RULES_CLASSES_NOTE = (u"Read the table with the two sources in mind. Parks Canada publishes all three "
                      u"classes and permits only Class 1 on its designated trails and beaches. BC's "
                      u"Recreation Sites and Trails policy uses the same three and adds a sharper line: a "
                      u"Class 1 e-bike meets the province's definition of a motor assisted cycle, while a "
                      u"Class 2 or Class 3 machine is also a motor vehicle.")

# ---- the federal layer: what Ottawa still does, and the day the old definition died
RULES_FED_HEAD = u"Ottawa: the 500 W / 32 km/h definition was repealed"
RULES_FEDERAL = [
    (u"The figure every shop quotes - a 500 W motor helping up to 32 km/h - was a federal definition, and "
     u"it is gone. Transport Canada's own page says so: \u201cAs of Feb. 4th 2021, the definition of power "
     u"assisted bicycle formerly located in subsection 2(1) of the Motor Vehicle Safety Regulations is no "
     u"longer in force, hence it is no longer a benchmark for assessing compliance at manufacturing or "
     u"importation of e-bicycles.\u201d"),
    (u"What replaced it is an import test, not a road rule: Transport Canada now assesses a machine's "
     u"on-road or off-road design first, and an e-bicycle \u201cdesigned to operate at speeds no greater "
     u"than 32 km/h (or 20 mph) will be considered non-regulated at importation while those that can "
     u"operate at speeds greater than 32 km/h (or 20 mph) will be subject to import compliance requirements "
     u"as restricted-use vehicles.\u201d"),
    (u"So the honest statement of Canadian e-bike law is two-layered. Federally there is no 500 W ceiling "
     u"and no 32 km/h ceiling on a public road any more - only a border test. The provinces kept the "
     u"repealed wording and wrote it into their own law, which is why the same numbers appear province to "
     u"province and why the province you ride in is the only rule that decides."),
]
RULES_FEDERAL_HTML = "\n    ".join('<p class="rulesec">%s</p>' % esc(t) for t in RULES_FEDERAL)

# ---- where Canadian law does draw classes: BC's two, in force; Ontario's two, proposed
RULES_BC_HEAD = u"Where Canadian law does draw classes: British Columbia"
RULES_BC_SUB = (u"British Columbia replaced its e-bike regulation in 2024 and is the one province that now "
                u"defines classes of e-bike in law - under different names and different numbers from the "
                u"three-class convention above. Its Motor Assisted Cycle (E-Bike) Regulation establishes two "
                u"classes, standard and light, and the province's own page publishes both side by side.")
RULES_BC_FIELDS = [
    ("Minimum rider age", "16", "14"),
    ("Maximum motor-assisted speed", "32 km/h", "25 km/h"),
    ("Maximum continuous power output", "500 W", "250 W"),
    ("Throttle assist", "Allowed", "Not equipped"),
]
RULES_BC_ROWS = "\n        ".join(
    '<tr><th scope="row">%s</th><td class="num">%s</td><td class="num">%s</td></tr>' % (esc(a), esc(b), esc(c))
    for a, b, c in RULES_BC_FIELDS)
RULES_BC_NOTE = (u"A light e-bike is the one machinery difference that matters: its motor may not propel "
                 u"the cycle unless the rider is pedalling, it may not exceed 250 W, it may not assist above "
                 u"25 km/h, and it may not be equipped with a throttle at all. Everything else that meets the "
                 u"province's criteria is a standard e-bike. Neither class needs a driver's licence, "
                 u"registration or insurance, and a helmet is required on both.")

RULES_ON_HEAD = u"Ontario: two classes proposed, not in force"
RULES_ON_NOTE = (u"Ontario is the other province moving this way, and it is worth being precise about how "
                 u"far it has got. The Ministry of Transportation posted a proposal on the Environmental "
                 u"Registry (notice 026-0422, posted 23 April 2026, comment period closed 7 June 2026) to "
                 u"update the definition of a power-assisted bicycle and to \u201cestablish distinct classes "
                 u"of e-bikes with tailored operator, vehicle and safety requirements\u201d. That is a "
                 u"proposal: as of the date read here, Ontario still has one category and one set of rules, "
                 u"and this page will not print class figures for a regulation that does not exist.")

# ---- province by province. Every row is a government page, read on the date shown. motor/speed/age are
# the figures the row prints, and the build checks each of those numbers really appears in that province's
# own quote below - a paraphrase that drifted from the page would stop the build.
RULES_PROVINCES = [
    dict(name="British Columbia",
         law=u"Motor Assisted Cycle (E-Bike) Regulation, B.C. Reg. 64/2024 (in force 5 April 2024)",
         motor=u"500 W or less (standard) / 250 W or less (light)", speed=u"32 km/h (standard) / 25 km/h (light)",
         age=u"16 (standard) / 14 (light)", helmet=u"Required — a bicycle safety helmet, all ages",
         papers=u"None: no licence, no registration, no insurance",
         where=u"Public roads where cycles are permitted; some municipalities set their own rules, and a "
               u"Class 1 machine is the only one allowed on Parks Canada trails.",
         url="https://www2.gov.bc.ca/gov/content/transportation/driving-and-cycling/cycling/"
             "cycling-regulations-restrictions-rules/e-bikes",
         src=u"Province of British Columbia, “E-bike requirements”",
         date=u"page last updated 4 November 2025",
         quote=(u"| Minimum rider age | 16 | 14 | Maximum motor-assisted speed | 32 km/h | 25 km/h | "
                u"Maximum continuous power output* | 500W | 250W | Throttle assist | Yes | No | "
                u"“Wearing a bicycle safety helmet is required when operating an e-bike.”")),
    dict(name="Alberta",
         law=u"Traffic Safety Act; Use of Highway and Rules of the Road Regulation, Alta. Reg. 304/2002",
         motor=u"500 W or less, all motors combined", speed=u"32 km/h on level ground",
         age=u"12", helmet=u"Required — all ages: an approved motorcycle helmet, or a bicycle helmet",
         papers=u"None: no licence, no registration, no insurance",
         where=u"Highways and roads, riding as far to the right as is practicable. A rider under the age of "
               u"16 may not carry a passenger.",
         url="https://www.transportation.alberta.ca/Content/docType41/Production/small_vehicle_booklet_final.pdf",
         src=u"Alberta Transportation, “Rules & Regulations Applying to Small Vehicles”",
         date=u"booklet updated November 2018, read 2026-10-09",
         quote=(u"“it has a total continuous power output rating, measured at the shaft of each motor, of "
                u"500 W or less [...] it is incapable of providing further assistance when the bicycle "
                u"attains a speed of 32 km/h on level ground [...] Minimum driving age: The minimum driving "
                u"age to operate a power bicycle is 12 years.”")),
    dict(name="Saskatchewan",
         law=u"The Traffic Safety Act, s. 247.1",
         motor=u"500 W or less", speed=u"32 km/h",
         age=u"14", helmet=u"Required — all ages: an approved bicycle or motorcycle helmet",
         papers=u"None: no licence, no registration, no insurance",
         where=u"Under the rules of the road for a bicycle, and not in any area restricted by a municipal "
               u"bylaw.",
         url="https://sgi.sk.ca/motorcycle/-/knowledge_base/motorcycle-handbook/power-assisted-bicycles1",
         src=u"SGI, “E-bikes (power-assisted bicycles)”",
         date=u"read 2026-10-09",
         quote=(u"“is equipped with an electric assist motor that is no larger than 500 watts [...] cannot "
                u"be operated at a speed of greater than 32 km/h (20 mph) on any level service [...] Age "
                u"restriction: 14 years of age or older [...] Operator requires an approved bicycle or "
                u"motorcycle helmet”")),
    dict(name="Manitoba",
         law=u"The Highway Traffic Act, C.C.S.M. c. H60, ss. 1(1), 145",
         motor=u"500 W or less, measured at the shaft", speed=u"32 km/h",
         age=u"14", helmet=u"Required — all ages: a properly fitted and fastened protective helmet",
         papers=u"None: no licence, no registration, no insurance",
         where=u"Highways and bicycle facilities, with the rights and duties of a driver of a motor "
               u"vehicle, except that a power-assisted bicycle may not be driven on a sidewalk.",
         url="https://web2.gov.mb.ca/laws/statutes/ccsm/h060.php",
         src=u"Manitoba, The Highway Traffic Act, C.C.S.M. c. H60 (s. 1(1) definition; s. 145)",
         date=u"Act read 2026-10-09",
         quote=(u"“the motor has a continuous power output rating, measured at its shaft, of 500 W or less "
                u"[...] the motor cannot provide the vehicle with motive power when it is travelling at more "
                u"than 32 km/h” / s. 145(2): “No person shall operate a power-assisted bicycle on a highway "
                u"or bicycle facility unless they are 14 years of age or older” / s. 145(4): “No person shall "
                u"ride on or operate a power-assisted bicycle on a highway or bicycle facility unless they "
                u"are wearing a properly fitted and fastened protective helmet”")),
    dict(name="Ontario",
         law=u"Highway Traffic Act, R.S.O. 1990, c. H.8, and O. Reg. 369/09",
         motor=u"500 W or less", speed=u"32 km/h",
         age=u"16", helmet=u"Required — all ages: an approved bicycle or motorcycle helmet",
         papers=u"None: no licence, no registration, no insurance",
         where=u"Most roads and highways where conventional bicycles are permitted. Not on the 400-series "
               u"and other controlled-access highways, and not where a municipal bylaw bans e-bikes.",
         url="https://www.ontario.ca/page/riding-e-bike",
         src=u"Government of Ontario, “Riding an e-bike”",
         date=u"page updated 19 July 2024, read 2026-10-09",
         quote=(u"“a maximum assisted speed of 32 km/h [...] a maximum weight of 120 kg [...] an electric "
                u"motor not exceeding 500 watts [...] you must [...] be 16 or older [...] wear an approved "
                u"bicycle or motorcycle helmet”")),
    dict(name="Quebec",
         law=u"Highway Safety Code, and the Protective Helmets Regulation",
         motor=u"500 W or less", speed=u"32 km/h",
         age=u"18", helmet=u"Required — all ages: a helmet meeting a listed standard",
         papers=u"None at 18 or over; a moped licence (Class 6D) at ages 14 to 17",
         where=u"All public roadways except highways and their access and exit ramps. An electric bike "
               u"cannot be registered, and a combustion engine on a bicycle is prohibited.",
         url="https://saaq.gouv.qc.ca/en/road-safety/modes-transportation/electric-bike",
         src=u"SAAQ, “Riding an Electric Bike”",
         date=u"last updated 25 May 2026",
         quote=(u"“the bike's electric motor must have a maximum power rating of no more than 500 watts and "
                u"must cease to generate power once the bicycle reaches a speed of no more than 32 km/h” / "
                u"“You must be aged 18 or older to ride an electric bike. However, people aged 14 to 17 who "
                u"hold a Class 6D (moped or scooter) licence are also authorized”")),
    dict(name="New Brunswick",
         law=u"Motor Vehicle Act (read through Service New Brunswick's registration page)",
         motor=u"500 W or less", speed=u"32 km/h",
         age=u"Not set on the page read", helmet=u"Required — all ages (the province's general bicycle rule)",
         papers=u"None for a compliant machine; over the limit it cannot be registered unless certified",
         where=u"Treated as a bicycle, so the requirements placed on cyclists apply.",
         url="https://www.gnb.ca/en/topic/driving-transportation/registration-inspection/motor-vehicle-registration.html",
         src=u"Government of New Brunswick, “Motor vehicle registration”",
         date=u"page read 2026-10-09",
         quote=(u"“If the vehicle can be powered by human force and has a motor equal to or less than 500W, "
                u"and the motor is not capable of assisting when the vehicle is travelling at a speed "
                u"greater than 32km/h then it can be considered a bicycle and all the requirements placed on "
                u"bicyclists are applicable.”")),
    dict(name="Nova Scotia",
         law=u"Motor Vehicle Act, R.S.N.S. 1989, c. 293, s. 2(c)(ii), as amended by Bill 111 (2002) — "
              u"being replaced by the Traffic Safety Act, S.N.S. 2025, c. 20",
         motor=u"500 W or less (or a 50 cc piston displacement)",
         speed=u"Thirty kilometres per hour — the Act writes the figure out in words",
         age=u"Not set in the Act",
         helmet=u"Required — all ages (a bicycle helmet, under the Act's Helmet Regulations)",
         papers=u"None: no licence, no registration, no insurance",
         where=u"Roads and highways under the rules of the road for a bicycle; a compliant machine cannot "
               u"be registered as a motor vehicle.",
         url="https://nslegislature.ca/legc/bills/58th_2nd/3rd_read/b111.htm",
         src=u"Nova Scotia House of Assembly, Motor Vehicle Act, Bill 111 (2002), s. 2(c)(ii)",
         date=u"Bill 111 assented 30 May 2002; read 2026-10-09, with the successor regulation due 19 October 2026",
         quote=(u"“a vehicle propelled by human and mechanical power that is fitted with pedals that are "
                u"operable at all times to propel the bicycle [...] and that has an attached motor driven by "
                u"electricity not producing more than 500 watts or with a piston displacement of not more "
                u"than 50 cubic centimetres and is incapable of providing further assistance when the "
                u"vehicle attains a speed of thirty kilometres per hour on level ground”")),
    dict(name="Prince Edward Island",
         law=u"Highway Traffic Act, R.S.P.E.I. 1988, c. H-5 — Power-Assisted Bicycles Regulations "
              u"(P.E.I. Reg. EC557/21)",
         motor=u"500 W or less, in total, measured at the shaft of each motor", speed=u"32 km/h",
         age=u"16", helmet=u"Required — all ages: a properly fitted and fastened bicycle safety helmet",
         papers=u"None: a power-assisted bicycle is deemed not to be a motor vehicle",
         where=u"Roadways and shoulders, and bicycle lanes where they are provided — not on a sidewalk or "
               u"walkway, and on a trail only from 1 April to 30 November.",
         url="https://www.princeedwardisland.ca/sites/default/files/legislation/"
             "h05-24-1-highway_traffic_act_power-assisted_regulations.pdf",
         src=u"Government of Prince Edward Island, Power-Assisted Bicycles Regulations",
         date=u"consolidation current to 23 September 2023, read 2026-10-09",
         quote=(u"“a total continuous power output rating, measured at the shaft of each motor, of 500 watts "
                u"or less [...] power assistance ceases when the bicycle attains a speed of 32 kilometres "
                u"per hour on level ground” / s. 13(2): “No person under the age of 16 years shall operate a "
                u"power-assisted bicycle.” / s. 13(8): “No person shall ride on or operate a power-assisted "
                u"bicycle unless the person is wearing a properly fitted and fastened bicycle safety "
                u"helmet.”")),
    dict(name="Newfoundland and Labrador",
         law=u"Highway Traffic Act, R.S.N.L. 1990, c. H-3 — no e-bike class in the Act; the province "
              u"applies the federal standard",
         motor=u"500 W or less", speed=u"32 km/h",
         age=u"Not set in the Act",
         helmet=u"Required — all ages (fine up to $180)",
         papers=u"None: no licence, no registration, no insurance",
         where=u"The rules of the road for a bicycle: a rider “has the same rights and duties as a driver "
               u"of a motor vehicle”. Not on a sidewalk.",
         url="https://rcmp.ca/en/nl/news/2025/09/"
             "rcmp-newfoundland-and-labrador-encourages-e-bike-and-bicycle-users-put-safety-first",
         src=u"Royal Canadian Mounted Police, Newfoundland and Labrador",
         date=u"release dated 12 September 2025, read 2026-10-09",
         quote=(u"“In Newfoundland and Labrador, e-bike owners must follow all federal legislation. The "
                u"e-bike motors cannot be more powerful than 500 watts, with a top speed of 32 km/h. They "
                u"also must have fully operable pedals [...]” / “Anyone riding an e-bike or bicycle in this "
                u"province, regardless of age, is required to wear an approved helmet [...] you may be fined "
                u"up to a maximum of $180.”")),
    dict(name="Yukon",
         law=u"Motor Vehicles Act, R.S.Y. 2002, c. 153, s. 1 — “electric power-assisted cycle”",
         motor=u"500 W or less in total", speed=u"32 km/h",
         age=u"Not set in the Act",
         helmet=u"Not set in the Act",
         papers=u"None: an electric power-assisted cycle is an excluded motor vehicle",
         where=u"Where cycles may ride; Whitehorse's own E-Bike Regulation Bylaw sorts Class 1, 2 and 3 by "
               u"trail.",
         url="https://laws.yukon.ca/cms/images/LEGISLATION/PRINCIPAL/2002/2002-0153/2002-0153.pdf",
         src=u"Government of Yukon, Motor Vehicles Act, s. 1",
         date=u"consolidation read 2026-10-09",
         quote=(u"“electric power-assisted cycle” means a vehicle that (a) has steering handlebars and is "
                u"equipped with pedals; [...] (d) has one or more motors that are electric only and have, "
                u"singly or in combination, the following characteristics (i) a continuous power output "
                u"rating, measured at the shaft of each motor, of 500 W or less in total for the motor or "
                u"combination of motors, [...] and (iv) the motor or combination of motors is incapable of "
                u"providing further assistance when the vehicle attains a speed of 32 km/h on level ground")),
    dict(name="Northwest Territories",
         law=u"Motor Vehicles Act, R.S.N.W.T. 1988, c. M-16 — no e-bike class; the Department of "
              u"Infrastructure publishes the power-bicycle rule",
         motor=u"500 W maximum", speed=u"32 km/h",
         age=u"None set — the department suggests 12 and over",
         helmet=u"Not required — an approved motorcycle helmet is recommended",
         papers=u"None: no licence, no registration, no insurance",
         where=u"Public roads under the rules of the road; community by-laws may add their own.",
         url="https://www.idmv.inf.gov.nt.ca/media/81148926-42bf-4d53-9b8f-b5b2fadf6bc3/-KKDZQ/Documents/"
             "Motorcycle%20Manual.pdf",
         src=u"Government of the Northwest Territories, Department of Infrastructure, “Motorcycle "
             u"Operator's Licence Information”",
         date=u"manual revised March 2020, read 2026-10-09",
         quote=(u"“A power bicycle is a pedal bicycle with an electric motor (maximum power of 500 watts), a "
                u"top-speed of 32 km/h, and no prescribed weight, nor allowance to be engine driven. [...] a "
                u"Driver's Licence is not required to operate.” / “Minimum Driving Age: There is currently no "
                u"age restriction placed on the operation of power bicycles. However, the Department of "
                u"Infrastructure strongly recommends that only those 12 years of age or older operate a "
                u"power bicycle.” / “Helmet: The Department of Infrastructure does not require operators of "
                u"or passengers on power bicycles to wear a helmet.”")),
    dict(name="Nunavut",
         law=u"Traffic Safety Act, R.S.N.W.T. 1988, c. M-16 (as renamed), s. 1, read with the All-terrain "
              u"Vehicles Act, R.S.N.W.T. 1988, c. A-3, s. 1(1)",
         motor=u"Not defined in the Act", speed=u"Not defined in the Act",
         age=u"Not set in the Act",
         helmet=u"Not set in the Act",
         papers=u"Not set in the Act",
         where=u"A motorized pedal bicycle is not a “bicycle” under the Act, and no e-bike class is written "
               u"into it; the All-terrain Vehicles Act counts “a pedal bicycle with motor attachment” as an "
               u"all-terrain vehicle, and community by-laws govern use.",
         url="https://www.nunavutlegislation.ca/sites/default/files/consolidated-law-current/"
             "consRSNWT1988cM-16.pdf",
         src=u"Government of Nunavut, Traffic Safety Act, s. 1",
         date=u"consolidation current to 6 December 2019, read 2026-10-09",
         quote=(u"“bicycle” means a device having any number of wheels upon which a person sits astride and "
                u"which is propelled by human muscular power through the use of pedals; (bicyclette)")),
]

RULES_PROV_HEAD = u"Province and territory, one by one: what each writes into law"
RULES_PROV_SUB = (u"One row per province and territory, each read from that jurisdiction's own "
                  u"government page on the date shown. Every figure below is in the verbatim quote in "
                  u"the sources at the foot of this page - the build checks that before it writes the "
                  u"file.")
RULES_PROV_NOTE = (u"Read the motor column as the one hard line. Every province that writes the rule "
                   u"caps a power-assisted bicycle at a 500 W continuous rating, and every one of "
                   u"them stops motor assistance at a published speed - so a motor rated above "
                   u"500 W, or assistance that continues past the cut-off, is what turns a bicycle "
                   u"into a motor vehicle that needs a licence and insurance. Three jurisdictions "
                   u"leave a rider rule open: Alberta sets a minimum age without a licence "
                   u"requirement, New Brunswick's registration page sets no minimum age at all, and "
                   u"the territories set none. Where a rule is not published, this page says so "
                   u"instead of filling the gap.")
RULES_PROV_MISSING = (u"Where a cell above reads “not set” or “not defined”, the page is reporting "
                      u"a gap in the law rather than filling one in. Nova Scotia still rides on its Motor "
                      u"Vehicle Act, which writes its cut-off out in words; the province is replacing "
                      u"that Act, and the successor regulation - the Traffic Safety Act Interpretation "
                      u"Regulations, N.S. Reg. 221/2026, published at novascotia.ca/just/regulations - "
                      u"takes effect 19 October 2026 and sets the figure at 32 km/h. Newfoundland and "
                      u"Labrador writes no e-bike class into its Highway Traffic Act at all, and applies "
                      u"the federal standard its RCMP restate; the Northwest Territories and Nunavut "
                      u"likewise write none, so the rule is published by the territory's own department "
                      u"(NWT) or left to the municipal by-law (Nunavut). Every one of them is named here "
                      u"rather than guessed at.")


def _rules_prov_row(p):
    return ('<tr><th scope="row" class="model">%s<span class="law">%s</span>'
            '<span class="src"><a href="%s" target="_blank" rel="noopener nofollow">%s</a> &middot; %s</span></th>'
            '<td>%s</td><td>%s</td><td class="num">%s</td><td>%s</td><td>%s</td><td>%s</td></tr>'
            % (esc(p["name"]), esc(p["law"]), esc(p["url"]), esc(p["src"]), esc(p["date"]),
               esc(p["motor"]), esc(p["speed"]), esc(p["age"]), esc(p["helmet"]), esc(p["papers"]),
               esc(p["where"])))


RULES_PROV_ROWS = "\n        ".join(_rules_prov_row(p) for p in RULES_PROVINCES)

# ---- what the classes mean for the bikes on this site: the maker's own published class, from data/products.json
RULES_BIKES_HEAD = u"The class each bike on this site is sold as"
RULES_BIKES_SUB = (u"Not one of these is this page's judgement. Each class string below is the maker's own "
                   u"published wording, read from the maker's product page on the same date as every other "
                   u"figure on this site, and held in this site's own data file.")
RULES_BIKES_NOTE = (u"Two things follow from the table. A class number is a maker's label, not a permission: "
                    u"the province you ride in decides whether the machine on it is a bicycle or a motor "
                    u"vehicle, and it decides that in watts and km/h. And where a maker's own wording leaves "
                    u"the ceiling adjustable, the provincial cut-off is the number that binds - a bike set "
                    u"above the provincial assist speed is outside the rule for the road it is on, whatever "
                    u"the spec sheet calls it.")


def _rules_bike_row(q):
    return ('<tr><th scope="row" class="model"><a href="../bikes/%s/">%s</a>'
            '<span class="mmaker">%s</span></th><td>%s</td><td class="num">%s</td></tr>'
            % (esc(q["id"]), esc(q["model"]), esc(q["maker"]), esc(q["eclass"]), esc(q["price_display"])))


RULES_BIKE_ROWS = "\n        ".join(_rules_bike_row(q) for q in ORDER)

# ---- the sources: every government page, its own date, and the verbatim quote the figures came from
RULES_SRC_HEAD = u"Every source, and what it says"
RULES_SRC_SUB = (u"Each source below was read on the date shown, and the rule in the table above is taken "
                 u"from the quoted text. Nothing on this page comes from memory, and where a government "
                 u"page did not state a rule, this page says so rather than filling the gap.")


def _rules_src_block(s, extra=""):
    return ('<li><strong>%s</strong> \u00b7 %s \u00b7 %s: '
            '<a href="%s" target="_blank" rel="noopener nofollow">%s</a>%s'
            '<blockquote class="quote">%s</blockquote></li>'
            % (s["name"], s["date"], s.get("src", ""), esc(s["url"]), esc(s["url"]), extra, esc(s["quote"])))


RULES_SOURCES = "\n        ".join(
    [_rules_src_block(s) for s in RULES_CLASS_SOURCES]
    + [_rules_src_block(dict(name=u"Transport Canada \u2014 Importing non-regulated vehicles",
                             url="https://tc.canada.ca/en/road-transportation/importing-vehicle/"
                                 "importing-non-regulated-vehicles",
                             date=u"read 2026-10-09",
                             quote=(u"As of Feb. 4th 2021, the definition of power assisted bicycle formerly "
                                    u"located in subsection 2(1) of the Motor Vehicle Safety Regulations is no "
                                    u"longer in force, hence it is no longer a benchmark for assessing "
                                    u"compliance at manufacturing or importation of e-bicycles. [...] "
                                    u"E-bicycles with off-road characteristics designed to operate at speeds "
                                    u"no greater than 32 km/h (or 20 mph) will be considered non-regulated at "
                                    u"importation while those that can operate at speeds greater than "
                                    u"32 km/h (or 20 mph) will be subject to import compliance requirements "
                                    u"as restricted-use vehicles.")))]
    + [_rules_src_block(dict(name=u"Ontario Ministry of Transportation \u2014 Environmental Registry "
                                  u"notice 026-0422",
                             url="https://ero.ontario.ca/notice/026-0422",
                             date=u"posted 23 April 2026, comment period closed 7 June 2026",
                             quote=(u"The Ministry of Transportation (MTO) is proposing to update and "
                                    u"modernize the definition of power-assisted bicycles (also known as "
                                    u"e-bikes) in Ontario through a new regulation governing their use and "
                                    u"safety. [...] the ability to establish distinct classes of e-bikes "
                                    u"with tailored operator, vehicle and safety requirements.")))]
    + [_rules_src_block(p) for p in RULES_PROVINCES])

# ---- the change ledger: what moved between reads. Rank 19 corrected Manitoba's s.145 only because a session
# went looking for it. A page that carries a quote and a date but no record of what changed between reads
# forces every future re-read to start from archaeology. One dated list turns the page's honesty into
# something a reader - and the next session - can audit. A read that finds nothing is recorded too, because a
# silent no-change is exactly how a drifted figure hides.
RULES_LEDGER_HEAD = u"Change ledger: what moved between reads"
RULES_LEDGER_SUB = (u"Every line below is a change to this page since it was first built, dated and tied to "
                    u"the jurisdiction it touches. The verbatim quotes the table above prints were last "
                    u"re-read against their government pages on the date in the sources at the foot of this "
                    u"page; where that re-read found nothing, the line says so, because an unrecorded "
                    u"no-change is how a drifted figure hides.")
RULES_CHANGELOG = [
    dict(date=u"2026-10-09", jur=u"Manitoba",
         change=(u"Highway Traffic Act s.145 was rewritten in gender-neutral wording, so this page's quoted "
                 u"\u201cunless he or she is 14 years of age or older\u201d no longer matched the Act. The "
                 u"quote now reads the Act's current \u201cunless they are 14 years of age or older\u201d, and "
                 u"the row's source moved from a parks policy PDF to the Act itself (web2.gov.mb.ca).")),
    dict(date=u"2026-10-09", jur=u"Nova Scotia, Prince Edward Island, Newfoundland and Labrador, Yukon, Northwest Territories, Nunavut",
         change=(u"Six jurisdictions added, so the table now covers all ten provinces and all three "
                 u"territories. Each is quoted from its own government page: Nova Scotia's Motor Vehicle Act "
                 u"(its cut-off is written out in words, \u201cthirty kilometres per hour\u201d), PEI's "
                 u"Power-Assisted Bicycles Regulations, the RCMP's Newfoundland and Labrador advisory, the "
                 u"Yukon Motor Vehicles Act, the NWT Department of Infrastructure's operator manual, and "
                 u"Nunavut's Traffic Safety Act.")),
    dict(date=u"2026-10-09", jur=u"British Columbia, Alberta, Saskatchewan, Ontario, Quebec, New Brunswick, Manitoba",
         change=(u"First build of this page: seven provinces, each read from its own government page, with the "
                 u"federal repeal of the 500 W / 32 km/h definition dated to 4 February 2021 and Ontario's two "
                 u"proposed classes named as a proposal and not a rule.")),
]


def _rules_ledger_row(e):
    return ('<li><span class="ldate">%s</span> <span class="ljur">%s</span> \u2014 %s</li>'
            % (esc(e["date"]), esc(e["jur"]), esc(e["change"])))


RULES_LEDGER_ROWS = "\n        ".join(_rules_ledger_row(e) for e in RULES_CHANGELOG)

RULES_TITLE = (u"E-bike classes in Canada: what Class 1, 2 and 3 mean, and what each province and territory requires "
               u"| Commuter E-Bikes CA")
RULES_OGTITLE = u"E-bike classes in Canada: what Class 1, 2 and 3 mean, and where the provinces differ"
RULES_DESC = (u"What Class 1, 2 and 3 e-bikes mean in Canada, what speed and power each province and territory allows, "
              u"which helmet is required and where you may ride - every rule quoted from a government page "
              u"and dated, with no affiliate link.")
RULES_INTRO = (u"Before the price, the motor or the battery: is the machine legal where you ride it? "
               u"Canadian e-bike law is written in watts and kilometres per hour, province by province - "
               u"not as Class 1, 2 or 3. This page sets out what the three classes are (in the words of a "
               u"federal agency that uses them), what Ottawa repealed and when, where a provincial law "
               u"really does define classes, and what each province and territory requires: motor limit, assist speed, "
               u"minimum age, helmet and paperwork. Every figure is quoted from a named government page and "
               u"dated; where a province has not published a rule, the page says so.")
RULES_DISCLOSURE = (u"this page has no affiliate link and nothing to buy. It carries no partner link, no "
                    u"commission and no product link at all; every off-site link on it is a government page, "
                    u"and this is general information about the law, not legal advice.")

RULES_PAGE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__</title>
<meta name="description" content="__DESC__">
<link rel="canonical" href="__CANONICAL__">
<meta property="og:type" content="article">
<meta property="og:site_name" content="Commuter E-Bikes CA">
<meta property="og:title" content="__OGTITLE__">
<meta property="og:description" content="__DESC__">
<meta property="og:url" content="__CANONICAL__">
<meta name="twitter:card" content="summary">
<meta name="twitter:title" content="__OGTITLE__">
<meta name="twitter:description" content="__DESC__">
<style>__CSS__
  .crumb{font-size:13px;color:var(--muted);margin:0 0 8px}
  .ruleshero{padding:34px 0 8px}
  .ruleshero h1{font-size:clamp(27px,4.6vw,42px);line-height:1.12;margin:0 0 12px;max-width:30ch}
  p.rulesec{margin:0 0 14px;color:#333842;max-width:76ch}
  table.rules .model{font-weight:700}
  table.rules .law{display:block;color:var(--muted);font-size:12.5px;font-weight:400;margin-top:2px}
  table.rules .src{display:block;color:var(--muted);font-size:12px;font-weight:400;margin-top:4px}
  table.rules td{vertical-align:top}
  ul.otherbikes{list-style:none;padding:0;margin:0;display:grid;gap:8px}
  ul.otherbikes a{font-size:14.5px}
  ul.sources li{margin:0 0 16px}
  blockquote.quote{margin:8px 0 0;padding:8px 12px;border-left:3px solid var(--accent);background:var(--card);
    border-radius:6px;color:#3a3f49;font-size:13.5px;max-width:80ch}
  ul.ledger{list-style:none;padding:0;margin:0}
  ul.ledger li{margin:0 0 12px;padding:0 0 12px;border-bottom:1px solid var(--line);max-width:80ch;color:#333842}
  ul.ledger li:last-child{border-bottom:none}
  ul.ledger .ldate{font-weight:700;font-variant-numeric:tabular-nums}
  ul.ledger .ljur{color:var(--accent);font-weight:700}
</style>
</head>
<body>
<header class="top"><div class="wrap">
  <a class="brand" href="../" style="color:inherit;text-decoration:none">Commuter E-Bikes CA</a>
  <span class="stamp">Rules read <strong>__CHECKED__</strong></span>
</div></header>

<main class="wrap">
  <section class="ruleshero" style="border-top:none">
    <p class="crumb"><a href="../">All __N_WORD__ commuter e-bikes, compared</a> &rsaquo; Classes and rules</p>
    <h1>What e-bike classes mean in Canada, and where the provinces differ</h1>
    <p class="deck">__INTRO__</p>
    <p class="disclosure" role="note"><strong>Disclosure:</strong> __DISC__</p>
  </section>

  <section id="classes">
    <h2>__CLASSES_HEAD__</h2>
    <p class="sub">__CLASSES_SUB__</p>
    <div class="tablewrap">
      <table class="rules">
        <caption>The three classes, as published by the sources at the foot of this page.</caption>
        <thead><tr>
          <th scope="col">Class</th><th scope="col">What the motor does</th>
          <th scope="col" class="num">Assist stops at</th><th scope="col">Throttle</th>
          <th scope="col">Where that class may ride</th>
        </tr></thead>
        <tbody>
        __CLASS_ROWS__
        </tbody>
      </table>
    </div>
    <p class="note">__CLASSES_NOTE__</p>
  </section>

  <section id="federal">
    <h2>__FED_HEAD__</h2>
    __FED__
  </section>

  <section id="bc">
    <h2>__BC_HEAD__</h2>
    <p class="sub">__BC_SUB__</p>
    <div class="tablewrap">
      <table class="rules">
        <caption>British Columbia's two classes of motor assisted cycle, from the province's own page.</caption>
        <thead><tr>
          <th scope="col">Requirement</th><th scope="col" class="num">Standard e-bike</th>
          <th scope="col" class="num">Light e-bike</th>
        </tr></thead>
        <tbody>
        __BC_ROWS__
        </tbody>
      </table>
    </div>
    <p class="note">__BC_NOTE__</p>
  </section>

  <section id="ontario">
    <h2>__ON_HEAD__</h2>
    <p class="rulesec">__ON_NOTE__</p>
  </section>

  <section id="provinces">
    <h2>__PROV_HEAD__</h2>
    <p class="sub">__PROV_SUB__</p>
    <div class="tablewrap">
      <table class="rules">
        <caption>One row per province or territory: motor limit, assist cut-off, minimum age, helmet and paperwork, each from that jurisdiction's own government page.</caption>
        <thead><tr>
          <th scope="col">Province</th><th scope="col">Motor limit</th>
          <th scope="col">Assist cut-off</th><th scope="col" class="num">Min. age</th>
          <th scope="col">Helmet</th><th scope="col">Licence / registration / insurance</th>
          <th scope="col">Where you may ride</th>
        </tr></thead>
        <tbody>
        __PROV_ROWS__
        </tbody>
      </table>
    </div>
    <p class="note">__PROV_NOTE__</p>
    <p class="note">__PROV_MISSING__</p>
  </section>

  <section id="bikes">
    <h2>__BIKES_HEAD__</h2>
    <p class="sub">__BIKES_SUB__</p>
    <div class="tablewrap">
      <table class="rules">
        <caption>Each class string below is the maker's own published wording for the bike, from this site's data file.</caption>
        <thead><tr>
          <th scope="col">Model</th><th scope="col">Class as the maker publishes it</th>
          <th scope="col" class="num">Price (CAD)</th>
        </tr></thead>
        <tbody>
        __BIKE_ROWS__
        </tbody>
      </table>
    </div>
    <p class="note">__BIKES_NOTE__</p>
  </section>

  <section id="sources">
    <h2>__SRC_HEAD__</h2>
    <p class="sub">__SRC_SUB__</p>
    <ul class="sources">__SOURCES__</ul>
  </section>

  <section id="ledger">
    <h2>__LEDGER_HEAD__</h2>
    <p class="sub">__LEDGER_SUB__</p>
    <ul class="ledger">
      __LEDGER_ROWS__
    </ul>
  </section>

  <section id="next">
    <h2>Read the rest</h2>
    <ul class="otherbikes">
      <li><a href="../">All __N_WORD__ commuter e-bikes, compared side by side</a></li>
      <li><a href="../how-far/">How far will it go? Range against your commute</a></li>
      <li><a href="../commute-costs/">What a commute actually costs, e-bike vs car vs transit</a></li>
      <li><a href="../gear/">Gear: helmets, locks and lights, and each bike's load rating</a></li>
      <li><a href="../trails/">Where you may ride: trails, parks and paths, one land manager at a time</a></li>
      <li><a href="../guide/">The free decision guide</a></li>
      <li><a href="../stats/">Page views on this site &mdash; the counts, read live</a></li>
    </ul>
  </section>
</main>

<footer><div class="wrap">
  <p><strong>Disclosure:</strong> __DISC__</p>
  <p>This is general information about published e-bike rules, not legal advice, and not advice about your particular riding, health or local by-laws. Rules change; read your province's own page before you buy or ride.</p>
  <p>Built __CHECKED__ by the GAMMA project. Sources: Transport Canada, Parks Canada, Recreation Sites and Trails BC, and each province's or territory's own page &mdash; all named above. Data: <a href="../data/products.json">products.json</a> &middot; <a href="../">the comparison</a>.</p>
</div></footer>
</body>
</html>
"""

# The template may carry no figure of its own: every digit in the output must come from a substitution.
_tmpl_probe = re.sub(r"(?s)<(style|script).*?</\1>", " ", RULES_PAGE)
_tmpl_probe = re.sub(r"(?s)<[^>]+>", " ", _tmpl_probe)
_tmpl_probe = re.sub(r"__[A-Z_0-9]*__", "", _tmpl_probe)
assert not re.search(r"\d", _tmpl_probe), \
    "a figure is typed into the rules template instead of being substituted"

_RULES_SUBST = {
    "__CSS__": CSS,
    "__N_WORD__": esc(N_WORD),
    "__CHECKED__": esc(CHECKED),
    "__TITLE__": esc(RULES_TITLE),
    "__OGTITLE__": esc(RULES_OGTITLE),
    "__DESC__": esc(RULES_DESC),
    "__CANONICAL__": "%s/rules/" % SITE,
    "__INTRO__": esc(RULES_INTRO),
    "__DISC__": esc(RULES_DISCLOSURE),
    "__CLASSES_HEAD__": esc(RULES_CLASSES_HEAD),
    "__CLASSES_SUB__": esc(RULES_CLASSES_SUB),
    "__CLASS_ROWS__": RULES_CLASS_ROWS,
    "__CLASSES_NOTE__": esc(RULES_CLASSES_NOTE),
    "__FED_HEAD__": esc(RULES_FED_HEAD),
    "__FED__": RULES_FEDERAL_HTML,
    "__BC_HEAD__": esc(RULES_BC_HEAD),
    "__BC_SUB__": esc(RULES_BC_SUB),
    "__BC_ROWS__": RULES_BC_ROWS,
    "__BC_NOTE__": esc(RULES_BC_NOTE),
    "__ON_HEAD__": esc(RULES_ON_HEAD),
    "__ON_NOTE__": esc(RULES_ON_NOTE),
    "__PROV_HEAD__": esc(RULES_PROV_HEAD),
    "__PROV_SUB__": esc(RULES_PROV_SUB),
    "__PROV_ROWS__": RULES_PROV_ROWS,
    "__PROV_NOTE__": esc(RULES_PROV_NOTE),
    "__PROV_MISSING__": esc(RULES_PROV_MISSING),
    "__BIKES_HEAD__": esc(RULES_BIKES_HEAD),
    "__BIKES_SUB__": esc(RULES_BIKES_SUB),
    "__BIKE_ROWS__": RULES_BIKE_ROWS,
    "__BIKES_NOTE__": esc(RULES_BIKES_NOTE),
    "__SRC_HEAD__": esc(RULES_SRC_HEAD),
    "__SRC_SUB__": esc(RULES_SRC_SUB),
    "__SOURCES__": RULES_SOURCES,
    "__LEDGER_HEAD__": esc(RULES_LEDGER_HEAD),
    "__LEDGER_SUB__": esc(RULES_LEDGER_SUB),
    "__LEDGER_ROWS__": RULES_LEDGER_ROWS,
}
_rules_out = RULES_PAGE
for _k, _v in _RULES_SUBST.items():
    _rules_out = _rules_out.replace(_k, _v)
write_page(os.path.join(ROOT, "rules", "index.html"), _rules_out, "rules")

# ---- the page is read back and checked before the sitemap is written
RULES_FILE = os.path.join(ROOT, "rules", "index.html")
RULES_TEXT = open(RULES_FILE, encoding="utf-8").read()

# 1. nothing here can pay, and it says nothing about the status of any program.
for _bad in ("config.js", "AFFILIATE_", 'data-aff=', 'class="buyaff"'):
    assert _bad not in RULES_TEXT, "affiliate element on the rules page: %r" % _bad

# 2. its own head: title, description, canonical and the social card.
assert '<link rel="canonical" href="%s/rules/">' % SITE in RULES_TEXT
for _head in ('<title>', 'name="description"', 'property="og:type"', 'property="og:site_name"',
              'property="og:title"', 'property="og:description"', 'property="og:url"',
              'name="twitter:card"', 'name="twitter:title"', 'name="twitter:description"'):
    assert _head in RULES_TEXT, "rules page is missing %s" % _head

# 3. no product link: every absolute link on the page is a GOVERNMENT page, never a shop or a maker.
_RULES_GOV = ("canada.ca", "gov.bc.ca", "alberta.ca", "sgi.sk.ca", "gov.mb.ca", "ontario.ca",
              "saaq.gouv.qc.ca", "gnb.ca", "nslegislature.ca", "novascotia.ca", "princeedwardisland.ca",
              "rcmp.ca", "yukon.ca", "gov.nt.ca", "nunavutlegislation.ca")
_rhrefs = re.findall(r'href="([^"]+)"', RULES_TEXT)
_rext = sorted(h for h in _rhrefs if h.startswith("http") and not h.startswith(SITE))
_rbad = [h for h in _rext if not h.split("//", 1)[1].split("/", 1)[0].endswith(_RULES_GOV)]
assert not _rbad, "the rules page links off to a non-government URL: %r" % _rbad
assert len(_rext) >= len(RULES_PROVINCES), "the rules page dropped its province source links"

# 4. every number that reached the page must come from a substitution, precomputed above.
_allowed_nums = set()
for _v in _RULES_SUBST.values():
    _allowed_nums |= set(re.findall(r"\d[\d,.]*", str(_v)))
_body_text = re.sub(r"(?s)<(style|script).*?</\1>", " ", RULES_TEXT.split("<body>", 1)[1])
_body_text = html.unescape(re.sub(r"(?s)<[^>]+>", " ", _body_text))
_page_nums = set(re.findall(r"\d[\d,.]*", _body_text))
assert _page_nums <= _allowed_nums, \
    "number on the rules page with no published source: %r" % sorted(_page_nums - _allowed_nums)

# 5. a province's figures must be IN that province's own quote, or the row is a paraphrase that drifted
#    from the page it cites. Spaces and commas are dropped on both sides so "500 W" matches "500W".
def _digits(s):
    return set(re.findall(r"\d+", str(s).replace(",", "").replace(" ", "")))


for _p in RULES_PROVINCES:
    _claimed = _digits(_p["motor"]) | _digits(_p["speed"]) | _digits(_p["age"])
    _in_quote = _digits(_p["quote"])
    assert _claimed <= _in_quote, \
        "%s: figures %r are not in that province's own quote %r" % (_p["name"], sorted(_claimed - _in_quote),
                                                                   _p["quote"])
print("rules page: %d bytes, %d figures, every one substituted from a named government source, "
      "no affiliate element, no product link, %d provinces" % (len(RULES_TEXT), len(_page_nums),
                                                               len(RULES_PROVINCES)))

# ================================================================ where you may ride: trails, parks and paths
# The rules page answers what a ROAD allows. It does not answer which trail, park or conservation area takes a
# Class 1 e-bike and which bans a throttle bike - the next question a rider asks. Crew-owned like /rules/ and
# /gear/: NO config.js, NO .aff element and NO product link; every off-site link is a GOVERNMENT or park-
# authority page, asserted host by host below, and every figure a row prints must sit inside that authority's
# own verbatim, dated quote or the build stops. The template carries no digit of its own.
TRAILS = [
    dict(who=u"Parks Canada \u2014 national parks and national historic sites",
         src=u"Parks Canada, \u201cVisitor guidelines \u2014 Pedal assist e-bikes\u201d",
         url="https://parks.canada.ca/voyage-travel/regles-rules",
         date=u"read 2026-10-09",
         ride=u"Pedal-assist only, on designated bike trails",
         rule=(u"Pedal-assist e-bikes are allowed on designated bike trails at select national parks \u2014 "
               u"contact the park to find out which. A pedal-assist e-bike is capped at 500 W and at 32 km/h "
               u"on level ground, and a bike with a throttle is not a pedal-assist e-bike and may be ridden "
               u"only on roads."),
         fig=u"500 W, 32 km/h",
         quote=(u"Pedal assist electric bicycles (e-bikes) are allowed on designated bike trails at select "
                u"national parks. Contact the park you are planning to visit to find out which trails you are "
                u"allowed to ride. [...] The motor can generate a maximum of 500W. Power assistance stops "
                u"when the bicycle attains a speed of 32 km/h on level ground. Please note that e-bikes "
                u"equipped with an accelerator (a throttle) are not pedal assist e-bikes and can only be "
                u"ridden on roads.")),
    dict(who=u"Parks Canada \u2014 Banff National Park (superintendent's order)",
         src=u"Parks Canada, Banff National Park, \u201cRestricted Activity: Electric bicycles (e-bikes)\u201d",
         url="https://parks.canada.ca/pn-np/ab/banff/bulletins/8942f86e-3565-4b9a-a424-7c86d7c97701",
         date=u"issued 28 March 2025, read 2026-10-09",
         ride=u"Pedal-assist only, on named trail segments; otherwise roads only",
         rule=(u"E-bikes are prohibited in Banff National Park except on paved roads and highways. "
               u"Pedal-assist e-bikes are allowed on named trail segments and networks, capped at 500 W and "
               u"32 km/h and with the motor disengaged below 3 km/h; a breach carries a maximum penalty of "
               u"$25 000."),
         fig=u"500 W, 32 km/h, 3 km/h, 25000",
         quote=(u"The use of electric bicycles (e-bikes) is prohibited in Banff National Park except on paved "
                u"roads and highways. Exceptions: Pedal assist e-bikes are permitted on trail segments, and "
                u"networks listed below. [...] Trail segments and networks where pedal assist e-bikes are "
                u"permitted [...] it has a total power output rating of 500 W or less, [...] is incapable of "
                u"providing further assistance when the bicycle attains a speed of 32 km/h on level ground, "
                u"[...] is equipped with a safety mechanism that prevents the motor from being engaged before "
                u"the bicycle attains a speed of 3 km/h. [...] Violators may be charged under the Canada "
                u"National Parks Act: maximum penalty $25 000.")),
    dict(who=u"BC Parks \u2014 provincial parks, protected areas and conservancies",
         src=u"BC Parks, \u201cCycling \u2014 E-bikes\u201d",
         url="https://bcparks.ca/plan-your-trip/things-to-do/cycling/",
         date=u"read 2026-10-09",
         ride=u"Class 1 wherever cycling is allowed; Class 2 and 3 where motor vehicles are",
         rule=(u"Class 1 e-bikes are allowed wherever cycling is already permitted, unless a sign closes the "
               u"trail to e-bikes. Class 2 and Class 3 e-bikes \u2014 the classes that may accelerate to "
               u"32 km/h and to 45 km/h \u2014 are usually allowed only where motor vehicles are permitted."),
         fig=u"32 km/h, 45 km/h",
         quote=(u"Electric bikes are welcome in many BC Parks. [...] Class 1 e-bikes are allowed where cycling "
                u"is already permitted, unless signs indicate that a trail is closed to e-bikes. Class 2 and 3 "
                u"e-bikes are usually allowed where motor vehicles are permitted, such as on roads and "
                u"off-roading tracks. [...] Class 1: 32 km per hour; Class 2: 32 km per hour; Class 3: "
                u"45 km per hour.")),
    dict(who=u"Recreation Sites and Trails BC \u2014 established recreation trails on Crown land",
         src=u"Recreation Sites and Trails BC, \u201cE-bike Policy\u201d",
         url=("https://www2.gov.bc.ca/assets/gov/sports-recreation-arts-and-culture/outdoor-recreation/"
              "camping-and-hiking/recreation-sites-and-trails/ebike_policy_final_04-25-2019.pdf"),
         date=u"policy dated 2019, read 2026-10-09",
         ride=u"Class 1 on non-motorized trails; all classes where motorized use is allowed",
         rule=(u"All classes of e-bike are permitted on a trail open to motorized use; Class 1 alone is "
               u"permitted on a trail open to non-motorized use unless e-bikes are specifically prohibited; "
               u"Class 2 and Class 3 are not permitted where motor vehicles are prohibited."),
         fig=u"Class 1, Class 2, Class 3",
         quote=(u"Default Designations. The following default designations apply unless specific exemptions, "
                u"prohibitions or allowances are provided [...] (a) All classes of e-bikes are permitted on "
                u"Established Recreation Trails open to both motorized and non-motorized use, (b) Class 1 "
                u"e-bikes / MAC are permitted on Established Recreation Trails open to non-motorized use "
                u"unless e-bikes are specifically prohibited. (c) Class 2 and 3 e-bikes are not permitted on "
                u"Established Recreation Trails that prohibit motorized vehicles.")),
    dict(who=u"National Capital Commission \u2014 Capital Pathway and Gatineau Park",
         src=u"National Capital Commission, \u201cShare the Path\u201d",
         url="https://ncc-ccn.gc.ca/places/share-the-path",
         date=u"read 2026-10-09",
         ride=u"Bicycle-style pedal e-bikes; throttle-only devices banned",
         rule=(u"Bicycle-style power-assisted e-bikes with operable pedals are permitted on the Capital "
               u"Pathway; devices powered exclusively by a throttle, and electric kick-style scooters, are "
               u"prohibited, and the pathway speed limit is 20 km/h."),
         fig=u"20 km/h",
         quote=(u"Rules for electric power-assisted vehicles. Here are the devices permitted and prohibited "
                u"on the Capital Pathway and parkways when they are open for active use only. Permitted: "
                u"Electric power-assisted bicycles (\u201ce-bikes\u201d), with operable pedals, that resemble "
                u"conventional bicycles; Electric power-assisted cargo bicycles (\u201ccargo e-bikes\u201d), "
                u"with operable pedals, for personal use; Motorized mobility aids, including but not limited "
                u"to powered wheelchairs and scooters with three to five wheels. Prohibited: Electric "
                u"power-assisted cargo bicycles for commercial use; Electric kick-style scooters; All devices "
                u"that are exclusively powered by a throttle; All other electric-powered vehicles that are not "
                u"specified above. [...] Travel at speeds that allow you to react in time for whatever might "
                u"arise. (Maximum 20 km/h)")),
    dict(who=u"Alberta Parks \u2014 provincial parks, provincial recreation areas and wildland provincial parks",
         src=u"Alberta Parks, \u201cFAQs \u2014 Cycling\u201d",
         url="https://albertaparks.ca/faqs",
         date=u"read 2026-10-09",
         ride=u"Class 1 only on designated cycling trails; no other class",
         rule=(u"Pedal-assist e-bikes are permitted on public roads in parks, and on pathways and trails where "
               u"cycling is permitted. A permitted e-bike is non-throttled, provides up to 500 W of continuous "
               u"maximum output and stops assisting when pedalling stops or 32 km/h is reached \u2014 a class 1 "
               u"e-bike. Other types or classes of e-bike are not permitted on designated cycling pathways and "
               u"trails in provincial parks, provincial recreation areas and wildland provincial parks."),
         fig=u"Class 1; 500 W; 32 km/h",
         quote=(u"Pedal assist electric-powered bikes (e-bikes) are permitted on public roads in parks and on "
                u"pathways and trails where cycling is permitted. [...] Permitted e-bikes are defined as "
                u"non-throttled electric powered bicycles that provide up to 500 Watts of continuous maximum "
                u"output. The electronic assist must stop when either pedaling stops or 32 km/h is reached. This "
                u"is sometimes referred to as a class 1 e-bike. [...] Other types or classes of e-bikes are not "
                u"permitted on designated cycling pathways and trails in provincial parks, provincial recreation "
                u"areas, and wildland provincial parks.")),
]

TRAIL_HEAD = u"One row per land manager: who allows what on the ground"
TRAIL_SUB = (u"Each row is one authority's own page, read on the date shown, and the rule is quoted from it. "
             u"The rule column prints only what that quote says; where a manager sets no e-bike rule of its "
             u"own, that is a gap this page reports rather than fills.")
TRAIL_NOTE = (u"Read the two columns against each other, because they disagree on purpose. The class numbers "
              u"are the manufacturers' convention; a land manager often decides the other way round \u2014 "
              u"Parks Canada and the NCC allow a pedal-assist machine that looks like a bicycle and turn away "
              u"a throttle bike \u2014 while BC Parks sorts by class and lets a Class 2 or Class 3 machine onto "
              u"a trail only where a motor vehicle may go. The same bike can be welcome on one manager's trail "
              u"and barred from the trail beside it.")
TRAIL_TITLE = (u"Where you can ride an e-bike in Canada: trails, parks and paths, one land manager at a time "
               u"| Commuter E-Bikes CA")
TRAIL_OGTITLE = u"Where you can ride an e-bike in Canada: trails, parks and paths"
TRAIL_DESC = (u"Where a Canadian e-bike may actually be ridden: national parks, BC's parks and recreation "
              u"trails, Alberta's provincial parks, and the National Capital Commission's pathway and "
              u"Gatineau Park \u2014 each rule quoted from the authority's own page and dated, with no "
              u"affiliate link.")
TRAIL_INTRO = (u"Road rules are one question; the ground under the wheels is another. An e-bike can be legal "
               u"in a province and still barred from the trail it is on, because the trail is the land "
               u"manager's decision, not the province's. This page sets out, manager by manager, what is "
               u"allowed on the trails, in each authority's own words and dated. Every figure is published by "
               u"the authority named; nothing here is this site's opinion.")
TRAIL_DISCLOSURE = (u"this page has no affiliate link and nothing to buy. It carries no partner link, no "
                    u"commission and no product link; every off-site link on it is a government or "
                    u"park-authority page, and this is general information, not legal advice.")


def _trail_row(t):
    return ('<tr><th scope="row" class="model">%s<span class="src">'
            '<a href="%s" target="_blank" rel="noopener nofollow">%s</a> &middot; %s</span></th>'
            '<td>%s</td><td>%s</td></tr>'
            % (esc(t["who"]), esc(t["url"]), esc(t["src"]), esc(t["date"]), esc(t["ride"]), esc(t["rule"])))


TRAIL_ROWS = "\n        ".join(_trail_row(t) for t in TRAILS)

TRAIL_SRC_HEAD = u"Every authority, and what it says"
TRAIL_SRC_SUB = (u"Each page below was read on the date shown, and the rule in the table above is taken from "
                 u"the quoted text. Nothing on this page comes from memory.")


def _trail_src_block(t):
    return ('<li><strong>%s</strong> \u00b7 %s \u00b7 %s: '
            '<a href="%s" target="_blank" rel="noopener nofollow">%s</a>'
            '<blockquote class="quote">%s</blockquote></li>'
            % (esc(t["who"]), esc(t["date"]), esc(t["src"]), esc(t["url"]), esc(t["url"]), esc(t["quote"])))


TRAIL_SOURCES = "\n        ".join(_trail_src_block(t) for t in TRAILS)

TRAILS_PAGE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__</title>
<meta name="description" content="__DESC__">
<link rel="canonical" href="__CANONICAL__">
<meta property="og:type" content="article">
<meta property="og:site_name" content="Commuter E-Bikes CA">
<meta property="og:title" content="__OGTITLE__">
<meta property="og:description" content="__DESC__">
<meta property="og:url" content="__CANONICAL__">
<meta name="twitter:card" content="summary">
<meta name="twitter:title" content="__OGTITLE__">
<meta name="twitter:description" content="__DESC__">
<style>__CSS__
  .crumb{font-size:13px;color:var(--muted);margin:0 0 8px}
  .trailhero{padding:34px 0 8px}
  .trailhero h1{font-size:clamp(27px,4.6vw,42px);line-height:1.12;margin:0 0 12px;max-width:34ch}
  table.trails .model{font-weight:700}
  table.trails .src{display:block;color:var(--muted);font-size:12px;font-weight:400;margin-top:4px}
  table.trails td{vertical-align:top}
  ul.otherbikes{list-style:none;padding:0;margin:0;display:grid;gap:8px}
  ul.otherbikes a{font-size:14.5px}
  ul.sources li{margin:0 0 16px}
  blockquote.quote{margin:8px 0 0;padding:8px 12px;border-left:3px solid var(--accent);background:var(--card);
    border-radius:6px;color:#3a3f49;font-size:13.5px;max-width:80ch}
</style>
</head>
<body>
<header class="top"><div class="wrap">
  <a class="brand" href="../" style="color:inherit;text-decoration:none">Commuter E-Bikes CA</a>
  <span class="stamp">Pages read <strong>__CHECKED__</strong></span>
</div></header>

<main class="wrap">
  <section class="trailhero" style="border-top:none">
    <p class="crumb"><a href="../">All __N_WORD__ commuter e-bikes, compared</a> &rsaquo; Where you may ride</p>
    <h1>Where you may ride an e-bike: trails, parks and paths, one land manager at a time</h1>
    <p class="deck">__INTRO__</p>
    <p class="disclosure" role="note"><strong>Disclosure:</strong> __DISC__</p>
  </section>

  <section id="trails">
    <h2>__TRAIL_HEAD__</h2>
    <p class="sub">__TRAIL_SUB__</p>
    <div class="tablewrap">
      <table class="rules trails">
        <caption>One row per land manager. Each rule is quoted from that manager's own page on the date shown.</caption>
        <thead><tr>
          <th scope="col">Who manages the ground</th>
          <th scope="col">What may ride there</th>
          <th scope="col">The rule, in the manager's own words</th>
        </tr></thead>
        <tbody>
        __TRAIL_ROWS__
        </tbody>
      </table>
    </div>
    <p class="note">__TRAIL_NOTE__</p>
  </section>

  <section id="sources">
    <h2>__SRC_HEAD__</h2>
    <p class="sub">__SRC_SUB__</p>
    <ul class="sources">__SOURCES__</ul>
  </section>

  <section id="next">
    <h2>Read the rest</h2>
    <ul class="otherbikes">
      <li><a href="../">All __N_WORD__ commuter e-bikes, compared side by side</a></li>
      <li><a href="../rules/">Classes and rules: what the three classes mean in Canada, province by province</a></li>
      <li><a href="../commute-costs/">What a commute actually costs, e-bike vs car vs transit</a></li>
      <li><a href="../gear/">Gear: helmets, locks and lights</a></li>
    </ul>
  </section>
</main>

<footer><div class="wrap">
  <p><strong>Disclosure:</strong> __DISC__</p>
  <p>This is general information about published trail and park rules, not legal advice, and not advice about your particular riding, health or by-laws. Rules change; read the land manager's own page before you ride.</p>
  <p>Built __CHECKED__ by the GAMMA project. Every authority is named above; data: <a href="../data/products.json">products.json</a> &middot; <a href="../">the comparison</a> &middot; <a href="../rules/">classes and rules</a>.</p>
</div></footer>
</body>
</html>
"""

# The template may carry no figure of its own: every digit in the output must come from a substitution.
_trail_probe = re.sub(r"(?s)<(style|script).*?</\1>", " ", TRAILS_PAGE)
_trail_probe = re.sub(r"(?s)<[^>]+>", " ", _trail_probe)
_trail_probe = re.sub(r"__[A-Z_0-9]*__", "", _trail_probe)
assert not re.search(r"\d", _trail_probe), \
    "a figure is typed into the trails template instead of being substituted"

_TRAILS_SUBST = {
    "__CSS__": CSS,
    "__N_WORD__": esc(N_WORD),
    "__CHECKED__": esc(CHECKED),
    "__TITLE__": esc(TRAIL_TITLE),
    "__OGTITLE__": esc(TRAIL_OGTITLE),
    "__DESC__": esc(TRAIL_DESC),
    "__CANONICAL__": "%s/trails/" % SITE,
    "__INTRO__": esc(TRAIL_INTRO),
    "__DISC__": esc(TRAIL_DISCLOSURE),
    "__TRAIL_HEAD__": esc(TRAIL_HEAD),
    "__TRAIL_SUB__": esc(TRAIL_SUB),
    "__TRAIL_ROWS__": TRAIL_ROWS,
    "__TRAIL_NOTE__": esc(TRAIL_NOTE),
    "__SRC_HEAD__": esc(TRAIL_SRC_HEAD),
    "__SRC_SUB__": esc(TRAIL_SRC_SUB),
    "__SOURCES__": TRAIL_SOURCES,
}
_trails_out = TRAILS_PAGE
for _k, _v in _TRAILS_SUBST.items():
    _trails_out = _trails_out.replace(_k, _v)
write_page(os.path.join(ROOT, "trails", "index.html"), _trails_out, "trails")

# ---- the page is read back and checked before the sitemap is written
TRAILS_FILE = os.path.join(ROOT, "trails", "index.html")
TRAILS_TEXT = open(TRAILS_FILE, encoding="utf-8").read()

# 1. nothing here can pay.
for _bad in ("config.js", "AFFILIATE_", 'data-aff=', 'class="buyaff"'):
    assert _bad not in TRAILS_TEXT, "affiliate element on the trails page: %r" % _bad

# 2. its own head.
assert '<link rel="canonical" href="%s/trails/">' % SITE in TRAILS_TEXT
for _head in ('<title>', 'name="description"', 'property="og:type"', 'property="og:site_name"',
              'property="og:title"', 'property="og:description"', 'property="og:url"',
              'name="twitter:card"', 'name="twitter:title"', 'name="twitter:description"'):
    assert _head in TRAILS_TEXT, "trails page is missing %s" % _head

# 3. no product link: every absolute link is a GOVERNMENT or park-authority page.
_TRAIL_GOV = ("canada.ca", "gc.ca", "bcparks.ca", "gov.bc.ca", "albertaparks.ca")
_threfs = re.findall(r'href="([^"]+)"', TRAILS_TEXT)
_thext = sorted(h for h in _threfs if h.startswith("http") and not h.startswith(SITE))
_tbad = [h for h in _thext if not h.split("//", 1)[1].split("/", 1)[0].endswith(_TRAIL_GOV)]
assert not _tbad, "the trails page links off to a non-government URL: %r" % _tbad
assert len(_thext) >= len(TRAILS), "the trails page dropped its authority source links"

# 4. every number that reached the page must come from a substitution.
_allowed_tn = set()
for _v in _TRAILS_SUBST.values():
    _allowed_tn |= set(re.findall(r"\d[\d,.]*", str(_v)))
_tbody = re.sub(r"(?s)<(style|script).*?</\1>", " ", TRAILS_TEXT.split("<body>", 1)[1])
_tbody = html.unescape(re.sub(r"(?s)<[^>]+>", " ", _tbody))
_tnums = set(re.findall(r"\d[\d,.]*", _tbody))
assert _tnums <= _allowed_tn, \
    "number on the trails page with no published source: %r" % sorted(_tnums - _allowed_tn)


# 5. a row's figures must be IN that authority's own quote, or the row is a paraphrase that drifted.
def _tdig(s):
    return set(re.findall(r"\d+", str(s).replace(",", "").replace(" ", "")))


for _t in TRAILS:
    _claimed = _tdig(_t["rule"]) | _tdig(_t["fig"]) | _tdig(_t["ride"])
    _inq = _tdig(_t["quote"])
    assert _claimed <= _inq, \
        "%s: figures %r are not in that authority's own quote" % (_t["who"], sorted(_claimed - _inq))
print("trails page: %d bytes, %d figures, every one substituted from a named authority's page, "
      "no affiliate element, no product link, %d authorities" % (len(TRAILS_TEXT), len(_tnums), len(TRAILS)))

# ================================================================ the reader: /stats/
# A count nobody can read is not a measurement. This page reads every key back through the service's
# /get endpoint and shows what it finds, so "how much traffic does this lane get" has an answer that
# can be checked rather than asserted. Generated here like every other page: its own title, its own
# meta description, its own canonical, listed in sitemap.xml, and linked from the landing page footer.
SITE_PATH = "/canada-ebike-compare"
assert SITE.endswith(SITE_PATH), "SITE_PATH has drifted from SITE"

def metric_segment(path):
    """The beacon's segment for a page, derived from the page's own path so the two cannot drift."""
    return "index" if not path else path.replace("/", "-")

# Every page this build generates, in page order: (site-relative path, the name shown on /stats/).
METRIC_PAGES = (
    [("", "The comparison &mdash; the landing page")]
    + [("bikes/%s" % p["id"], "%s %s \u2014 %s" % (p["maker"], p["model"], p["price_display"]))
       for p in ORDER]
    + [("how-far", "How far will it go? &mdash; the range picker")]
    + [("guide", "The decision guide &mdash; the free front-door page")]
    + [("commute-costs", "What a commute costs &mdash; e-bike vs car vs transit, per year")]
    + [("gear", "Gear &mdash; helmets, locks and lights, and what each bike is rated to carry")]
    + [("rules", "Classes and rules &mdash; what Class 1/2/3 mean in Canada, province by province")]
    + [("trails", "Where you may ride &mdash; trails, parks and paths, one land manager at a time")]
    + [("vs/%s" % s, "%s" % pair_label(*pair)) for s, pair in zip(PAIR_SLUGS, PAIRS)]
    + [("stats", "This page &mdash; the counts")]
)

STATS_PAGE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Page views on this site | Commuter E-Bikes CA</title>
<meta name="description" content="How many page views each page of this Canadian commuter e-bike comparison has been counted for, read live. Counted anonymously: no cookie, no referring page, no identifier.">
<link rel="canonical" href="__CANONICAL__">
<style>__CSS__
  .crumb{font-size:13px;color:var(--muted);margin:0 0 8px}
  .stathero{padding:30px 0 8px}
  .stathero h1{font-size:clamp(26px,4.4vw,40px);line-height:1.12;margin:0 0 10px;max-width:24ch}
  .statwrap{border:1px solid var(--line);border-radius:10px;background:var(--card);overflow-x:auto}
  table.stats{min-width:560px}
  table.stats td.num,table.stats th.num{text-align:right;font-variant-numeric:tabular-nums;font-weight:700;white-space:nowrap}
  table.stats td.pkey{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;font-size:12px;color:var(--muted);word-break:break-all}
  table.stats tr.total th,table.stats tr.total td{border-top:2px solid var(--line);font-weight:700}
  #status{font-size:14px;color:var(--muted);max-width:78ch;margin:0 0 18px}
  ol.method{margin:0;padding-left:22px}
  ol.method li{margin:0 0 9px;max-width:76ch;color:#333842}
  code{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;font-size:13px}
</style>
</head>
<body>
<header class="top"><div class="wrap">
  <span class="brand">Commuter E-Bikes CA</span>
  <span class="stamp">Counts read <strong id="asof">&hellip;</strong></span>
</div></header>

<main class="wrap">
  <section class="stathero" style="border-top:none">
    <p class="crumb"><a href="../">&larr; The comparison</a></p>
    <h1>Page views on this site</h1>
    <p class="deck">This site counts its own page views, anonymously, and shows the number here. The reason is blunt: a comparison site nobody finds earns nothing, and until this page existed there was no way to tell whether anyone was finding this one.</p>
    <p id="status">Reading the counters&hellip;</p>
    <p class="disclosure" role="note"><strong>Disclosure:</strong> this page has no live affiliate links and nothing to buy. It carries no analytics product, no cookie and no third-party script beyond the count described below.</p>
  </section>

  <section id="counts">
    <h2>The counts</h2>
    <p class="sub">One row per page on this site, read live from the counting service when this page loaded. Reload to refresh.</p>
    <div class="statwrap">
      <table class="stats">
        <caption>Every count below is fetched directly from your browser to the counting service, so this page serves the same bytes to everyone &mdash; no number is baked into the file.</caption>
        <thead><tr><th scope="col">Page</th><th scope="col">Counter key</th><th scope="col" class="num">Views</th></tr></thead>
        <tbody>
__ROWS__
          <tr class="total"><th scope="row" colspan="2">All pages</th><td class="num" id="total">&hellip;</td></tr>
        </tbody>
      </table>
    </div>
  </section>

  <section id="method">
    <h2>What is counted, and what is not</h2>
    <ol class="method">
      <li><strong>Counted:</strong> one anonymous increment per page load, fired by a few lines of script that every page on this site carries. The counter names the <em>page</em>, and nothing else.</li>
      <li><strong>Not counted:</strong> any visitor with JavaScript switched off &mdash; and <strong>counted:</strong> any software that loads a page and runs scripts, crawlers included. These numbers are a floor, not a census; a small number is not proof that nobody looked.</li>
      <li><strong>What leaves a visitor's browser:</strong> one plain GET carrying no cookie (<code>credentials: omit</code>), no referring page (<code>referrerPolicy: no-referrer</code>) and no identifier of any kind. A counting service, like any web server, necessarily sees the requesting IP address; nothing else about a visitor is sent or stored.</li>
      <li><strong>Where the numbers live:</strong> the counters are kept by <a href="__BASE__" target="_blank" rel="noopener">Abacus</a>, a free counting API that needs no account, no signup and no key, under the namespace <code>__NS__</code>. Every row above reads its own key back the same way, and any value is a plain address you can open yourself &mdash; for example this site's landing-page counter, <a href="__BASE__/get/__NS__/__EXAMPLEKEY__"><code>__BASE__/get/__NS__/__EXAMPLEKEY__</code></a>. Every key on this page is a real counter that a page on this site fires when it loads; there is no placeholder. It is a third party with no uptime promise: where it cannot be reached, the rows above say so rather than showing a zero. It also allows only 30 reads per 10 seconds per address, and this page reads 15 counters &mdash; so it reads them one at a time, about two a second, and waits out a rate-limited read instead of calling the counter dead.</li>
      <li><strong>Nothing is sold, profiled or shared.</strong> There is no analytics product here, no cross-site tracking and no attempt to identify anyone. The only use made of these numbers is knowing whether this site is being read.</li>
    </ol>
  </section>
</main>

<footer><div class="wrap">
  <p><strong>Disclosure:</strong> this site carries no live affiliate links. No purchase through this page earns anyone a commission today, and nothing on this page is paid for.</p>
  <p>This is general product information, not advice about your particular riding, health or local by-laws.</p>
  <p>Built __CHECKED__ by the GAMMA project. Data: <a href="../data/products.json">products.json</a> &middot; <a href="../">the comparison</a> &middot; <a href="../how-far/">the range picker</a>.</p>
</div></footer>

<script>
(function(){
  var BASE = "__BASE__/get/__NS__/";
  var cells = Array.prototype.slice.call(document.querySelectorAll("[data-metric-key]"));
  var status = document.getElementById("status");
  var total = document.getElementById("total");
  var asof = document.getElementById("asof");
  var stamp = new Date();
  var sum = 0, read = 0, missing = 0, failed = 0;
  asof.textContent = stamp.toLocaleString();

  /* The counting service allows 30 requests per 10 seconds per IP and this page reads 15 counters. Fired
     all at once, a second look at this page inside one window made most rows read "unavailable" - measured
     on the live page, twice, not guessed. So the reads are paced at about two a second (a full read is
     ~10 s, which keeps two consecutive looks inside the limit) and a rate-limited read is waited out and
     retried rather than reported as a dead counter. A row reads "unavailable" only after every retry. */
  var GAP = 500, RETRY_AFTER = 4000, TRIES = 4;

  function pause(ms){ return new Promise(function(r){ setTimeout(r, ms); }); }

  function finish(){
    total.textContent = sum.toLocaleString() + (failed ? " (partial)" : "");
    status.textContent = "Read " + read + " of " + cells.length + " counters"
      + (missing ? ", of which " + missing + " have never been hit and are shown as 0" : "")
      + (failed ? ", and " + failed + " could not be reached (shown as \"unavailable\" and excluded from the total)" : "")
      + ". Read at " + stamp.toLocaleString() + ". These are page loads that ran scripts, not people.";
  }

  function one(cell, tries){
    return fetch(BASE + cell.getAttribute("data-metric-key"), {cache:"no-store"})
      .then(function(r){
        if (r.status === 404) { missing++; cell.textContent = "0"; cell.title = "no hit has reached this page yet"; return; }
        if (r.status === 429) {
          if (tries > 1) return pause(RETRY_AFTER).then(function(){ return one(cell, tries - 1); });
          throw new Error("rate limited");
        }
        if (!r.ok) throw new Error("HTTP " + r.status);
        return r.json().then(function(j){ read++; var v = j.value|0; sum += v; cell.textContent = v.toLocaleString(); });
      })
      .catch(function(){ failed++; cell.textContent = "unavailable"; });
  }

  var i = 0;
  (function next(){
    if (i >= cells.length) { finish(); return; }
    var cell = cells[i++];
    status.textContent = "Reading the counters (" + i + " of " + cells.length + ")\u2026";
    one(cell, TRIES).then(function(){ return pause(GAP).then(next); });
  })();
})();
</script>
</body>
</html>
"""

STATS_ROWS = "\n".join(
    '          <tr><th scope="row"><a href="../%s">%s</a></th>'
    '<td class="pkey">%s</td>'
    '<td class="num" data-metric-key="%s">&hellip;</td></tr>'
    % (esc(path + "/" if path else ""), label, esc(metric_key(metric_segment(path))),
       esc(metric_key(metric_segment(path))))
    for path, label in METRIC_PAGES)

_stats_out = (STATS_PAGE
              .replace("__CSS__", CSS)
              .replace("__CANONICAL__", "%s/stats/" % SITE)
              .replace("__ROWS__", STATS_ROWS)
              .replace("__NS__", esc(METRIC_NS))
              .replace("__BASE__", esc(METRIC_BASE))
              # Named, real key - the landing page's own counter - so the page explains itself with an
              # address that actually answers instead of a <key> template that reads like a broken row.
              .replace("__EXAMPLEKEY__", esc(metric_key(metric_segment(""))))
              .replace("__CHECKED__", esc(CHECKED)))
write_page(os.path.join(ROOT, "stats", "index.html"), _stats_out, "stats")

# ---------------------------------------------------------------- the beacon and the reader must agree
# A statistics page that reads a key no page writes is fiction, and a page whose beacon drifted from
# its row is a blind spot. So every generated page is read back off disk and its beacon key compared
# with the key its row on /stats/ will fetch. Any mismatch, any extra or any missing page stops the
# build - before sitemap.xml is written.
_BEACON_RE = re.compile(r'fetch\("https://[^"]*/hit/[^/]+/([A-Za-z0-9_.-]+)"')
_UNSUB = re.compile(r"__[A-Z_][A-Z_0-9]*__")
for _path, _label in METRIC_PAGES:
    _file = os.path.join(ROOT, _path, "index.html")
    _text = open(_file, encoding="utf-8").read()
    _want = [metric_key(metric_segment(_path))]
    _got = _BEACON_RE.findall(_text)
    assert _got == _want, "beacon/reader mismatch in %s: beacon %r, row %r" % (_file, _got, _want)
    # A build token left in the output is a page that says __DESC__ to a reader and to a crawler.
    _left = sorted(set(_UNSUB.findall(_text)))
    assert not _left, "%s still carries unsubstituted build tokens: %r" % (_file, _left)
    print("beacon ok: %s -> %s" % (os.path.relpath(_file, ROOT).replace(os.sep, "/"), _want[0]))
_KEYS = [metric_key(metric_segment(p)) for p, _ in METRIC_PAGES]
assert len(set(_KEYS)) == len(_KEYS), "two pages share one counter key"

# The reader itself is read back too. A row is only reading a real key if the key it prints is a key some
# page fires, and nothing on the page may be an unsubstituted template: a bare <key> on a stats page reads
# as a broken row to anyone who looks at it, whether or not the script behind it works.
_stats_text = open(os.path.join(ROOT, "stats", "index.html"), encoding="utf-8").read()
for _bad in ("&lt;key&gt;", "<key>", "__BASE__", "__NS__", "__ROWS__", "__CSS__", "__CANONICAL__",
             "__CHECKED__", "__EXAMPLEKEY__"):
    assert _bad not in _stats_text, "unsubstituted token on /stats/: %r" % _bad
_ROWS_READ = re.findall(r'data-metric-key="([^"]+)"', _stats_text)
assert _ROWS_READ == _KEYS, \
    "/stats/ reads keys no page fires (or misses one): %r" % (set(_ROWS_READ) ^ set(_KEYS),)
print("stats reader: %d rows, every one a live beacon key, no placeholder token" % len(_ROWS_READ))

# ---------------------------------------------------------------- sitemap + robots
URLS = (["%s/" % SITE] + ["%s/bikes/%s/" % (SITE, p["id"]) for p in ORDER]
        + ["%s/how-far/" % SITE] + ["%s/guide/" % SITE] + ["%s/commute-costs/" % SITE]
        + [("%s/gear/" % SITE)] + [("%s/rules/" % SITE)] + [("%s/trails/" % SITE)]
        + ["%s/stats/" % SITE]
        + ["%s/vs/%s/" % (SITE, s) for s in PAIR_SLUGS])
# The sitemap and the beacon list are the same set of pages, or one of them is lying. Asserted, not assumed.
_metric_urls = sorted(("%s/%s/" % (SITE, p)) if p else ("%s/" % SITE) for p, _l in METRIC_PAGES)
assert sorted(URLS) == _metric_urls, \
    "sitemap and the page list disagree: %r" % (set(URLS) ^ set(_metric_urls),)
sitemap = ('<?xml version="1.0" encoding="UTF-8"?>\n'
           '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
           + "\n".join("  <url><loc>%s</loc><lastmod>%s</lastmod></url>" % (u, esc(CHECKED)) for u in URLS)
           + "\n</urlset>\n")
open(os.path.join(ROOT, "sitemap.xml"), "w", encoding="utf-8").write(sitemap)
print("wrote sitemap.xml (%d urls)" % len(URLS))

robots = "User-agent: *\nAllow: /\n\nSitemap: %s/sitemap.xml\n" % SITE
open(os.path.join(ROOT, "robots.txt"), "w", encoding="utf-8").write(robots)
print("wrote robots.txt")

# ================================================================ PDF
# invariant mode fixes reportlab's CreationDate/ModDate and the trailer file ID to a constant, so the
# PDF - like every HTML/XML/TXT file above - is byte-identical across rebuilds. Content streams are
# unchanged; only the two timestamp strings and the document ID would otherwise differ on every run.
from reportlab import rl_config
rl_config.invariant = 1
from reportlab.lib.pagesizes import landscape, letter
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
                                PageBreak, KeepTogether)
from reportlab.lib.enums import TA_LEFT

INK = colors.HexColor("#16181d"); MUTED = colors.HexColor("#5d6270")
ACCE = colors.HexColor("#0e6b53"); LINE = colors.HexColor("#d8d2c6")
HEADBG = colors.HexColor("#f3efe7"); AMBER = colors.HexColor("#a6550c")

H1 = ParagraphStyle("H1", fontName="Times-Bold", fontSize=30, leading=33, textColor=INK, spaceAfter=8)
H2 = ParagraphStyle("H2", fontName="Times-Bold", fontSize=19, leading=22, textColor=INK, spaceBefore=14, spaceAfter=6)
H3 = ParagraphStyle("H3", fontName="Helvetica-Bold", fontSize=11.5, leading=14, textColor=INK, spaceBefore=8, spaceAfter=2)
BODY = ParagraphStyle("BODY", fontName="Helvetica", fontSize=10.5, leading=14.5, textColor=colors.HexColor("#2c313a"))
SMALL = ParagraphStyle("SMALL", fontName="Helvetica", fontSize=8.4, leading=11, textColor=MUTED)
CELL = ParagraphStyle("CELL", fontName="Helvetica", fontSize=8.2, leading=10.2, textColor=INK)
CELLB = ParagraphStyle("CELLB", fontName="Helvetica-Bold", fontSize=8.6, leading=10.4, textColor=INK)
NOTE = ParagraphStyle("NOTE", fontName="Helvetica-Oblique", fontSize=9, leading=12, textColor=MUTED, spaceBefore=6)

PDF = os.path.join(ROOT, "guide", "canada-commuter-ebike-guide.pdf")
doc = SimpleDocTemplate(PDF, pagesize=landscape(letter), leftMargin=40, rightMargin=40,
                        topMargin=38, bottomMargin=36, title="Canadian Commuter E-Bike Guide",
                        author="GAMMA")

def footer(canvas, d):
    canvas.saveState()
    canvas.setStrokeColor(LINE); canvas.setLineWidth(0.6)
    canvas.line(40, 30, landscape(letter)[0]-40, 30)
    canvas.setFont("Helvetica", 8); canvas.setFillColor(MUTED)
    canvas.drawString(40, 20, "Canadian commuter e-bike guide - specs from each maker's own product page - checked %s" % CHECKED)
    canvas.drawRightString(landscape(letter)[0]-40, 20, "Page %d" % d.page)
    canvas.restoreState()

story = []
story.append(Paragraph(GUIDE_TITLE, H1))
story.append(Paragraph(GUIDE_INTRO, BODY))
story.append(Spacer(1, 10))
story.append(Paragraph("<b>Disclosure:</b> " + GUIDE_DISCLOSURE, SMALL))
story.append(Spacer(1, 6))
story.append(Paragraph(GUIDE_PICKS_HEAD, H2))
for title, pid, body in PICKS:
    p = BY_ID[pid]
    block: list = [
        Paragraph(title, H3),
        Paragraph("<font color='#0a5340'><b>%s %s &middot; %s</b></font>" % (p["maker"], p["model"], p["price_display"]), SMALL),
    ]
    if p.get("availability"):
        block.append(Paragraph("<font color='#a6550c'><b>%s</b></font>" % p["availability"], SMALL))
    block.append(Paragraph(body, BODY))
    story.append(KeepTogether(block))

story.append(Paragraph(GUIDE_COMPARE_HEAD, H2))
story.append(Paragraph(GUIDE_COMPARE_NOTE, SMALL))
story.append(Spacer(1, 8))
rows = [[Paragraph(l.replace("\n", "<br/>"), CELLB) for l, _f in GUIDE_TABLE]]
for p in ORDER:
    modelcell = "<b>%s</b><br/><font size=7 color='#5d6270'>%s</font>" % (p["model"], p["maker"])
    if p.get("availability"):
        modelcell += "<br/><font size=7 color='#a6550c'><b>%s</b></font>" % p["availability"]
    rows.append([Paragraph(modelcell, CELL) if f is None
                 else Paragraph("<b>%s</b>" % p[f], CELL) if f == "price_display"
                 else Paragraph(p[f], CELL)
                 for _l, f in GUIDE_TABLE])
widths = [86, 56, 96, 42, 74, 86, 60, 76, 64, 60]
tbl = Table(rows, colWidths=widths, repeatRows=1)
tbl.setStyle(TableStyle([
    ("BACKGROUND", (0,0), (-1,0), HEADBG),
    ("LINEBELOW", (0,0), (-1,-1), 0.5, LINE),
    ("VALIGN", (0,0), (-1,-1), "TOP"),
    ("TOPPADDING", (0,0), (-1,-1), 6),
    ("BOTTOMPADDING", (0,0), (-1,-1), 6),
    ("LEFTPADDING", (0,0), (-1,-1), 5),
    ("RIGHTPADDING", (0,0), (-1,-1), 5),
]))
story.append(tbl)
story.append(Paragraph(GUIDE_COMPARE_NOTE2, NOTE))

story.append(Spacer(1, 14))
story.append(Paragraph(GUIDE_HOUSEHOLD_HEAD, H2))
for p in ORDER:
    story.append(KeepTogether([
        Paragraph("%s %s &nbsp;&middot;&nbsp; %s" % (p["maker"], p["model"], p["price_display"]), H3),
        Paragraph(p["best_for"], BODY),
        Paragraph("Source: %s (checked %s)." % (p["source_url"], CHECKED), SMALL),
        Spacer(1, 6),
    ]))

story.append(Spacer(1, 14))
story.append(Paragraph(GUIDE_SOURCES_HEAD, H2))
story.append(Paragraph(GUIDE_SOURCES_NOTE, BODY))
story.append(Spacer(1, 6))
for p in ORDER:
    story.append(KeepTogether([
        Paragraph("<b>%s %s</b> - %s" % (p["maker"], p["model"], p["source_url"]), SMALL),
        Paragraph(p["source_note"], SMALL),
        Spacer(1, 5),
    ]))
story.append(Spacer(1, 8))
story.append(Paragraph(GUIDE_CAVEATS, NOTE))

doc.build(story, onFirstPage=footer, onLaterPages=footer)
print("wrote", PDF)

# ---------------------------------------------------------------- the page and the PDF cannot drift
# /guide/index.html and the PDF are two artefacts of one guide, and the whole point of generating both from
# the same source is that neither can be edited without the other. Proven here: the PDF just written is read
# back through its own text layer, and every string the page prints from that shared source — the figures,
# the one-line verdicts, the headings, the notes — must be present in it. reportlab wraps lines where the
# page does not, so both sides are compared whitespace-normalised. A figure typed onto the page and not
# into the guide stops the build here.
# pypdf is a build-time dependency for this check. The build refuses to run rather than skip it: an
# assertion that can silently not run is not a guard.
try:
    import pypdf
except ImportError:
    raise SystemExit("pypdf is required: this build reads the PDF it just wrote back to prove the guide "
                     "page and the PDF carry the same figures. Install it with: py -3.10 -m pip install pypdf")

_PDF_TEXT = " ".join(" ".join((_pg.extract_text() or "").split())
                     for _pg in pypdf.PdfReader(PDF).pages)
assert len(_PDF_TEXT) > 5000, "the PDF's text layer came back nearly empty - the drift check would be a lie"

def _norm(s):
    return " ".join(str(s).split())

_SHARED = [GUIDE_TITLE, GUIDE_INTRO, GUIDE_DISCLOSURE, GUIDE_PICKS_HEAD, GUIDE_COMPARE_HEAD,
           GUIDE_COMPARE_NOTE, GUIDE_COMPARE_NOTE2, GUIDE_HOUSEHOLD_HEAD, GUIDE_SOURCES_HEAD,
           GUIDE_SOURCES_NOTE, GUIDE_CAVEATS]
_FIGURES = [p[f] for p in ORDER for _l, f in GUIDE_TABLE if f and p.get(f)]
_VERDICTS = [x for pk in PICKS for x in (pk[0], pk[2])]
_BESTFOR = [p["best_for"] for p in ORDER]

_absent = [s for s in _SHARED + _FIGURES + _VERDICTS + _BESTFOR if _norm(s) not in _PDF_TEXT]
assert not _absent, ("on the guide page but in neither the guide PDF nor products.json: %r"
                     % (_absent[:4],))

# And the coarser net: no NUMBER may appear anywhere in the page's own text that the PDF does not carry.
# Figures are the thing this site can be sued over, so a stray one anywhere - a heading, a sub, a caption -
# is caught here, not only inside the blocks the page is built from.
_page_text = re.sub(r"(?s)<(style|script).*?</\1>", " ", GUIDE_TEXT)
_page_text = html.unescape(re.sub(r"(?s)<[^>]+>", " ", _page_text))
_page_nums = sorted(set(re.findall(r"\d[\d,.]*", _page_text)))
_stray = [n for n in _page_nums if n not in _PDF_TEXT]
assert not _stray, "number(s) on the guide page that the guide PDF does not carry: %r" % (_stray,)
print("guide page vs PDF: %d shared strings and %d numbers, all present in the PDF's own text"
      % (len(_SHARED) + len(_FIGURES) + len(_VERDICTS) + len(_BESTFOR), len(_page_nums)))

# ================================================================ the share card: one Open Graph image per page
# Every page carried OG/Twitter tags and no og:image, so a link pasted anywhere previewed as bare text.
# This block emits one deterministic 1200x630 PNG per generated page and points that page's og:image and
# twitter:image at it. No external asset and no account: the typeface is Vera, which ships inside the
# reportlab package this build already uses for the PDF, and the card is drawn from the page's own title -
# never a hand-written string - so a page cannot have a card that contradicts it.
#
# Named deviation, not a silent one: reportlab's own raster backend (reportlab.graphics.renderPM) has no
# backend installed on this box - rlPyCairo and the _renderPM C extension are both absent, checked
# 2026-10-09 - so the layout is measured with reportlab's own font engine (pdfmetrics.stringWidth) and the
# raster is written by Pillow, which is installed. The output is a plain PNG: no metadata, no timestamp,
# byte-identical across rebuilds (built twice and diffed).
from PIL import Image, ImageDraw, ImageFont
import reportlab
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

_FONT_DIR = os.path.join(os.path.dirname(reportlab.__file__), "fonts")
VERA_TTF = os.path.join(_FONT_DIR, "Vera.ttf")
VERA_BD_TTF = os.path.join(_FONT_DIR, "VeraBd.ttf")
assert os.path.exists(VERA_TTF) and os.path.exists(VERA_BD_TTF), \
    "the Vera typeface that ships inside reportlab is missing from %s" % _FONT_DIR
pdfmetrics.registerFont(TTFont("Vera", VERA_TTF))
pdfmetrics.registerFont(TTFont("VeraBd", VERA_BD_TTF))

OG_W, OG_H = 1200, 630
OG_PAPER, OG_INK = (247, 244, 238), (22, 24, 29)
OG_MUTED, OG_ACCENT, OG_RULE = (122, 116, 104), (14, 107, 83), (222, 216, 205)
OG_DIR = os.path.join(ROOT, "og")


def _og_wrap(text, font_name, size, max_w, max_lines=None):
    """reportlab measures every line; the wrap is therefore the same engine that sets the PDF."""
    lines, cur = [], ""
    for word in text.split():
        trial = (cur + " " + word).strip()
        if cur and pdfmetrics.stringWidth(trial, font_name, size) > max_w:
            lines.append(cur)
            cur = word
        else:
            cur = trial
    if cur:
        lines.append(cur)
    if max_lines is not None and len(lines) > max_lines:
        lines = lines[:max_lines]
        lines[-1] = lines[-1].rstrip(",;: ") + "\u2026"
    return lines


def _og_card(title, out_path):
    """One deterministic share card. Nothing on it is typed here: the title comes off the page itself."""
    im = Image.new("RGB", (OG_W, OG_H), OG_PAPER)
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, 14, OG_H], fill=OG_ACCENT)
    d.rectangle([64, OG_H - 132, OG_W - 64, OG_H - 132], fill=OG_RULE)

    # Shrink the title until it sets in three lines; only then allow a fourth. A title is never cut short
    # while there is still room to set it smaller, so no card carries an ellipsis it did not have to.
    size = 78
    while size > 40 and len(_og_wrap(title, "VeraBd", size, OG_W - 180)) > 3:
        size -= 3
    lines = _og_wrap(title, "VeraBd", size, OG_W - 180, 4)
    f_title = ImageFont.truetype(VERA_BD_TTF, size)
    f_kick = ImageFont.truetype(VERA_TTF, 30)
    f_foot = ImageFont.truetype(VERA_TTF, 26)

    d.text((70, 76), "Commuter E-Bikes CA", font=f_kick, fill=OG_MUTED)
    y = 232
    for line in lines:
        d.text((70, y), line, font=f_title, fill=OG_INK)
        y += int(size * 1.22)
    d.text((70, OG_H - 104), "canada-ebike-compare \u00b7 every figure from a named source, dated",
           font=f_foot, fill=OG_MUTED)
    im.save(out_path, "PNG")


def _og_title_of(html_text):
    m = re.search(r"(?s)<title>(.*?)</title>", html_text)
    assert m, "a page with no <title> cannot have a share card"
    t = html.unescape(m.group(1)).strip()
    return re.sub(r"\s*\|\s*Commuter E-Bikes CA\s*$", "", t)


os.makedirs(OG_DIR, exist_ok=True)
OG_BY_PAGE = {}
for _path, _label in METRIC_PAGES:
    _seg = metric_segment(_path)
    _file = os.path.join(ROOT, _path, "index.html")
    _text = open(_file, encoding="utf-8").read()

    # 1. the card, from the page's own title
    _png = os.path.join(OG_DIR, "%s.png" % _seg)
    _og_card(_og_title_of(_text), _png)
    OG_BY_PAGE[_path] = _png

    # 2. the head. The page's own title, description and canonical are reused verbatim, and only the tags
    #    the page is missing are added - so nothing already on the page is rewritten or re-worded.
    _img_url = "%s/og/%s.png" % (SITE, _seg)
    _title = _og_title_of(_text)
    _desc_m = re.search(r'<meta name="description" content="(.*?)">', _text, re.S)
    _canon_m = re.search(r'<link rel="canonical" href="(.*?)">', _text)
    assert _desc_m, "%s: no description to build a social card from" % _file
    _desc = _desc_m.group(1)
    _canon = _canon_m.group(1) if _canon_m else ("%s/%s" % (SITE, (_path + "/") if _path else ""))
    _add = []
    for _tag, _want in (('property="og:type"', '<meta property="og:type" content="article">'),
                        ('property="og:site_name"', '<meta property="og:site_name" content="Commuter E-Bikes CA">'),
                        ('property="og:title"', '<meta property="og:title" content="%s">' % esc(_title)),
                        ('property="og:description"', '<meta property="og:description" content="%s">' % esc(_desc)),
                        ('property="og:url"', '<meta property="og:url" content="%s">' % esc(_canon)),
                        ('name="twitter:title"', '<meta name="twitter:title" content="%s">' % esc(_title)),
                        ('name="twitter:description"',
                         '<meta name="twitter:description" content="%s">' % esc(_desc))):
        if _tag not in _text:
            _add.append(_want)
    _add.append('<meta property="og:image" content="%s">' % esc(_img_url))
    _add.append('<meta property="og:image:alt" content="%s">' % esc(_title))
    _add.append('<meta name="twitter:image" content="%s">' % esc(_img_url))
    if 'name="twitter:card"' not in _text:
        _add.append('<meta name="twitter:card" content="summary_large_image">')
    else:
        _text = _text.replace('<meta name="twitter:card" content="summary">',
                              '<meta name="twitter:card" content="summary_large_image">', 1)
    assert "</head>" in _text, "%s has no </head> to place a social card in" % _file
    _text = _text.replace("</head>", "%s\n</head>" % "\n".join(_add), 1)
    open(_file, "w", encoding="utf-8").write(_text)

# 3. read every page back: the card it names must exist, be exactly one reference, and be a real 1200x630 PNG.
import struct
assert set(OG_BY_PAGE) == {p for p, _l in METRIC_PAGES}, "a page has no share card"
for _path, _label in METRIC_PAGES:
    _file = os.path.join(ROOT, _path, "index.html")
    _text = open(_file, encoding="utf-8").read()
    _seg = metric_segment(_path)
    _url = "%s/og/%s.png" % (SITE, _seg)
    for _attr in ('property="og:image"', 'name="twitter:image"'):
        assert _text.count('<meta %s content="%s">' % (_attr, esc(_url))) == 1, \
            "%s: %s is not exactly one reference to %s" % (_file, _attr, _url)
    assert 'content="summary_large_image"' in _text, "%s: twitter card is not the large one" % _file
    for _need in ('property="og:type"', 'property="og:site_name"', 'property="og:title"',
                  'property="og:description"', 'property="og:url"', 'property="og:image"',
                  'name="twitter:card"', 'name="twitter:title"', 'name="twitter:description"',
                  'name="twitter:image"'):
        assert _need in _text, "%s is missing %s after the share-card pass" % (_file, _need)
    _png = OG_BY_PAGE[_path]
    _raw = open(_png, "rb").read()
    assert _raw[:8] == b"\x89PNG\r\n\x1a\n", "%s is not a PNG" % _png
    assert struct.unpack(">II", _raw[16:24]) == (OG_W, OG_H), "%s is not %dx%d" % (_png, OG_W, OG_H)
    assert len(_raw) > 4000, "%s is a suspiciously empty PNG" % _png
print("share cards: %d pages, one %dx%d PNG each in og/, every page naming its own card and no other"
      % (len(METRIC_PAGES), OG_W, OG_H))
