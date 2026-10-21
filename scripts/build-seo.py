"""Build the three localized static pages and the deployment archive.

Usage: python3 scripts/build-seo.py
Set SITE_URL to build for another domain. No third-party packages are required.
"""

from html import escape
import json
from pathlib import Path
import re
import shutil
from string import Template
import sys
import tempfile
from urllib.parse import quote
from xml.etree import ElementTree
import zipfile

from site_config import (
    ARCHIVE_PATH,
    OUTPUT_DIRECTORY,
    PROJECT_ROOT,
    SOURCE_DIRECTORY,
    load_config,
)
from structured_data import build_structured_data

STATIC_ASSETS = ("site.css", "site.js", "hero.jpg", "favicon.svg")
SITEMAP_NAMESPACE = "http://www.sitemaps.org/schemas/sitemap/0.9"
XHTML_NAMESPACE = "http://www.w3.org/1999/xhtml"
PAGE_PLACEHOLDER = re.compile(r"\$\{(telegram_[^}]*|locale_[^}]*|asset_prefix)\}")


def html_attributes(attributes: dict) -> str:
    return " ".join(
        f'{name}="{escape(str(value), quote=True)}"'
        for name, value in attributes.items()
    )


def meta_tag(content: str, *, name=None, property_name=None) -> str:
    key = "property" if property_name else "name"
    return "<meta " + html_attributes({key: property_name or name, "content": content}) + ">"


def link_tag(**attributes) -> str:
    return "<link " + html_attributes(attributes) + ">"


def language_urls(config: dict) -> dict:
    urls = {
        language: config["site_url"] + metadata["path"]
        for language, metadata in config["locales"].items()
    }
    urls["x-default"] = config["site_url"]
    return urls


def build_head(config: dict, language: str, content: str) -> str:
    metadata = config["locales"][language]
    page_url = config["site_url"] + metadata["path"]
    asset_prefix = "../" * len(Path(metadata["path"]).parts) or "./"
    image_url = config["site_url"] + "hero.jpg"

    tags = [
        '<meta charset="UTF-8">',
        meta_tag("width=device-width,initial-scale=1", name="viewport"),
        meta_tag("#0c213b", name="theme-color"),
        "<title>" + escape(metadata["title"]) + "</title>",
        meta_tag(metadata["description"], name="description"),
        meta_tag("index,follow,max-image-preview:large", name="robots"),
        link_tag(rel="canonical", href=page_url),
    ]
    for code, url in language_urls(config).items():
        tags.append(link_tag(rel="alternate", hreflang=code, href=url))

    social_metadata = {
        "og:type": "website",
        "og:site_name": "Дарья Хамидуллина",
        "og:title": metadata["title"],
        "og:description": metadata["description"],
        "og:url": page_url,
        "og:locale": metadata["social_locale"],
        "og:image": image_url,
        "og:image:width": "1122",
        "og:image:height": "1402",
        "og:image:alt": metadata["image_alt"],
    }
    for property_name, value in social_metadata.items():
        tags.append(meta_tag(value, property_name=property_name))
    for other_language, other_metadata in config["locales"].items():
        if other_language != language:
            tags.append(meta_tag(
                other_metadata["social_locale"], property_name="og:locale:alternate"
            ))

    twitter_metadata = {
        "twitter:card": "summary_large_image",
        "twitter:title": metadata["title"],
        "twitter:description": metadata["description"],
        "twitter:image": image_url,
    }
    for name, value in twitter_metadata.items():
        tags.append(meta_tag(value, name=name))

    tags.extend([
        link_tag(rel="icon", href=asset_prefix + "favicon.svg", type="image/svg+xml"),
        link_tag(**{
            "rel": "preload",
            "as": "image",
            "href": asset_prefix + "hero.jpg",
            "fetchpriority": "high",
        }),
        link_tag(rel="stylesheet", href=asset_prefix + "site.css"),
    ])
    structured_data = build_structured_data(config, language, content)
    # Escaping </ prevents page text from closing the JSON-LD script element.
    schema_json = json.dumps(structured_data, ensure_ascii=False, indent=2).replace("</", "<\\/")
    tags.append('<script type="application/ld+json">\n' + schema_json + "\n</script>")
    tags.append(f'<script src="{escape(asset_prefix, quote=True)}site.js" defer></script>')
    return "\n    ".join(line for tag in tags for line in tag.splitlines())


def render_page_links(markup: str, links: dict) -> str:
    """Replace reserved link tokens while preserving dollar signs in page copy."""
    def replace(match):
        name = match[1]
        if name not in links:
            raise ValueError(f"Unknown page link placeholder: ${{{name}}}")
        return links[name]

    rendered = PAGE_PLACEHOLDER.sub(replace, markup)
    if re.search(r"\$\{(?:telegram_|locale_|asset_prefix)", rendered):
        raise ValueError("Unclosed page link placeholder in page markup.")
    return rendered


