"use strict";
// slot-mapping.js: маппинг UI <-> settings и вспомогательные таблицы.
(function (ns) {
  const { elements } = ns;

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

  function extractRecentResults(payload) {
    if (!payload) return [];
    if (Array.isArray(payload.recent_results)) return payload.recent_results;
    if (payload.slot && Array.isArray(payload.slot.recent_results)) {
      return payload.slot.recent_results;
    }
    return [];
  }

  function extractLatestResult(payload) {
    if (payload && payload.latest_result) return payload.latest_result;
    const list = extractRecentResults(payload);
    return list.length ? list[0] : null;
  }

  function getPromptValue() {
    return (elements.promptInput?.value || "").trim();
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

  function needsPrompt(needs) {
    return (needs && needs.prompt) ?? true;
  }

  ns.mapping = {
    FIELD_MAP,
    extractRecentResults,
    extractLatestResult,
    getPromptValue,
    collectProviderSettings,
    hydrateImageConfig,
    needsPrompt,
  };
})(window.SlotPage || (window.SlotPage = {}));
