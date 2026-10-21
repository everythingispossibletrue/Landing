(() => {
  "use strict";

  const reducedMotionPreference =
    typeof window.matchMedia === "function"
      ? window.matchMedia("(prefers-reduced-motion: reduce)")
      : null;

  function motionIsEnabled() {
    return !reducedMotionPreference?.matches;
  }

  function observeMotionPreference(callback) {
    if (typeof reducedMotionPreference?.addEventListener === "function") {
      reducedMotionPreference.addEventListener("change", callback);
    } else if (typeof reducedMotionPreference?.addListener === "function") {
      reducedMotionPreference.addListener(callback);
    }
  }

  function redirectLegacyLanguageLink() {
    // Older links used ?lang=en; each language now has its own static page.
    const language = new URLSearchParams(window.location.search).get("lang");
    if (!["ru", "en", "kk"].includes(language)) return;

    const languageLink = document.querySelector(`[data-lang="${language}"]`);
    if (languageLink) {
      window.location.replace(languageLink.href + window.location.hash);
    }
  }

  function updateLanguageLinks() {
    const currentLanguage = document.documentElement.lang;

    document.querySelectorAll("[data-lang]").forEach((link) => {
      const isCurrentLanguage = link.dataset.lang === currentLanguage;
      link.classList.toggle("active", isCurrentLanguage);

      if (isCurrentLanguage) {
        link.setAttribute("aria-current", "page");
      } else {
        link.removeAttribute("aria-current");
      }
    });
  }

  function setupNavigationMenu() {
    const header = document.querySelector("header");
    const navigation = header?.querySelector("nav");
    const menuButton = header?.querySelector(".menu");
    if (!navigation || !menuButton) return;

    function setMenuOpen(isOpen) {
      navigation.classList.toggle("open", isOpen);
      menuButton.classList.toggle("is-open", isOpen);
      menuButton.setAttribute("aria-expanded", String(isOpen));
      menuButton.setAttribute(
        "aria-label",
        isOpen ? menuButton.dataset.closeLabel : menuButton.dataset.openLabel,
      );
    }

    function closeMenu() {
      setMenuOpen(false);
    }

    menuButton.addEventListener("click", () => {
      setMenuOpen(!navigation.classList.contains("open"));
    });

    navigation.querySelectorAll("a").forEach((link) => {
      link.addEventListener("click", closeMenu);
    });

    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape" && navigation.classList.contains("open")) {
        closeMenu();
        menuButton.focus();
      }
    });

    document.addEventListener("click", (event) => {
      if (navigation.classList.contains("open") && !header.contains(event.target)) {
        closeMenu();
      }
    });

    window.addEventListener(
      "resize",
      () => {
        if (
          navigation.classList.contains("open") &&
          window.getComputedStyle(menuButton).display === "none"
        ) {
          closeMenu();
        }
      },
      { passive: true },
    );

    // The navigation stays visible without JavaScript until its controls are ready.
    document.documentElement.classList.add("js-navigation");
  }

  function setupHeroAnimation() {
    const hero = document.querySelector(".hero");
    if (!hero || !motionIsEnabled()) return;

    hero.classList.add("hero-enter");
    hero
      .querySelectorAll(".eyebrow, h1, .intro, .hero-actions, .signature, .hero-art")
      .forEach((element, index) => {
        element.style.setProperty("--enter-delay", `${index * 85}ms`);
      });
  }

  function setupAccordionAnimation(details, onSizeChange) {
    const summary = details.querySelector("summary");
    if (!summary) return;

    let activeAnimation = null;
    let requestedOpen = details.open;
    let originalOverflow = details.style.overflow;

    function clearAnimation() {
      details.style.overflow = originalOverflow;
      activeAnimation = null;
      onSizeChange();
    }

    function finishAnimation() {
      // Leave the content available until the closing animation finishes.
      details.open = requestedOpen;
      clearAnimation();
    }

    observeMotionPreference(() => {
      if (motionIsEnabled() || !activeAnimation) return;

      const animation = activeAnimation;
      animation.onfinish = null;
      animation.oncancel = null;
      finishAnimation();
      animation.cancel();
    });

    summary.addEventListener("click", (event) => {
      // Keep native <details> behavior when motion is reduced or unsupported.
      if (!motionIsEnabled() || typeof details.animate !== "function") return;

      event.preventDefault();
      if (activeAnimation) return;

      requestedOpen = !details.open;
      const startHeight = details.getBoundingClientRect().height;
      if (requestedOpen) details.open = true;

      const styles = window.getComputedStyle(details);
      const borderHeight =
        parseFloat(styles.borderTopWidth || 0) + parseFloat(styles.borderBottomWidth || 0);
      const endHeight = requestedOpen
        ? details.getBoundingClientRect().height
        : summary.getBoundingClientRect().height + borderHeight;

      originalOverflow = details.style.overflow;
      details.style.overflow = "hidden";
      activeAnimation = details.animate(
        { height: [`${startHeight}px`, `${endHeight}px`] },
        { duration: 240, easing: "cubic-bezier(.22,1,.36,1)" },
      );

      activeAnimation.onfinish = finishAnimation;
      activeAnimation.oncancel = clearAnimation;
    });
  }

  function setupBackToTop() {
    const backToTopLink = document.querySelector(".back-to-top");
    if (!backToTopLink) return;

    backToTopLink.addEventListener("click", (event) => {
      event.preventDefault();
      window.scrollTo({
        top: 0,
        behavior: motionIsEnabled() ? "smooth" : "auto",
      });
    });
  }

  function setupScrollTracking() {
    const progressBar = document.querySelector(".progress");
    const backToTopLink = document.querySelector(".back-to-top");
    const navigationLinks = document.querySelectorAll("nav a");
    const navigationTargets = new Set(Array.from(navigationLinks, (link) => link.hash));
    const sections = Array.from(document.querySelectorAll("main section[id]")).filter((section) =>
      navigationTargets.has(`#${section.id}`),
    );
    let pendingFrame = 0;

    function updateScrollState() {
      const maximumScroll = Math.max(0, document.documentElement.scrollHeight - window.innerHeight);

      if (progressBar) {
        const progress =
          maximumScroll > 0
            ? Math.max(0, Math.min(100, (window.scrollY / maximumScroll) * 100))
            : 0;
        progressBar.style.width = `${progress}%`;
      }

      if (backToTopLink) {
        backToTopLink.hidden = window.scrollY < Math.max(500, window.innerHeight * 0.7);
      }

      let currentSectionId = "";
      sections.forEach((section) => {
        if (section.getBoundingClientRect().top <= 150) currentSectionId = section.id;
      });

      // An open tab with its own menu link, such as the business services, marks its section.
      const openPanel = document
        .getElementById(currentSectionId)
        ?.querySelector("[data-tab-panel]:not([hidden])");
      if (openPanel && navigationTargets.has(`#${openPanel.id}`)) currentSectionId = openPanel.id;

      navigationLinks.forEach((link) => {
        const isCurrentSection = link.hash === `#${currentSectionId}`;
        link.classList.toggle("current", isCurrentSection);

        if (isCurrentSection) {
          link.setAttribute("aria-current", "location");
        } else {
          link.removeAttribute("aria-current");
        }
      });
    }

    function scheduleScrollUpdate() {
      if (pendingFrame) return;

      pendingFrame = window.requestAnimationFrame(() => {
        pendingFrame = 0;
        updateScrollState();
      });
    }

    window.addEventListener("scroll", scheduleScrollUpdate, { passive: true });
    window.addEventListener("resize", scheduleScrollUpdate, { passive: true });
    document.addEventListener("toggle", scheduleScrollUpdate, true);
    updateScrollState();
    return scheduleScrollUpdate;
  }

  function setupServiceTabs(onChange) {
    const tabList = document.querySelector("[data-service-tabs]");
    const tabs = Array.from(tabList?.querySelectorAll("[data-tab-target]") ?? []);
    const panels = tabs.map((tab) => document.getElementById(tab.dataset.tabTarget));
    if (!tabs.length || panels.includes(null)) return () => {};

    // Without JavaScript the tabs stay plain links and both panels remain visible.
    tabList.setAttribute("role", "tablist");
    tabList.setAttribute("aria-label", tabList.dataset.tabsLabel);
    tabs.forEach((tab, index) => {
      tab.setAttribute("role", "tab");
      tab.setAttribute("aria-controls", panels[index].id);
      panels[index].setAttribute("role", "tabpanel");
      panels[index].setAttribute("aria-labelledby", tab.id);
    });

    function selectTab(selectedIndex) {
      tabs.forEach((tab, index) => {
        const isSelected = index === selectedIndex;
        tab.setAttribute("aria-selected", String(isSelected));
        tab.tabIndex = isSelected ? 0 : -1;
        panels[index].hidden = !isSelected;
      });
      onChange();
    }

    tabList.addEventListener("click", (event) => {
      const tab = event.target.closest("[data-tab-target]");
      if (!tab) return;

      // Switch in place instead of jumping to the panel anchor.
      event.preventDefault();
      selectTab(tabs.indexOf(tab));
    });

    tabList.addEventListener("keydown", (event) => {
      const currentIndex = tabs.indexOf(event.target);
      if (currentIndex === -1) return;

      if (event.key === " ") {
        event.preventDefault();
        selectTab(currentIndex);
        return;
      }

      const lastIndex = tabs.length - 1;
      const nextIndex = {
        ArrowLeft: currentIndex === 0 ? lastIndex : currentIndex - 1,
        ArrowRight: currentIndex === lastIndex ? 0 : currentIndex + 1,
        Home: 0,
        End: lastIndex,
      }[event.key];
      if (nextIndex === undefined) return;

      event.preventDefault();
      selectTab(nextIndex);
      tabs[nextIndex].focus();
    });

    selectTab(0);

    return function revealTarget(target) {
      const index = panels.findIndex((panel) => panel.contains(target));
      if (index !== -1 && panels[index].hidden) selectTab(index);
    };
  }

  function setupReviewCarousel() {
    const carousel = document.querySelector("[data-carousel]");
    const track = carousel?.querySelector("[data-carousel-track]");
    const controls = carousel?.querySelector("[data-carousel-controls]");
    const previousButton = controls?.querySelector("[data-carousel-previous]");
    const nextButton = controls?.querySelector("[data-carousel-next]");
    if (!track || !previousButton || !nextButton) return;

    function updateButtons() {
      const maximumScroll = track.scrollWidth - track.clientWidth;
      previousButton.disabled = track.scrollLeft <= 1;
      nextButton.disabled = track.scrollLeft >= maximumScroll - 1;
    }

    function scrollReviews(direction) {
      // Scroll snapping settles the track on the nearest card.
      track.scrollBy({
        left: direction * track.clientWidth * 0.8,
        behavior: motionIsEnabled() ? "smooth" : "auto",
      });
    }

    previousButton.addEventListener("click", () => scrollReviews(-1));
    nextButton.addEventListener("click", () => scrollReviews(1));
    track.addEventListener("scroll", updateButtons, { passive: true });
    window.addEventListener("resize", updateButtons, { passive: true });
    controls.hidden = false;
    updateButtons();
  }

  function elementForHash(hash) {
    const fragment = hash.slice(1);
    if (!fragment) return null;

    try {
      return document.getElementById(decodeURIComponent(fragment));
    } catch {
      // A malformed URL fragment must not prevent the other controls from working.
      return document.getElementById(fragment);
    }
  }

  function revealLinkedTabs(revealTarget) {
    // Menu and card links, such as "For business", open the tab that holds their target.
    document.addEventListener("click", (event) => {
      const link = event.target.closest?.('a[href^="#"]');
      if (!link || link.closest("[data-service-tabs]")) return;

      const target = elementForHash(link.hash);
      if (target) revealTarget(target);
    });
  }

  function scrollToInitialAnchor(revealTarget) {
    const target = elementForHash(window.location.hash);
    if (target) {
      revealTarget(target);
      window.requestAnimationFrame(() => {
        // `auto` otherwise inherits the page's smooth-scroll CSS on first load.
        const root = document.documentElement;
        const previousBehavior = root.style.scrollBehavior;
        root.style.scrollBehavior = "auto";
        try {
          target.scrollIntoView({ block: "start", behavior: "auto" });
        } finally {
          root.style.scrollBehavior = previousBehavior;
        }
      });
    }
  }

  function initializeSite() {
    redirectLegacyLanguageLink();
    updateLanguageLinks();
    setupNavigationMenu();
    setupBackToTop();
    setupHeroAnimation();
    const scheduleScrollUpdate = setupScrollTracking();
    document.querySelectorAll("details").forEach((details) => {
      setupAccordionAnimation(details, scheduleScrollUpdate);
    });
    const revealTarget = setupServiceTabs(scheduleScrollUpdate);
    revealLinkedTabs(revealTarget);
    setupReviewCarousel();
    scrollToInitialAnchor(revealTarget);
    observeMotionPreference(setupHeroAnimation);
  }

  initializeSite();
})();
