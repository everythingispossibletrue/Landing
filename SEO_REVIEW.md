# SEO review — 21 October 2026

Implemented for `https://waymark-darya-career.shrewdstork3.chatgpt.site/`.

## Completed

- Crawlable, fully rendered Russian `/`, English `/en/` and Kazakh `/kk/` pages. Each contains its language's text, title, description, structured data and one H1 in the initial HTML.
- Self-referencing canonical URLs and reciprocal RU/EN/KK/x-default hreflang links, also declared in the sitemap.
- Real language links work without JavaScript. Old `?lang=en` and `?lang=kk` bookmarks redirect through JavaScript to the corresponding static paths.
- Titles, descriptions and visible service headings describe career consulting, Almaty/online delivery, HR consulting and recruitment. No invented credentials, reviews or keyword stuffing.
- JSON-LD graph connects the actual consultant, website, page, service catalog, five career services and five business services. Prices are included only where shown in the page. No fabricated business address, ratings or unsupported rich-result claims.
- Robots.txt, sitemap.xml, Open Graph/Twitter metadata and an SVG favicon included in the deployment and production ZIP.
- Shared CSS and deferred JavaScript replace inline duplication. Hero image retains explicit dimensions, high fetch priority and preload; its empty HTML alt is appropriate for a decorative illustration.
- Anonymous request returned HTTP 403. Existing owner-only access is intentionally retained at the user's explicit request. Indexing remains blocked by access control despite the indexable page markup.

## Validation

- `python3 scripts/check-seo.py` with `python3 -m http.server 4173 --bind 127.0.0.1 --directory dist` running: all three pages, unique IDs, anchors, assets, language, H1, metadata, canonical, hreflang, service counts, sitemap, robots, ZIP and ten HTTP routes pass.
- `node --check dist/site.js`: passes.
- jsdom: CSS parsing and runtime on RU/EN/KK, language links, menu open/close, Escape, outside click, business navigation and structured data pass.
- Browser runtime returned no available browsers. No rendered screenshots, Lighthouse/PageSpeed scores or Core Web Vitals measurements were obtained.
- No Search Console submission, ownership verification, ranking or actual indexation is claimed.

## Maintaining the site

Edit `src/site.html` for retained content/design or `scripts/build-seo.py` for SEO metadata and page generation. Run `python3 scripts/build-seo.py` to regenerate `dist/` and `waymark-production.zip`. Deploy the entire contents of `dist/`, retaining `en/` and `kk/` subdirectories; the old two-file deployment instructions no longer apply.

When moving to a different public origin, run `SITE_URL=https://your-domain.example python3 scripts/build-seo.py`, update the check's BASE, and rebuild before upload. When public access is desired, verify anonymous HTTP 200 and absence of server-level noindex restrictions, then verify the actual public domain in Search Console and submit its sitemap. Access stays private until explicitly changed.

## References

- [Google Search Essentials](https://developers.google.com/search/docs/essentials)
- [Localized versions](https://developers.google.com/search/docs/specialty/international/localized-versions)
- [JavaScript SEO](https://developers.google.com/search/docs/crawling-indexing/javascript/javascript-seo-basics)
- [Sitemaps](https://developers.google.com/search/docs/crawling-indexing/sitemaps/build-sitemap)
