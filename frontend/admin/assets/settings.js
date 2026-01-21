(function () {
  if (!window.AdminAuth) return;
  AdminAuth.requireToken();

  const dataset = document.body.dataset || {};
  const settingsEndpoint = dataset.settingsEndpoint || "/api/settings";
  const statsHref = dataset.statsHref || "/ui/stats";
  const dashboardHref = dataset.dashboardHref || "/ui/static/admin/dashboard.html";
  const galleryHref = dataset.galleryHref || "/ui/static/admin/gallery.html";
  const defaultProviders =
    dataset.providers?.split(",").map((item) => item.trim()).filter(Boolean) || [
      "gemini",
      "turbotext",
      "gpt-image-1.5",
    ];

  const form = document.getElementById("settings-form");
  const statusEl = document.getElementById("settings-status");
  const providerList = document.getElementById("provider-keys");
  const rotatedMeta = document.getElementById("password-meta");
  const syncInput = document.getElementById("sync-response");
  const ttlInput = document.getElementById("ttl-hours");
  const passwordInput = document.getElementById("ingest-password");
  const FIELD_MAP = {
    sync_response_seconds: "#sync-response",
    result_ttl_hours: "#ttl-hours",
    ingest_password: "#ingest-password",
  };

  let initialValues = null;

  setupToolbar();
  loadSettings();

  function setupToolbar() {
    const statsBtn = document.querySelector('[data-action="go-stats"]');
    const slotsBtn = document.querySelector('[data-action="go-slots"]');
    const galleryBtn = document.querySelector('[data-action="go-gallery"]');
    const logoutBtn = document.querySelector('[data-action="logout"]');

    statsBtn && statsBtn.addEventListener("click", () => (window.location.href = statsHref));
    slotsBtn && slotsBtn.addEventListener("click", () => (window.location.href = dashboardHref));
    galleryBtn && galleryBtn.addEventListener("click", () => (window.location.href = galleryHref));
    logoutBtn && logoutBtn.addEventListener("click", () => {
      AdminAuth.clearToken();
      window.location.replace(AdminAuth.getLoginPath());
    });
  }

  async function loadSettings() {
    setStatus("Загружаем настройки…", "info");
    try {
      const response = await AdminAuth.authFetch(settingsEndpoint);
      if (!response.ok) throw new Error("Не удалось получить настройки");
      const payload = await response.json();
      applySettings(payload);
      setStatus("", "info");
    } catch (error) {
      setStatus(error && error.message ? error.message : "Ошибка загрузки", "error");
    }
  }

  function applySettings(payload) {
    initialValues = payload;
    if (syncInput) syncInput.value = payload.sync_response_seconds;
    if (ttlInput) ttlInput.value = payload.result_ttl_hours;
    if (passwordInput) passwordInput.value = payload.ingest_password || "";
    if (rotatedMeta) {
      if (payload.ingest_password_rotated_at) {
        const rotatedAt = formatDate(payload.ingest_password_rotated_at);
        const rotatedBy = payload.ingest_password_rotated_by || "admin";
        rotatedMeta.textContent = "Пароль обновлён " + rotatedAt + " (" + rotatedBy + ")";
      } else {
        rotatedMeta.textContent = "Пароль ещё не ротировался";
      }
    }
    renderProviderKeys(payload.provider_keys || {});
  }

  function renderProviderKeys(map) {
    if (!providerList) return;
    providerList.innerHTML = "";
    const providers = Array.from(new Set([...Object.keys(map), ...defaultProviders].filter(Boolean)));
    if (!providers.length) {
      providers.push("provider");
    }
    providers.forEach((name) => {
      const li = document.createElement("li");
      const status = map[name];
      const title = document.createElement("div");
      title.className = "provider-title";
      title.textContent = name;

      const meta = document.createElement("div");
      meta.className = "provider-meta";
      meta.textContent = status && status.configured
        ? "Ключ настроен · обновлён " + (status.updated_at ? formatDate(status.updated_at) : "ранее")
        : "Ключ не настроен";

      const input = document.createElement("input");
      input.type = "password";
      input.placeholder = "Новый ключ";
      input.dataset.provider = name;

      li.appendChild(title);
      li.appendChild(meta);
      li.appendChild(input);
      providerList.appendChild(li);
    });
  }

  if (form) {
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      clearFieldErrors();
      const payload = buildPayload();
      if (!payload) {
        setStatus("Нет изменений", "info");
        return;
      }
      try {
        setStatus("Сохраняем…", "info");
        const response = await AdminAuth.authFetch(settingsEndpoint, {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
        if (!response.ok) {
          if (response.status === 422) {
            let details = {};
            try {
              details = await response.json();
            } catch (err) {
              /* ignore */
            }
            const applied = applyFieldErrors(details);
            if (!applied && details && typeof details.detail === "string") {
              setStatus(details.detail, "error");
            } else {
              setStatus("Исправьте выделенные поля.", "error");
            }
            return;
          }
          let message = "Не удалось сохранить";
          try {
            const err = await response.json();
            message = err && err.detail ? err.detail : message;
          } catch (err) {
            /* ignore */
          }
          throw new Error(message);
        }
        const updated = await response.json();
        applySettings(updated);
        if (providerList) {
          providerList.querySelectorAll('input[data-provider]').forEach((input) => {
            input.value = "";
          });
        }
        clearFieldErrors();
        setStatus("Настройки сохранены", "success");
      } catch (error) {
        setStatus(error && error.message ? error.message : "Ошибка сохранения", "error");
      }
    });
  }

  function buildPayload() {
    if (!initialValues) return null;
    const payload = {};
    if (syncInput) {
      const syncVal = Number(syncInput.value);
      if (!Number.isNaN(syncVal) && syncVal !== initialValues.sync_response_seconds) {
        payload.sync_response_seconds = syncVal;
      }
    }
    if (ttlInput) {
      const ttlVal = Number(ttlInput.value);
      if (!Number.isNaN(ttlVal) && ttlVal !== initialValues.result_ttl_hours) {
        payload.result_ttl_hours = ttlVal;
      }
    }
    if (passwordInput) {
      const pwdVal = passwordInput.value.trim();
      if (pwdVal !== initialValues.ingest_password) {
        payload.ingest_password = pwdVal;
      }
    }
    if (providerList) {
      const providerPayload = {};
      providerList.querySelectorAll('input[data-provider]').forEach((input) => {
        const value = input.value.trim();
        if (value) {
          providerPayload[input.dataset.provider] = value;
        }
      });
      if (Object.keys(providerPayload).length) {
        payload.provider_keys = providerPayload;
      }
    }
    return Object.keys(payload).length ? payload : null;
  }

  function setStatus(message, kind) {
    if (!statusEl) return;
    statusEl.textContent = message || "";
    statusEl.className = kind === "success" ? "form-success" : kind === "error" ? "form-error" : "muted-hint";
  }

  function clearFieldErrors() {
    if (!form) return;
    form.querySelectorAll(".has-error").forEach((node) => {
      node.classList.remove("has-error");
      node.removeAttribute("aria-invalid");
      node.removeAttribute("title");
    });
  }

  function normalizeIssues(payload) {
    if (!payload) return [];
    if (Array.isArray(payload.errors)) return payload.errors;
    if (Array.isArray(payload.detail)) return payload.detail;
    return [];
  }

  function fieldSelector(path) {
    if (!path) return null;
    if (FIELD_MAP[path]) return FIELD_MAP[path];
    if (path.startsWith("provider_keys.")) {
      const [, provider] = path.split(".");
      if (provider) {
        return `input[data-provider="${provider}"]`;
      }
    }
    return null;
  }

  function deriveFieldPath(issue) {
    if (issue.field) return issue.field;
    if (!Array.isArray(issue.loc)) return "";
    const filtered = issue.loc.filter(Boolean).filter((part) => part !== "body");
    return filtered.join(".");
  }

  function applyFieldErrors(payload) {
    if (!form) return false;
    const issues = normalizeIssues(payload);
    if (!issues.length) return false;
    let applied = false;
    issues.forEach((issue) => {
      const path = deriveFieldPath(issue);
      const selector = fieldSelector(path);
      if (!selector) return;
      const el = form.querySelector(selector);
      if (!el) return;
      applied = true;
      el.classList.add("has-error");
      el.setAttribute("aria-invalid", "true");
      const message = issue.message || issue.msg;
      if (message) el.setAttribute("title", message);
    });
    return applied;
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
