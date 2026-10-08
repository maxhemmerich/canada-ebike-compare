/* GAMMA site config.
 * Affiliate destinations live here as ONE NAMED CONSTANT PER PRODUCT.
 * Every value is null on purpose: no affiliate tracking link exists yet, so no button
 * on the site may point at a live paying link. When a real tracking link exists, set the
 * matching constant to it and the row labels itself "affiliate link".
 * While a constant is null the row renders nothing extra — the disclosure above the fold
 * already covers the absence, and nothing here asserts the status of any application.
 */
window.GAMMA_CONFIG = {
  updated: "2026-10-07",
  // Shown above the fold on the page. Keep it true.
  disclosure: "Disclosure: this page has no live affiliate links yet. Nothing here is paid for and no purchase through this page earns anyone a commission today. Every product link below goes to the maker's own website. If partner links go live, this box will say which ones are affiliate links.",

  // One constant per product. null = no tracking link configured; not live.
  AFFILIATE_RADSTER_ROAD: null,     // Rad Power Bikes - affiliate program application required
  AFFILIATE_RADKICK_7SPEED: null,   // Rad Power Bikes - affiliate program application required
  AFFILIATE_VELOTRIC_TEMPO: null,   // Velotric Canada - 7% via Impact (velotric.ca/pages/affiliate)
  AFFILIATE_VELOTRIC_DISCOVER_3: null, // Velotric Canada - 7% via Impact
  AFFILIATE_SURFACE604_ROOK: null,  // Surface 604 - direct program enquiry required

  products: {
    "radster-road":        { name: "Radster Road",       maker: "Rad Power Bikes", status: "not live" },
    "radkick-7speed":      { name: "RadKick 7-Speed",    maker: "Rad Power Bikes", status: "not live" },
    "velotric-tempo":      { name: "Tempo",              maker: "Velotric",        status: "not live" },
    "velotric-discover-3": { name: "Discover 3",         maker: "Velotric",        status: "not live" },
    "surface604-rook":     { name: "Rook",               maker: "Surface 604",     status: "not live" }
  }
};
