import apiClient from './client';

const TERMINAL_STATUSES = new Set([
  'completed',
  'completed_with_warnings',
  'cancelled',
  'timed_out',
  'interrupted',
  'failed_validation',
  'failed_compile',
  'failed_executable',
  'failed_input_write',
  'failed_execution',
  'failed_convergence',
  'failed_outputs',
  'failed_budget',
  'failed_postprocessing'
]);

export function createRun(projectId, payload, options = {}) {
  return apiClient.post(`/projects/${encodeURIComponent(projectId)}/runs`, payload, options);
}

export function listRuns(projectId, params = {}) {
  return apiClient.get(`/projects/${encodeURIComponent(projectId)}/runs`, { params });
}

export function getRun(projectId, runId) {
  return apiClient.get(`/projects/${encodeURIComponent(projectId)}/runs/${encodeURIComponent(runId)}`);
}

export function getRunSummary(projectId, runId) {
  return apiClient.get(`/projects/${encodeURIComponent(projectId)}/runs/${encodeURIComponent(runId)}/summary`);
}

export function cancelRun(projectId, runId, payload = {}) {
  return apiClient.post(`/projects/${encodeURIComponent(projectId)}/runs/${encodeURIComponent(runId)}/cancel`, payload);
}

export function isTerminalRunStatus(status) {
  return TERMINAL_STATUSES.has(status);
}

export async function pollRun(projectId, runId, options = {}) {
  const initialDelay = options.initialDelay || 500;
  const maxDelay = options.maxDelay || 3000;
  const timeoutMs = options.timeoutMs || 0;
  const onUpdate = options.onUpdate || (() => {});
  const started = Date.now();
  let delay = initialDelay;
  while (true) {
    if (timeoutMs > 0 && Date.now() - started > timeoutMs) {
      throw new Error(`Polling timed out for run ${runId}`);
    }
    const response = await getRun(projectId, runId);
    const run = response.data.run;
    onUpdate(run);
    if (run && isTerminalRunStatus(run.status)) return run;
    await new Promise(resolve => setTimeout(resolve, delay));
    delay = Math.min(maxDelay, Math.round(delay * 1.4));
  }
}
