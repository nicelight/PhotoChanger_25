"use strict";
// slot-events.js: обработчики событий и сценарии UI.
(function (ns) {
  const { state, elements, providers, constants, endpoints, auth } = ns;
  const dom = ns.dom;
  const api = ns.api;
  const mapping = ns.mapping;

  function ensureAuth() {
    if (!auth || typeof auth.requireToken !== "function") {
      console.error("[SlotPage] AdminAuth is required for slot management UI.");
      dom.toast?.("Требуется авторизация администратора", "error");
      return false;
    }
    try {
      auth.requireToken();
      return true;
    } catch (err) {
      console.warn("[SlotPage] AdminAuth.requireToken failed", err);
      return false;
    }
  }

  function bindCopyButton() {
    if (!elements.copyButton || !elements.ingestInput) return;
    elements.copyButton.addEventListener("click", async () => {
      const value = (elements.ingestInput.value || "").trim();
      if (!value) {
        dom.toast("Нет ссылки для копирования", "error");
        return;
      }
      try {
        await navigator.clipboard.writeText(value);
        dom.toast("Ссылка скопирована", "success");
      } catch (e) {
        elements.ingestInput.select();
        document.execCommand("copy");
        dom.toast("Ссылка скопирована", "success");
      }
    });
  }

  function bindToggle(toggle, panel, onChange) {
    if (!toggle || !panel) return;
    const apply = () => {
      if (toggle.checked) {
        dom.show(panel);
      } else {
        dom.hide(panel);
        if (typeof onChange === "function") onChange(false);
      }
    };
    toggle.addEventListener("change", apply);
    apply();
  }

  function bindSlot(prefix) {
    const input = prefix === "second" ? elements.secondInput : elements.firstInput;
    const preview =
      prefix === "second" ? document.getElementById("preview-second") : document.getElementById("preview-first");
    const drop = prefix === "second" ? elements.secondDrop : elements.firstDrop;
    const err = prefix === "second" ? elements.secondError : elements.firstError;
    const statusField = prefix === "second" ? elements.secondStatus : elements.firstStatus;
    let url = null;

    function setErr(msg) {
      if (!err) return;
      err.textContent = msg || "";
      err.style.display = msg ? "block" : "none";
    }

    function clear() {
      if (url) {
        URL.revokeObjectURL(url);
        url = null;
      }
      if (preview) {
        preview.style.opacity = "0";
        preview.addEventListener(
          "transitionend",
          function hideOnFade(e) {
            if (e.propertyName === "opacity") {
              preview.style.display = "none";
              preview.removeEventListener("transitionend", hideOnFade);
            }
          }
        );
      }
      if (drop) {
        drop.classList.remove("has-image");
      }
      if (statusField) {
        statusField.value = "removed";
      }
      if (prefix === "second") {
        state.templateMediaState.pendingFile = null;
        state.templateMediaState.mediaId = "";
        if (elements.secondHiddenId) elements.secondHiddenId.value = "";
      }
      if (prefix === "first") {
        state.testImageState.file = null;
      }
    }

    function onFile(file) {
      if (!file) return;
      if (!dom.isValidFile(file)) {
        setErr("Неверный формат. Разрешены JPG/PNG/WebP.");
        if (input) input.value = "";
        clear();
        return;
      }
      setErr("");
      if (url) URL.revokeObjectURL(url);
      url = URL.createObjectURL(file);
      if (prefix === "second") {
        state.templateMediaState.pendingFile = file;
        state.templateMediaState.mediaId = "";
        if (elements.secondHiddenId) elements.secondHiddenId.value = "";
      }
      if (prefix === "first") {
        state.testImageState.file = file;
      }
      if (drop) drop.classList.add("has-image");
      if (preview) {
        preview.src = url;
        preview.style.display = "block";
        preview.style.opacity = "0";
        requestAnimationFrame(() => {
          preview.style.opacity = "1";
        });
      }
      if (statusField) statusField.value = "present";
    }

    if (input) {
      input.addEventListener("change", () => onFile(input.files && input.files[0]));
    }

    if (drop) {
      drop.addEventListener("click", (e) => {
        const target = e.target;
        if (target && target.getAttribute && target.getAttribute("data-action") === "remove") {
          e.preventDefault();
          e.stopPropagation();
          if (input) input.value = "";
          clear();
        }
      });
      drop.addEventListener("dragover", (e) => {
        e.preventDefault();
        drop.classList.add("dragging");
      });
      drop.addEventListener("dragenter", (e) => {
        e.preventDefault();
        drop.classList.add("dragging");
      });
      drop.addEventListener("dragleave", () => drop.classList.remove("dragging"));
      drop.addEventListener("drop", (e) => {
        e.preventDefault();
        drop.classList.remove("dragging");
        const file = e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files[0];
        if (file) {
          onFile(file);
          if (input) {
            const dt = new DataTransfer();
            dt.items.add(file);
            input.files = dt.files;
          }
        }
      });
    }
  }

  function bindProviderSelect() {
    if (!elements.providerSelect || !elements.operationSelect) return;
    elements.providerSelect.addEventListener("change", () => {
      const prov = elements.providerSelect.value;
      resetOperation();
      dom.updateImageConfigVisibility(prov);
      const config = providers[prov];
      if (!prov || !config) {
        state.slotMeta.provider = "";
        state.slotMeta.modelName = "";
        updateSlotHeader("");
        return;
      }
      const ops = config.operations || {};
      const frag = document.createDocumentFragment();
      Object.entries(ops).forEach(([key, meta]) => {
        const opt = document.createElement("option");
        opt.value = key;
        opt.textContent = meta.label;
        frag.appendChild(opt);
      });
      elements.operationSelect.appendChild(frag);
      elements.operationSelect.disabled = false;
      state.slotMeta.provider = prov;
      state.slotMeta.modelName =
        prov === state.slotMeta.provider && state.slotMeta.modelName
          ? state.slotMeta.modelName
          : config.label || prov;

      if (prov !== "turbotext") {
        const defaultOp =
          (ops && state.slotMeta.operation && ops[state.slotMeta.operation] && state.slotMeta.operation) ||
          ops[constants.GEMINI_DEFAULT_OPERATION]
            ? constants.GEMINI_DEFAULT_OPERATION
            : Object.keys(ops || {})[0];
        if (elements.operationSelectWrap) elements.operationSelectWrap.style.display = "none";
        setOperationValue(prov, defaultOp);
      } else {
        if (elements.operationSelectWrap) elements.operationSelectWrap.style.display = "";
        setOperationValue(prov, constants.TURBOTEXT_DEFAULT_OPERATION);
      }

      updateSlotHeader(prov);
    });
  }

  function bindOperationSelect() {
    if (!elements.operationSelect || !elements.providerSelect) return;
    elements.operationSelect.addEventListener("change", () => {
      const prov = elements.providerSelect.value;
      const op = elements.operationSelect.value;
      if (!prov || !op || !providers[prov] || !providers[prov].operations[op]) return;
      if (prov === "turbotext" && op !== constants.TURBOTEXT_DEFAULT_OPERATION) {
        dom.toast("Эта операция пока ещё не работает в Turbotext. Используйте Image2Image.", "error");
        elements.operationSelect.value = constants.TURBOTEXT_DEFAULT_OPERATION;
        setOperationValue(prov, constants.TURBOTEXT_DEFAULT_OPERATION);
        return;
      }
      setOperationValue(prov, op);
    });
  }

  function resetOperation() {
    if (!elements.operationSelect) return;
    elements.operationSelect.innerHTML = '<option value="" disabled selected>— выберите операцию —</option>';
    elements.operationSelect.disabled = true;
    state.slotMeta.operation = "";
    if (elements.requirementsHint) elements.requirementsHint.style.display = "none";
    if (elements.operationSelectWrap) elements.operationSelectWrap.style.display = "";
  }

  function setOperationValue(provider, opKey) {
    if (!provider || !opKey) return;
    const cfg = providers[provider];
    if (!cfg || !cfg.operations || !cfg.operations[opKey]) return;
    if (elements.operationSelect) elements.operationSelect.value = opKey;
    state.slotMeta.operation = opKey;
    applyNeeds(cfg.operations[opKey].needs);
  }

  function applyNeeds(needs) {
    const normalized = needs || { prompt: true, second: false, first: true };
    if (elements.promptInput) {
      const label = elements.promptInput.closest(".card")?.querySelector("label.title");
      if (label) {
        label.textContent = normalized.prompt ? "Промпт" : "Промпт (промпт опционален)";
      }
    }
    if (elements.requirementsHint) {
      const req = [];
      if (normalized.first) req.push("нужно «Фото для тестов»");
      if (normalized.second) req.push("нужно «Изображение — Шаблон стиля»");
      if (normalized.prompt) req.push("нужен текстовый промпт");
      elements.requirementsHint.textContent = req.length
        ? `Для выбранной операции: ${req.join("; ")}.`
        : "Для выбранной операции специальных требований нет.";
      elements.requirementsHint.style.display = "";
    }
  }

  function updateSlotHeader(providerOverride) {
    const provider = providerOverride || state.slotMeta.provider || "";
    const providerLabel = provider && ns.providers[provider]?.label ? ns.providers[provider].label : provider;
    const displayName = state.slotMeta.modelName || providerLabel || "— выберите провайдера —";
    if (elements.slotModelText) {
      const slugPart = provider ? ` (${provider})` : "";
      elements.slotModelText.textContent = `AI-модель: ${displayName}${slugPart}`;
    }
    if (elements.slotIdValue) elements.slotIdValue.textContent = state.slotMeta.id;
    if (elements.ingestInput) {
      const url = generateIngestURL(state.slotMeta.id);
      elements.ingestInput.value = url;
      if (elements.copyButton) elements.copyButton.disabled = !provider;
    }
  }

  function generateIngestURL(slotId) {
    if (!slotId || !endpoints.ingestBase) return "";
    const base = endpoints.ingestBase.endsWith("/") ? endpoints.ingestBase.slice(0, -1) : endpoints.ingestBase;
    return `${base}/${slotId}`;
  }

  function hydrateFromDataset() {
    if (!elements.slotModelText) return;
    updateSlotHeader(state.slotMeta.provider);
    if (state.slotMeta.provider && elements.providerSelect) {
      elements.providerSelect.value = state.slotMeta.provider;
      elements.providerSelect.dispatchEvent(new Event("change"));
      if (state.slotMeta.provider !== "turbotext" && state.slotMeta.operation) {
        setOperationValue(state.slotMeta.provider, state.slotMeta.operation);
      }
      if (state.slotMeta.provider === "turbotext" && state.slotMeta.operation) {
        elements.operationSelect.value = state.slotMeta.operation;
        elements.operationSelect.dispatchEvent(new Event("change"));
      }
    } else {
      updateSlotHeader("");
    }
  }

  function handleSecondToggle(enabled) {
    if (enabled === false) {
      if (elements.secondStatus) elements.secondStatus.value = "removed";
      if (elements.secondHiddenId) elements.secondHiddenId.value = "";
      if (elements.secondInput) elements.secondInput.value = "";
      if (elements.secondDrop) elements.secondDrop.classList.remove("has-image");
      const preview = document.getElementById("preview-second");
      if (preview) {
        preview.src = "";
        preview.style.display = "none";
      }
      state.templateMediaState.pendingFile = null;
      state.templateMediaState.mediaId = "";
    }
  }

  function needsTemplateMedia() {
    const hasStatus = elements.secondStatus && elements.secondStatus.value === "present";
    const toggleOn = elements.toggleSecond ? elements.toggleSecond.checked : true;
    return hasStatus && toggleOn;
  }

  async function ensureTemplateMediaBinding() {
    const templateState = state.templateMediaState;
    if (templateState.pendingFile) {
      const data = await api.uploadTemplateMedia(state.slotMeta.id, templateState.kind, templateState.pendingFile);
      templateState.mediaId = data.media_object_id || data.id || "";
      templateState.pendingFile = null;
      if (elements.secondHiddenId && templateState.mediaId) {
        elements.secondHiddenId.value = templateState.mediaId;
      }
    }
    if (templateState.mediaId) {
      return [
        {
          media_kind: templateState.kind,
          media_object_id: templateState.mediaId,
          role: "template",
        },
      ];
    }
    return [];
  }

  async function collectTemplateMediaBindings() {
    if (!needsTemplateMedia()) {
      return [];
    }
    const bindings = await ensureTemplateMediaBinding();
    if (!bindings.length) {
      throw new Error('Добавьте шаблонное изображение или отключите блок «Изображение — Шаблон стиля».');
    }
    return bindings;
  }

  async function loadRecentResults(options) {
    const grid = elements.resultsGrid;
    if (!grid) return;
    const silent = options && options.silent;
    if (elements.resultsEmpty) elements.resultsEmpty.style.display = "none";
    if (!silent) grid.classList.add("-loading");
    dom.setResultsError("");
    try {
      const payload = await api.fetchSlotDetails();
      const latest = mapping.extractLatestResult(payload);
      dom.renderRecentResults(latest ? [latest] : []);
    } catch (err) {
      console.warn("[Recent results]", err);
      dom.setResultsError("Не удалось загрузить результаты.");
      if (elements.resultsEmpty) elements.resultsEmpty.style.display = "";
    } finally {
      grid.classList.remove("-loading");
    }
  }

  async function bootstrapSlotFromServer() {
    if (!endpoints.slotApi) return null;
    const payload = await api.fetchSlotDetails();
    hydrateSlotFromServer(payload);
    const latest = mapping.extractLatestResult(payload);
    dom.renderRecentResults(latest ? [latest] : []);
    return payload;
  }

  function hydrateSlotFromServer(payload) {
    if (!payload) return;
    const slot = payload.slot || payload;
    if (!slot || typeof slot !== "object") return;
    state.slotMeta.provider = slot.provider || state.slotMeta.provider;
    state.slotMeta.operation = slot.operation || state.slotMeta.operation;
    state.slotMeta.modelName = slot.display_name || state.slotMeta.modelName;
    if (elements.titleInput) {
      elements.titleInput.value = slot.display_name || "";
    }
    if (elements.promptInput && slot.settings && typeof slot.settings.prompt === "string") {
      elements.promptInput.value = slot.settings.prompt;
    }
    mapping.hydrateImageConfig(slot);
    if (slot.template_media && slot.template_media.length) {
      const binding = slot.template_media[0];
      state.templateMediaState.mediaId = binding.media_object_id;
      state.templateMediaState.pendingFile = null;
      if (elements.secondHiddenId) elements.secondHiddenId.value = binding.media_object_id;
      if (elements.secondStatus) elements.secondStatus.value = "present";
      if (elements.toggleSecond && !elements.toggleSecond.checked) {
        elements.toggleSecond.checked = true;
        elements.toggleSecond.dispatchEvent(new Event("change"));
      }
      const previewUrl = binding.preview_url || `/public/provider-media/${binding.media_object_id}`;
      const preview = document.getElementById("preview-second");
      if (previewUrl && preview) {
        preview.src = previewUrl;
        preview.style.display = "block";
        preview.style.opacity = "1";
      }
      if (elements.secondDrop) {
        elements.secondDrop.classList.add("has-image");
      }
    }
    updateSlotHeader(slot.provider || state.slotMeta.provider);
    if (elements.providerSelect && slot.provider) {
      elements.providerSelect.value = slot.provider;
      elements.providerSelect.dispatchEvent(new Event("change"));
    }
    if (elements.operationSelect && slot.operation) {
      elements.operationSelect.value = slot.operation;
      elements.operationSelect.dispatchEvent(new Event("change"));
    }
  }

  async function persistAndToast(payload, provider) {
    const { response, data } = await api.saveSlot(payload);
    if (response.status === 422) {
      dom.applyFieldErrors(data, mapping.FIELD_MAP);
      throw new Error("Проверьте выделенные поля");
    }
    if (!response.ok) {
      throw new Error(`Сервис вернул статус ${response.status}`);
    }
    state.slotMeta.provider = provider;
    state.slotMeta.modelName =
      provider === state.slotMeta.provider && state.slotMeta.modelName
        ? state.slotMeta.modelName
        : (providers[provider]?.label || provider);
    updateSlotHeader(provider);
    if (elements.copyButton) elements.copyButton.disabled = false;
    dom.pulse(elements.form);
    dom.toast("Конфигурация сохранена через PUT /api/slots/{slot_id}", "success");
    if (elements.serverResponse) {
      elements.serverResponse.textContent = `Слот «${payload.display_name}» обновлён через ${endpoints.slotSave}.`;
    }
    hydrateSlotFromServer(data);
  }

  async function runTestSlot(templateBindings) {
    if (!state.testImageState.file) {
      throw new Error("Загрузите файл «Фото для тестов».");
    }
    const prov = state.slotMeta.provider || elements.providerSelect.value;
    const op = state.slotMeta.operation || elements.operationSelect.value;
    const slotPayload = {
      provider: prov,
      operation: op,
      settings: mapping.collectProviderSettings(prov),
    };
    if (templateBindings?.length) {
      slotPayload.template_media = templateBindings;
    }
    const title = (elements.titleInput?.value || "").trim();
    if (title) {
      slotPayload.display_name = title;
    }
    const formData = new FormData();
    formData.append("slot_payload", JSON.stringify(slotPayload));
    formData.append("test_image", state.testImageState.file, state.testImageState.file.name || "test-image.jpg");
    const { response, data } = await api.runTest(formData);
    if (response.status === 422) {
      dom.applyFieldErrors(data, mapping.FIELD_MAP);
      throw new Error("Исправьте ошибки тестового запуска.");
    }
    if (!response.ok) {
      let message = `Test-run завершился статусом ${response.status}`;
      message =
        data?.detail?.message ||
        data?.message ||
        (typeof data?.detail === "string" ? data.detail : message);
      throw new Error(message);
    }
    return data || {};
  }

  function bindSaveButton() {
    if (!elements.saveButton) return;
    elements.saveButton.addEventListener("click", async () => {
      if (!elements.form) return;
      dom.clearFieldErrors();
      const title = (elements.titleInput?.value || "").trim();
      const prov = elements.providerSelect?.value;
      if (!title) {
        dom.toast("Заполните название слота", "error");
        dom.pulse(elements.form);
        return;
      }
      if (!prov) {
        dom.toast("Выберите провайдера", "error");
        dom.pulse(elements.form);
        return;
      }
      const provConfig = providers[prov];
      if (!provConfig) {
        dom.toast("Провайдер недоступен", "error");
        dom.pulse(elements.form);
        return;
      }
      let op = state.slotMeta.operation || elements.operationSelect.value;
      if (prov === "gemini" && !op) {
        op = ns.constants.GEMINI_DEFAULT_OPERATION;
        setOperationValue(prov, op);
      }
      if (prov === "turbotext") {
        if (!op) op = constants.TURBOTEXT_DEFAULT_OPERATION;
        if (op !== constants.TURBOTEXT_DEFAULT_OPERATION) {
          op = constants.TURBOTEXT_DEFAULT_OPERATION;
          setOperationValue(prov, op);
        }
      }
      if (!op) {
        dom.toast("Выберите операцию", "error");
        dom.pulse(elements.form);
        return;
      }
      state.slotMeta.operation = op;
      const needs = provConfig.operations?.[op]?.needs || { prompt: true, second: false, first: true };
      if (mapping.needsPrompt(needs) && !mapping.getPromptValue()) {
        dom.toast("Добавьте текстовый промпт для операции", "error");
        dom.pulse(elements.form);
        return;
      }
      const secondEnabled = elements.toggleSecond ? elements.toggleSecond.checked : true;
      if (needs.second && secondEnabled && (!elements.secondStatus || elements.secondStatus.value !== "present")) {
        dom.toast("Для этой операции требуется «Изображение — Шаблон стиля»", "error");
        dom.pulse(elements.form);
        return;
      }
      try {
        const templateMedia = await collectTemplateMediaBindings();
        const payload = {
          slot_id: state.slotMeta.id,
          display_name: title,
          provider: prov,
          operation: op,
          is_active: true,
          size_limit_mb: endpoints.slotLimitMb,
          sync_response_seconds: endpoints.slotSyncSeconds,
          settings: mapping.collectProviderSettings(prov),
          template_media: templateMedia,
        };
        await persistAndToast(payload, prov);
      } catch (err) {
        console.warn("[Save slot]", err);
        dom.toast(err.message || "Не удалось сохранить слот", "error");
      }
    });
  }

  function bindTestButton() {
    if (!elements.testButton) return;
    elements.testButton.addEventListener("click", async () => {
      dom.clearFieldErrors();
      if (!elements.firstStatus || elements.firstStatus.value !== "present") {
        dom.toast("Загрузите тестовое фото перед запуском «Тест1».", "error");
        return;
      }
      if (!(state.slotMeta.provider || elements.providerSelect?.value)) {
        dom.toast("Сначала выберите провайдера и операцию.", "error");
        return;
      }
      const prov = state.slotMeta.provider || elements.providerSelect.value;
      const op = state.slotMeta.operation || elements.operationSelect.value;
      const provConfig = providers[prov];
      const needs = provConfig?.operations?.[op]?.needs || { prompt: true, second: false, first: true };
      if (mapping.needsPrompt(needs) && !mapping.getPromptValue()) {
        dom.toast("Добавьте промпт перед тестовым запуском.", "error");
        return;
      }
      const secondEnabled = elements.toggleSecond ? elements.toggleSecond.checked : true;
      if (needs.second && secondEnabled && (!elements.secondStatus || elements.secondStatus.value !== "present")) {
        dom.toast("Для выбранной операции нужен шаблон «Изображение — Шаблон стиля».", "error");
        return;
      }
      try {
        dom.showProcessing("Отправляем тестовый запуск…");
        const templateBindings = await collectTemplateMediaBindings();
        await runTestSlot(templateBindings);
        dom.pulse(elements.form);
        dom.hideProcessing();
        dom.toast("Тестовый запуск отправлен. Смотрите обновления в галерее ниже.", "success");
      } catch (err) {
        console.warn("[Test run]", err);
        dom.hideProcessing();
        dom.toast(err.message || "Не удалось выполнить тест", "error");
      }
    });
  }

  function bindRecentResults() {
    if (elements.resultsRefresh) {
      elements.resultsRefresh.addEventListener("click", () => loadRecentResults({ silent: false }));
    }
  }

  ns.events = {
    ensureAuth,
    bindCopyButton,
    bindToggle,
    bindSlot,
    bindProviderSelect,
    bindOperationSelect,
    bindSaveButton,
    bindTestButton,
    bindRecentResults,
    hydrateFromDataset,
    handleSecondToggle,
    updateSlotHeader,
    loadRecentResults,
    bootstrapSlotFromServer,
  };
})(window.SlotPage || (window.SlotPage = {}));
