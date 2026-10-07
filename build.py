#!/usr/bin/env python
# build.py — generates index.html and the decision-guide PDF from data/products.json.
# Render with:  py -3.10 build.py
import json, os, html

ROOT = os.path.dirname(os.path.abspath(__file__))
DATA = json.load(open(os.path.join(ROOT, "data", "products.json"), encoding="utf-8"))
PRODUCTS = DATA["products"]
BY_ID = {p["id"]: p for p in PRODUCTS}
CHECKED = DATA["checked_on"]

def esc(s):
    return html.escape(str(s), quote=True)

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
def model_cell(p):
    return ('<th scope="row" class="model">'
            f'<span class="mname">{esc(p["model"])}</span>'
            f'<span class="mmaker">{esc(p["maker"])}</span>'
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

ROWS = "\n".join(row_html(p) for p in PRODUCTS)

def pick_html(title, pid, body):
    p = BY_ID[pid]
    return (f'<article class="pick"><h3>{esc(title)}</h3>'
            f'<p class="pickwho">{esc(p["maker"])} {esc(p["model"])} &middot; {esc(p["price_display"])}</p>'
            f'<p>{esc(body)}</p></article>')

PICKS_HTML = "\n".join(pick_html(*pk) for pk in PICKS)

def source_html(p):
    return (f'<li><strong>{esc(p["maker"])} {esc(p["model"])}</strong> &mdash; '
            f'<a href="{esc(p["source_url"])}" target="_blank" rel="noopener nofollow">{esc(p["source_url"])}</a>'
            f'<br><span class="fn">{esc(p["source_note"])}</span></li>')

SOURCES_HTML = "\n".join(source_html(p) for p in PRODUCTS)

def detail_html(p):
    return (f'<article class="detail"><h3>{esc(p["maker"])} {esc(p["model"])} <span class="dprice">{esc(p["price_display"])}</span></h3>'
            f'<p>{esc(p["best_for"])}</p>'
            f'<p class="src">Source: <a href="{esc(p["source_url"])}" target="_blank" rel="noopener nofollow">{esc(p["maker"])} product page</a>, checked {esc(CHECKED)}.</p></article>')

DETAILS_HTML = "\n".join(detail_html(p) for p in PRODUCTS)

PAGE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
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
  td.price{font-variant-numeric:tabular-nums;font-weight:700;white-space:nowrap}
  .aff{display:block;font-size:11px;color:var(--muted);margin-top:4px;font-weight:400}
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
        <caption>Bikes listed cheapest to dearest. Specs read __CHECKED__; prices move, so confirm on the maker's page before you buy.</caption>
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
  <p>Built __CHECKED__ by the GAMMA-NATE project. Data: <a href="data/products.json">products.json</a>.</p>
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
    var live = cfg[affMap[id]];
    el.textContent = live ? "affiliate link" : "partner link pending approval";
  });
})();
</script>
</body>
</html>
"""

out = (PAGE
       .replace("__CHECKED__", esc(CHECKED))
       .replace("__DISCLOSURE__", esc(json.load(open(os.path.join(ROOT,"data","products.json"), encoding="utf-8"))["currency_note"]) + " " + "<strong>Disclosure:</strong> no live affiliate links yet; every product link goes to the maker's own site.")
       .replace("__PICKS__", PICKS_HTML)
       .replace("__ROWS__", ROWS)
       .replace("__DETAILS__", DETAILS_HTML)
       .replace("__SOURCES__", SOURCES_HTML))
open(os.path.join(ROOT, "index.html"), "w", encoding="utf-8").write(out)
print("wrote index.html")

# ================================================================ PDF
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
                        author="GAMMA-NATE")

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
    story.append(KeepTogether([
        Paragraph(title, H3),
        Paragraph("<font color='#0a5340'><b>%s %s &middot; %s</b></font>" % (p["maker"], p["model"], p["price_display"]), SMALL),
        Paragraph(body, BODY),
    ]))

story.append(PageBreak())
story.append(Paragraph("The comparison", H2))
story.append(Paragraph("Cheapest to dearest. Claimed range is the maker's estimate, not a test. Weight is the maker's figure. Where a maker does not publish a figure, the cell says so.", SMALL))
story.append(Spacer(1, 8))
hdr = ["Model", "Price\n(CAD)", "Motor", "Torque", "Battery", "Claimed\nrange", "Weight", "Brakes", "Class", "Warranty"]
rows = [[Paragraph(x.replace("\n", "<br/>"), CELLB) for x in hdr]]
for p in PRODUCTS:
    rows.append([
        Paragraph("<b>%s</b><br/><font size=7 color='#5d6270'>%s</font>" % (p["model"], p["maker"]), CELL),
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
for p in PRODUCTS:
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
for p in PRODUCTS:
    story.append(KeepTogether([
        Paragraph("<b>%s %s</b> - %s" % (p["maker"], p["model"], p["source_url"]), SMALL),
        Paragraph(p["source_note"], SMALL),
        Spacer(1, 5),
    ]))
story.append(Spacer(1, 8))
story.append(Paragraph("Two caveats worth naming. Claimed range is the maker's figure and depends on rider weight, hills, temperature and assist level. Weight is the maker's figure too. Where a maker does not publish a figure on the page we read, this guide says so rather than guessing. This is general product information, not advice about your riding or your province's e-bike rules - check those before you buy.", NOTE))

doc.build(story, onFirstPage=footer, onLaterPages=footer)
print("wrote", PDF)
