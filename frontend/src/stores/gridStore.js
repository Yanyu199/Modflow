import Vue from 'vue';

export const gridStore = Vue.observable({
  activeGridModelId: null,
  currentGridModel: null,
  summary: null,
  quality: {},
  selectedCellId: null,
  visibleLayer: 0,
  scale: null,
  loading: false,
  error: null
});

export function setGridModel(model) {
  gridStore.currentGridModel = model || null;
  gridStore.activeGridModelId = model ? model.grid_model_id : null;
  gridStore.quality = model ? (model.quality || {}) : {};
  gridStore.summary = model && model.quality ? model.quality.summary : null;
  gridStore.scale = model && model.resource_estimate ? model.resource_estimate.scale : null;
}

export function resetGridStore() {
  setGridModel(null);
  gridStore.selectedCellId = null;
  gridStore.visibleLayer = 0;
  gridStore.loading = false;
  gridStore.error = null;
}
