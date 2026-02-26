<template>
  <div class="legend-panel" v-if="visible && min !== null && max !== null">
    <div class="legend-title">水头 (m)</div>
    <div class="legend-body">
      <div class="legend-labels">
        <span>{{ max.toFixed(2) }}</span>
        <span>{{ ((max + min) / 2).toFixed(2) }}</span>
        <span>{{ min.toFixed(2) }}</span>
      </div>
      <div class="gradient-bar"></div>
    </div>
  </div>
</template>

<script>
export default {
  name: 'LegendPanel',
  props: {
    min: { type: Number, default: null },
    max: { type: Number, default: null },
    visible: { type: Boolean, default: true }
  }
};
</script>

<style scoped>
.legend-panel {
  position: absolute;
  bottom: 20px;
  right: 660px; /* 根据实际布局调整 */
  background: rgba(255, 255, 255, 0.9);
  padding: 10px;
  border-radius: 6px;
  box-shadow: 0 2px 12px rgba(0,0,0,0.15);
  z-index: 20;
  pointer-events: auto;
  display: flex;
  flex-direction: column;
  align-items: center;
}
.legend-title {
  font-size: 12px;
  font-weight: bold;
  color: #333;
  margin-bottom: 5px;
}
.legend-body {
  display: flex;
  flex-direction: row;
  align-items: center;
  height: 120px; 
}
.gradient-bar {
  width: 15px;
  height: 100%;
  border-radius: 2px;
  /* 修改：从下(红/低) 到 上(蓝/高) 的渐变 */
  background: linear-gradient(to top, 
    hsl(0, 80%, 50%),    /* Red (Min/Low) */
    hsl(60, 80%, 50%),   /* Yellow */
    hsl(120, 80%, 50%),  /* Green */
    hsl(180, 80%, 50%),  /* Cyan */
    hsl(240, 80%, 50%)   /* Blue (Max/High) */
  );
  border: 1px solid #ccc;
  margin-left: 8px;
}
.legend-labels {
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  height: 100%;
  text-align: right;
  font-size: 11px;
  font-weight: bold;
  color: #555;
  font-family: monospace;
}
</style>