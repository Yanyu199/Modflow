import apiClient, { API_BASE_URL } from './client';

export { API_BASE_URL };

export function uploadShapefile(formData, options = {}) {
  return apiClient.post('/upload-shapefile', formData, options);
}

export function uploadFaults(formData, options = {}) {
  return apiClient.post('/upload-faults', formData, options);
}
