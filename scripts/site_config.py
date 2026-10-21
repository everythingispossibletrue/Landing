"""Project paths and shared configuration for the static site tools."""

import json
import os
from pathlib import Path
import re
from urllib.parse import unquote, urlsplit

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SOURCE_DIRECTORY = PROJECT_ROOT / "src"
OUTPUT_DIRECTORY = PROJECT_ROOT / "dist"
ARCHIVE_PATH = PROJECT_ROOT / "waymark-production.zip"
REQUIRED_LOCALES = {"ru", "en", "kk"}
LOCALE_PATH = re.compile(r"(?:[A-Za-z0-9_-]+/)*")


def validate_locale_paths(locales: dict) -> None:
    """Accept distinct relative URL directories, with Russian at the site root."""
    if not isinstance(locales, dict) or set(locales) != REQUIRED_LOCALES:
        raise ValueError("Config locales must contain exactly ru, en, and kk.")

    paths = []
    for language, metadata in locales.items():
        if not isinstance(metadata, dict):
            raise ValueError(f"Config locales.{language} must be an object.")
        path = metadata.get("path")
        if not isinstance(path, str) or not LOCALE_PATH.fullmatch(path):
            raise ValueError(
                f"Config locales.{language}.path must be a relative directory "
                "such as 'en/' or 'languages/en/', without dots or URL parameters."
            )
        paths.append(path)

    if locales["ru"]["path"] != "":
        raise ValueError("Config locales.ru.path must be empty: Russian is the root page.")
    if len(paths) != len(set(paths)):
        raise ValueError("Config locale paths must be distinct.")


def load_config(config_path=None) -> dict:
    """Load site metadata and allow a different deployment origin at build time."""
    path = Path(config_path) if config_path is not None else SOURCE_DIRECTORY / "site-config.json"
    config = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(config, dict):
        raise ValueError(f"{path}: configuration must be an object.")
    validate_locale_paths(config.get("locales"))

    required_fields = ("site_url", "site_name", "email", "telegram_url")
    locale_fields = (
        "title", "description", "person_name", "job_title", "social_locale", "image_alt"
    )
    for name in required_fields:
        if not isinstance(config.get(name), str) or not config[name].strip():
            raise ValueError(f"Config {name} must be a nonempty string.")
    for language, metadata in config["locales"].items():
        for name in locale_fields:
            if not isinstance(metadata.get(name), str) or not metadata[name].strip():
                raise ValueError(f"Config locales.{language}.{name} must be a nonempty string.")

    site_url = os.environ.get("SITE_URL", config["site_url"])
    if any(character.isspace() for character in site_url):
        raise ValueError("SITE_URL cannot contain whitespace.")
    site_url = site_url.rstrip("/") + "/"
    parsed_url = urlsplit(site_url)

    if parsed_url.scheme not in {"https", "http"} or not parsed_url.hostname:
        raise ValueError("SITE_URL must be an absolute HTTP or HTTPS URL.")
    try:
        parsed_url.port
    except ValueError as error:
        raise ValueError("SITE_URL contains an invalid port.") from error
    if parsed_url.username or parsed_url.password:
        raise ValueError("SITE_URL cannot contain credentials.")
    if parsed_url.query or parsed_url.fragment:
        raise ValueError("SITE_URL cannot contain a query string or fragment.")
    if "\\" in site_url or any(part in {".", ".."} for part in unquote(parsed_url.path).split("/")):
        raise ValueError("SITE_URL cannot contain backslashes or traversal path segments.")

    config["site_url"] = site_url
    return config
