/* Chart.js grafiklari: <canvas data-chart="ID"> + {{ spec|json_script:"ID" }}
 *
 * Spec: {type: "bar"|"line"|"doughnut", labels: [...], datasets: [{label, data, color}],
 *        max, suffix, stacked, horizontal}
 * Mark qoidalari: ustun <= 24px, 4px yumaloq uch; chiziq 2px; nuqta r=4 + 2px oq halqa;
 * to‘r chiziqlari ingichka va sokin; >= 2 seriya uchun legenda; hover tooltip doimo yoqiq.
 */
(function () {
  "use strict";
  if (!window.Chart) return;

  const SURFACE = "#ffffff";
  const GRID = "#eceef3";
  const TEXT = "#4b5563";
  const MUTED = "#6b7280";

  Chart.defaults.font.family = getComputedStyle(document.body).fontFamily;
  Chart.defaults.font.size = 12;
  Chart.defaults.color = MUTED;

  function fmt(v, suffix) {
    if (v === null || v === undefined || Number.isNaN(v)) return "—";
    const n = Math.round(v * 10) / 10;
    return n.toLocaleString("uz-UZ") + (suffix || "");
  }

  // Uzun yorliqlarni so‘zlar bo‘yicha qatorlarga bo‘lish (yorliqlar kesilmasin va tushib qolmasin)
  function wrapLabel(label, max) {
    if (typeof label !== "string" || label.length <= max) return label;
    const words = label.split(" ");
    const lines = [];
    let line = "";
    words.forEach(function (w) {
      if ((line + " " + w).trim().length > max && line) { lines.push(line); line = w; }
      else { line = (line + " " + w).trim(); }
    });
    if (line) lines.push(line);
    return lines;
  }

  // Tor ekranda (telefon) kategoriya yorliqlari bir-birining ustiga tushmasin: bitta ustun kengligiga qarab o'raladi
  function labelWidth(width, count) {
    if (!width || !count) return 14;
    return Math.max(6, Math.min(14, Math.floor(width / count / 7.5)));
  }

  function build(spec, width) {
    const type = spec.type || "bar";
    const multi = (spec.datasets || []).length > 1;
    const datasets = (spec.datasets || []).map(function (ds) {
      const base = { label: ds.label, data: ds.data };
      if (type === "bar") {
        return Object.assign(base, {
          backgroundColor: ds.color, borderWidth: 0, borderRadius: 4, borderSkipped: "start",
          maxBarThickness: 24, categoryPercentage: 0.7, barPercentage: 0.85,
        });
      }
      if (type === "line") {
        return Object.assign(base, {
          borderColor: ds.color, backgroundColor: ds.fill ? ds.color + "1a" : ds.color,
          fill: !!ds.fill, borderWidth: 2, tension: 0.25, spanGaps: true,
          pointRadius: 4, pointHoverRadius: 6, pointBackgroundColor: ds.color,
          pointBorderColor: SURFACE, pointBorderWidth: 2, borderCapStyle: "round", borderJoinStyle: "round",
        });
      }
      return Object.assign(base, {
        backgroundColor: ds.colors || ds.color, borderColor: SURFACE, borderWidth: 2, hoverOffset: 4,
      });
    });

    const options = {
      responsive: true,
      maintainAspectRatio: false,
      animation: { duration: 400 },
      interaction: type === "line" ? { mode: "index", intersect: false } : { mode: "nearest", intersect: true },
      plugins: {
        legend: {
          display: type === "doughnut" || multi,
          position: type === "doughnut" ? "right" : "top",
          align: "end",
          labels: { usePointStyle: true, pointStyle: "rectRounded", boxWidth: 10, boxHeight: 10, color: TEXT, padding: 14 },
        },
        tooltip: {
          backgroundColor: "#111827", padding: 10, cornerRadius: 8, displayColors: true, boxPadding: 4,
          callbacks: {
            label: function (ctx) {
              const v = type === "doughnut" ? ctx.parsed : (spec.horizontal ? ctx.parsed.x : ctx.parsed.y);
              return " " + (ctx.dataset.label || ctx.label) + ": " + fmt(v, spec.suffix);
            },
          },
        },
      },
    };

    if (type !== "doughnut") {
      const valueAxis = {
        beginAtZero: true,
        suggestedMax: spec.max || undefined,
        max: spec.max || undefined,
        stacked: !!spec.stacked,
        grid: { color: GRID, drawTicks: false },
        border: { display: false },
        ticks: { padding: 8, precision: 0, callback: function (v) { return fmt(v, spec.suffix); } },
      };
      const categoryAxis = {
        stacked: !!spec.stacked,
        grid: { display: false },
        border: { color: GRID },
        ticks: { color: TEXT, autoSkip: (spec.labels || []).length > 12, maxRotation: 0 },
      };
      options.indexAxis = spec.horizontal ? "y" : "x";
      options.scales = spec.horizontal ? { x: valueAxis, y: categoryAxis } : { x: categoryAxis, y: valueAxis };
    } else {
      options.cutout = "68%";
    }
    const labels = (type === "doughnut" || spec.horizontal) ? spec.labels
      : (spec.labels || []).map(function (l) { return wrapLabel(l, labelWidth(width, (spec.labels || []).length)); });
    if (type !== "doughnut") {
      options.plugins.tooltip.callbacks.title = function (items) {
        const l = items[0] && items[0].label;
        return Array.isArray(l) ? l.join(" ") : l;
      };
    }
    return { type: type, data: { labels: labels, datasets: datasets }, options: options };
  }

  document.querySelectorAll("canvas[data-chart]").forEach(function (canvas) {
    const el = document.getElementById(canvas.dataset.chart);
    if (!el) return;
    try {
      new Chart(canvas, build(JSON.parse(el.textContent), canvas.parentElement.clientWidth));
    } catch (err) {
      console.error("Grafikni chizib bo‘lmadi", err);
    }
  });
})();
