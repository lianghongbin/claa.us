/**
 * SimpleUI 后台补丁（财务 claa.us）
 * - 修复 openTab / menuActive
 * - 标签关闭：统一 tab id 为字符串 + 委托点击 × + 修复 handleTabsEdit
 * - 除首页外最多 5 个业务标签
 */
(function () {
  "use strict";

  var STORAGE_KEY = "finance_menu_storage";
  var STORAGE_VERSION = "finance-menu-v6";
  var MAX_CONTENT_TABS = 5;

  function tabIdEquals(a, b) {
    return String(a) === String(b);
  }

  function isHomeTabId(id) {
    return tabIdEquals(id, 0) || tabIdEquals(id, "0");
  }

  function syncHashFromTab(tab) {
    if (tab && tab.url && tab.url.indexOf("http") !== 0) {
      location.hash = "#" + (tab.url || "/");
    }
  }

  function normalizeTabsState(app) {
    if (!app || !app.tabs) {
      return;
    }
    for (var i = 0; i < app.tabs.length; i++) {
      app.tabs[i].id = String(app.tabs[i].id);
      if (app.tabs[i].eid != null) {
        app.tabs[i].eid = String(app.tabs[i].eid);
      }
    }
    if (app.tabModel != null && app.tabModel !== "") {
      app.tabModel = String(app.tabModel);
    }
  }

  function removeTabById(app, targetName) {
    targetName = String(targetName);
    if (isHomeTabId(targetName)) {
      return false;
    }
    normalizeTabsState(app);
    var before = app.tabs.length;
    app.tabs = app.tabs.filter(function (tab) {
      return !tabIdEquals(tab.id, targetName);
    });
    if (app.tabs.length < before) {
      if (typeof app.syncTabs === "function") {
        app.syncTabs();
      }
      if (app.$nextTick) {
        app.$nextTick(function () {
          app.$forceUpdate();
        });
      } else {
        app.$forceUpdate();
      }
      return true;
    }
    return false;
  }

  function closeTab(app, targetName) {
    if (!app || !app.tabs) {
      return;
    }
    targetName = String(targetName);
    normalizeTabsState(app);

    var closingActive = tabIdEquals(app.tabModel, targetName);
    if (!closingActive) {
      removeTabById(app, targetName);
      return;
    }

    var next = "0";
    var nextTab = null;
    for (var i = 0; i < app.tabs.length; i++) {
      if (tabIdEquals(app.tabs[i].id, targetName)) {
        nextTab = app.tabs[i + 1] || app.tabs[i - 1];
        if (nextTab) {
          next = String(nextTab.id);
          setMenuActive(app, nextTab.index != null ? nextTab.index : nextTab.eid);
          app.breadcrumbs = nextTab.breadcrumbs;
          syncHashFromTab(nextTab);
        }
        break;
      }
    }
    app.tabModel = next;
    removeTabById(app, targetName);
    syncMenuFromActiveTab(app);
    resetLoadingState(app);
  }

  function setMenuActive(app, eid) {
    if (eid == null || eid === "") {
      return;
    }
    app.menuActive = String(eid);
  }

  function activeTab(app) {
    if (!app || !app.tabs) {
      return null;
    }
    for (var i = 0; i < app.tabs.length; i++) {
      if (tabIdEquals(app.tabs[i].id, app.tabModel)) {
        return app.tabs[i];
      }
    }
    return app.tabs[0] || null;
  }

  function syncMenuFromActiveTab(app) {
    var tab = activeTab(app);
    if (!tab) {
      return;
    }
    setMenuActive(app, tab.index != null ? tab.index : tab.eid);
  }

  function ensureValidTabModel(app) {
    if (!app || !app.tabs || !app.tabs.length) {
      return;
    }
    var ok = false;
    for (var i = 0; i < app.tabs.length; i++) {
      if (tabIdEquals(app.tabs[i].id, app.tabModel)) {
        ok = true;
        break;
      }
    }
    if (!ok) {
      app.tabModel = String(app.tabs[0].id);
      syncMenuFromActiveTab(app);
    }
  }

  function resetLoadingState(app) {
    if (!app) {
      return;
    }
    app.loading = false;
    if (!app.tabs) {
      return;
    }
    for (var i = 0; i < app.tabs.length; i++) {
      app.tabs[i].loading = false;
    }
  }

  function enforceTabLimit(app) {
    if (!app || !app.tabs || app.tabs.length <= 1 + MAX_CONTENT_TABS) {
      return;
    }
    var activeId = String(app.tabModel);
    while (app.tabs.length > 1 + MAX_CONTENT_TABS) {
      var removeAt = -1;
      for (var i = 1; i < app.tabs.length; i++) {
        if (String(app.tabs[i].id) !== activeId) {
          removeAt = i;
          break;
        }
      }
      if (removeAt < 0) {
        break;
      }
      app.tabs.splice(removeAt, 1);
    }
    if (typeof app.syncTabs === "function") {
      app.syncTabs();
    }
    ensureValidTabModel(app);
  }

  function clearStaleTabs() {
    try {
      if (sessionStorage.getItem(STORAGE_KEY) === STORAGE_VERSION) {
        return;
      }
      sessionStorage.removeItem("tabs");
      sessionStorage.setItem(STORAGE_KEY, STORAGE_VERSION);
    } catch (err) {
      /* ignore */
    }
  }

  function paneNameFromCloseClick(event) {
    var closeEl = event.target;
    if (!closeEl || !closeEl.classList || !closeEl.classList.contains("el-icon-close")) {
      return null;
    }
    var tabItem = closeEl.closest(".el-tabs__item");
    if (!tabItem || !tabItem.closest(".el-tabs__header")) {
      return null;
    }
    var idAttr = tabItem.getAttribute("id") || "";
    if (idAttr.indexOf("tab-") !== 0) {
      return null;
    }
    return idAttr.slice(4);
  }

  function installTabCloseDelegation() {
    if (window._financeTabCloseDelegation) {
      return;
    }
    document.addEventListener(
      "click",
      function (event) {
        if (!window.app || window.self !== window.top) {
          return;
        }
        var paneName = paneNameFromCloseClick(event);
        if (paneName == null) {
          return;
        }
        event.stopPropagation();
        event.preventDefault();
        closeTab(window.app, paneName);
      },
      true
    );
    window._financeTabCloseDelegation = true;
  }

  function patchOpenTab(app) {
    if (app._financeOpenTabPatch) {
      return;
    }
    var orig = app.openTab;
    app.openTab = function (data, index, selected, loading) {
      if (index == null && data && data.eid != null) {
        index = data.eid;
      }
      var result = orig.call(this, data, index, selected, loading);
      normalizeTabsState(this);
      if (index != null && index !== "") {
        setMenuActive(this, index);
        for (var i = 0; i < this.tabs.length; i++) {
          if (tabIdEquals(this.tabs[i].eid, data.eid)) {
            this.tabs[i].index = index;
            break;
          }
        }
      }
      if (this.tabs.length > 1 + MAX_CONTENT_TABS) {
        enforceTabLimit(this);
        syncMenuFromActiveTab(this);
      }
      return result;
    };
    app._financeOpenTabPatch = true;
  }

  function patchHandleTabsEdit(app) {
    if (app._financeTabsEditPatch) {
      return;
    }
    app.handleTabsEdit = function (targetName, action) {
      if (action !== "remove") {
        return;
      }
      closeTab(this, targetName);
    };
    if (app.$options && app.$options.methods) {
      app.$options.methods.handleTabsEdit = app.handleTabsEdit;
    }
    app._financeTabsEditPatch = true;
  }

  function patchTabClick(app) {
    if (app._financeTabClickPatch) {
      return;
    }
    var orig = app.tabClick;
    app.tabClick = function (tab) {
      orig.call(this, tab);
      syncMenuFromActiveTab(this);
    };
    app._financeTabClickPatch = true;
  }

  function patchIframeLoad(app) {
    if (app._financeIframeLoadPatch) {
      return;
    }
    var orig = app.iframeLoad;
    app.iframeLoad = function (tab, e) {
      orig.call(this, tab, e);
      resetLoadingState(this);
    };
    app._financeIframeLoadPatch = true;
  }

  function bootstrap(app) {
    app.__financeCloseTab = function (targetName) {
      closeTab(app, targetName);
    };
    patchOpenTab(app);
    patchHandleTabsEdit(app);
    patchTabClick(app);
    patchIframeLoad(app);
    normalizeTabsState(app);
    ensureValidTabModel(app);
    enforceTabLimit(app);
    syncMenuFromActiveTab(app);
    resetLoadingState(app);
  }

  function boot(app) {
    if (window.self !== window.top) {
      return;
    }
    clearStaleTabs();
    installTabCloseDelegation();
    var target = app || window.app;
    if (!target) {
      return;
    }
    if (target.$nextTick) {
      target.$nextTick(function () {
        bootstrap(target);
      });
    } else {
      bootstrap(target);
    }
  }

  var prevRenderCallback = window.renderCallback;
  window.renderCallback = function (app) {
    if (typeof prevRenderCallback === "function") {
      prevRenderCallback(app);
    }
    boot(app);
  };

  function waitForApp() {
    if (window.app) {
      boot(window.app);
      return;
    }
    var n = 0;
    var timer = setInterval(function () {
      if (window.app) {
        clearInterval(timer);
        boot(window.app);
      } else if (++n > 120) {
        clearInterval(timer);
      }
    }, 50);
  }

  installTabCloseDelegation();

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", waitForApp);
  } else {
    waitForApp();
  }
})();
