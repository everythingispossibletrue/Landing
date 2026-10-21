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

  function scrollToInitialAnchor() {
    if (!window.location.hash) return;

    const fragment = window.location.hash.slice(1);
    let targetId;

    try {
      targetId = decodeURIComponent(fragment);
    } catch {
      // A malformed URL fragment must not prevent the other controls from working.
      targetId = fragment;
    }

    const target = document.getElementById(targetId);
    if (target) {
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
    scrollToInitialAnchor();
    observeMotionPreference(setupHeroAnimation);
  }

  initializeSite();
})();
