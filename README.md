# Canadian Commuter E-Bike Comparison

A comparison page for seven commuter e-bikes you can buy in Canada, one indexable page per model,
and a free decision-guide PDF. Built as a static site (no framework, no build step at runtime) so
it loads fast and can be linked to.

Live: https://maxhemmerich.github.io/canada-ebike-compare/

## The rule this site follows

**Every product fact on the page comes from the maker's own published material** — their
product page or spec sheet — and the page says which page each number came from. Nothing is
written from memory, and no figure is estimated by us. Where a maker does not publish a
figure, the table says "not stated" rather than guessing.

- Source of truth: `data/products.json` (each product carries its `source_url` and a note on
  what was read).
- `build.py` renders `index.html`, the per-model pages, the **range picker**, the **decision guide as a
  page** (`guide/index.html`) and `guide/canada-commuter-ebike-guide.pdf` from that one file, so no two
  of them can disagree.
- Nothing on a per-model page is written by hand either: its title, description, canonical URL and
  every specification row are generated from the same record. A figure a maker does not publish is
  absent from the row list rather than guessed.

## Honesty / disclosure

There are **no live affiliate links on this site**. The affiliate destinations are declared in
`config.js` as one named constant per product, and every one is `null`. Every product link goes
to the maker's own website, unmonetised; a row is labelled "affiliate link" only when its
constant holds a real tracking link. If paid partner links are ever added, they will be
labelled as such.

Two models added later (Aventon Soltera 2.5, OHM Cruise 3) deliberately have **no** constant at
all — the program that would cover each one is named in the comment block of `config.js` and
nowhere else, and no account has been applied for. Adding a model is a catalogue decision, not an
affiliate one.

