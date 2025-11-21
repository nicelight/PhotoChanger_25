"use strict";
(function (ns) {
  const { state, elements, providers, constants, auth } = ns;
  const dom = ns.dom;
  const api = ns.api;

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

  function bindToggle(toggle, panel) {
    if (!toggle || !panel) return;
    const apply = () => (toggle.checked ? dom.show(panel) : dom.hide(panel));
    toggle.addEventListener("change", apply);
    apply();
  }

  function bindSlot(prefix) {
    const input = prefix === "second" ? elements.secondInput : elements.firstInput;
    const preview = prefix === "second" ? document.getElementById("preview-second") : document.getElementById("preview-first");
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
      const config = providers[prov];
      if (!prov || !config) {
        state.slotMeta.provider = "";
        state.slotMeta.modelName = "";
        api.updateSlotHeader("");
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

      if (prov === "gemini") {
        const defaultOp =
          (ops && state.slotMeta.operation && ops[state.slotMeta.operation] && state.slotMeta.operation) ||
          ops[constants.GEMINI_DEFAULT_OPERATION]
            ? constants.GEMINI_DEFAULT_OPERATION
            : Object.keys(ops || {})[0];
        if (elements.operationSelectWrap) elements.operationSelectWrap.style.display = "none";
        setOperationValue(prov, defaultOp);
      } else {
        if (elements.operationSelectWrap) elements.operationSelectWrap.style.display = "";
        if (prov === "turbotext") {
          setOperationValue(prov, constants.TURBOTEXT_DEFAULT_OPERATION);
        }
      }

      api.updateSlotHeader(prov);
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
        label.textContent = normalized.prompt
          ? "Промпт"
          : "Промпт (промпт опционален)";
      }
    }
    if (elements.toggleFirst) {
      elements.toggleFirst.checked = normalized.first || elements.toggleFirst.checked;
      elements.toggleFirst.dispatchEvent(new Event("change"));
    }
    if (elements.toggleSecond) {
      elements.toggleSecond.checked = normalized.second || elements.toggleSecond.checked;
      elements.toggleSecond.dispatchEvent(new Event("change"));
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

  function hydrateFromDataset() {
    if (!elements.slotModelText) return;
    api.updateSlotHeader(state.slotMeta.provider);
    if (state.slotMeta.provider && elements.providerSelect) {
      elements.providerSelect.value = state.slotMeta.provider;
      elements.providerSelect.dispatchEvent(new Event("change"));
      if (state.slotMeta.provider === "gemini" && state.slotMeta.operation) {
        setOperationValue("gemini", state.slotMeta.operation);
      }
      if (state.slotMeta.provider === "turbotext" && state.slotMeta.operation) {
        elements.operationSelect.value = state.slotMeta.operation;
        elements.operationSelect.dispatchEvent(new Event("change"));
      }
    } else {
      api.updateSlotHeader("");
    }
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
      if (api.needsPrompt(needs) && !api.getPromptValue()) {
        dom.toast("Добавьте текстовый промпт для операции", "error");
        dom.pulse(elements.form);
        return;
      }
      if (needs.second && (!elements.secondStatus || elements.secondStatus.value !== "present")) {
        dom.toast("Для этой операции требуется «Изображение — Шаблон стиля»", "error");
        dom.pulse(elements.form);
        return;
      }
      try {
        const templateMedia = await api.collectTemplateMediaBindings();
        const payload = {
          slot_id: state.slotMeta.id,
          display_name: title,
          provider: prov,
          operation: op,
          is_active: true,
          size_limit_mb: endpoints.slotLimitMb,
          sync_response_seconds: endpoints.slotSyncSeconds,
          settings: api.collectProviderSettings(prov),
          template_media: templateMedia,
        };
        await api.persistAndToast(payload, prov);
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
      if (api.needsPrompt(needs) && !api.getPromptValue()) {
        dom.toast("Добавьте промпт перед тестовым запуском.", "error");
        return;
      }
      if (needs.second && (!elements.secondStatus || elements.secondStatus.value !== "present")) {
        dom.toast("Для выбранной операции нужен шаблон «Изображение — Шаблон стиля».", "error");
        return;
      }
      try {
        const templateBindings = await api.collectTemplateMediaBindings();
        await api.runTestSlot(templateBindings);
        dom.pulse(elements.form);
        dom.toast("Тестовый запуск отправлен. Смотрите обновления в галерее ниже.", "success");
      } catch (err) {
        console.warn("[Test run]", err);
        dom.toast(err.message || "Не удалось выполнить тест", "error");
      }
    });
  }

  function bindRecentResults() {
    if (elements.resultsRefresh) {
      elements.resultsRefresh.addEventListener("click", () => api.loadRecentResults({ silent: false }));
    }
  }

  function init() {
    if (!ensureAuth()) {
      return;
    }
    bindCopyButton();
    bindToggle(elements.toggleSecond, elements.secondWrap);
    bindToggle(elements.toggleFirst, elements.firstWrap);
    bindSlot("second");
    bindSlot("first");
    bindProviderSelect();
    bindOperationSelect();
    bindSaveButton();
    bindTestButton();
    bindRecentResults();
    hydrateFromDataset();
    if (typeof api.bootstrapSlotFromServer === "function") {
      api.bootstrapSlotFromServer().catch((err) => {
        console.warn("[SlotPage] Unable to bootstrap slot", err);
        dom.toast("Не удалось загрузить данные слота", "error");
      });
    }
  }

  document.addEventListener("DOMContentLoaded", init);
})(window.SlotPage || (window.SlotPage = {}));
