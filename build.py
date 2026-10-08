#!/usr/bin/env python
# build.py — generates index.html and the decision-guide PDF from data/products.json.
# Render with:  py -3.10 build.py
import json, os, html, re

ROOT = os.path.dirname(os.path.abspath(__file__))
DATA = json.load(open(os.path.join(ROOT, "data", "products.json"), encoding="utf-8"))
PRODUCTS = DATA["products"]
BY_ID = {p["id"]: p for p in PRODUCTS}
CHECKED = DATA["checked_on"]

# ---------------------------------------------------------------- order
# ONE deterministic order for every list of the five bikes, on the page and in the PDF.
# The table caption promises cheapest-to-dearest, so sort by price ascending. Three models
# tie at CA$2,699, so ties break by model name A-Z and then by id: the same data always
# builds the identical page (no reliance on the order rows happen to sit in products.json).
ORDER = sorted(PRODUCTS, key=lambda p: (p["price_cad"], p["model"].lower(), p["id"]))
TIE_NOTE = "equal-price bikes A-Z"

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
        high=129, low=105, low_label="throttle only, from the maker's 65 mi figure",
        high_from='the maker\'s published pedal-assist figure "80 mi / ~129 km PAS (65 mi throttle)"',
        low_from='the maker\'s published throttle-only figure "65 mi", converted to km (1 mi = 1.609344 km)'),
    "surface604-rook": dict(
        high=150, low=None, low_label=None,
        high_from='the maker\'s single published figure "up to 150 km (maker, eco mode)"',
        low_from=None),
}
_RANGE_TOKENS = {"radster-road": ("104", "40"), "radkick-7speed": ("56", "24"),
                 "velotric-tempo": ("97",), "velotric-discover-3": ("129", "65"),
                 "surface604-rook": ("150",)}
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
     "At 39 lb the Tempo is 16 lb lighter than anything else here, and light enough to ride with the motor off. The 374 Wh battery is the trade-off."),
    ("The longest commute on one charge",
     "surface604-rook",
     "The Rook carries the biggest battery here (960 Wh) and claims the longest range of the five: up to 150 km in eco. It is also the only bike here that ships at Class 3."),
    ("The best all-round daily commuter",
     "velotric-discover-3",
     "750 W of motor, a 730 Wh battery and ~129 km of claimed pedal assist, with lights, fenders and a rack included. The most complete package of the five."),
    ("The cheapest way in, without buying a toy",
     "radkick-7speed",
     "At CA$1,899 the RadKick 7-Speed is the lowest price here and still has hydraulic brakes and a rear rack. Its 360 Wh battery is the honest limit: short trips only."),
    ("A bike that feels like a bike, on a long mixed commute",
     "radster-road",
     "The Radster Road pairs a torque sensor with a 100 Nm motor, so the assist follows your pedalling instead of pushing you. It is the heaviest of the five."),
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
<meta name="description" content="Five commuter e-bikes you can buy in Canada for CA$1,899-CA$2,699, compared on price, motor, battery, range, weight and warranty, with every spec traced to the maker's own product page.">
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
    <h1>Five commuter e-bikes you can buy in Canada, sorted out</h1>
    <p class="deck">CA$1,899 to CA$2,699. Real specs from each maker's own product page, so you can tell which bike fits a real commute instead of a spec sheet.</p>
    <div class="cta">
      <a class="btn" href="guide/canada-commuter-ebike-guide.pdf" download>Download the free PDF guide</a>
      <a class="btn ghost" href="#compare">Compare the five</a>
      <a class="btn ghost" href="how-far/">How far will it go?</a>
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
    <p class="sub">The decision guide, in full. The same pages are in the free PDF.</p>
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
  <p>Built __CHECKED__ by the GAMMA project. Data: <a href="data/products.json">products.json</a>.</p>
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
       .replace("__DISCLOSURE__", esc(json.load(open(os.path.join(ROOT,"data","products.json"), encoding="utf-8"))["currency_note"]) + " " + "<strong>Disclosure:</strong> no live affiliate links yet; every product link goes to the maker's own site.")
       .replace("__PICKS__", PICKS_HTML)
       .replace("__ROWS__", ROWS)
       .replace("__DETAILS__", DETAILS_HTML)
       .replace("__PAIRS__", PAIR_CARDS)
       .replace("__SOURCES__", SOURCES_HTML))
