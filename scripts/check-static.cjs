const assert = require("node:assert/strict");
const { readFileSync, existsSync, statSync } = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");
const { JSDOM } = require("jsdom");
const root = path.resolve(__dirname, "..");
const base = "https://everythingispossibletrue.github.io/Landing/";

for (const [language, file] of [
  ["ru", "index.html"],
  ["en", "en/index.html"],
  ["kk", "kk/index.html"],
]) {
  test(`${language}: complete static page, metadata and local links work under /Landing/`, () => {
    const html = readFileSync(path.join(root, file), "utf8");
    const url = new URL(file.replace(/index\.html$/, ""), base);
    const dom = new JSDOM(html, { url: url.href });
    const document = dom.window.document;
    try {
      assert.equal(document.documentElement.lang, language);
      assert.ok(document.querySelector("main h1"));
      assert.ok(document.querySelector("#contact"));
      assert.ok(!html.includes("${"), "No unresolved templates");
      assert.equal(document.querySelector('link[rel="canonical"]').href, url.href);
      assert.deepEqual(
        [...document.querySelectorAll(".languages [data-lang]")].map((a) => a.dataset.lang),
        ["kk", "ru", "en"],
      );
      assert.equal(document.querySelectorAll('a[href="https://wa.me/77475064616"]').length, 4);
      for (const element of document.querySelectorAll("[href], [src]")) {
        const raw = element.getAttribute("href") ?? element.getAttribute("src");
        if (!raw || /^(mailto:|tel:|data:)/.test(raw)) continue;
        const destination = new URL(raw, url);
        if (destination.origin !== url.origin) continue;
        assert.ok(destination.pathname.startsWith("/Landing/"), raw);
        assert.ok(!destination.pathname.includes("/dist/"), raw);
        const relative = decodeURIComponent(destination.pathname.slice("/Landing/".length));
        let target = path.resolve(root, relative);
        assert.ok(target === root || target.startsWith(root + path.sep), raw);
        assert.ok(existsSync(target), `${raw}: missing ${relative}`);
        if (statSync(target).isDirectory()) target = path.join(target, "index.html");
        assert.ok(existsSync(target), raw);
        if (destination.hash && target.endsWith(".html")) {
          const other = new JSDOM(readFileSync(target, "utf8"));
          try {
            assert.ok(
              other.window.document.getElementById(decodeURIComponent(destination.hash.slice(1))),
              raw,
            );
          } finally {
            other.window.close();
          }
        }
      }
      for (const script of document.scripts) {
        if (script.type === "application/ld+json") JSON.parse(script.textContent);
        else if (!script.src) new vm.Script(script.textContent);
      }
      assert.equal(
        document
          .querySelector(".hero-portrait")
          .getAttribute("src")
          .endsWith("portrait-cutout.png"),
        true,
      );
    } finally {
      dom.window.close();
    }
  });
}

test("site has no build dependency or redirect to dist", () => {
  const config = JSON.parse(readFileSync(path.join(root, "package.json")));
  assert.equal(config.scripts.build, undefined);
  assert.equal(config.scripts.pretest, undefined);
  assert.ok(!existsSync(path.join(root, "dist")));
  assert.ok(!existsSync(path.join(root, "src")));
  assert.ok(existsSync(path.join(root, ".nojekyll")));
  const workflow = readFileSync(path.join(root, ".github/workflows/pages.yml"), "utf8");
  assert.ok(!workflow.includes("build-seo.py"));
  assert.ok(workflow.includes("path: ."));
  assert.ok(readFileSync(path.join(root, "robots.txt"), "utf8").includes(base + "sitemap.xml"));
  const sitemap = readFileSync(path.join(root, "sitemap.xml"), "utf8");
  for (const locale of ["", "en/", "kk/"]) assert.ok(sitemap.includes(base + locale));
  new vm.Script(readFileSync(path.join(root, "site.js"), "utf8"));
});

test("old dist links redirect to static pages, preserving language, query and anchor", () => {
  const markup = readFileSync(path.join(root, "404.html"), "utf8");
  const script = markup.match(/<script>([\s\S]*?)<\/script>/)[1];
  for (const [oldPath, newPath] of [
    ["dist/", ""],
    ["dist", ""],
    ["dist/index.html", ""],
    ["dist/en/", "en/"],
    ["dist/kk/index.html", "kk/"],
    ["missing-page/", null],
  ]) {
    let actual;
    vm.runInNewContext(script, {
      URL,
      window: {
        location: {
          href: base + oldPath + "?lang=en#services",
          replace: (url) => {
            actual = url;
          },
        },
      },
    });
    assert.equal(actual, newPath === null ? undefined : base + newPath + "?lang=en#services");
  }
});
