const assert = require("node:assert/strict");
const { readFileSync } = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");
const { JSDOM } = require("jsdom");

const projectRoot = path.resolve(__dirname, "..");
const siteScript = readFileSync(path.join(projectRoot, "src/site.js"), "utf8");

// jsdom supplies real DOM events; geometry and animation completion are controlled
// because they require a rendering engine in a browser.
function createBrowser(
  testContext,
  { language = "ru", query = "", hash = "", reducedMotion = false, motionApi = "modern" } = {},
) {
  const pagePath = language === "ru" ? "index.html" : `${language}/index.html`;
  const url = `https://example.com/${language === "ru" ? "" : `${language}/`}${query}${hash}`;
  const html = readFileSync(path.join(projectRoot, "dist", pagePath), "utf8");
  const dom = new JSDOM(html, { url });
  const { window } = dom;
  const { document } = window;
  testContext.after(() => window.close());

  const frames = new Map();
  const redirects = [];
  const scrollCalls = [];
  const anchorScrolls = [];
  const motionListeners = [];
  const sectionPositions = new Map();
  let nextFrameId = 1;
  let scrollTop = 0;
  let viewportWidth = 800;
  let viewportHeight = 1000;
  let documentHeight = 3000;

  document.documentElement.style.scrollBehavior = "smooth";

  document.querySelectorAll("main section[id]").forEach((section, index) => {
    sectionPositions.set(section.id, index === 0 ? 0 : 10000 + index * 500);
    section.getBoundingClientRect = () => ({
      top: sectionPositions.get(section.id) - scrollTop,
    });
  });
  Object.defineProperty(document.documentElement, "scrollHeight", {
    get: () => documentHeight,
  });
  window.HTMLElement.prototype.scrollIntoView = function (options) {
    anchorScrolls.push({
      id: this.id,
      options,
      scrollBehavior: document.documentElement.style.scrollBehavior,
    });
  };

  const motionPreference = { matches: reducedMotion };
  if (motionApi === "modern") {
    motionPreference.addEventListener = (eventName, callback) => motionListeners.push(callback);
  } else if (motionApi === "legacy") {
    motionPreference.addListener = (callback) => motionListeners.push(callback);
  }
  const browserWindow = {
    location: {
      search: window.location.search,
      hash: window.location.hash,
      replace: (destination) => redirects.push(destination),
    },
    getComputedStyle: (element) =>
      element.matches(".menu")
        ? { display: viewportWidth > 960 ? "none" : "block" }
        : window.getComputedStyle(element),
    addEventListener: window.addEventListener.bind(window),
    requestAnimationFrame: (callback) => {
      const id = nextFrameId++;
      frames.set(id, callback);
      return id;
    },
    scrollTo: (options) => scrollCalls.push(options),
    get innerHeight() {
      return viewportHeight;
    },
    get scrollY() {
      return scrollTop;
    },
  };
  if (motionApi !== "missing") browserWindow.matchMedia = () => motionPreference;

  vm.runInNewContext(siteScript, {
    window: browserWindow,
    document,
    URLSearchParams,
  });

  return {
    document,
    window,
    redirects,
    scrollCalls,
    anchorScrolls,
    frames,
    sectionPositions,
    flushFrames() {
      const callbacks = [...frames.values()];
      frames.clear();
      callbacks.forEach((callback) => callback());
    },
    setScroll(top, height = viewportHeight, fullHeight = documentHeight) {
      scrollTop = top;
      viewportHeight = height;
      documentHeight = fullHeight;
      window.dispatchEvent(new window.Event("scroll"));
    },
    setViewportWidth(width) {
      viewportWidth = width;
      window.dispatchEvent(new window.Event("resize"));
    },
    setDocumentHeight(height) {
      documentHeight = height;
    },
    setReducedMotion(matches) {
      motionPreference.matches = matches;
      motionListeners.forEach((callback) => callback({ matches }));
    },
  };
}