open(os.path.join(ROOT, "index.html"), "w", encoding="utf-8").write(out)
print("wrote index.html")

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
    <p class="crumb"><a href="../../">All five commuter e-bikes, compared</a> &rsaquo; __MAKER__</p>
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
      <a class="btn" href="../../#compare">Compare all five side by side</a>
      <a class="btn ghost" href="../../guide/canada-commuter-ebike-guide.pdf" download>Download the free PDF guide</a>
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
  <p>Built __CHECKED__ by the GAMMA project. Data: <a href="../../data/products.json">products.json</a> &middot; <a href="../../">the comparison</a>.</p>
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
    d = os.path.join(ROOT, "bikes", p["id"])
    os.makedirs(d, exist_ok=True)
    open(os.path.join(d, "index.html"), "w", encoding="utf-8").write(bike_html(p))
    print("wrote bikes/%s/index.html" % p["id"])

# ================================================================ "how far will it go" range picker
# The one page here that answers a question instead of listing a spec sheet: a buyer types a round-trip
# distance and sees which of the five bikes claims to cover it, from the sourced figures already in
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
<meta name="description" content="How big a battery do you need for a 14 km commute? Enter your round-trip distance and see which of five Canadian commuter e-bikes claims to cover it, using each maker's own published range figure.">
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
    <p class="crumb"><a href="../">All five commuter e-bikes, compared</a> &rsaquo; Range picker</p>
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
      <li><strong>One conversion, named.</strong> The Discover 3's lowest figure is published in miles (65 mi) and is shown here converted to kilometres.</li>
      <li><strong>Battery size is the whole story only sometimes.</strong> The Wh figure above is the maker's published capacity; two bikes can post the same miles from different Wh once weight and assist level are counted in.</li>
    </ol>
  </section>

  <section id="next">
    <h2>Read the rest</h2>
    <ul class="otherbikes">
      <li><a href="../">All five commuter e-bikes, compared side by side</a></li>
      __BIKELINKS__
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
        ? "All five bikes claim to cover a " + dShow + " km round trip on the highest figure their maker publishes."
        : cover.length + " of the 5 bikes claim to cover a " + dShow + " km round trip on the highest figure their maker publishes; "
          + short.length + (short.length === 1 ? " does not." : " do not.");
    } else {
      sum.textContent = "Hills on: " + cover.length + " of the 5 claim to cover a " + dShow
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
               .replace("__CANONICAL__", "%s/how-far/" % SITE)
               .replace("__CHECKED__", esc(CHECKED))
               .replace("__FIGROWS__", FIG_ROWS)
               .replace("__BIKELINKS__", BIKE_LINKS)
               .replace("__PICKERDATA__", PICKER_DATA))
os.makedirs(os.path.join(ROOT, "how-far"), exist_ok=True)
open(os.path.join(ROOT, "how-far", "index.html"), "w", encoding="utf-8").write(_picker_out)
print("wrote how-far/index.html")

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
    <p class="crumb"><a href="../../">All five commuter e-bikes, compared</a> &rsaquo; Head to head</p>
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
    links = ['<li><a href="../../">All five commuter e-bikes, compared side by side</a></li>']
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
    d = os.path.join(ROOT, "vs", slug)
    os.makedirs(d, exist_ok=True)
    open(os.path.join(d, "index.html"), "w", encoding="utf-8").write(out)
    print("wrote vs/%s/index.html" % slug)

for _pa, _pb in PAIRS:
    vs_page(_pa, _pb)

