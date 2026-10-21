const assert = require("node:assert/strict");
const { readFileSync } = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");

const entryPoint = readFileSync(path.join(__dirname, "../index.html"), "utf8");
const redirectScript = entryPoint.match(/<script>([\s\S]*?)<\/script>/)[1];

for (const [source, expected] of [
  ["https://example.com/?lang=en#business", "https://example.com/dist/?lang=en#business"],
  [
    "https://example.com/career/index.html?lang=kk#services",
    "https://example.com/career/dist/?lang=kk#services",
  ],
  [
    "file:///Users/example/career/index.html?lang=en#faq",
    "file:///Users/example/career/dist/?lang=en#faq",
  ],
]) {
  test(`repository entry preserves the selected language and anchor: ${source}`, () => {
    const url = new URL(source);
    let actual;
    vm.runInNewContext(redirectScript, {
      URL,
      window: {
        location: {
          href: url.href,
          search: url.search,
          hash: url.hash,
          replace(destination) {
            actual = destination;
          },
        },
      },
    });
    assert.equal(actual, expected);
  });
}

const { JSDOM } = require("jsdom");
const { resolve } = require("node:path");

for (const [language, directory] of [
  ["ru", ""],
  ["en", "en"],
  ["kk", "kk"],
]) {
  test(`${language}: navigation controls and page markup retain accessibility hooks`, () => {
    const markup = readFileSync(resolve(__dirname, "../dist", directory, "index.html"), "utf8");
    const dom = new JSDOM(markup);
    const { document } = dom.window;
    try {
      const menuButton = document.querySelector("button.menu");
      const navigation = document.getElementById(menuButton.getAttribute("aria-controls"));
      assert.equal(navigation?.tagName, "NAV");
      assert.ok(navigation.getAttribute("aria-label"));
      assert.equal(menuButton.type, "button");
      assert.equal(document.querySelector(".languages").getAttribute("role"), "group");

      for (const image of document.images) {
        assert.ok(
          image.hasAttribute("alt"),
          "An image needs alternative text or explicit decorative alt",
        );
      }
      for (const link of document.querySelectorAll('a[target="_blank"]')) {
        assert.ok(link.relList.contains("noopener"), "New-window links must prevent opener access");
      }
      assert.equal(
        document.querySelectorAll(
          "a a, a button, button a, button button, summary a, summary button",
        ).length,
        0,
      );
      assert.equal(
        document.querySelectorAll("[id]").length,
        new Set([...document.querySelectorAll("[id]")].map((element) => element.id)).size,
      );
    } finally {
      dom.window.close();
    }
  });
}