test("the mobile menu closes through links, Escape and outside clicks", (context) => {
  const { document, window } = createBrowser(context);
  const menuButton = document.querySelector(".menu");
  const navigation = document.querySelector("nav");

  menuButton.click();
  assert.equal(navigation.classList.contains("open"), true);
  assert.equal(menuButton.getAttribute("aria-expanded"), "true");
  assert.equal(menuButton.getAttribute("aria-label"), menuButton.dataset.closeLabel);

  navigation.querySelector("a").click();
  assert.equal(navigation.classList.contains("open"), false);
  assert.equal(menuButton.getAttribute("aria-expanded"), "false");
  assert.equal(menuButton.getAttribute("aria-label"), menuButton.dataset.openLabel);

  menuButton.click();
  document.dispatchEvent(new window.KeyboardEvent("keydown", { key: "Escape", bubbles: true }));
  assert.equal(navigation.classList.contains("open"), false);
  assert.equal(document.activeElement, menuButton);

  menuButton.click();
  document.querySelector("header .languages").click();
  assert.equal(navigation.classList.contains("open"), true);
  document.querySelector("main").click();
  assert.equal(navigation.classList.contains("open"), false);
});

test("mobile navigation resets after visiting the desktop layout", (context) => {
  const browser = createBrowser(context);
  const menuButton = browser.document.querySelector(".menu");
  const navigation = browser.document.querySelector("nav");

  assert.equal(browser.document.documentElement.classList.contains("js-navigation"), true);
  menuButton.click();
  browser.setViewportWidth(1200);
  assert.equal(navigation.classList.contains("open"), false);
  assert.equal(menuButton.getAttribute("aria-expanded"), "false");
  browser.setViewportWidth(800);
  assert.equal(navigation.classList.contains("open"), false);
  menuButton.click();
  assert.equal(navigation.classList.contains("open"), true);
});

test("scroll updates are batched and keep progress, navigation and back-to-top in sync", (context) => {
  const browser = createBrowser(context);
  const { document, window } = browser;
  const backToTop = document.querySelector(".back-to-top");
  const audienceLink = document.querySelector('nav a[href="#audience"]');
  const businessLink = document.querySelector('nav a[href="#business"]');

  assert.equal(backToTop.hidden, true);
  browser.sectionPositions.set("audience", 900);
  browser.sectionPositions.set("business", 1900);
  browser.setScroll(1000);
  browser.setScroll(1000);
  window.dispatchEvent(new window.Event("resize"));
  assert.equal(browser.frames.size, 1);
  browser.flushFrames();

  assert.equal(document.querySelector(".progress").style.width, "50%");
  assert.equal(backToTop.hidden, false);
  assert.equal(audienceLink.getAttribute("aria-current"), "location");
  assert.equal(businessLink.hasAttribute("aria-current"), false);

  browser.setScroll(2000);
  browser.flushFrames();
  assert.equal(document.querySelector(".progress").style.width, "100%");
  assert.equal(audienceLink.classList.contains("current"), false);
  assert.equal(businessLink.getAttribute("aria-current"), "location");

  browser.setScroll(0, 1000, 800);
  browser.flushFrames();
  assert.equal(document.querySelector(".progress").style.width, "0%");
  assert.equal(backToTop.hidden, true);

  browser.setScroll(-100, 1000, 3000);
  browser.flushFrames();
  assert.equal(document.querySelector(".progress").style.width, "0%");
});

test("native accordion changes refresh progress without scrolling", (context) => {
  const browser = createBrowser(context);
  browser.setScroll(1000);
  browser.flushFrames();
  assert.equal(browser.document.querySelector(".progress").style.width, "50%");

  browser.setDocumentHeight(5000);
  browser.document.querySelector("details").dispatchEvent(new browser.window.Event("toggle"));
  browser.flushFrames();
  assert.equal(browser.document.querySelector(".progress").style.width, "25%");
});

