(function () {
  "use strict";

  function trim(s) {
    return (s || "").replace(/\s+/g, " ").trim();
  }

  function fieldLabelForSelector(selectorEl) {
    var row = selectorEl.closest(".form-row");
    if (!row) {
      return "";
    }
    var label = row.querySelector("label");
    if (!label) {
      return "";
    }
    return trim(label.textContent.replace(/[:：]\s*$/, ""));
  }

  function needsTitle(h2) {
    if (!h2) {
      return false;
    }
    var t = trim(h2.textContent);
    return !t || t === "?" || t === "？" || t.length < 2;
  }

  function initSelectorTitles() {
    document.querySelectorAll("div.selector").forEach(function (sel) {
      var fromH2 = sel.querySelector(".selector-available h2");
      var toH2 = sel.querySelector(".selector-chosen h2");
      var name = fieldLabelForSelector(sel);
      var suffix = name ? " " + name : "";
      if (needsTitle(fromH2)) {
        fromH2.textContent = "可选" + suffix;
      }
      if (needsTitle(toH2)) {
        toH2.textContent = "已选" + suffix;
      }
    });
  }

  function initCompactDateFields() {
    document.querySelectorAll("input.vDateField").forEach(function (input) {
      if (input.dataset.dateCompact === "1") {
        return;
      }
      var shortcuts = input.nextElementSibling;
      if (
        !shortcuts ||
        !shortcuts.classList ||
        !shortcuts.classList.contains("datetimeshortcuts")
      ) {
        return;
      }

      input.dataset.dateCompact = "1";
      var dateWrap = input.closest("p.date");
      if (dateWrap) {
        dateWrap.classList.add("finance-date-field");
      }

      var calendarLink = shortcuts.querySelector(
        "a.calendarlink, a[id^='calendarlink']"
      );

      shortcuts.querySelectorAll("a").forEach(function (a) {
        if (a !== calendarLink) {
          a.style.display = "none";
        }
      });

      function openCalendar(evt) {
        if (!calendarLink) {
          return;
        }
        if (evt) {
          evt.preventDefault();
          evt.stopPropagation();
        }
        calendarLink.click();
      }

      input.addEventListener("click", openCalendar);
      input.style.cursor = "pointer";
    });
  }

  function measureLabelTextWidth(label) {
    var probe = document.createElement("span");
    var style = window.getComputedStyle(label);
    probe.textContent = trim(label.textContent.replace(/[:：]\s*$/, "")) + "：";
    probe.style.cssText =
      "position:absolute;left:-9999px;top:0;white-space:nowrap;visibility:hidden;" +
      "font-size:" +
      style.fontSize +
      ";font-weight:" +
      style.fontWeight +
      ";font-family:" +
      style.fontFamily +
      ";";
    document.body.appendChild(probe);
    var width = probe.offsetWidth;
    document.body.removeChild(probe);
    return width;
  }

  function syncLabelWidths() {
    if (!document.body.classList.contains("admin-compact-form")) {
      return;
    }
    var labels = document.querySelectorAll(
      "fieldset.module > .form-row .flex-container > label, fieldset.module > .form-row > div > label, fieldset.module > .form-row > .fieldBox > label"
    );
    var max = 0;
    labels.forEach(function (label) {
      if (label.classList.contains("vCheckboxLabel")) {
        return;
      }
      if (!label.closest("fieldset.module")) {
        return;
      }
      max = Math.max(max, measureLabelTextWidth(label));
    });
    if (max > 0) {
      var width = Math.min(Math.ceil(max) + 6, 160);
      document.documentElement.style.setProperty(
        "--admin-form-label-width",
        width + "px"
      );
    }
  }

  function runAfterAdminWidgets() {
    initCompactDateFields();
    initSelectorTitles();
    syncLabelWidths();
  }

  function positionCalendarPopup(calBox, num) {
    if (!calBox) {
      return;
    }
    var input =
      window.DateTimeShortcuts &&
      window.DateTimeShortcuts.calendarInputs &&
      window.DateTimeShortcuts.calendarInputs[num];
    if (!input) {
      return;
    }

    calBox.style.position = "fixed";
    calBox.style.zIndex = "10050";
    calBox.style.margin = "0";
    calBox.style.right = "auto";

    var anchor = input.closest("p.date") || input;
    var anchorRect = anchor.getBoundingClientRect();
    var width = calBox.offsetWidth || 320;
    var height = calBox.offsetHeight || 280;
    var gap = 8;
    var left = (window.innerWidth - width) / 2;
    var top = anchorRect.bottom + gap;

    if (top + height > window.innerHeight - gap) {
      top = anchorRect.top - height - gap;
    }

    calBox.style.left = Math.max(gap, Math.round(left)) + "px";
    calBox.style.top = Math.max(gap, Math.round(top)) + "px";
  }

  function patchDateTimeShortcuts() {
    if (
      typeof window.DateTimeShortcuts === "undefined" ||
      !window.DateTimeShortcuts.init
    ) {
      return;
    }
    if (window.DateTimeShortcuts._financePatched) {
      return;
    }
    window.DateTimeShortcuts._financePatched = true;
    var originalInit = window.DateTimeShortcuts.init;
    window.DateTimeShortcuts.init = function () {
      originalInit.apply(this, arguments);
      runAfterAdminWidgets();
    };

    if (!document.body.classList.contains("admin-compact-form")) {
      return;
    }

    var originalOpenCalendar = DateTimeShortcuts.openCalendar;
    DateTimeShortcuts.openCalendar = function (num) {
      originalOpenCalendar.call(DateTimeShortcuts, num);
      var calBox = document.getElementById(
        DateTimeShortcuts.calendarDivName1 + num
      );
      if (!calBox) {
        return;
      }
      requestAnimationFrame(function () {
        positionCalendarPopup(calBox, num);
      });
    };
  }

  function run() {
    patchDateTimeShortcuts();
    runAfterAdminWidgets();
    if (typeof SelectFilter !== "undefined" && SelectFilter.init) {
      var orig = SelectFilter.init;
      if (!SelectFilter._financePatched) {
        SelectFilter._financePatched = true;
        SelectFilter.init = function () {
          var ret = orig.apply(this, arguments);
          initSelectorTitles();
          syncLabelWidths();
          return ret;
        };
      }
    }
  }

  patchDateTimeShortcuts();

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", run);
  } else {
    run();
  }

  window.addEventListener("load", function () {
    patchDateTimeShortcuts();
    runAfterAdminWidgets();
  });
})();
