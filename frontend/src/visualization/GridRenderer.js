export function estimateDrawCalls(layerCount) {
  return Math.max(0, Number(layerCount || 0));
}

export function shouldUseLayerMode(totalCells, maxVisibleCells = 200000) {
  return Number(totalCells || 0) > maxVisibleCells;
}
