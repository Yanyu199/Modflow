import axios from 'axios';

function configuredBaseUrl() {
  const runtimeValue = typeof window !== 'undefined'
    ? (window.__FLOPY_API_BASE_URL__ || (window.__FLOPY_CONFIG__ && window.__FLOPY_CONFIG__.apiBaseUrl))
    : null;
  const buildValue = typeof process !== 'undefined' && process.env
    ? process.env.FLOPY_API_BASE_URL
    : null;
  return (runtimeValue || buildValue || 'http://localhost:5000').replace(/\/$/, '');
}

export const API_BASE_URL = configuredBaseUrl();

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000
});

export function normalizeApiError(error) {
  const payload = error && error.response && error.response.data ? error.response.data : null;
  return {
    message: (payload && (payload.error || payload.message)) || (error && error.message) || 'Request failed',
    code: (payload && payload.code) || (payload && payload.error && payload.error.code) || 'api_error',
    details: payload && payload.details ? payload.details : null,
    status: error && error.response ? error.response.status : null
  };
}

export function createCancelSource() {
  return axios.CancelToken.source();
}

export function isCancel(error) {
  return axios.isCancel(error);
}

export default apiClient;
