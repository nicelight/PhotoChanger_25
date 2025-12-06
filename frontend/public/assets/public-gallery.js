(function () {
  const dataset = document.body.dataset || {};
  const endpoint = dataset.publicGalleryEndpoint || "/pub/gallery";
  const listEl = document.getElementById("public-list");
  const statusEl = document.getElementById("public-status");
  const reloadBtn = document.getElementById("public-reload");

  if (reloadBtn) reloadBtn.addEventListener("click", loadGallery);
  buildSkeleton();
  loadGallery();

  function buildSkeleton() {
    if (!listEl) return;
    listEl.innerHTML = "";
    const fragment = document.createDocumentFragment();
    for (let i = 1; i <= 15; i += 1) {
      const slotId = `slot-${String(i).padStart(3, "0")}`;
      fragment.appendChild(createSlotCard(slotId, true));
    }
    listEl.appendChild(fragment);
  }

  function createSlotCard(slotId, loading) {
    const details = document.createElement("details");
    details.className = "gallery-slot";
    details.dataset.slotId = slotId;
    if (loading) details.open = false;

    const summary = document.createElement("summary");
    const titleWrap = document.createElement("div");
    titleWrap.className = "gallery-title";
    const title = document.createElement("div");
    title.textContent = slotId;
    const meta = document.createElement("small");
    meta.textContent = loading ? "Загружаем…" : "";
    titleWrap.appendChild(title);
    titleWrap.appendChild(meta);

    const hint = document.createElement("div");
    hint.className = "gallery-meta";
    hint.textContent = "Разверните, чтобы увидеть превью";

    summary.appendChild(titleWrap);
    summary.appendChild(hint);
    summary.setAttribute("aria-label", "Галерея слота " + slotId);

    const body = document.createElement("div");
    body.className = "gallery-body";
    const placeholder = document.createElement("p");
    placeholder.className = "gallery-empty";
    placeholder.textContent = loading ? "Загружаем…" : "Нет данных";
    body.appendChild(placeholder);

    details.appendChild(summary);
    details.appendChild(body);
    return details;
  }

  async function loadGallery() {
    setStatus("Загружаем галерею…");
    try {
      const resp = await fetch(endpoint);
      if (resp.status === 403) {
        setStatus("Ссылка больше не активна. Обратитесь к администратору.", "error");
        renderInactive();
        return;
      }
      if (resp.status === 429) {
        setStatus("Слишком часто. Повторите позже.", "error");
        return;
      }
      if (!resp.ok) {
        throw new Error("HTTP " + resp.status);
      }
      const data = await resp.json();
      renderGallery(data);
      setStatus("Данные обновлены.");
      setTimeout(() => setStatus(""), 1800);
    } catch (err) {
      setStatus("Не удалось загрузить публичную галерею.", "error");
    }
  }

  function renderInactive() {
    if (!listEl) return;
    listEl.innerHTML = '<p class="gallery-empty">Публичный доступ отключён.</p>';
  }

  function renderGallery(payload) {
    if (!payload || !Array.isArray(payload.slots)) {
      renderInactive();
      return;
    }
    if (!listEl) return;
    listEl.innerHTML = "";
    const fragment = document.createDocumentFragment();
    payload.slots.forEach((slot) => fragment.appendChild(renderSlot(slot)));
    listEl.appendChild(fragment);
  }

  function renderSlot(slot) {
    const details = createSlotCard(slot.slot_id, false);
    const title = details.querySelector(".gallery-title div");
    const meta = details.querySelector(".gallery-title small");
    const hint = details.querySelector(".gallery-meta");
    const body = details.querySelector(".gallery-body");
    if (title) title.textContent = slot.display_name || slot.slot_id;
    if (meta) {
      const parts = [];
      parts.push(slot.slot_id);
      if (slot.provider) parts.push(slot.provider);
      if (slot.operation) parts.push(slot.operation);
      meta.textContent = parts.join(" · ");
    }
    if (hint) {
      hint.textContent = slot.is_active ? "Активен" : "Отключен";
    }
    if (!body) return details;

    const mergedResults = [];
    if (slot.latest_result) {
      mergedResults.push(slot.latest_result);
    }
    if (Array.isArray(slot.recent_results)) {
      slot.recent_results.forEach((item) => {
        if (!item) return;
        if (mergedResults.find((r) => r.job_id === item.job_id)) return;
        mergedResults.push(item);
      });
    }

    const ready = mergedResults.filter((item) => item && (item.download_url || item.public_url));
    if (!ready.length) {
      body.innerHTML = '<p class="gallery-empty">Нет готовых результатов.</p>';
      return details;
    }

    const grid = document.createElement("div");
    grid.className = "slot-results__grid";
    ready.forEach((item) => grid.appendChild(buildResultCard(item)));
    body.innerHTML = "";
    body.appendChild(grid);
    return details;
  }

  function buildResultCard(item) {
    const node = document.createElement("article");
    node.className = "slot-results__item";

    const thumbWrap = document.createElement("div");
    thumbWrap.className = "slot-results__thumb-wrap";
    const link = document.createElement("a");
    link.className = "slot-results__thumb-link";
    link.href = item.download_url || item.public_url || "#";
    link.target = "_blank";
    link.rel = "noopener noreferrer";
    const img = document.createElement("img");
    img.className = "slot-results__thumb";
    img.loading = "lazy";
    img.decoding = "async";
    img.alt = "Превью результата обработки";
    img.src = item.thumbnail_url || item.download_url || item.public_url || "";
    link.appendChild(img);
    thumbWrap.appendChild(link);

    const meta = document.createElement("div");
    meta.className = "slot-results__meta";
    const completed = document.createElement("strong");
    completed.textContent = "Завершено: " + formatDate(item.finished_at);
    meta.appendChild(completed);
    if (item.job_id) {
      const job = document.createElement("span");
      job.className = "job-id";
      job.textContent = "Job ID: " + item.job_id;
      meta.appendChild(job);
    }
    if (item.result_expires_at || item.expires_at) {
      const expires = document.createElement("span");
      expires.textContent = "Активно до " + formatDate(item.result_expires_at || item.expires_at);
      meta.appendChild(expires);
    }
    if (item.mime) {
      const mime = document.createElement("span");
      mime.textContent = "Формат: " + item.mime;
      meta.appendChild(mime);
    }
    if (item.status) {
      const status = document.createElement("span");
      status.textContent = "Статус: " + item.status;
      meta.appendChild(status);
    }

    const actions = document.createElement("div");
    actions.className = "slot-results__actions";
    const downloadBtn = document.createElement("a");
    downloadBtn.className = "btn -ghost";
    downloadBtn.textContent = "Скачать";
    if (item.download_url || item.public_url) {
      downloadBtn.href = item.download_url || item.public_url;
      downloadBtn.target = "_blank";
      downloadBtn.rel = "noopener noreferrer";
      downloadBtn.setAttribute("download", "");
    } else {
      downloadBtn.setAttribute("aria-disabled", "true");
      downloadBtn.classList.add("is-disabled");
    }
    actions.appendChild(downloadBtn);

    node.appendChild(thumbWrap);
    node.appendChild(meta);
    node.appendChild(actions);
    return node;
  }

  function formatDate(value) {
    if (!value) return "—";
    try {
      const date = new Date(value);
      if (Number.isNaN(date.getTime())) return value;
      return new Intl.DateTimeFormat("ru-RU", { dateStyle: "medium", timeStyle: "short" }).format(date);
    } catch (err) {
      return value;
    }
  }

  function setStatus(message, kind) {
    if (!statusEl) return;
    statusEl.textContent = message || "";
    statusEl.className = kind === "error" ? "form-error" : "muted-hint";
  }
})();
