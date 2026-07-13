import apiClient from './client';

export function createProject(payload) {
  return apiClient.post('/projects', payload);
}

export function updateProject(projectId, payload) {
  return apiClient.put(`/projects/${encodeURIComponent(projectId)}`, payload);
}

export function getProject(projectId) {
  return apiClient.get(`/projects/${encodeURIComponent(projectId)}`);
}
