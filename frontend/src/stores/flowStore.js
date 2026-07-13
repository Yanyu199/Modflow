import Vue from 'vue';

export const flowStore = Vue.observable({
  activeFlowModelId: null,
  currentFlowModel: null,
  checker: null,
  packagePreview: null,
  draft: null,
  loading: false,
  error: null
});

export function setFlowModel(model, checker = null, packagePreview = null) {
  flowStore.currentFlowModel = model || null;
  flowStore.activeFlowModelId = model ? model.flow_model_id : null;
  flowStore.checker = checker;
  flowStore.packagePreview = packagePreview;
}

export function setFlowChecker(checker) {
  flowStore.checker = checker || null;
}

export function setPackagePreview(packagePreview) {
  flowStore.packagePreview = packagePreview || null;
}

export function resetFlowStore() {
  setFlowModel(null, null, null);
  flowStore.draft = null;
  flowStore.loading = false;
  flowStore.error = null;
}
