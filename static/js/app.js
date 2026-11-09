/* Refleksiv portfolio — umumiy interfeys skriptlari (Vanilla JS) */
(function () {
  "use strict";

  function humanSize(bytes) {
    if (!bytes) return "0 B";
    const units = ["B", "KB", "MB", "GB"];
    let i = 0, size = bytes;
    while (size >= 1024 && i < units.length - 1) { size /= 1024; i++; }
    return (i === 0 ? size : size.toFixed(1)) + " " + units[i];
  }

  /* --- Sidebar (mobil) --- */
  document.addEventListener("click", function (e) {
    if (e.target.closest("[data-sidebar-toggle]")) {
      document.body.classList.toggle("sidebar-open");
    } else if (e.target.classList.contains("sidebar-backdrop") || e.target.closest(".app-sidebar a")) {
      document.body.classList.remove("sidebar-open");
    }
  });
  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape") document.body.classList.remove("sidebar-open");
  });
  window.addEventListener("resize", function () {
    if (window.innerWidth >= 992) document.body.classList.remove("sidebar-open");
  });

  /* --- Mobil: ro'yxat jadvallari kartaga aylanadi; har bir katakka ustun nomi (data-label) qo'yiladi --- */
  document.querySelectorAll("table.table-stack").forEach(function (table) {
    const heads = Array.from(table.querySelectorAll("thead th")).map(function (th) { return th.textContent.trim(); });
    table.querySelectorAll("tbody tr").forEach(function (row) {
      Array.from(row.children).forEach(function (cell, i) {
        if (cell.hasAttribute("colspan")) return;
        if (!cell.textContent.trim()) {
          // matn yo'q: faqat tugma/belgi bo'lsa — yorliqsiz (amallar), aks holda bo'sh katak kartada ko'rsatilmaydi
          if (!cell.querySelector("img,svg,i,button,a,input,select")) cell.classList.add("cell-empty");
        } else if (heads[i]) {
          cell.setAttribute("data-label", heads[i]);
        }
      });
    });
  });

  /* --- Tasdiqlash (data-confirm) --- */
  document.addEventListener("submit", function (e) {
    const form = e.target;
    const msg = form.getAttribute("data-confirm") ||
      (e.submitter && e.submitter.getAttribute("data-confirm"));
    if (msg && !window.confirm(msg)) {
      e.preventDefault();
      return;
    }
    // Ikki marta yuborishning oldini olish
    if (!e.defaultPrevented && !form.hasAttribute("data-allow-resubmit")) {
      const buttons = form.querySelectorAll("button[type=submit], input[type=submit]");
      window.setTimeout(function () {
        buttons.forEach(function (b) { b.disabled = true; });
      }, 0);
      const progress = form.querySelector("[data-upload-progress]");
      if (progress && form.querySelector("input[type=file]")) progress.classList.remove("d-none");
    }
  });

  /* --- Drag & drop fayl yuklash --- */
  function initDropzone(input) {
    if (input.dataset.dzReady) return;
    input.dataset.dzReady = "1";
    const maxMb = parseInt(input.dataset.maxMb || document.body.dataset.maxUploadMb || "0", 10);
    const maxVideoMb = parseInt(document.body.dataset.maxVideoMb || "0", 10);
    const zone = document.createElement("div");
    zone.className = "dropzone";
    zone.innerHTML =
      '<div class="dz-icon"><i class="bi bi-cloud-arrow-up"></i></div>' +
      '<div class="dz-title"></div>' +
      '<div class="dz-hint"></div><ul class="dz-files"></ul>';
    const t = document.body.dataset;
    zone.querySelector(".dz-title").textContent = t.i18nDropTitle || "";
    const hint = zone.querySelector(".dz-hint");
    const accept = input.getAttribute("accept");
    hint.textContent = (accept ? (t.i18nAllowed || "") + ": " + accept.replaceAll(",", ", ") : "") +
      (maxMb ? " · " + (t.i18nSize || "") + ": " + (t.i18nDocument || "") + " " + maxMb + " MB" +
        (maxVideoMb ? ", " + (t.i18nVideo || "") + " " + maxVideoMb + " MB" : "") : "");
    input.parentNode.insertBefore(zone, input);
    zone.appendChild(input);
    input.classList.remove("form-control");
    const list = zone.querySelector(".dz-files");

    function render() {
      list.innerHTML = "";
      Array.from(input.files).forEach(function (f) {
        const li = document.createElement("li");
        const isVideo = /^video\//.test(f.type);
        const limit = (isVideo ? maxVideoMb : maxMb) * 1024 * 1024;
        if (limit && f.size > limit) li.classList.add("too-big");
        const icon = document.createElement("i");
        icon.className = "bi " + (isVideo ? "bi-camera-video" : /^audio\//.test(f.type) ? "bi-music-note-beamed"
          : /^image\//.test(f.type) ? "bi-image" : "bi-file-earmark");
        const name = document.createElement("span");
        name.textContent = f.name;
        const size = document.createElement("span");
        size.className = "size";
        size.textContent = humanSize(f.size) + (li.classList.contains("too-big") ? " — juda katta" : "");
        li.append(icon, name, size);
        list.appendChild(li);
      });
    }

    zone.addEventListener("click", function (e) {
      if (e.target !== input) input.click();
    });
    ["dragenter", "dragover"].forEach(function (ev) {
      zone.addEventListener(ev, function (e) { e.preventDefault(); zone.classList.add("dragover"); });
    });
    ["dragleave", "drop"].forEach(function (ev) {
      zone.addEventListener(ev, function (e) { e.preventDefault(); zone.classList.remove("dragover"); });
    });
    zone.addEventListener("drop", function (e) {
      const dt = new DataTransfer();
      if (input.multiple) Array.from(input.files).forEach(function (f) { dt.items.add(f); });
      Array.from(e.dataTransfer.files).forEach(function (f) { dt.items.add(f); });
      input.files = dt.files;
      render();
    });
    input.addEventListener("change", render);
  }
  document.querySelectorAll("input[type=file][data-dropzone]").forEach(initDropzone);

  /* --- Baholash: jami ballni jonli hisoblash --- */
  const scoreInputs = document.querySelectorAll("[data-score-input]");
  if (scoreInputs.length) {
    const totalEl = document.querySelector("[data-score-total]");
    const barEl = document.querySelector("[data-score-bar]");
    const maxTotal = Array.from(scoreInputs).reduce(function (s, i) { return s + parseInt(i.dataset.max || "0", 10); }, 0);
    function recalc() {
      let total = 0;
      scoreInputs.forEach(function (i) {
        const v = parseInt(i.value || "0", 10);
        const max = parseInt(i.dataset.max || "0", 10);
        i.classList.toggle("is-invalid", v < 0 || v > max);
        total += isNaN(v) ? 0 : v;
        const bar = i.closest(".criterion-card") && i.closest(".criterion-card").querySelector(".progress-bar");
        if (bar && max) bar.style.width = Math.min(100, Math.max(0, v * 100 / max)) + "%";
      });
      if (totalEl) totalEl.textContent = total + " / " + maxTotal;
      if (barEl && maxTotal) barEl.style.width = Math.min(100, total * 100 / maxTotal) + "%";
    }
    scoreInputs.forEach(function (i) { i.addEventListener("input", recalc); });
    recalc();
  }

  /* --- Textarea avtomatik balandlik --- */
  document.querySelectorAll("textarea[data-autosize]").forEach(function (ta) {
    function fit() { ta.style.height = "auto"; ta.style.height = Math.max(ta.scrollHeight + 2, 96) + "px"; }
    ta.addEventListener("input", fit);
    fit();
  });

  /* --- Refleksiya: to'ldirilish darajasi va bosqichlar holati --- */
  const reflectionBox = document.querySelector("[data-reflection-progress]");
  if (reflectionBox) {
    const fields = Array.from(document.querySelectorAll("textarea[name^='q_']"));
    const text = reflectionBox.querySelector("[data-progress-text]");
    const bar = reflectionBox.querySelector("[data-progress-bar]");
    function updateProgress() {
      const done = fields.filter(function (f) { return f.value.trim(); }).length;
      if (text) text.textContent = done + " / " + fields.length;
      if (bar) bar.style.width = (fields.length ? Math.round(100 * done / fields.length) : 0) + "%";
      reflectionBox.querySelectorAll("[data-stage-chip]").forEach(function (chip) {
        const section = document.querySelector('[data-stage="' + chip.dataset.stageChip + '"]');
        const own = section ? Array.from(section.querySelectorAll("textarea")) : [];
        chip.classList.toggle("done", own.length > 0 && own.every(function (f) { return f.value.trim(); }));
      });
    }
    fields.forEach(function (f) { f.addEventListener("input", updateProgress); });
    updateProgress();
  }

  /* --- Jadvalni CSV ga eksport (import natijalari, parollar) --- */
  document.querySelectorAll("[data-export-table]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      const table = document.querySelector(btn.dataset.exportTable);
      if (!table) return;
      const rows = Array.from(table.querySelectorAll("tr")).map(function (tr) {
        return Array.from(tr.querySelectorAll("th,td")).map(function (c) {
          return '"' + c.innerText.replace(/"/g, '""').trim() + '"';
        }).join(";");
      });
      const blob = new Blob(["﻿" + rows.join("\n")], { type: "text/csv;charset=utf-8" });
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = btn.dataset.filename || "export.csv";
      a.click();
      URL.revokeObjectURL(a.href);
    });
  });

  /* --- Biriktirish turi: talaba / guruh --- */
  document.querySelectorAll("[data-target-switch]").forEach(function (wrap) {
    const radios = wrap.querySelectorAll("input[type=radio]");
    function apply() {
      const value = (wrap.querySelector("input[type=radio]:checked") || {}).value;
      document.querySelectorAll("[data-target-field]").forEach(function (el) {
        el.classList.toggle("d-none", el.dataset.targetField !== value);
      });
    }
    radios.forEach(function (r) { r.addEventListener("change", apply); });
    apply();
  });

  /* --- Bootstrap tooltip --- */
  if (window.bootstrap) {
    document.querySelectorAll('[data-bs-toggle="tooltip"]').forEach(function (el) {
      new bootstrap.Tooltip(el);
    });
  }
})();
