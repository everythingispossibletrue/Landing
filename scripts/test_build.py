"""Regression tests for build failures, editable copy, and HTML-derived schema.

Run with: python3 -m unittest discover -s scripts -p 'test_*.py'
Every build test uses a temporary project; it never changes the real dist files.
"""

from contextlib import redirect_stdout
from copy import deepcopy
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch
from zipfile import ZipFile

from html_document import parse_html
from site_config import load_config
from structured_data import build_structured_data, business_services, career_services


SCRIPTS_DIRECTORY = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPTS_DIRECTORY.parent


def import_script(name, filename):
    specification = importlib.util.spec_from_file_location(name, SCRIPTS_DIRECTORY / filename)
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module


builder = import_script("site_builder", "build-seo.py")
seo_checks = import_script("site_seo_checks", "check-seo.py")


class BuildTests(unittest.TestCase):
    def setUp(self):
        temporary_project = tempfile.TemporaryDirectory(prefix="waymark-build-test-")
        self.addCleanup(temporary_project.cleanup)
        self.project = Path(temporary_project.name)
        self.source = self.project / "src"
        self.output = self.project / "dist"
        self.archive = self.project / "waymark-production.zip"
        shutil.copytree(PROJECT_ROOT / "src", self.source)
        config_path = self.source / "site-config.json"
        self.config = json.loads(config_path.read_text(encoding="utf-8"))

        paths = patch.multiple(
            builder,
            PROJECT_ROOT=self.project,
            SOURCE_DIRECTORY=self.source,
            OUTPUT_DIRECTORY=self.output,
            ARCHIVE_PATH=self.archive,
        )
        paths.start()
        self.addCleanup(paths.stop)

    def output_snapshot(self):
        files = [self.archive]
        files.extend(self.output.rglob("*"))
        files.extend((self.project / "deployment-extras").rglob("*"))
        return {
            path.relative_to(self.project).as_posix(): path.read_bytes()
            for path in files if path.is_file()
        }

    def test_rebuild_removes_stale_pages_from_output_and_archive(self):
        builder.build_site(self.config)
        old_page = self.output / "retired" / "index.html"
        old_page.parent.mkdir()
        old_page.write_text("Old page", encoding="utf-8")
        host_file = self.project / "deployment-extras" / ".htaccess"
        host_file.write_text("Custom host setting", encoding="utf-8")

        builder.build_site(self.config)

        self.assertFalse(old_page.exists())
        self.assertEqual(host_file.read_text(), "Custom host setting")
        with ZipFile(self.archive) as archive:
            self.assertNotIn("retired/index.html", archive.namelist())
            self.assertEqual(len(archive.namelist()), 10)
        self.assertEqual(list(self.project.glob(".waymark-build-*")), [])

    def test_failed_page_render_preserves_previous_build(self):
        builder.build_site(self.config)
        previous_output = self.output_snapshot()
        russian_page = self.source / "pages" / "ru.html"
        russian_page.write_text(russian_page.read_text() + "\n<p>A changed page.</p>\n")
        (self.source / "pages" / "en.html").unlink()

        with self.assertRaises(FileNotFoundError):
            builder.build_site(self.config)

        self.assertEqual(self.output_snapshot(), previous_output)
        self.assertEqual(list(self.project.glob(".waymark-build-*")), [])

    def test_failed_packaging_preserves_previous_build(self):
        builder.build_site(self.config)
        previous_output = self.output_snapshot()

        with patch.object(builder, "package_site", side_effect=OSError("Disk full")):
            with self.assertRaisesRegex(OSError, "Disk full"):
                builder.build_site(self.config)

        self.assertEqual(self.output_snapshot(), previous_output)
        self.assertEqual(list(self.project.glob(".waymark-build-*")), [])

    def test_failed_publication_rolls_back_previous_build(self):
        builder.build_site(self.config)
        previous_output = self.output_snapshot()
        original_replace = Path.replace

        def fail_archive_move(source, destination):
            if Path(destination) == self.archive and source.name == self.archive.name:
                raise PermissionError("Archive is locked")
            return original_replace(source, destination)

        with patch.object(Path, "replace", fail_archive_move):
            with self.assertRaisesRegex(OSError, "Recovery files remain"):
                builder.build_site(self.config)

        self.assertEqual(self.output_snapshot(), previous_output)
        self.assertEqual(len(list(self.project.glob(".waymark-build-*"))), 1)

    def test_dollar_signs_in_editorial_copy_survive_building(self):
        page = self.source / "pages" / "ru.html"
        copy = "Budget $500; $salary and ${salary} remain literal."
        page.write_text(page.read_text() + f"\n<p>{copy}</p>\n", encoding="utf-8")

        builder.build_site(self.config)

        self.assertIn(copy, (self.output / "index.html").read_text(encoding="utf-8"))

    def test_unknown_reserved_link_token_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "telegram_missing"):
            builder.render_page_links('<a href="${telegram_missing}">Contact</a>', {})
        with self.assertRaisesRegex(ValueError, "Unclosed"):
            builder.render_page_links('<a href="${telegram_missing">Contact</a>', {})

    def test_nested_locale_routes_and_site_url_subpath(self):
        config = deepcopy(self.config)
        config["locales"]["en"]["path"] = "languages/en/"
        config["locales"]["kk"]["path"] = "languages/kk/"
        config_path = self.source / "site-config.json"
        config_path.write_text(json.dumps(config, ensure_ascii=False), encoding="utf-8")
        with patch.dict(os.environ, {"SITE_URL": "https://example.test/career"}):
            config = load_config(config_path)
        builder.build_site(config)

        expected_urls = seo_checks.SiteConfig(
            config["site_url"],
            {language: metadata["path"] for language, metadata in config["locales"].items()},
        )
        with redirect_stdout(io.StringIO()):
            seo_checks.check_pages(self.output.resolve(), expected_urls)
            seo_checks.check_sitemap_and_robots(self.output, expected_urls)
            seo_checks.check_archive(self.output, self.archive)
        english = (self.output / "languages" / "en" / "index.html").read_text()
        self.assertIn('href="https://example.test/career/languages/en/"', english)
        self.assertIn('src="../../portrait.webp"', english)
        self.assertIn('data-lang="ru" href="../../"', english)

    def test_empty_title_and_indexing_directives_are_detected(self):
        builder.build_site(self.config)
        html = (self.output / "index.html").read_text(encoding="utf-8")
        expected_urls = seo_checks.SiteConfig(
            self.config["site_url"],
            {language: metadata["path"] for language, metadata in self.config["locales"].items()},
        )
        ordinary_copy = html.replace(
            "</main>", "<p>The word noindex in copy is allowed.</p></main>"
        )
        seo_checks.check_metadata(seo_checks.PageParser(ordinary_copy), "ru", expected_urls)
        blocked = html.replace('content="index,follow,max-image-preview:large"', 'content="none"')
        with self.assertRaisesRegex(seo_checks.CheckError, "prevents indexing"):
            seo_checks.check_metadata(seo_checks.PageParser(blocked), "ru", expected_urls)
        title = self.config["locales"]["ru"]["title"]
        empty_title = html.replace(f"<title>{title}</title>", "<title> </title>")
        with self.assertRaisesRegex(seo_checks.CheckError, "TITLE"):
            seo_checks.check_metadata(seo_checks.PageParser(empty_title), "ru", expected_urls)


