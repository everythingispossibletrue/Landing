"""Check generated pages, SEO files, and the deployment archive.

The default checks read files from disk. Add --base-url to also check routes
served by a local preview or a deployed site.

Canonical URLs come from src/site-config.json. SITE_URL overrides the origin,
matching the build script's behavior when using a custom domain.
"""

from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import sys
from urllib.parse import quote, unquote, urljoin, urlsplit
from urllib.request import urlopen
from xml.etree import ElementTree
from zipfile import BadZipFile, ZipFile

from html_document import parse_html
from site_config import load_config as load_site_config


PROJECT_ROOT = Path(__file__).resolve().parent.parent
SITEMAP_NAMESPACE = "{http://www.sitemaps.org/schemas/sitemap/0.9}"
XHTML_NAMESPACE = "{http://www.w3.org/1999/xhtml}"


class CheckError(Exception):
    """A generated file does not satisfy a site requirement."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CheckError(message)


@dataclass
class SiteConfig:
    site_url: str
    locale_paths: dict[str, str]

    @property
    def alternate_urls(self) -> dict[str, str]:
        urls = {
            language: urljoin(self.site_url, path)
            for language, path in self.locale_paths.items()
        }
        return {**urls, "x-default": urls["ru"]}


def load_config() -> SiteConfig:
    data = load_site_config()
    locale_paths = {
        language: metadata["path"]
        for language, metadata in data["locales"].items()
    }
    return SiteConfig(data["site_url"], locale_paths)


class PageParser(HTMLParser):
    """Collect element attributes and complete JSON-LD script contents."""

    def __init__(self, html: str):
        super().__init__()
        self.tags: list[tuple[str, dict[str, str | None]]] = []
        self.schema_scripts: list[str] = []
        self._schema_parts: list[str] | None = None
        self.document = parse_html(html)
        self.feed(html)
        self.close()

    def handle_starttag(self, tag: str, attributes: list[tuple[str, str | None]]) -> None:
        attribute_map = dict(attributes)
        self.tags.append((tag, attribute_map))
        if tag == "script" and attribute_map.get("type") == "application/ld+json":
            self._schema_parts = []

    def handle_data(self, data: str) -> None:
        if self._schema_parts is not None:
            self._schema_parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "script" and self._schema_parts is not None:
            self.schema_scripts.append("".join(self._schema_parts))
            self._schema_parts = None

    def elements(self, tag: str) -> list[dict[str, str | None]]:
        return [attributes for name, attributes in self.tags if name == tag]

    @property
    def ids(self) -> list[str]:
        return [attributes["id"] for _, attributes in self.tags if attributes.get("id")]


def check_metadata(page: PageParser, language: str, config: SiteConfig) -> None:
    label = f"{language}:"
    html_elements = page.elements("html")
    require(
        len(html_elements) == 1 and html_elements[0].get("lang") == language,
        f"{label} expected one <html lang='{language}'> element.",
    )
    for element_name in ("title", "h1"):
        elements = list(page.document.find_all(element_name))
        require(
            len(elements) == 1 and bool(elements[0].text),
            f"{label} expected one nonempty {element_name.upper()}.",
        )

    descriptions = [tag for tag in page.elements("meta") if tag.get("name") == "description"]
    require(
        len(descriptions) == 1 and bool(descriptions[0].get("content")),
        f"{label} expected one nonempty meta description.",
    )
    for meta in page.elements("meta"):
        if (meta.get("name") or "").lower() in {"robots", "googlebot", "bingbot"}:
            directives = set(re.split(r"[\s,]+", (meta.get("content") or "").lower()))
            require(
                not directives.intersection({"noindex", "none"}),
                f"{label} meta {meta['name']} prevents indexing.",
            )
    canonical_links = [tag for tag in page.elements("link") if tag.get("rel") == "canonical"]
    expected_url = config.alternate_urls[language]
    require(
        len(canonical_links) == 1 and canonical_links[0].get("href") == expected_url,
        f"{label} canonical URL must be {expected_url}.",
    )

    alternate_links = [tag for tag in page.elements("link") if tag.get("rel") == "alternate"]
    alternates = {tag.get("hreflang"): tag.get("href") for tag in alternate_links}
    require(
        len(alternate_links) == len(config.alternate_urls)
        and alternates == config.alternate_urls,
        f"{label} hreflang links must match all configured locales and x-default.",
    )

    language_links = [tag for tag in page.elements("a") if tag.get("data-lang")]
    require(
        len(language_links) == len(config.locale_paths)
        and {tag["data-lang"] for tag in language_links} == set(config.locale_paths),
        f"{label} language navigation must contain one link per locale.",
    )
    for link in language_links:
        target_language = link["data-lang"]
        require(
            bool(link.get("href"))
            and urljoin(expected_url, link["href"]) == config.alternate_urls[target_language],
            f"{label} language link for {target_language} points to the wrong page.",
        )


def check_schema(page: PageParser, language: str) -> None:
    require(len(page.schema_scripts) == 1, f"{language}: expected one JSON-LD script.")
    try:
        schema = json.loads(page.schema_scripts[0])
    except json.JSONDecodeError as error:
        raise CheckError(f"{language}: invalid JSON-LD: {error}") from error

    graph = schema.get("@graph", []) if isinstance(schema, dict) else []
    require(isinstance(graph, list), f"{language}: JSON-LD @graph must be a list.")
    services = [node for node in graph if isinstance(node, dict) and node.get("@type") == "Service"]
    require(len(services) == 10, f"{language}: expected 10 schema services, found {len(services)}.")
    web_pages = [
        node for node in graph
        if isinstance(node, dict) and node.get("@type") == "WebPage"
    ]
    require(
        len(web_pages) == 1 and web_pages[0].get("inLanguage") == language,
        f"{language}: schema WebPage.inLanguage must match the page language.",
    )


def check_local_references(page: PageParser, page_path: Path, dist_dir: Path) -> None:
    duplicate_ids = [value for value, count in Counter(page.ids).items() if count > 1]
    require(not duplicate_ids, f"{page_path}: duplicate IDs: {', '.join(duplicate_ids)}.")

    for tag, attributes in page.tags:
        reference = attributes.get("href") if tag in {"a", "link"} else attributes.get("src")
        if not reference:
            continue
        url = urlsplit(reference)
        if url.scheme or url.netloc:
            continue

        relative_path = unquote(url.path)
        if relative_path.startswith("/"):
            target = dist_dir / relative_path.lstrip("/")
        else:
            target = page_path.parent / relative_path if relative_path else page_path
        target = target.resolve()
        require(
            target.is_relative_to(dist_dir),
            f"{page_path}: local reference escapes the output directory: {reference}.",
        )
        if target.is_dir():
            target = target / "index.html"
        require(target.is_file(), f"{page_path}: missing local target for {reference}: {target}.")

        if url.fragment and target.suffix == ".html":
            target_page = page
            if target != page_path:
                target_page = PageParser(target.read_text(encoding="utf-8"))
            require(
                unquote(url.fragment) in target_page.ids,
                f"{page_path}: anchor {reference} has no matching ID in {target}.",
            )

    for image in page.elements("img"):
        require(
            bool(image.get("src"))
            and str(image.get("width", "")).isdigit()
            and str(image.get("height", "")).isdigit()
            and int(image["width"]) > 0
            and int(image["height"]) > 0,
            f"{page_path}: every image needs a source and positive width/height dimensions.",
        )


def check_pages(dist_dir: Path, config: SiteConfig) -> None:
    for language, path in config.locale_paths.items():
        page_path = dist_dir / path / "index.html"
        html = page_path.read_text(encoding="utf-8")
        page = PageParser(html)
        check_metadata(page, language, config)
        check_schema(page, language)
        check_local_references(page, page_path, dist_dir)
        require(
            not re.search(r"\bconst\s+pages\s*=", html),
            f"{language}: page still embeds the old client-side translation bundle.",
        )
        print(
            f"{language}: metadata, headings, schema, links, and images passed "
            f"({page_path.stat().st_size:,} bytes)."
        )


def check_sitemap_and_robots(dist_dir: Path, config: SiteConfig) -> None:
    root = ElementTree.parse(dist_dir / "sitemap.xml").getroot()
    require(root.tag == SITEMAP_NAMESPACE + "urlset", "sitemap.xml: expected a sitemap urlset.")
    urls = root.findall(SITEMAP_NAMESPACE + "url")
    locations = [node.findtext(SITEMAP_NAMESPACE + "loc") for node in urls]
    expected_locations = {config.alternate_urls[language] for language in config.locale_paths}
    require(
        len(locations) == len(expected_locations) and set(locations) == expected_locations,
        "sitemap.xml: page URLs must match the configured locales.",
    )
    for node in urls:
        links = node.findall(XHTML_NAMESPACE + "link")
        alternates = {link.get("hreflang"): link.get("href") for link in links}
        require(
            len(links) == len(config.alternate_urls)
            and alternates == config.alternate_urls
            and all(link.get("rel") == "alternate" for link in links),
            "sitemap.xml: each page must list all hreflang alternatives and x-default.",
        )

    robots = (dist_dir / "robots.txt").read_text(encoding="utf-8")
    expected_sitemap = f"Sitemap: {urljoin(config.site_url, 'sitemap.xml')}"
    require(expected_sitemap in robots.splitlines(), f"robots.txt: missing '{expected_sitemap}'.")
    print("Sitemap URLs, hreflang alternatives, and robots.txt passed.")


def check_archive(dist_dir: Path, archive_path: Path) -> None:
    files = {
        path.relative_to(dist_dir).as_posix(): path
        for path in dist_dir.rglob("*")
        if path.is_file()
    }
    with ZipFile(archive_path) as archive:
        entries = [entry.filename for entry in archive.infolist() if not entry.is_dir()]
        require(len(entries) == len(set(entries)), f"{archive_path}: duplicate archive entries.")
        missing = set(files) - set(entries)
        extra = set(entries) - set(files)
        require(
            not missing and not extra,
            f"{archive_path}: contents differ from dist; "
            f"missing={sorted(missing)}, extra={sorted(extra)}.",
        )
        for name, path in files.items():
            require(
                archive.read(name) == path.read_bytes(),
                f"{archive_path}: stale content for {name}.",
            )
    print(f"Deployment archive passed ({len(files)} files match the generated output).")


def check_http_routes(base_url: str, dist_dir: Path, config: SiteConfig) -> None:
    base_url = base_url.rstrip("/") + "/"
    parsed_url = urlsplit(base_url)
    require(
        parsed_url.scheme in {"http", "https"}
        and bool(parsed_url.netloc)
        and not parsed_url.query
        and not parsed_url.fragment,
        "--base-url must be an HTTP(S) URL without a query or fragment.",
    )
    routes = list(config.locale_paths.values())
    routes.extend(
        quote(path.relative_to(dist_dir).as_posix())
        for path in sorted(dist_dir.rglob("*"))
        if path.is_file() and path.name != "index.html"
    )
    routes.append("?lang=en")
    for route in routes:
        url = urljoin(base_url, route)
        with urlopen(url, timeout=10) as response:
            require(
                response.status == 200,
                f"HTTP: {url} returned {response.status}, expected 200.",
            )
    print(f"HTTP route checks passed ({len(routes)} routes at {base_url}).")


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dist-dir",
        type=Path,
        default=PROJECT_ROOT / "dist",
        help="Generated site directory.",
    )
    parser.add_argument(
        "--archive",
        type=Path,
        default=PROJECT_ROOT / "waymark-production.zip",
        help="Deployment ZIP to compare with the site.",
    )
    parser.add_argument(
        "--base-url",
        help="Also check HTTP routes, for example http://127.0.0.1:4173/.",
    )
    return parser.parse_args()


def main() -> int:
    arguments = parse_arguments()
    dist_dir = arguments.dist_dir.resolve()
    try:
        config = load_config()
        check_pages(dist_dir, config)
        check_sitemap_and_robots(dist_dir, config)
        check_archive(dist_dir, arguments.archive)
        if arguments.base_url:
            check_http_routes(arguments.base_url, dist_dir, config)
    except (CheckError, OSError, ValueError, ElementTree.ParseError, BadZipFile) as error:
        print(f"SEO check failed: {error}", file=sys.stderr)
        return 1

    print("All SEO checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