for (const [linkedSection, followingSection] of [
  ["expertise", "approach"],
  ["process", "consultation-results"],
]) {
  test(`${linkedSection} stays active while scrolling through ${followingSection}`, (context) => {
    const browser = createBrowser(context);
    const navigationLink = browser.document.querySelector(`nav a[href="#${linkedSection}"]`);
    browser.sectionPositions.set(linkedSection, 900);
    browser.sectionPositions.set(followingSection, 1200);

    browser.setScroll(1000);
    browser.flushFrames();
    assert.equal(navigationLink.getAttribute("aria-current"), "location");

    browser.setScroll(1200);
    browser.flushFrames();
    assert.equal(navigationLink.getAttribute("aria-current"), "location");
    assert.equal(navigationLink.classList.contains("current"), true);
    assert.equal(browser.document.querySelectorAll('nav a[aria-current="location"]').length, 1);
  });
}

test("motion preferences control hero entry and back-to-top scrolling", (context) => {
  const browser = createBrowser(context, { reducedMotion: true });
  const hero = browser.document.querySelector(".hero");
  const backToTop = browser.document.querySelector(".back-to-top");

  assert.equal(hero.classList.contains("hero-enter"), false);
  backToTop.click();
  assert.equal(browser.scrollCalls.at(-1).behavior, "auto");

  browser.setReducedMotion(false);
  assert.equal(hero.classList.contains("hero-enter"), true);
  assert.equal(hero.querySelector("h1").style.getPropertyValue("--enter-delay"), "85ms");
  backToTop.click();
  assert.equal(browser.scrollCalls.at(-1).behavior, "smooth");

  browser.setReducedMotion(true);
  backToTop.click();
  assert.equal(browser.scrollCalls.at(-1).behavior, "auto");
});

test("accordions finish opening and closing before accepting another animation", (context) => {
  const { document, window } = createBrowser(context);
  const details = document.querySelector("details");
  const summary = details.querySelector("summary");
  const animations = [];

  details.style.borderTop = "2px solid";
  details.style.borderBottom = "2px solid";
  details.getBoundingClientRect = () => ({ height: details.open ? 160 : 40 });
  summary.getBoundingClientRect = () => ({ height: 36 });
  details.animate = (keyframes, options) => {
    const animation = { keyframes, options };
    animations.push(animation);
    return animation;
  };
  const clickSummary = () =>
    summary.dispatchEvent(new window.MouseEvent("click", { bubbles: true, cancelable: true }));

  assert.equal(clickSummary(), false);
  assert.equal(details.open, true);
  assert.equal(details.style.overflow, "hidden");
  assert.deepEqual(Array.from(animations[0].keyframes.height), ["40px", "160px"]);
  clickSummary();
  assert.equal(animations.length, 1);

  animations[0].onfinish();
  assert.equal(details.style.overflow, "");
  clickSummary();
  assert.equal(details.open, true);
  assert.deepEqual(Array.from(animations[1].keyframes.height), ["160px", "40px"]);
  animations[1].onfinish();
  assert.equal(details.open, false);
  assert.equal(details.style.overflow, "");

  clickSummary();
  animations[2].oncancel();
  assert.equal(details.style.overflow, "");
  clickSummary();
  assert.equal(animations.length, 4);
});

test("reduced motion leaves accordions to their native browser behavior", (context) => {
  const { document, window } = createBrowser(context, { reducedMotion: true });
  const details = document.querySelector("details");
  details.animate = () => assert.fail("Reduced motion must skip accordion animation");

  const event = new window.MouseEvent("click", {
    bubbles: true,
    cancelable: true,
  });
  details.querySelector("summary").dispatchEvent(event);
  assert.equal(event.defaultPrevented, false);
  assert.equal(details.open, true);
});