class ConfigTests(unittest.TestCase):
    def test_unsafe_and_duplicate_locale_paths_are_rejected(self):
        original = json.loads((PROJECT_ROOT / "src" / "site-config.json").read_text())
        paths = (
            "../escape/", "/outside/", "en//", "%2e%2e/escape/", "en/?query=yes",
            "en/#fragment", "en\\other/", "https://example.test/", "", "kk/",
        )
        with tempfile.TemporaryDirectory(prefix="waymark-config-test-") as directory:
            config_path = Path(directory) / "site-config.json"
            for path in paths:
                with self.subTest(path=path):
                    config = deepcopy(original)
                    config["locales"]["en"]["path"] = path
                    config_path.write_text(json.dumps(config), encoding="utf-8")
                    with self.assertRaises(ValueError):
                        load_config(config_path)


class HtmlReaderTests(unittest.TestCase):
    def test_inline_markup_preserves_words_and_punctuation(self):
        document = parse_html("<h3>Linked<span>In</span> &amp; C<span>++</span><br>coaching</h3>")
        self.assertEqual(document.require("h3").text, "LinkedIn & C++ coaching")
        self.assertEqual(parse_html("<p>A<span> B </span>C</p>").require("p").text, "A B C")

    def test_breaks_stay_inside_paragraphs(self):
        paragraph = parse_html("<p>Before<br>after</p>").require("p")
        self.assertEqual(paragraph.text, "Before after")

    def test_omitted_list_end_tags_and_nested_bullets(self):
        markup = """
            <ul class="business-list">
              <li><h3>First</h3><p>Description</p><ul><li>Nested detail</li></ul>
              <li><h3>Second</h3><p>More information</p>
            </ul>
        """
        services = business_services(parse_html(markup), "https://example.test/", "#person")
        self.assertEqual([service["name"] for service in services], ["First", "Second"])

    def test_missing_classes_do_not_crash_search(self):
        document = parse_html("<article class></article>")
        self.assertEqual(list(document.find_all("article", "offer")), [])

    def test_missing_service_id_and_section_raise_clear_errors(self):
        with self.assertRaisesRegex(ValueError, "id attribute"):
            career_services(parse_html('<article class="offer"></article>'), "/", "#person")
        config = load_config()
        with self.assertRaisesRegex(ValueError, "services"):
            build_structured_data(config, "ru", '<ul class="business-list"></ul>')


if __name__ == "__main__":
    unittest.main()
