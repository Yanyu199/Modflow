import Vue from 'vue';

export const geologyStore = Vue.observable({
  activeGeologyModelId: null,
  currentGeologyModel: null,
  diagnostics: null,
  summary: null,
  loading: false,
  error: null
});

export function setGeologyModel(model) {
  geologyStore.currentGeologyModel = model || null;
  geologyStore.activeGeologyModelId = model ? model.geology_model_id : null;
  geologyStore.diagnostics = model ? model.diagnostics : null;
  geologyStore.summary = model && model.diagnostics ? model.diagnostics.summary : null;
}

export function resetGeologyStore() {
  setGeologyModel(null);
  geologyStore.loading = false;
  geologyStore.error = null;
}
