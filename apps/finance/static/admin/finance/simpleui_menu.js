/**
 * SimpleUI 后台补丁（财务 claa.us）
 * - 修复 openTab / menuActive
 * - 标签关闭见 templates/admin/index.html 内联脚本（避免 CDN 缓存旧 JS）
 * - 除首页外最多 5 个业务标签
 */
(function () {
  "use strict";

  var STORAGE_KEY = "finance_menu_storage";
  var STORAGE_VERSION = "finance-menu-v8";
  var MAX_CONTENT_TABS = 5;

  function tabIdEquals(a, b) {
    return String(a) === String(b);
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
    app.syncTabs = function () {};
    patchOpenTab(app);
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

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", waitForApp);
  } else {
    waitForApp();
  }
})();
