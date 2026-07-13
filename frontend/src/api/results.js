import apiClient from './client';

export function listResultVariables(projectId, runId) {
  return apiClient.get(`/projects/${encodeURIComponent(projectId)}/runs/${encodeURIComponent(runId)}/results/variables`);
}

export function getBudget(projectId, runId) {
  return apiClient.get(`/projects/${encodeURIComponent(projectId)}/runs/${encodeURIComponent(runId)}/results/budget`);
}

export function getHeadSlice(projectId, runId, params = {}, options = {}) {
  const responseType = params.format === 'binary' ? 'arraybuffer' : 'json';
  return apiClient.get(`/projects/${encodeURIComponent(projectId)}/runs/${encodeURIComponent(runId)}/results/head`, {
    params,
    responseType,
    ...options
  });
}

export function parseBinaryHeadSlice(response) {
  const metadataHeader = response.headers ? response.headers['x-result-metadata'] : null;
  const metadata = metadataHeader ? JSON.parse(metadataHeader) : {};
  return {
    metadata,
    values: new Float64Array(response.data)
  };
}

export function exportModel(points) {
  return apiClient.post('/export-model', { points }, { responseType: 'blob' });
}
