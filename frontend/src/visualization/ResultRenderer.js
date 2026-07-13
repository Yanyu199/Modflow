export function sliceKey({ projectId, runId, variable, layer, timeIndex, rowStart, rowEnd, columnStart, columnEnd, format }) {
  return [
    projectId,
    runId,
    variable || 'head',
    layer || 0,
    timeIndex === undefined ? -1 : timeIndex,
    rowStart || 0,
    rowEnd || '',
    columnStart || 0,
    columnEnd || '',
    format || 'binary'
  ].join(':');
}
