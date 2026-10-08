# Canadian Commuter E-Bike Comparison

A single page that compares five commuter e-bikes you can buy in Canada, plus a free
decision-guide PDF. Built as a static site (no framework, no build step at runtime) so it
loads fast and can be linked to.

Live: https://maxhemmerich.github.io/canada-ebike-compare/

## The rule this site follows

**Every product fact on the page comes from the maker's own published material** — their
product page or spec sheet — and the page says which page each number came from. Nothing is
written from memory, and no figure is estimated by us. Where a maker does not publish a
figure, the table says "not stated" rather than guessing.

- Source of truth: `data/products.json` (each product carries its `source_url` and a note on
  what was read).
- `build.py` renders `index.html` **and** `guide/canada-commuter-ebike-guide.pdf` from that one
  file, so the page and the PDF can never disagree.

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

## Rebuilding

```
py -3.10 build.py        # regenerates index.html and the PDF from data/products.json
```

Requires `reportlab` (PDF) only. The page is plain HTML/CSS/JS.

## Layout

- `index.html` — generated; the page
- `config.js` — affiliate placeholder constants + the on-page disclosure text
- `data/products.json` — the sourced dataset (single source of truth)
- `build.py` — generator
- `guide/canada-commuter-ebike-guide.pdf` — the decision guide (4 pages)
