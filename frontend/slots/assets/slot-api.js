"use strict";
(function (ns) {
  const { elements, state, endpoints, providers, constants, auth } = ns;
  const dom = ns.dom;

  const FIELD_MAP = {
    display_name: "#title",
    provider: "#provider",
    operation: "#operation",
    "settings.prompt": "#long",
    "settings.image_config.aspect_ratio": "#aspect-ratio",
    "settings.image_config.image_size": "#resolution",
    "settings.output.size": "#resolution",
    template_media: "#drop-second",
    "slot_payload.provider": "#provider",
    "slot_payload.operation": "#operation",
    "slot_payload.settings.prompt": "#long",
    "slot_payload.settings.image_config.aspect_ratio": "#aspect-ratio",
    "slot_payload.settings.image_config.image_size": "#resolution",
    "slot_payload.template_media": "#drop-second",
    "slot_payload.template_media.0.media_object_id": "#drop-second",
  };

  function authorizedFetch(input, init) {
    if (!auth || typeof auth.authFetch !== "function") {
      throw new Error("AdminAuth недоступен: обновите страницу после входа.");
    }
    return auth.authFetch(input, init);
  }

  async function requestSlotDetails() {
    if (!endpoints.slotApi) return { recent_results: [] };
    const response = await authorizedFetch(endpoints.slotApi, { headers: { Accept: "application/json" } });
    if (!response.ok) {
      throw new Error(`API ответил статусом ${response.status}`);
    }
    return response.json();
  }

  function extractRecentResults(payload) {
    if (!payload) return [];
    if (Array.isArray(payload.recent_results)) return payload.recent_results;
    if (payload.slot && Array.isArray(payload.slot.recent_results)) {
      return payload.slot.recent_results;
    }
    return [];
  }

  async function loadRecentResults(options) {
    const grid = elements.resultsGrid;
    if (!grid) return;
    const silent = options && options.silent;
    if (elements.resultsEmpty) elements.resultsEmpty.style.display = "none";
    if (!silent) grid.classList.add("-loading");
    dom.setResultsError("");
    try {
      const payload = await requestSlotDetails();
      const latest = extractLatestResult(payload);
      dom.renderRecentResults(latest ? [latest] : []);
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
      const response = await authorizedFetch(endpoints.templateUpload, { method: "POST", body: formData });
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

  function needsTemplateMedia() {
    const hasStatus = elements.secondStatus && elements.secondStatus.value === "present";
    const toggleOn = elements.toggleSecond ? elements.toggleSecond.checked : true;
    return hasStatus && toggleOn;
  }

  function getPromptValue() {
    return (elements.promptInput?.value || "").trim();
  }

  function collectProviderSettings(provider) {
    const settings = { prompt: getPromptValue() };
    if (provider === "gemini") {
      settings.output = { mime_type: "image/png" };
      const imageConfig = collectImageConfig(provider);
      if (Object.keys(imageConfig).length) {
        settings.image_config = imageConfig;
      }
    }
    if (provider === "gemini-3-pro") {
      settings.output = { mime_type: "image/png" };
      const imageConfig = collectImageConfig(provider);
      if (Object.keys(imageConfig).length) {
        settings.image_config = imageConfig;
      }
    }
    if (provider === "gpt-image-1.5") {
      const output = { format: "png" };
      const mappedSize = mapGptSizeFromUi();
      if (mappedSize) {
        output.size = mappedSize;
      }
      settings.output = output;
    }
    return settings;
  }

  async function persistSlot(payload) {
    if (!endpoints.slotSave) {
      throw new Error("Endpoint сохранения слота не настроен.");
    }
    const response = await authorizedFetch(endpoints.slotSave, {
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
      const url = generateIngestURL(state.slotMeta.id);
      elements.ingestInput.value = url;
      if (elements.copyButton) elements.copyButton.disabled = !provider;
    }
  }

  async function bootstrapSlotFromServer() {
    if (!endpoints.slotApi) return null;
    const payload = await requestSlotDetails();
    hydrateSlotFromServer(payload);
    const latest = extractLatestResult(payload);
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
    hydrateImageConfig(slot);
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

  function collectImageConfig(provider) {
    const config = {};
    const aspectRatio = (elements.aspectRatioSelect?.value || "").trim();
    const resolution = (elements.resolutionSelect?.value || "").trim();
    if (provider === "gemini") {
      if (aspectRatio) config.aspect_ratio = aspectRatio;
      return config;
    }
    if (aspectRatio && resolution) {
      config.aspect_ratio = aspectRatio;
      config.image_size = resolution;
    }
    return config;
  }

  function mapGptSizeFromUi() {
    const aspect = (elements.aspectRatioSelect?.value || "").trim();
    const resolution = (elements.resolutionSelect?.value || "").trim();
    if (!aspect || !resolution) return "";
    const table = GPT_SIZE_TABLE[aspect];
    if (!table) return "";
    return table[resolution] || "";
  }

  function hydrateImageConfig(slot) {
    if (!slot || !slot.settings) return;
    if (slot.provider === "gemini" || slot.provider === "gemini-3-pro") {
      const cfg = slot.settings.image_config || {};
      if (elements.aspectRatioSelect && cfg.aspect_ratio) {
        elements.aspectRatioSelect.value = cfg.aspect_ratio;
      }
      if (slot.provider === "gemini") {
        if (elements.resolutionSelect) elements.resolutionSelect.value = "";
      } else if (elements.resolutionSelect && cfg.image_size) {
        elements.resolutionSelect.value = cfg.image_size;
      }
      return;
    }
    if (slot.provider === "gpt-image-1.5") {
      const output = slot.settings.output || {};
      const size = output.size;
      if (!size) return;
      const mapped = GPT_SIZE_REVERSE[size];
      if (mapped) {
        if (elements.aspectRatioSelect) elements.aspectRatioSelect.value = mapped.aspect;
        if (elements.resolutionSelect) elements.resolutionSelect.value = mapped.resolution;
      }
    }
  }

  const GPT_SIZE_TABLE = {
    "1:1": { "1K": "1024x1024", "2K": "2048x2048", "4K": "4096x4096" },
    "2:3": { "1K": "848x1264", "2K": "1696x2528", "4K": "3392x5056" },
    "3:2": { "1K": "1264x848", "2K": "2528x1696", "4K": "5056x3392" },
    "3:4": { "1K": "896x1200", "2K": "1792x2400", "4K": "3584x4800" },
    "4:3": { "1K": "1200x896", "2K": "2400x1792", "4K": "4800x3584" },
    "4:5": { "1K": "928x1152", "2K": "1856x2304", "4K": "3712x4608" },
    "5:4": { "1K": "1152x928", "2K": "2304x1856", "4K": "4608x3712" },
    "9:16": { "1K": "768x1376", "2K": "1536x2752", "4K": "3072x5504" },
    "16:9": { "1K": "1376x768", "2K": "2752x1536", "4K": "5504x3072" },
    "21:9": { "1K": "1584x672", "2K": "3168x1344", "4K": "6336x2688" },
  };

  const GPT_SIZE_REVERSE = Object.entries(GPT_SIZE_TABLE).reduce((acc, [aspect, sizes]) => {
    Object.entries(sizes).forEach(([resolution, size]) => {
      acc[size] = { aspect, resolution };
    });
    return acc;
  }, {});

  function extractLatestResult(payload) {
    if (payload && payload.latest_result) return payload.latest_result;
    const list = extractRecentResults(payload);
    return list.length ? list[0] : null;
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
    const prov = state.slotMeta.provider || elements.providerSelect.value;
    const op = state.slotMeta.operation || elements.operationSelect.value;
    const slotPayload = {
      provider: prov,
      operation: op,
      settings: collectProviderSettings(prov),
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
    formData.append(
      "test_image",
      state.testImageState.file,
      state.testImageState.file.name || "test-image.jpg"
    );
    const response = await authorizedFetch(endpoints.testRun, { method: "POST", body: formData });
    if (response.status === 422) {
      const body = await response.json().catch(() => ({}));
      dom.applyFieldErrors(body, FIELD_MAP);
      throw new Error("Исправьте ошибки тестового запуска.");
    }
    if (!response.ok) {
      let message = `Test-run завершился статусом ${response.status}`;
      try {
        const body = await response.json();
        message =
          body?.detail?.message ||
          body?.message ||
          (typeof body?.detail === "string" ? body.detail : message);
      } catch (_) {
        // ignore parse errors, fallback to default message
      }
      throw new Error(message);
    }
    return response.json().catch(() => ({}));
  }

  function generateIngestURL(slotId) {
    if (!slotId || !endpoints.ingestBase) return "";
    const base = endpoints.ingestBase.endsWith("/") ? endpoints.ingestBase.slice(0, -1) : endpoints.ingestBase;
    return `${base}/${slotId}`;
  }

  ns.api = {
    loadRecentResults,
    bootstrapSlotFromServer,
    collectTemplateMediaBindings,
    getPromptValue,
    collectProviderSettings,
    persistAndToast,
    needsTemplateMedia,
    runTestSlot,
    generateIngestURL,
    updateSlotHeader,
    needsPrompt,
    extractLatestResult,
  };
})(window.SlotPage || (window.SlotPage = {}));
