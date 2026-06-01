(function () {
  "use strict";

  function readPayload() {
    var el = document.getElementById("finance-dashboard-chart-data");
    if (!el || !el.textContent) {
      return null;
    }
    try {
      return JSON.parse(el.textContent);
    } catch (e) {
      console.warn("finance dashboard: invalid chart JSON", e);
      return null;
    }
  }

  function emptyPlugin(message) {
    return {
      id: "financeEmpty",
      afterDraw: function (chart) {
        var hasData =
          chart.data.datasets &&
          chart.data.datasets.some(function (ds) {
            return ds.data && ds.data.some(function (v) {
              return Number(v) > 0;
            });
          });
        if (hasData) {
          return;
        }
        var ctx = chart.ctx;
        var w = chart.width;
        var h = chart.height;
        ctx.save();
        ctx.textAlign = "center";
        ctx.textBaseline = "middle";
        ctx.fillStyle = "#909399";
        ctx.font = "14px sans-serif";
        ctx.fillText(message, w / 2, h / 2);
        ctx.restore();
      },
    };
  }

  function initTrendChart(data, labels) {
    var canvas = document.getElementById("finance-trend-chart");
    if (!canvas || !window.Chart) {
      return;
    }
    var trend = data.trend || {};
    new Chart(canvas, {
      type: "bar",
      data: {
        labels: trend.labels || [],
        datasets: [
          {
            label: labels.income,
            data: trend.income || [],
            backgroundColor: "rgba(45, 164, 78, 0.75)",
            borderRadius: 4,
            order: 2,
          },
          {
            label: labels.expense,
            data: trend.expense || [],
            backgroundColor: "rgba(207, 34, 46, 0.75)",
            borderRadius: 4,
            order: 3,
          },
          {
            label: labels.net,
            data: trend.net || [],
            type: "line",
            borderColor: "#0969da",
            backgroundColor: "rgba(9, 105, 218, 0.12)",
            borderWidth: 2,
            tension: 0.25,
            fill: true,
            order: 1,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: { mode: "index", intersect: false },
        plugins: {
          legend: { position: "top" },
        },
        scales: {
          y: {
            beginAtZero: true,
            ticks: { precision: 0 },
          },
        },
      },
      plugins: [emptyPlugin(labels.noData)],
    });
  }

  function initDonutChart(canvasId, slice, label, colors) {
    var canvas = document.getElementById(canvasId);
    if (!canvas || !window.Chart) {
      return;
    }
    slice = slice || { labels: [], values: [] };
    new Chart(canvas, {
      type: "doughnut",
      data: {
        labels: slice.labels,
        datasets: [
          {
            data: slice.values,
            backgroundColor: colors,
            borderWidth: 1,
            borderColor: "#fff",
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { position: "bottom" },
        },
      },
      plugins: [emptyPlugin(label)],
    });
  }

  function palette(n) {
    var base = [
      "#2da44e",
      "#0969da",
      "#bc4c00",
      "#8250df",
      "#cf222e",
      "#1b7c83",
      "#bf8700",
      "#6e7781",
    ];
    var out = [];
    for (var i = 0; i < n; i++) {
      out.push(base[i % base.length]);
    }
    return out;
  }

  document.addEventListener("DOMContentLoaded", function () {
    var data = readPayload();
    if (!data) {
      return;
    }
    var labels = window.FINANCE_DASHBOARD_I18N || {
      income: "Income",
      expense: "Expense",
      net: "Net profit",
      noData: "No data",
    };
    initTrendChart(data, labels);
    var income = data.income_by_category || { labels: [], values: [] };
    var expense = data.expense_by_category || { labels: [], values: [] };
    initDonutChart(
      "finance-income-pie-chart",
      income,
      labels.noData,
      palette(income.labels.length)
    );
    initDonutChart(
      "finance-expense-pie-chart",
      expense,
      labels.noData,
      palette(expense.labels.length)
    );
  });
})();
