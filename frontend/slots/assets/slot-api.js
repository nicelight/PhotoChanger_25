"use strict";
(function (ns) {
  const { elements, state, endpoints, providers, constants } = ns;
  const dom = ns.dom;

  const FIELD_MAP = {
    display_name: "#title",
    provider: "#provider",
    operation: "#operation",
    "settings.prompt": "#long",
    template_media: "#drop-second",
  };

  async function requestRecentResults() {
    if (!endpoints.slotApi) return { recent_results: [] };
    const response = await fetch(endpoints.slotApi, { headers: { Accept: "application/json" } });
    if (!response.ok) {
      throw new Error(`API ответил статусом ${response.status}`);
    }
    return response.json();
  }

  async function loadRecentResults(options) {
    const grid = elements.resultsGrid;
    if (!grid) return;
    const silent = options && options.silent;
    if (elements.resultsEmpty) elements.resultsEmpty.style.display = "none";
    if (!silent) grid.classList.add("-loading");
    dom.setResultsError("");
    try {
      const payload = await requestRecentResults();
      const list = payload?.recent_results || payload?.slot?.recent_results || [];
      dom.renderRecentResults(list);
    } catch (err) {
      console.warn("[Recent results]", err);
      dom.setResultsError("Не удалось загрузить результаты.");
      if (elements.resultsEmpty) elements.resultsEmpty.style.display = "";
    } finally {
      grid.classList.remove("-loading");
    }
  }

  async function ensureTemplateMediaBinding() {
    const templateState = state.templateMediaState;
    if (templateState.pendingFile) {
      if (!endpoints.templateUpload) {
        throw new Error("Endpoint регистрации шаблонов не настроен.");
      }
      const formData = new FormData();
      formData.append("slot_id", state.slotMeta.id);
      formData.append("media_kind", templateState.kind);
      formData.append(
        "file",
        templateState.pendingFile,
        templateState.pendingFile.name || "template-image.png"
      );
      const response = await fetch(endpoints.templateUpload, { method: "POST", body: formData });
      if (!response.ok) {
        throw new Error(`Не удалось загрузить шаблонное изображение (HTTP ${response.status})`);
      }
      const data = await response.json();
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

  function needsTemplateMedia() {
    return elements.secondStatus && elements.secondStatus.value === "present";
  }

  function getPromptValue() {
    return (elements.promptInput?.value || "").trim();
  }

  function collectProviderSettings(provider) {
    const settings = { prompt: getPromptValue() };
    if (provider === "gemini") {
      settings.output = { mime_type: "image/png" };
    }
    return settings;
  }

  async function persistSlot(payload) {
    if (!endpoints.slotSave) {
      throw new Error("Endpoint сохранения слота не настроен.");
    }
    const response = await fetch(endpoints.slotSave, {
      method: "PUT",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
      },
      body: JSON.stringify(payload),
    });
    if (response.status === 422) {
      const body = await response.json().catch(() => ({}));
      dom.applyFieldErrors(body, FIELD_MAP);
      throw new Error("Проверьте выделенные поля");
    }
    if (!response.ok) {
      throw new Error(`Сервис вернул статус ${response.status}`);
    }
    return response.json().catch(() => ({}));
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
      const url = generateIngestURL(state.slotMeta.id, provider);
      elements.ingestInput.value = url;
      if (elements.copyButton) elements.copyButton.disabled = !provider;
    }
  }

  function hydrateSlotFromServer(payload) {
    if (!payload) return;
    const slot = payload.slot || payload;
    if (!slot || typeof slot !== "object") return;
    state.slotMeta.provider = slot.provider || state.slotMeta.provider;
    state.slotMeta.operation = slot.operation || state.slotMeta.operation;
    state.slotMeta.modelName = slot.display_name || state.slotMeta.modelName;
    if (elements.promptInput && slot.settings && typeof slot.settings.prompt === "string") {
      elements.promptInput.value = slot.settings.prompt;
    }
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
    }
    updateSlotHeader(slot.provider || state.slotMeta.provider);
  }

  async function persistAndToast(payload, provider) {
    const data = await persistSlot(payload);
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

  function needsPrompt(needs) {
    return (needs && needs.prompt) ?? true;
  }

  async function runTestSlot(templateBindings) {
    if (!state.testImageState.file) {
      throw new Error("Загрузите файл «Фото для тестов».");
    }
    if (!endpoints.testRun) {
      throw new Error("Endpoint test-run не настроен.");
    }
    const formData = new FormData();
    formData.append("prompt", getPromptValue());
    formData.append("provider", elements.providerSelect.value);
    formData.append("operation", state.slotMeta.operation || elements.operationSelect.value);
    formData.append(
      "test_image",
      state.testImageState.file,
      state.testImageState.file.name || "test-image.jpg"
    );
    if (templateBindings?.length) {
      formData.append("template_media", JSON.stringify(templateBindings));
    }
    const response = await fetch(endpoints.testRun, { method: "POST", body: formData });
    if (response.status === 422) {
      const body = await response.json().catch(() => ({}));
      dom.applyFieldErrors(body, FIELD_MAP);
      throw new Error("Исправьте ошибки тестового запуска.");
    }
    if (!response.ok) {
      throw new Error(`Test-run завершился статусом ${response.status}`);
    }
    return response.json().catch(() => ({}));
  }

  function generateIngestURL(slotId, providerSlug) {
    if (slotId && providerSlug) {
      return `${endpoints.ingestBase}${providerSlug}/${slotId}`;
    }
    return "";
  }

  ns.api = {
    loadRecentResults,
    collectTemplateMediaBindings,
    getPromptValue,
    collectProviderSettings,
    persistAndToast,
    needsTemplateMedia,
    runTestSlot,
    generateIngestURL,
    updateSlotHeader,
    needsPrompt,
  };
})(window.SlotPage || (window.SlotPage = {}));
