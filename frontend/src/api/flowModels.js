import apiClient from './client';

export function validateFlowModel(projectId, payload) {
  return apiClient.post(`/projects/${encodeURIComponent(projectId)}/flow-models/validate`, payload);
}

export function createFlowModel(projectId, payload) {
  return apiClient.post(`/projects/${encodeURIComponent(projectId)}/flow-models`, payload);
}

export function updateFlowModel(projectId, flowModelId, payload) {
  return apiClient.put(`/projects/${encodeURIComponent(projectId)}/flow-models/${encodeURIComponent(flowModelId)}`, payload);
}

export function getPackagePreview(projectId, flowModelId) {
  return apiClient.get(`/projects/${encodeURIComponent(projectId)}/flow-models/${encodeURIComponent(flowModelId)}/package-preview`);
}
