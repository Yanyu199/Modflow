import apiClient from './client';

export function createGrid(projectId, payload) {
  return apiClient.post(`/projects/${encodeURIComponent(projectId)}/grids`, payload);
}

export function getGridRenderData(projectId, gridModelId) {
  return apiClient.get(`/projects/${encodeURIComponent(projectId)}/grids/${encodeURIComponent(gridModelId)}/render-data`);
}

export function getGridCell(projectId, gridModelId, cellId) {
  return apiClient.get(
    `/projects/${encodeURIComponent(projectId)}/grids/${encodeURIComponent(gridModelId)}/cells/${encodeURIComponent(cellId)}`
  );
}
