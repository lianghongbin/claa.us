(function () {
  "use strict";

  var STATUS_FIELDS = ["is_active", "is_staff", "is_superuser"];

  function initAddUserGrid() {
    var fieldset = document.querySelector("fieldset.accounts-add-grid");
    if (!fieldset || fieldset.dataset.statusGrouped === "1") {
      return;
    }

    var emailRow = fieldset.querySelector(".form-row.field-email");
    if (!emailRow) {
      return;
    }

    var statusRows = STATUS_FIELDS.map(function (name) {
      return fieldset.querySelector(".form-row.field-" + name);
    }).filter(Boolean);

    if (statusRows.length === 0) {
      return;
    }

    fieldset.dataset.statusGrouped = "1";

    var groupRow = document.createElement("div");
    groupRow.className = "form-row accounts-status-group field-status-group";

    var outer = document.createElement("div");
    var flex = document.createElement("div");
    flex.className = "flex-container fieldBox field-status-group";

    var label = document.createElement("label");
    label.className = "required";
    label.textContent = "状态：";

    var controls = document.createElement("div");
    controls.className = "accounts-status-checkboxes";

    statusRows.forEach(function (row) {
      var box = row.querySelector(".flex-container.checkbox-row");
      if (box) {
        controls.appendChild(box);
      }
      row.remove();
    });

    flex.appendChild(label);
    flex.appendChild(controls);
    outer.appendChild(flex);
    groupRow.appendChild(outer);

    emailRow.insertAdjacentElement("afterend", groupRow);
  }

  function run() {
    initAddUserGrid();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", run);
  } else {
    run();
  }
  window.addEventListener("load", run);
})();
