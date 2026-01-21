"use strict";
// slot-api.js: только сетевые запросы к backend API.
(function (ns) {
  const { endpoints, auth } = ns;

  function authorizedFetch(input, init) {
    if (!auth || typeof auth.authFetch !== "function") {
      throw new Error("AdminAuth недоступен: обновите страницу после входа.");
    }
    return auth.authFetch(input, init);
  }

  async function fetchSlotDetails() {
    if (!endpoints.slotApi) return { recent_results: [] };
    const response = await authorizedFetch(endpoints.slotApi, { headers: { Accept: "application/json" } });
    if (!response.ok) {
      throw new Error(`API ответил статусом ${response.status}`);
    }
    return response.json();
  }

  async function saveSlot(payload) {
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
    const data = await response.json().catch(() => ({}));
    return { response, data };
  }

  async function runTest(payloadFormData) {
    if (!endpoints.testRun) {
      throw new Error("Endpoint test-run не настроен.");
    }
    const response = await authorizedFetch(endpoints.testRun, { method: "POST", body: payloadFormData });
    let data = null;
    try {
      data = await response.json();
    } catch (_) {
      data = {};
    }
    return { response, data };
  }

  async function uploadTemplateMedia(slotId, mediaKind, file) {
    if (!endpoints.templateUpload) {
      throw new Error("Endpoint регистрации шаблонов не настроен.");
    }
    const formData = new FormData();
    formData.append("slot_id", slotId);
    formData.append("media_kind", mediaKind);
    formData.append("file", file, file.name || "template-image.png");
    const response = await authorizedFetch(endpoints.templateUpload, { method: "POST", body: formData });
    if (!response.ok) {
      throw new Error(`Не удалось загрузить шаблонное изображение (HTTP ${response.status})`);
    }
    return response.json();
  }

  ns.api = {
    fetchSlotDetails,
    saveSlot,
    runTest,
    uploadTemplateMedia,
  };
})(window.SlotPage || (window.SlotPage = {}));