# ---------------------------------------------------------------- sitemap + robots
URLS = (["%s/" % SITE] + ["%s/bikes/%s/" % (SITE, p["id"]) for p in ORDER]
        + ["%s/how-far/" % SITE] + ["%s/vs/%s/" % (SITE, s) for s in PAIR_SLUGS])
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
story.append(Paragraph("Canadian commuter e-bikes, sorted out", H1))
story.append(Paragraph("Five bikes you can buy in Canada for CA$1,899 to CA$2,699. Every figure in this guide was read from the maker's own product page on %s - no remembered specs. Prices move, so confirm before you buy." % CHECKED, BODY))
story.append(Spacer(1, 10))
story.append(Paragraph("<b>Disclosure:</b> this guide was not paid for and carries no live affiliate links. Product names link to the makers' own pages. If paid partner links are ever added, they will be labelled as such.", SMALL))
story.append(Spacer(1, 6))
story.append(Paragraph("Which one, in one line each", H2))
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

story.append(PageBreak())
story.append(Paragraph("The comparison", H2))
story.append(Paragraph("Cheapest to dearest; %s. Claimed range is the maker's estimate, not a test. Weight is the maker's figure. Where a maker does not publish a figure, the cell says so." % TIE_NOTE, SMALL))
story.append(Spacer(1, 8))
hdr = ["Model", "Price\n(CAD)", "Motor", "Torque", "Battery", "Claimed\nrange", "Weight", "Brakes", "Class", "Warranty"]
rows = [[Paragraph(x.replace("\n", "<br/>"), CELLB) for x in hdr]]
for p in ORDER:
    modelcell = "<b>%s</b><br/><font size=7 color='#5d6270'>%s</font>" % (p["model"], p["maker"])
    if p.get("availability"):
        modelcell += "<br/><font size=7 color='#a6550c'><b>%s</b></font>" % p["availability"]
    rows.append([
        Paragraph(modelcell, CELL),
        Paragraph("<b>%s</b>" % p["price_display"], CELL),
        Paragraph(p["motor"], CELL), Paragraph(p["torque"], CELL), Paragraph(p["battery"], CELL),
        Paragraph(p["range"], CELL), Paragraph(p["weight"], CELL), Paragraph(p["brakes"], CELL),
        Paragraph(p["eclass"], CELL), Paragraph(p["warranty"], CELL),
    ])
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
story.append(Paragraph("Cheapest is not the same as best value: the RadKick costs the least but carries the smallest battery. Match the battery to your round-trip distance, not the price tag.", NOTE))

story.append(PageBreak())
story.append(Paragraph("Which one for which household", H2))
for p in ORDER:
    story.append(KeepTogether([
        Paragraph("%s %s &nbsp;&middot;&nbsp; %s" % (p["maker"], p["model"], p["price_display"]), H3),
        Paragraph(p["best_for"], BODY),
        Paragraph("Source: %s (checked %s)." % (p["source_url"], CHECKED), SMALL),
        Spacer(1, 6),
    ]))

story.append(PageBreak())
story.append(Paragraph("Where every number comes from", H2))
story.append(Paragraph("Each bike below links to the exact page the figures were read from, on %s." % CHECKED, BODY))
story.append(Spacer(1, 6))
for p in ORDER:
    story.append(KeepTogether([
        Paragraph("<b>%s %s</b> - %s" % (p["maker"], p["model"], p["source_url"]), SMALL),
        Paragraph(p["source_note"], SMALL),
        Spacer(1, 5),
    ]))
story.append(Spacer(1, 8))
story.append(Paragraph("Two caveats worth naming. Claimed range is the maker's figure and depends on rider weight, hills, temperature and assist level. Weight is the maker's figure too. Where a maker does not publish a figure on the page we read, this guide says so rather than guessing. This is general product information, not advice about your riding or your province's e-bike rules - check those before you buy.", NOTE))

doc.build(story, onFirstPage=footer, onLaterPages=footer)
print("wrote", PDF)
