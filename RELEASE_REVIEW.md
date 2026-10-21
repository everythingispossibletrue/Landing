# Release review — 21 October 2026

The current SEO release supersedes the previous two-file upload. Deploy **all files and subdirectories in `dist/`**, or extract `waymark-production.zip` at the web root. Keep the `en/` and `kk/` directories. No package installation or server-side build is needed for static hosting.

The site includes Russian `/`, English `/en/`, Kazakh `/kk/`, shared CSS/JS, the hero JPEG, SVG favicon, robots.txt and sitemap.xml. Old language query links remain supported through JavaScript.

Source: readable HTML in `src/pages/`, shared CSS/JS in `src/`, and `scripts/build-seo.py`. See `README.md` for file roles and commands. Build with `python3 scripts/build-seo.py`. The default canonical origin is the existing Sites URL; set `SITE_URL` when publishing to a different domain.

See [SEO_REVIEW.md](SEO_REVIEW.md) for completed SEO work, verification and the explicit private-access constraint. Local structural/HTTP checks and jsdom interaction checks pass; rendered browser QA and performance scores remain unverified because no browser was available.

Subsequent local bug fixes and verification are documented in [CODE_REVIEW.md](CODE_REVIEW.md). The production archive includes these fixes. Updating the GitHub source repository does not deploy this revision to Sites; Sites hosting remains unchanged.
