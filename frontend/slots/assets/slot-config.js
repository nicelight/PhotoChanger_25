"use strict";
(function (ns, doc) {
  ns.providers = {
    gemini: {
      label: "Gemini",
      operations: {
        style_transfer: { label: "Style Transfer", needs: { prompt: true, second: true, first: false } },
        identity_transfer: { label: "Identity Transfer", needs: { prompt: true, second: true, first: true } },
        image_edit: { label: "Image Edit", needs: { prompt: true, second: false, first: true } },
      },
    },
    "gemini-3-pro": {
      label: "Gemini 3 Pro",
      operations: {
        image_edit: { label: "Image Edit", needs: { prompt: true, second: false, first: true } },
      },
    },
    "gpt-image-1.5": {
      label: "GPT Image 1.5",
      operations: {
        image_edit: { label: "Image Edit", needs: { prompt: true, second: false, first: true } },
      },
    },
    turbotext: {
      label: "TurboText",
      operations: {
        image2image: { label: "Image2Image (рекомендуем)", needs: { prompt: true, second: false, first: true } },
        style_transfer: { label: "Style Transfer", needs: { prompt: true, second: true, first: true } },
        image_edit: { label: "Image Edit", needs: { prompt: true, second: false, first: true } },
        identity_transfer: { label: "Identity Transfer", needs: { prompt: false, second: true, first: true } },
      },
    },
  };

  ns.constants = {
    TURBOTEXT_DEFAULT_OPERATION: "image2image",
    GEMINI_DEFAULT_OPERATION: "identity_transfer",
  };

  const dataset = doc.body.dataset;
  const slotMeta = {
    id: dataset.slotId || "slot-000",
    provider: dataset.provider || "",
    operation: dataset.operation || "",
    modelName: dataset.modelName || "",
  };

  const templateMediaState = {
    pendingFile: null,
    mediaId: dataset.templateMediaId || "",
    kind: dataset.templateMediaKind || "style_reference",
  };

  const testImageState = { file: null };

  const $ = (id) => doc.getElementById(id);

  const elements = {
    form: $("upload-form"),
    titleInput: $("title"),
    providerSelect: $("provider"),
    operationSelect: $("operation"),
    operationSelectWrap: $("operation-select-wrap"),
    requirementsHint: $("op-req"),
    promptInput: $("long"),
    slotModelText: $("slot-model-text"),
    slotIdValue: $("slot-id-value"),
    ingestInput: $("ingest-url"),
    copyButton: $("btn-copy"),
    saveButton: $("btn-save1"),
    testButton: $("btn-test1"),
    toggleSecond: $("toggle-second"),
    toggleFirst: $("toggle-first"),
    secondWrap: $("second-wrap"),
    firstWrap: $("first-wrap"),
    secondDrop: $("drop-second"),
    firstDrop: $("drop-first"),
    secondInput: $("input-second"),
    firstInput: $("input-first"),
    secondStatus: $("Second_image_status"),
    firstStatus: $("First_image_status"),
    secondHiddenId: $("Second_image_media_id"),
    secondError: $("error-second"),
    firstError: $("error-first"),
    hintFirst: $("hint-first"),
    resultsGrid: $("slot-results-grid"),
    resultsEmpty: $("slot-results-empty"),
    resultsError: $("slot-results-error"),
    resultsRefresh: $("results-refresh"),
    galleryLink: $("gallery-link"),
    toast: $("toast"),
    serverResponse: $("server-response"),
    imageConfigCard: $("image-config-card"),
    aspectRatioSelect: $("aspect-ratio"),
    resolutionSelect: $("resolution"),
  };

  if (elements.slotIdValue) {
    elements.slotIdValue.textContent = slotMeta.id;
  }

  const endpoints = {
    slotApi: dataset.slotApi || "",
    slotSave: dataset.slotSave || dataset.slotApi || "",
    testRun: dataset.testRun || "",
    templateUpload: dataset.templateUpload || "",
    slotLimitMb: Number(dataset.slotLimitMb || 15),
    slotSyncSeconds: Number(dataset.slotSync || 48),
    ingestBase: dataset.ingestBase || "https://api.example.com/ingest/",
    galleryHref: dataset.galleryHref || "/ui/static/admin/gallery.html",
  };

  ns.state = {
    slotMeta,
    templateMediaState,
    testImageState,
  };
  ns.elements = elements;
  ns.endpoints = endpoints;
  ns.utils = { $, byId: $ };
  ns.auth = window.AdminAuth || null;
})(window.SlotPage || (window.SlotPage = {}), document);
