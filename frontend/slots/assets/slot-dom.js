"use strict";
(function (ns) {
  const { elements, state } = ns;

  function formatDateTime(value) {
    if (!value) return "";
    try {
      const dt = new Date(value);
      if (Number.isNaN(dt.getTime())) return value;
      return new Intl.DateTimeFormat("ru-RU", { dateStyle: "medium", timeStyle: "short" }).format(dt);
    } catch (err) {
      return value;
    }
  }

  function renderRecentResults(list) {
    const grid = elements.resultsGrid;
    if (!grid) return;
    grid.innerHTML = "";
    const items = Array.isArray(list) ? list : [];
    if (!items.length) {
      if (elements.resultsEmpty) elements.resultsEmpty.style.display = "";
      return;
    }
    if (elements.resultsEmpty) elements.resultsEmpty.style.display = "none";
    items.forEach((item) => {
      const node = document.createElement("article");
      node.className = "slot-results__item";
      node.setAttribute("role", "listitem");

      const thumbWrap = document.createElement("div");
      thumbWrap.className = "slot-results__thumb-wrap";
      const img = document.createElement("img");
      img.className = "slot-results__thumb";
      img.loading = "lazy";
      img.decoding = "async";
      img.alt = "Превью результата обработки";
      img.src = item.thumbnail_url || item.download_url || "";
      thumbWrap.appendChild(img);

      const meta = document.createElement("div");
      meta.className = "slot-results__meta";
      const completed = document.createElement("strong");
      completed.textContent = `Завершено: ${formatDateTime(item.completed_at)}`;
      const expires = document.createElement("span");
      expires.textContent = `Ссылка активна до ${formatDateTime(item.result_expires_at)}`;
      const mime = document.createElement("span");
      mime.textContent = item.mime ? `Формат: ${item.mime}` : "";
      meta.appendChild(completed);
      meta.appendChild(expires);
      if (item.mime) meta.appendChild(mime);

      const actions = document.createElement("div");
      actions.className = "slot-results__actions";
      const downloadBtn = document.createElement("a");
      downloadBtn.className = "btn -ghost";
      downloadBtn.href = item.download_url || "#";
      downloadBtn.target = "_blank";
      downloadBtn.rel = "noopener noreferrer";
      downloadBtn.textContent = "Скачать";
      if (item.download_url) {
        downloadBtn.setAttribute("download", "");
      } else {
        downloadBtn.setAttribute("aria-disabled", "true");
        downloadBtn.classList.add("is-disabled");
      }
      actions.appendChild(downloadBtn);

      node.appendChild(thumbWrap);
      node.appendChild(meta);
      node.appendChild(actions);
      grid.appendChild(node);
    });
  }

  function setResultsError(message) {
    if (!elements.resultsError) return;
    if (message) {
      elements.resultsError.textContent = message;
      elements.resultsError.style.display = "";
    } else {
      elements.resultsError.textContent = "";
      elements.resultsError.style.display = "none";
    }
  }

  function toast(msg, type) {
    const box = elements.toast;
    if (!box) return;
    const item = document.createElement("div");
    item.className = `toast-item ${type || ""}`;
    item.textContent = msg;
    box.appendChild(item);
    requestAnimationFrame(() => item.classList.add("show"));
    setTimeout(() => {
      item.classList.remove("show");
      setTimeout(() => item.remove(), 300);
    }, 4200);
  }

  function clearFieldErrors() {
    document.querySelectorAll(".has-error").forEach((node) => {
      node.classList.remove("has-error");
      node.removeAttribute("aria-invalid");
      if (node.dataset && node.dataset.errorMessage) {
        delete node.dataset.errorMessage;
      }
    });
  }

  function normalizeIssues(payload) {
    if (!payload) return [];
    if (Array.isArray(payload.errors)) return payload.errors;
    if (Array.isArray(payload.detail)) return payload.detail;
    return [];
  }

  function deriveFieldPath(issue) {
    if (issue.field) return issue.field;
    if (!Array.isArray(issue.loc)) return "";
    const filtered = issue.loc.filter(Boolean).filter((part) => part !== "body");
    return filtered.join(".");
  }

  function applyFieldErrors(payload, fieldMap) {
    const issues = normalizeIssues(payload);
    if (!issues.length) return false;
    issues.forEach((issue) => {
      const fieldPath = deriveFieldPath(issue);
      const selector = fieldMap[fieldPath];
      if (!selector) return;
      const el = document.querySelector(selector);
      if (!el) return;
      el.classList.add("has-error");
      el.setAttribute("aria-invalid", "true");
      const message = issue.message || issue.msg;
      if (message) el.dataset.errorMessage = message;
    });
    return true;
  }

  function setStatus(name, present) {
    const el = document.getElementById(`${name}_status`);
    if (el) el.value = present ? "present" : "removed";
  }

  function show(el) {
    if (el) el.classList.add("show");
  }

  function hide(el) {
    if (el) el.classList.remove("show");
  }

  function pulse(el) {
    if (!el) return;
    el.classList.remove("-pulse");
    void el.offsetWidth;
    el.classList.add("-pulse");
  }

  function isValidFile(file) {
    if (!file) return false;
    const t = (file.type || "").toLowerCase();
    if (t === "image/jpeg" || t === "image/png" || t === "image/jpg" || t === "image/webp") return true;
    const name = (file.name || "").toLowerCase();
    return /(\.jpe?g|\.png|\.webp)$/.test(name);
  }

  ns.dom = {
    formatDateTime,
    renderRecentResults,
    setResultsError,
    toast,
    clearFieldErrors,
    applyFieldErrors,
    setStatus,
    show,
    hide,
    pulse,
    isValidFile,
  };
})(window.SlotPage || (window.SlotPage = {}));
