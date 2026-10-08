# Canadian Commuter E-Bike Comparison

A comparison page for five commuter e-bikes you can buy in Canada, one indexable page per model,
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
- `build.py` renders `index.html`, the five per-model pages, the **range picker** and
  `guide/canada-commuter-ebike-guide.pdf` from that one file, so no two of them can disagree.
- Nothing on a per-model page is written by hand either: its title, description, canonical URL and
  every specification row are generated from the same record. A figure a maker does not publish is
  absent from the row list rather than guessed.

## Honesty / disclosure

There are **no live affiliate links on this site**. The affiliate destinations are declared in
`config.js` as one named constant per product, and every one is `null`. Every product link goes
to the maker's own website, unmonetised; a row is labelled "affiliate link" only when its
constant holds a real tracking link. If paid partner links are ever added, they will be
labelled as such.

Availability is carried as an `availability` field on the product (currently set only for the
Rook, which showed out of stock on the date checked) and is rendered in the bike's comparison
row wherever it is present — a product whose stock we did not observe gets no badge, never an
invented "in stock".

## The range picker

`how-far/` answers the query a buyer actually types — *"how big a battery do I need for a 14 km
commute"* — instead of presenting another spec sheet. The visitor enters a round-trip distance and
ticks a box for a hilly route or a load; the page then lists which of the five bikes claims to cover
it, in two buckets: those covered on the maker's **highest published figure**, and those covered only
on that figure where the maker publishes no lower one.

It invents nothing. Each model has two numbers, both taken from the `range` string already in
`data/products.json`, and `build.py` asserts at the top of every run that each number appears
literally in that string — a drifted figure stops the build before a single file is written. There is
no derating factor: no maker here publishes a hills figure, so the hills box changes *which* published
figure you are measured against (the maker's own low end, where one exists) rather than applying a
percentage of our own making. The one conversion is named on the page (the Discover 3's 65 mi
throttle figure). The whole table of figures, quoted verbatim, is on the page for the reader to check.

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

Requires `reportlab` (PDF) only. The pages are plain HTML/CSS/JS.

## Layout

- `index.html` — generated; the comparison page
- `bikes/<model>/index.html` — generated; one page per model, with its own title, meta description
  and canonical URL, built from the same dataset and linking back to the comparison
- `how-far/index.html` — generated; the range picker, reading the published range figures from the
  same dataset and quoting them in full on the page
- `sitemap.xml` — generated; the seven indexable URLs (the comparison, the five bikes and the picker)
- `indexnow.py` + `indexnow.key` + `<key>.txt` — the sitemap-submission script, its key, and the
  hosted key file IndexNow verifies
- `robots.txt` — generated; note it is ignored by crawlers here, because this site sits on a
  subpath of `maxhemmerich.github.io` and only the robots.txt at the host root is read
- `config.js` — affiliate placeholder constants + the on-page disclosure text
- `data/products.json` — the sourced dataset (single source of truth)
- `build.py` — generator
- `guide/canada-commuter-ebike-guide.pdf` — the decision guide (4 pages)

The per-model pages offer a partner button **only** when that bike's constant in `config.js` holds a
real tracking link; while the constant is `null` the element is removed, so the page carries no link
and asserts nothing about any application.
