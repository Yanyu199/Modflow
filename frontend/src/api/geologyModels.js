import apiClient from './client';

export function validateGeologyModel(projectId, payload) {
  return apiClient.post(`/projects/${encodeURIComponent(projectId)}/geology-models/validate`, payload);
}

export function createGeologyModel(projectId, payload) {
  return apiClient.post(`/projects/${encodeURIComponent(projectId)}/geology-models`, payload);
}

export function uploadBoreholes(formData, options = {}) {
  return apiClient.post('/upload-boreholes', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    ...options
  });
}