for (const initiallyOpen of [false, true]) {
  test(`enabling reduced motion settles a ${initiallyOpen ? "closing" : "opening"} accordion`, (context) => {
    const browser = createBrowser(context);
    const details = browser.document.querySelector("details");
    details.open = initiallyOpen;
    details.style.overflow = "visible";
    let cancelled = false;
    const animation = { cancel: () => (cancelled = true) };
    details.animate = () => animation;

    details.querySelector("summary").click();
    assert.equal(details.style.overflow, "hidden");
    browser.setReducedMotion(true);
    assert.equal(cancelled, true);
    assert.equal(details.open, !initiallyOpen);
    assert.equal(details.style.overflow, "visible");
    assert.equal(animation.onfinish, null);

    details.querySelector("summary").click();
    assert.equal(details.open, initiallyOpen);
  });
}

test("finishing an animated accordion refreshes progress for its final height", (context) => {
  const browser = createBrowser(context);
  const details = browser.document.querySelector("details");
  const animation = {};
  details.animate = () => animation;
  browser.setScroll(1000);
  browser.flushFrames();

  details.querySelector("summary").click();
  browser.setDocumentHeight(5000);
  animation.onfinish();
  browser.flushFrames();
  assert.equal(browser.document.querySelector(".progress").style.width, "25%");
});

test("legacy media-query listeners still react to motion preference changes", (context) => {
  const browser = createBrowser(context, { motionApi: "legacy", reducedMotion: true });
  assert.equal(browser.document.querySelector(".hero").classList.contains("hero-enter"), false);
  browser.setReducedMotion(false);
  assert.equal(browser.document.querySelector(".hero").classList.contains("hero-enter"), true);
});

test("missing matchMedia support does not disable the page controls", (context) => {
  const browser = createBrowser(context, { motionApi: "missing" });
  browser.document.querySelector(".menu").click();
  assert.equal(browser.document.querySelector("nav").classList.contains("open"), true);
  browser.document.querySelector(".back-to-top").click();
  assert.equal(browser.scrollCalls.at(-1).behavior, "smooth");
});

for (const language of ["ru", "en", "kk"]) {
  test(`${language}: language links retain legacy redirects and the current page marker`, (context) => {
    const destinationLanguage = { ru: "en", en: "kk", kk: "ru" }[language];
    const browser = createBrowser(context, {
      language,
      query: `?lang=${destinationLanguage}`,
      hash: "#business",
    });
    const currentLink = browser.document.querySelector(`[data-lang="${language}"]`);
    const destinationLink = browser.document.querySelector(`[data-lang="${destinationLanguage}"]`);
    assert.equal(currentLink.getAttribute("aria-current"), "page");
    assert.equal(currentLink.classList.contains("active"), true);
    assert.deepEqual(browser.redirects, [`${destinationLink.href}#business`]);
    assert.equal(browser.document.querySelectorAll('[data-lang][aria-current="page"]').length, 1);
  });
}

test("initial anchors are decoded and unsupported language parameters are ignored", (context) => {
  const browser = createBrowser(context, {
    query: "?lang=unsupported",
    hash: "#%62usiness",
  });
  assert.deepEqual(browser.redirects, []);
  browser.flushFrames();
  assert.equal(browser.anchorScrolls.length, 1);
  assert.equal(browser.anchorScrolls[0].id, "business");
  assert.equal(browser.anchorScrolls[0].options.block, "start");
  assert.equal(browser.anchorScrolls[0].scrollBehavior, "auto");
  assert.equal(browser.document.documentElement.style.scrollBehavior, "smooth");
});

test("malformed URL fragments do not break the page controls", (context) => {
  const browser = createBrowser(context, { hash: "#%E0%A4%A" });
  browser.document.querySelector(".menu").click();
  assert.equal(browser.document.querySelector("nav").classList.contains("open"), true);
  browser.setScroll(1000);
  browser.flushFrames();
  assert.equal(browser.document.querySelector(".progress").style.width, "50%");
});
