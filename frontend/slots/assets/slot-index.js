"use strict";
// slot-index.js: единая точка входа для страницы слота.
(function (ns) {
  const { elements, endpoints } = ns;
  const dom = ns.dom;
  const events = ns.events;

  function init() {
    if (!events.ensureAuth()) {
      return;
    }
    if (elements.galleryLink && endpoints.galleryHref) {
      elements.galleryLink.href = endpoints.galleryHref;
    }
    events.bindCopyButton();
    events.bindToggle(elements.toggleSecond, elements.secondWrap, events.handleSecondToggle);
    events.bindToggle(elements.toggleFirst, elements.firstWrap);
    events.bindSlot("second");
    events.bindSlot("first");
    events.bindProviderSelect();
    events.bindOperationSelect();
    events.bindSaveButton();
    events.bindTestButton();
    events.bindRecentResults();
    events.hydrateFromDataset();
    dom.updateImageConfigVisibility(ns.state.slotMeta.provider);
    if (typeof events.bootstrapSlotFromServer === "function") {
      events.bootstrapSlotFromServer().catch((err) => {
        console.warn("[SlotPage] Unable to bootstrap slot", err);
        dom.toast("Не удалось загрузить данные слота", "error");
      });
    }
  }

  document.addEventListener("DOMContentLoaded", init);
})(window.SlotPage || (window.SlotPage = {}));
