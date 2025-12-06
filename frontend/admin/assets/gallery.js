(function () {
  if (!window.AdminAuth) return;
  AdminAuth.requireToken();

  const dataset = document.body.dataset || {};
  const statsHref = dataset.statsHref || "/ui/stats";
  const settingsHref = dataset.settingsHref || "/ui/static/admin/settings.html";
  const dashboardHref = dataset.dashboardHref || "/ui/static/admin/dashboard.html";
  const slotBase = dataset.slotEndpointBase || "/api/slots/";
  const resultsLimit = Number(dataset.resultsLimit || 10);
  const shareEndpoint = dataset.shareEndpoint || "/api/gallery/share";
  const publicGalleryUrl = dataset.publicGalleryUrl || "/pubgallery";
  const rateLimitHint = dataset.rateLimitHint || "Лимит: 30 запросов в минуту.";

  const listEl = document.getElementById("gallery-list");
  const statusEl = document.getElementById("gallery-status");
  const reloadBtn = document.getElementById("gallery-reload");
  const shareBtn = document.getElementById("share-gallery");
  const shareHint = document.getElementById("gallery-share-hint");

  const slotIds = Array.from({ length: 15 }, (_, i) => `slot-${String(i + 1).padStart(3, "0")}`);

  setupToolbar();
  buildSkeleton();
  loadAllSlots();
  if (reloadBtn) reloadBtn.addEventListener("click", loadAllSlots);
  if (shareBtn) shareBtn.addEventListener("click", sharePublicGallery);
  if (shareHint) shareHint.textContent = rateLimitHint + ` Ссылка: ${publicGalleryUrl}`;

  function setupToolbar() {
    const slotsBtn = document.querySelector('[data-action="go-slots"]');
    const statsBtn = document.querySelector('[data-action="go-stats"]');
    const settingsBtn = document.querySelector('[data-action="go-settings"]');
    const galleryBtn = document.querySelector('[data-action="go-gallery"]');
    const logoutBtn = document.querySelector('[data-action="logout"]');

    galleryBtn && galleryBtn.classList.add("is-active");
    slotsBtn && slotsBtn.addEventListener("click", () => (window.location.href = dashboardHref));
    statsBtn && statsBtn.addEventListener("click", () => (window.location.href = statsHref));
    settingsBtn && settingsBtn.addEventListener("click", () => (window.location.href = settingsHref));
    logoutBtn &&
      logoutBtn.addEventListener("click", () => {
        AdminAuth.clearToken();
        window.location.replace(AdminAuth.getLoginPath());
      });
  }

  function buildSkeleton() {
    if (!listEl) return;
    listEl.innerHTML = "";
    slotIds.forEach((slotId) => listEl.appendChild(createSlotCard(slotId)));
  }

  function createSlotCard(slotId) {
    const details = document.createElement("details");
    details.className = "gallery-slot";
    details.dataset.slotId = slotId;

    const summary = document.createElement("summary");
    const titleWrap = document.createElement("div");
    titleWrap.className = "gallery-title";
    const title = document.createElement("div");
    title.textContent = slotId;
    const meta = document.createElement("small");
    meta.textContent = "Загружаем…";
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
    placeholder.textContent = "Загружаем…";
    body.appendChild(placeholder);

    details.appendChild(summary);
    details.appendChild(body);
    return details;
  }

  async function loadAllSlots() {
    setStatus("Загружаем галерею…");
    if (listEl) {
      listEl.querySelectorAll(".gallery-empty").forEach((node) => (node.textContent = "Загружаем…"));
    }
    const results = await Promise.allSettled(
      slotIds.map((slotId) =>
        loadSlot(slotId).catch((err) => {
          renderError(slotId, err && err.message ? err.message : "Не удалось загрузить слот");
          throw err;
        })
      )
    );
    const failed = results.filter((r) => r.status === "rejected").length;
    if (failed) {
      setStatus(`Не загрузились ${failed} из ${slotIds.length} слотов.`);
    } else {
      setStatus("Галерея обновлена.");
      setTimeout(() => setStatus(""), 1800);
    }
  }

  async function loadSlot(slotId) {
    const url = buildSlotUrl(slotId);
    const response = await AdminAuth.authFetch(url);
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }
    const data = await response.json();
    renderSlot(data);
    return true;
  }

  function renderSlot(payload) {
    if (!payload || !payload.slot_id) return;
    const card = listEl?.querySelector(`[data-slot-id="${payload.slot_id}"]`);
    if (!card) return;
    const title = card.querySelector(".gallery-title div");
    const meta = card.querySelector(".gallery-title small");
    const hint = card.querySelector(".gallery-meta");
    const body = card.querySelector(".gallery-body");

    if (title) title.textContent = payload.display_name || payload.slot_id;
    if (meta) {
      const parts = [];
      parts.push(payload.slot_id);
      if (payload.provider) parts.push(payload.provider);
      if (payload.operation) parts.push(payload.operation);
      meta.textContent = parts.join(" · ");
    }
    if (hint) {
      hint.textContent = payload.is_active ? "Активен" : "Отключен";
    }
    if (!body) return;

    const mergedResults = [];
    if (payload.latest_result) {
      mergedResults.push(payload.latest_result);
    }
    if (Array.isArray(payload.recent_results)) {
      for (const item of payload.recent_results) {
        if (!item) continue;
        if (mergedResults.find((r) => r.job_id === item.job_id)) continue;
        mergedResults.push(item);
        if (mergedResults.length >= resultsLimit) break;
      }
    }

    const ready = mergedResults.filter((item) => item && (item.download_url || item.public_url));
    if (!ready.length) {
      body.innerHTML = '<p class="gallery-empty">Нет готовых результатов.</p>';
      return;
    }

    const grid = document.createElement("div");
    grid.className = "slot-results__grid";
    ready.forEach((item) => grid.appendChild(buildResultCard(item)));

    body.innerHTML = "";
    body.appendChild(grid);
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
    completed.textContent = "Завершено: " + formatDate(item.finished_at || item.completed_at);
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

  function renderError(slotId, message) {
    const card = listEl?.querySelector(`[data-slot-id="${slotId}"]`);
    if (!card) return;
    const meta = card.querySelector(".gallery-title small");
    const body = card.querySelector(".gallery-body");
    if (meta) meta.textContent = "Ошибка загрузки";
    if (body) {
      body.innerHTML = `<p class="gallery-empty">Не удалось загрузить ${slotId}: ${message}</p>`;
    }
  }

  function buildSlotUrl(slotId) {
    if (!slotId) return "/api/slots";
    const base = slotBase.endsWith("/") ? slotBase.slice(0, -1) : slotBase;
    return `${base}/${slotId}`;
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

  async function sharePublicGallery() {
    if (!shareEndpoint) return;
    if (shareBtn) {
      shareBtn.disabled = true;
      shareBtn.textContent = "Активируем…";
    }
    setStatus("Активируем публичный доступ…");
    try {
      const resp = await AdminAuth.authFetch(shareEndpoint, { method: "POST" });
      if (!resp.ok) {
        throw new Error("Не удалось активировать ссылку");
      }
      const data = await resp.json();
      const until = data.share_until ? formatDate(data.share_until) : "";
      setStatus(`Публичный доступ включён${until ? " до " + until : ""}. Ссылка: ${publicGalleryUrl}`);
      if (shareHint) {
        shareHint.textContent = `${rateLimitHint}. Ссылка: ${publicGalleryUrl}`;
      }
    } catch (err) {
      setStatus(err && err.message ? err.message : "Ошибка активации", "error");
    } finally {
      if (shareBtn) {
        shareBtn.disabled = false;
        shareBtn.textContent = "Расшарить на 15 минут";
      }
    }
  }
})();
