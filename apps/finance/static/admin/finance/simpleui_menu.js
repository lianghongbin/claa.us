/**
 * SimpleUI 后台补丁（财务 claa.us）
 * - 修复 openTab 未正确更新 menuActive
 * - 关闭「非当前」标签时不改写菜单高亮与 hash（SimpleUI 原逻辑缺陷）
 * - 除首页外最多 5 个业务标签，淘汰最早打开的
 */
(function () {
  "use strict";

  var STORAGE_KEY = "finance_menu_storage";
  var STORAGE_VERSION = "finance-menu-v5";
  var MAX_CONTENT_TABS = 5;

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
      if (String(app.tabs[i].id) === String(app.tabModel)) {
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
      if (String(app.tabs[i].id) === String(app.tabModel)) {
        ok = true;
        break;
      }
    }
    if (!ok) {
      app.tabModel = app.tabs[0].id;
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

  /** 仅剔除多余标签，不改当前选中的 tab / 菜单 / hash */
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
      if (index != null && index !== "") {
        setMenuActive(this, index);
        for (var i = 0; i < this.tabs.length; i++) {
          if (this.tabs[i].eid === data.eid) {
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
    var orig = app.handleTabsEdit;
    app.handleTabsEdit = function (targetName, action) {
      if (action !== "remove") {
        return orig.call(this, targetName, action);
      }
      if (String(this.tabModel) !== String(targetName)) {
        this.tabs = this.tabs.filter(function (tab) {
          return tab.id !== targetName;
        });
        if (typeof this.syncTabs === "function") {
          this.syncTabs();
        }
        return;
      }
      orig.call(this, targetName, action);
      syncMenuFromActiveTab(this);
      resetLoadingState(this);
    };
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
    patchOpenTab(app);
    patchHandleTabsEdit(app);
    patchTabClick(app);
    patchIframeLoad(app);
    ensureValidTabModel(app);
    enforceTabLimit(app);
    syncMenuFromActiveTab(app);
    resetLoadingState(app);
  }

  function boot() {
    if (window.self !== window.top) {
      return;
    }
    clearStaleTabs();
    function run() {
      if (!window.app) {
        return;
      }
      if (window.app.$nextTick) {
        window.app.$nextTick(function () {
          bootstrap(window.app);
        });
      } else {
        bootstrap(window.app);
      }
    }
    if (window.app) {
      run();
    } else {
      var n = 0;
      var timer = setInterval(function () {
        if (window.app) {
          clearInterval(timer);
          run();
        } else if (++n > 120) {
          clearInterval(timer);
        }
      }, 50);
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