def build_pages(config: dict, output_directory: Path) -> None:
    template_path = SOURCE_DIRECTORY / "templates" / "document.html"
    template = Template(template_path.read_text(encoding="utf-8"))
    messages_path = SOURCE_DIRECTORY / "telegram-messages.json"
    messages = json.loads(messages_path.read_text(encoding="utf-8"))

    for language, metadata in config["locales"].items():
        source_path = SOURCE_DIRECTORY / "pages" / f"{language}.html"
        asset_prefix = "../" * len(Path(metadata["path"]).parts) or "./"
        link_values = {
            "telegram_" + name.replace("-", "_"): escape(
                config["telegram_url"] + "?text=" + quote(message, safe=""), quote=True
            )
            for name, message in messages[language].items()
        }
        link_values["asset_prefix"] = asset_prefix
        for code, locale in config["locales"].items():
            link_values["locale_" + code] = asset_prefix + locale["path"]
        content = render_page_links(source_path.read_text(encoding="utf-8"), link_values).rstrip()
        document = template.substitute(
            language=language,
            head=build_head(config, language, content),
            content="\n    ".join(content.splitlines()),
        )
        output_path = output_directory / metadata["path"] / "index.html"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(document, encoding="utf-8")


def copy_assets(output_directory: Path) -> None:
    for filename in STATIC_ASSETS:
        shutil.copyfile(SOURCE_DIRECTORY / filename, output_directory / filename)


def write_crawler_files(config: dict, output_directory: Path) -> None:
    robots = "User-agent: *\nAllow: /\n\nSitemap: " + config["site_url"] + "sitemap.xml\n"
    (output_directory / "robots.txt").write_text(robots, encoding="utf-8")

    ElementTree.register_namespace("", SITEMAP_NAMESPACE)
    ElementTree.register_namespace("xhtml", XHTML_NAMESPACE)
    root = ElementTree.Element(f"{{{SITEMAP_NAMESPACE}}}urlset")
    for metadata in config["locales"].values():
        entry = ElementTree.SubElement(root, f"{{{SITEMAP_NAMESPACE}}}url")
        location = ElementTree.SubElement(entry, f"{{{SITEMAP_NAMESPACE}}}loc")
        location.text = config["site_url"] + metadata["path"]
        for language, url in language_urls(config).items():
            ElementTree.SubElement(entry, f"{{{XHTML_NAMESPACE}}}link", {
                "rel": "alternate",
                "hreflang": language,
                "href": url,
            })
    ElementTree.indent(root, space="  ")
    ElementTree.ElementTree(root).write(
        output_directory / "sitemap.xml", encoding="utf-8", xml_declaration=True
    )


def package_site(output_directory: Path, archive_path: Path) -> None:
    with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(output_directory.rglob("*")):
            if path.is_file():
                archive.write(path, path.relative_to(output_directory))


def publish_artifacts(artifacts: list, backup_directory: Path) -> None:
    """Replace completed artifacts, restoring previous files if a move fails."""
    backup_directory.mkdir()
    backups = []
    published = []
    try:
        for index, (staged_path, destination) in enumerate(artifacts):
            destination.parent.mkdir(parents=True, exist_ok=True)
            if destination.exists() or destination.is_symlink():
                backup = backup_directory / str(index)
                destination.replace(backup)
                backups.append((backup, destination))
            staged_path.replace(destination)
            published.append(destination)
    except BaseException:
        for destination in reversed(published):
            if destination.is_dir() and not destination.is_symlink():
                shutil.rmtree(destination)
            else:
                destination.unlink()
        for backup, destination in reversed(backups):
            backup.replace(destination)
        raise


def build_site(config: dict) -> None:
    """Prepare a fresh build before changing any previously generated output."""
    staging_directory = Path(tempfile.mkdtemp(prefix=".waymark-build-", dir=PROJECT_ROOT))
    preserve_staging = False
    try:
        output_directory = staging_directory / "dist"
        output_directory.mkdir()
        archive_path = staging_directory / ARCHIVE_PATH.name
        build_pages(config, output_directory)
        copy_assets(output_directory)
        write_crawler_files(config, output_directory)
        package_site(output_directory, archive_path)

        artifacts = [(output_directory, OUTPUT_DIRECTORY), (archive_path, ARCHIVE_PATH)]
        extras_directory = staging_directory / "deployment-extras"
        extras_directory.mkdir()
        for filename in ("robots.txt", "sitemap.xml"):
            staged_file = extras_directory / filename
            shutil.copyfile(output_directory / filename, staged_file)
            artifacts.append((staged_file, PROJECT_ROOT / "deployment-extras" / filename))

        # Keep recovery files if publication or its rollback encounters an OS error.
        preserve_staging = True
        try:
            publish_artifacts(artifacts, staging_directory / "backups")
        except Exception as error:
            raise OSError(
                "Could not publish the build. "
                f"Recovery files remain in {staging_directory}: {error}"
            ) from error
        preserve_staging = False
    finally:
        if not preserve_staging:
            shutil.rmtree(staging_directory)


def main() -> int:
    try:
        build_site(load_config())
    except (OSError, ValueError, KeyError) as error:
        print(f"Build failed: {error}", file=sys.stderr)
        return 1
    print("Built RU, EN and KK pages, shared assets, crawler files and production ZIP.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
