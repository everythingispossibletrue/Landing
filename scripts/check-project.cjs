const assert = require("node:assert/strict");
const { readFileSync } = require("node:fs");
const path = require("node:path");
const test = require("node:test");

const { JSDOM } = require("jsdom");
const { resolve } = require("node:path");

for (const [language, directory] of [
  ["ru", ""],
  ["en", "en"],
  ["kk", "kk"],
]) {
  test(`${language}: navigation controls and page markup retain accessibility hooks`, () => {
    const markup = readFileSync(resolve(__dirname, "..", directory, "index.html"), "utf8");
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