Availability is carried as an `availability` field on the product and is rendered in the bike's
comparison row wherever it is present — three models carry one today (the Rook, "Out of stock when
checked"; the Soltera 2.5, "Limited stock when checked"; the Cruise 3, "In stock when checked"), each
in the maker's own words or from the maker's own cart state. A product whose stock we did not observe
gets no badge, never an invented "in stock".

## The range picker

`how-far/` answers the query a buyer actually types — *"how big a battery do I need for a 14 km
commute"* — instead of presenting another spec sheet. The visitor enters a round-trip distance and
ticks a box for a hilly route or a load; the page then lists which of the bikes claims to cover
it, in two buckets: those covered on the maker's **highest published figure**, and those covered only
on that figure where the maker publishes no lower one.

It invents nothing. Each model has two numbers, both taken from the `range` string already in
`data/products.json`, and `build.py` asserts at the top of every run that each number appears
literally in that string — a drifted figure stops the build before a single file is written. There is
no derating factor: no maker here publishes a hills figure, so the hills box changes *which* published
figure you are measured against (the maker's own low end, where one exists) rather than applying a
percentage of our own making. The conversions are named on the page (the Discover 3's 65 mi throttle
figure, and the Soltera 2.5's 46 mi range, which the maker publishes in miles only). The whole table of
figures, quoted verbatim, is on the page for the reader to check.

## The decision guide, as a page and as a PDF

`guide/` is the guide itself — the free front-door document a writer or a forum can link to. It is
generated from the **same source objects** as the PDF (`GUIDE_TITLE`, `GUIDE_INTRO`,
`GUIDE_TABLE`, the `PICKS` verdicts, `DETAILS_HTML`, `SOURCES_HTML`), so the two cannot drift: the
one-line verdicts, the comparison table, the household section and the sources list are one
definition each, rendered twice.

That claim is checked, not asserted. After the PDF is written, `build.py` reads its **text layer**
back and requires every figure, heading, note and verdict the page carries to be present in it
(whitespace-normalised, because reportlab wraps lines); it then extracts every *number* from the
page's own text and requires each one to appear in the PDF as well. A figure typed onto the page and
not into the guide stops the build. The page also carries its own `<title>`, meta description,
canonical URL and Open Graph / Twitter card, is linked from the comparison page and the range
picker, and is listed in `sitemap.xml`.

**No affiliate element is emitted on it at all** — no `config.js`, no `.aff` element — and it
repeats the disclosure.

## Measuring whether anyone is reading it

This site counts its own page views, anonymously, with **no account and no analytics product**. Every
generated page carries a few lines of script that fire one increment per page load, and `stats/` reads
every counter back and shows it.

- Counter service: [Abacus](https://abacus.jasoncameron.dev) — free, no signup, no key, CORS-enabled.
  `GET /hit/<namespace>/<key>` increments and answers `{"value": N}`; `GET /get/<namespace>/<key>` reads
  without incrementing. Namespace `maxhemmerich.github.io`, one key per page
  (`canada-ebike-compare-<page>`).
- **Nothing visitor-identifying is sent**: no cookie (`credentials: omit`), no referring page
  (`referrerPolicy: no-referrer`), no identifier of any kind. The counter names the page. As with any
  HTTP request the service necessarily sees the requesting IP address; nothing else leaves the page.
- What it counts is **page loads that ran JavaScript**. A visitor with scripting off is not counted, and
  a crawler that renders pages is. The number is a floor, not a census, and `stats/` says so.
- `build.py` owns all of it: every page is written through one `write_page()` call that inserts the
  beacon, and the build then reads each generated page back off disk and asserts its beacon key matches
  the key its row on `stats/` will fetch, that no page is left carrying an unsubstituted `__TOKEN__`,
  and that `sitemap.xml` and the page list are the same set of URLs. A drifted key, a missing page or a
  page with two beacons stops the build before `sitemap.xml` is written.
- Every row on `stats/` reads its own real key: the build asserts the list of keys the page will fetch
  is exactly the list of beacons the pages fire, and that the page carries no `<key>`-style placeholder.
- The reader fetches its counters **one at a time**, about 2.5 a second, and waits out a `429` instead of
  reporting a dead counter. That is a repair, not a precaution: fired in parallel, a second look at the
  page inside the service's 30-reads-per-10-seconds window made 9 to 10 of the 15 rows read "unavailable"
  on the live page, measured twice before the change.

## Telling crawlers the pages exist

`indexnow.py` posts every URL in the generated `sitemap.xml` to `https://api.indexnow.org/indexnow`,
which feeds Bing and the other engines that share the IndexNow protocol. It needs no account. The key
file lives inside this project's own subpath (`<key>.txt`, generated from `indexnow.key`) and the POST
body points at it with `keyLocation`, which is what IndexNow allows for a site on a host root we do not
own. Run it after a push:

```
py -3.10 indexnow.py --dry-run   # print the payload only
py -3.10 indexnow.py             # POST it and print the literal HTTP response
```

## Rebuilding

```
py -3.10 build.py        # regenerates every page below from data/products.json
```

Requires `reportlab` (for the PDF) and `pypdf` (which reads that PDF's text back to prove the guide page
and the PDF carry the same figures). The pages are plain HTML/CSS/JS.

## Layout

- `index.html` — generated; the comparison page
- `bikes/<model>/index.html` — generated; one page per model, with its own title, meta description
  and canonical URL, built from the same dataset and linking back to the comparison
- `how-far/index.html` — generated; the range picker, reading the published range figures from the
  same dataset and quoting them in full on the page
- `vs/<a>-vs-<b>/index.html` — generated; one head-to-head page per pair in `build.py`'s `PAIRS` list,
  two columns drawn from the same dataset, linked from the comparison page and from both models' own
  pages, and carrying no affiliate element of any kind
- `stats/index.html` — generated; reads every page counter back from the counting service and shows
  the counts, with its own title, description and canonical URL. Linked from the comparison page footer
- `guide/index.html` — generated; the decision guide as an indexable page, from the same source as the
  PDF, with its own title, description, canonical URL and social card, and no affiliate element
- `sitemap.xml` — generated; the twenty indexable URLs (the comparison, the seven bikes, the range
  picker, the decision guide, `commute-costs/`, `gear/`, `rules/`, `trails/`, `stats/` and the five
  head-to-head pages)
- `commute-costs/index.html` — generated; what a commute costs per year by e-bike, car and transit, in
  seven cities, every figure substituted from a named source
- `gear/index.html`, `rules/index.html`, `trails/index.html` — generated; gear checklists and each
  bike's load rating, the Canadian class and province rules, and the land managers' own trail rules.
  Each quotes a named authority's own words and carries no affiliate element of any kind
- `feed.xml` — generated; an RSS 2.0 status feed, one item per model with its price and availability
- `og/*.png` — generated; one 1200×630 social card per page, drawn from that page's own title
- `indexnow.py` + `indexnow.key` + `<key>.txt` — the sitemap-submission script, its key, and the
  hosted key file IndexNow verifies
- `robots.txt` — generated; note it is ignored by crawlers here, because this site sits on a
  subpath of `maxhemmerich.github.io` and only the robots.txt at the host root is read
- `config.js` — affiliate placeholder constants + the on-page disclosure text
- `data/products.json` — the sourced dataset (single source of truth)
- `build.py` — generator
- `linkgate.py` — the link gate `build.py` runs last. It reads every generated page back off disk and
  resolves every reference the page carries against the tree — literal `href`/`src`, every `srcset`
  candidate, the `og:image`/`twitter:image` share card, `<link rel="canonical">` (which must name the
  page it sits on), and every `url`/`@id` inside a JSON data block — and stops the build on any that
  does not land. Run it on its own against any tree: `py -3.10 linkgate.py <root> <site-url>`
- `guide/canada-commuter-ebike-guide.pdf` — the decision guide (5 pages)

The per-model pages offer a partner button **only** when that bike's constant in `config.js` holds a
real tracking link; while the constant is `null` the element is removed, so the page carries no link
and asserts nothing about any application.
