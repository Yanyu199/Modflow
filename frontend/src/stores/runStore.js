import Vue from 'vue';
import { cancelRun, createRun, isTerminalRunStatus, listRuns, pollRun } from '../api/runs';

export const runStore = Vue.observable({
  currentRun: null,
  runHistory: [],
  polling: false,
  submitting: false,
  cancelling: false,
  error: null
});

let activePollToken = 0;

export function setCurrentRun(run) {
  runStore.currentRun = run || null;
}

export function setRunHistory(runs) {
  runStore.runHistory = Array.isArray(runs) ? runs : [];
}

export async function refreshRunHistory(projectId, params = { limit: 10 }) {
  if (!projectId) return [];
  const response = await listRuns(projectId, params);
  setRunHistory(response.data.runs || []);
  return runStore.runHistory;
}

export async function submitAndPollRun(projectId, flowModelId, options = {}) {
  runStore.submitting = true;
  runStore.error = null;
  const idempotencyKey = options.idempotencyKey || `${projectId}:${flowModelId}`;
  try {
    const response = await createRun(
      projectId,
      { flow_model_id: flowModelId, keep_artifacts: options.keepArtifacts },
      { headers: { 'Idempotency-Key': idempotencyKey } }
    );
    setCurrentRun(response.data.run || null);
    const runId = response.data.run_id;
    const pollToken = ++activePollToken;
    runStore.submitting = false;
    runStore.polling = true;
    const finalRun = await pollRun(projectId, runId, {
      onUpdate(run) {
        if (pollToken === activePollToken) setCurrentRun(run);
      }
    });
    if (pollToken === activePollToken) {
      setCurrentRun(finalRun);
      runStore.polling = false;
    }
    await refreshRunHistory(projectId);
    return finalRun;
  } catch (error) {
    runStore.error = error;
    runStore.submitting = false;
    runStore.polling = false;
    throw error;
  }
}

export async function requestRunCancel(projectId, runId, reason = 'user requested cancel') {
  if (!projectId || !runId) return null;
  if (runStore.currentRun && isTerminalRunStatus(runStore.currentRun.status)) return runStore.currentRun;
  runStore.cancelling = true;
  try {
    const response = await cancelRun(projectId, runId, { reason });
    setCurrentRun(response.data.run || null);
    return runStore.currentRun;
  } finally {
    runStore.cancelling = false;
  }
}

export function stopRunPolling() {
  activePollToken += 1;
  runStore.polling = false;
}

export function resetRunStore() {
  stopRunPolling();
  setCurrentRun(null);
  setRunHistory([]);
  runStore.submitting = false;
  runStore.cancelling = false;
  runStore.error = null;
}
