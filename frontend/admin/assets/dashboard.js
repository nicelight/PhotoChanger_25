(function () {
  if (!window.AdminAuth) return;
  AdminAuth.requireToken();

  const dataset = document.body.dataset || {};
  const slotsEndpoint = dataset.slotsEndpoint || "/api/slots";
  const ingestTemplate = dataset.ingestTemplate || "/api/ingest/{slot_id}";
  const slotPageBase = dataset.slotPage || "/ui/static/slots";
  const statsHref = dataset.statsHref || "/ui/stats";
  const settingsHref = dataset.settingsHref || "/ui/static/admin/settings.html";
  const galleryHref = dataset.galleryHref || "/ui/static/admin/gallery.html";

  const listEl = document.getElementById("slots-list");
  const errorEl = document.getElementById("slots-error");
  const emptyEl = document.getElementById("slots-empty");
  const reloadBtn = document.getElementById("reload-slots");

  setupToolbar();
  loadSlots();

  if (reloadBtn) reloadBtn.addEventListener("click", loadSlots);

  function setupToolbar() {
    const statsBtn = document.querySelector('[data-action="go-stats"]');
    const galleryBtn = document.querySelector('[data-action="go-gallery"]');
    const settingsBtn = document.querySelector('[data-action="go-settings"]');
    const logoutBtn = document.querySelector('[data-action="logout"]');

    statsBtn && statsBtn.addEventListener("click", () => (window.location.href = statsHref));
    galleryBtn && galleryBtn.addEventListener("click", () => (window.location.href = galleryHref));
    settingsBtn && settingsBtn.addEventListener("click", () => (window.location.href = settingsHref));
    logoutBtn && logoutBtn.addEventListener("click", () => {
      AdminAuth.clearToken();
      window.location.replace(AdminAuth.getLoginPath());
    });
  }

  function showError(message) {
    if (!errorEl) return;
    errorEl.textContent = message;
    errorEl.hidden = !message;
  }

  async function loadSlots() {
    showError("");
    try {
      const response = await AdminAuth.authFetch(slotsEndpoint);
      if (!response.ok) {
        throw new Error("Не удалось загрузить список слотов");
      }
      const slots = await response.json();
      renderSlots(Array.isArray(slots) ? slots : []);
    } catch (error) {
      showError(error && error.message ? error.message : "Ошибка загрузки данных");
      renderSlots([]);
    }
  }

  function renderSlots(slots) {
    if (!listEl) return;
    listEl.innerHTML = "";
    if (!slots.length) {
      if (emptyEl) emptyEl.hidden = false;
      return;
    }
    if (emptyEl) emptyEl.hidden = true;
    const fragment = document.createDocumentFragment();
    slots.forEach((slot) => fragment.appendChild(buildRow(slot)));
    listEl.appendChild(fragment);
  }

  function buildRow(slot) {
    const article = document.createElement("article");
    article.className = "slot-row";

    const body = document.createElement("div");
    body.className = "slot-row__body";

    const title = document.createElement("a");
    title.className = "slot-row__title";
    title.textContent = slot.display_name || slot.slot_id;
    const pageBase = slotPageBase.endsWith("/") ? slotPageBase.slice(0, -1) : slotPageBase;
    title.href = pageBase + "/" + slot.slot_id + ".html";
    title.setAttribute("aria-label", "Открыть настройки слота " + slot.slot_id);

    const meta = document.createElement("div");
    meta.className = "slot-row__meta";
    const updated = slot.updated_at ? formatDate(slot.updated_at) : "—";
    meta.textContent = "Последнее обновление: " + updated + " · Провайдер: " + slot.provider + " · Операция: " + slot.operation;

    body.appendChild(title);
    body.appendChild(meta);

    const ingestWrap = document.createElement("label");
    ingestWrap.className = "ingest-field";
    ingestWrap.setAttribute("aria-label", "Ingest ссылка слота " + slot.slot_id);

    const input = document.createElement("input");
    input.type = "text";
    input.readOnly = true;
    input.value = toIngestLink(slot.slot_id);

    const copyBtn = document.createElement("button");
    copyBtn.type = "button";
    copyBtn.textContent = "Копировать";
    copyBtn.addEventListener("click", () => copyLink(input.value, copyBtn));

    ingestWrap.appendChild(input);
    ingestWrap.appendChild(copyBtn);

    const actions = document.createElement("div");
    actions.className = "slot-row__actions";

    const status = document.createElement("span");
    status.className = "status-pill";
    status.textContent = slot.is_active ? "Активен" : "Отключен";

    const editBtn = document.createElement("button");
    editBtn.className = "icon-btn";
    editBtn.type = "button";
    editBtn.setAttribute("aria-label", "Открыть слот " + slot.slot_id);
    editBtn.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M15.232 5.232 18.768 8.768"/><path d="M16 13v6a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V10a2 2 0 0 1 2-2h6"/><path d="m8 16 9-9"/></svg>';
    editBtn.addEventListener("click", () => {
      window.location.href = pageBase + "/" + slot.slot_id + ".html";
    });

    actions.appendChild(status);
    actions.appendChild(editBtn);

    article.appendChild(body);
    article.appendChild(ingestWrap);
    article.appendChild(actions);

    return article;
  }

  function toIngestLink(slotId) {
    if (!slotId) return "";
    if (ingestTemplate.indexOf("{slot_id}") >= 0) {
      return ingestTemplate.replace("{slot_id}", slotId);
    }
    const needsSlash = ingestTemplate.endsWith("/") ? "" : "/";
    return ingestTemplate + needsSlash + slotId;
  }

  function copyLink(value, button) {
    if (!value) return;
    if (!navigator.clipboard) {
      fallbackCopy(value, button);
      return;
    }
    navigator.clipboard.writeText(value).then(
      () => {
        button.textContent = "Скопировано";
        setTimeout(() => (button.textContent = "Копировать"), 1600);
      },
      () => {
        fallbackCopy(value, button);
      }
    );
  }

  function fallbackCopy(value, button) {
    const textArea = document.createElement("textarea");
    textArea.value = value;
    textArea.style.position = "fixed";
    document.body.appendChild(textArea);
    textArea.focus();
    textArea.select();
    try {
      document.execCommand("copy");
      button.textContent = "Скопировано";
    } catch (err) {
      button.textContent = "Ошибка";
    }
    setTimeout(() => (button.textContent = "Копировать"), 1600);
    document.body.removeChild(textArea);
  }

  function formatDate(value) {
    try {
      const date = new Date(value);
      return new Intl.DateTimeFormat("ru-RU", {
        dateStyle: "medium",
        timeStyle: "short",
      }).format(date);
    } catch (err) {
      return value;
    }
  }
})();
