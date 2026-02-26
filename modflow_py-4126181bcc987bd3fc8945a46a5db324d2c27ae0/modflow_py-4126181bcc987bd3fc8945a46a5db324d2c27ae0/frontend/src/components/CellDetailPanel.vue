<template>
  <transition name="el-fade-in">
    <div class="flow-panel-compact" v-if="cellData && cellData.head !== null">
      <div class="panel-header">
        <span class="cell-id">
          <i class="el-icon-location"></i> L{{cellData.layer}}-R{{cellData.row}}-C{{cellData.col}}
        </span>
        <span class="close-btn" @click="$emit('close')">×</span>
      </div>
      <div class="panel-body">
        <div style="margin-top: 10px; border-top: 1px dashed #eee; padding-top: 10px;">
          <el-button type="primary" size="mini" style="width: 100%" @click="$emit('trace-particle', cellData)">
            从该点追踪路径
          </el-button>
        </div>
        <div class="head-row">
           <span class="label">水头 (Head):</span>
           <span class="value highlight">{{ cellData.head.toFixed(2) }} m</span>
        </div>
        <div class="flow-grid-container" v-if="cellData.flows">
          <div class="grid-label">单元流量通量 (m³/d)</div>
          <div class="mini-grid">
             <div class="mini-cell empty"></div>
             <div class="mini-cell top" title="Top">↑ {{ fmt(cellData.flows.top) }}</div>
             <div class="mini-cell empty"></div>
             
             <div class="mini-cell left" title="Left">← {{ fmt(cellData.flows.left) }}</div>
             <div class="mini-cell center"><i class="el-icon-s-data"></i></div>
             <div class="mini-cell right" title="Right">{{ fmt(cellData.flows.right) }} →</div>
             
             <div class="mini-cell empty"></div>
             <div class="mini-cell bottom" title="Bottom">↓ {{ fmt(cellData.flows.bottom) }}</div>
             <div class="mini-cell empty"></div>
          </div>
          <div class="z-flow-row">
             <div class="z-item"><span>Front:</span> {{ fmt(cellData.flows.front) }}</div>
             <div class="z-item"><span>Back:</span> {{ fmt(cellData.flows.back) }}</div>
          </div>
        </div>
      </div>
    </div>
  </transition>
</template>

<script>
export default {
  name: 'CellDetailPanel',
  props: {
    cellData: {
      type: Object,
      default: null
    }
  },
  methods: {
    fmt(val) {
      if (val === undefined || val === null) return '0.00';
      const num = parseFloat(val);
      if (isNaN(num)) return '0.00';
      if (Math.abs(num) < 0.001 && Math.abs(num) > 0) return num.toExponential(1);
      return num.toFixed(2);
    }
  }
};
</script>

<style scoped>
.flow-panel-compact {
  position: absolute; bottom: 20px; right: 410px; width: 240px;
  background: rgba(255, 255, 255, 0.98); 
  border-radius: 8px; box-shadow: 0 4px 20px rgba(0,0,0,0.25);
  font-family: 'Roboto Mono', monospace; z-index: 30;
  display: flex; flex-direction: column; border: 1px solid #ebeef5;
  pointer-events: auto;
}
.panel-header { background: #409EFF; color: #fff; padding: 10px 12px; display: flex; justify-content: space-between; align-items: center; font-size: 13px; font-weight: bold; border-top-left-radius: 8px; border-top-right-radius: 8px; }
.close-btn { cursor: pointer; font-size: 18px; line-height: 1; }
.close-btn:hover { color: #ffd04b; }
.panel-body { padding: 12px; font-size: 12px; color: #333; }
.head-row { display: flex; justify-content: space-between; margin-bottom: 10px; border-bottom: 1px solid #eee; padding-bottom: 8px;}
.highlight { color: #409EFF; font-weight: bold; font-size: 14px; }
.flow-grid-container { background: #f8f9fa; padding: 8px; border-radius: 4px; border: 1px solid #e4e7ed; }
.grid-label { text-align: center; color: #909399; margin-bottom: 5px; font-size: 11px; }
.mini-grid { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 3px; margin-bottom: 5px; text-align: center; }
.mini-cell { padding: 4px 2px; border-radius: 3px; font-size: 11px; display: flex; align-items: center; justify-content: center; }
.mini-cell.top, .mini-cell.bottom { background: #e1f3d8; color: #67C23A; font-weight: bold; cursor: help; }
.mini-cell.left, .mini-cell.right { background: #d9ecff; color: #409EFF; font-weight: bold; cursor: help; }
.mini-cell.center { color: #909399; font-size: 14px; }
.z-flow-row { display: flex; justify-content: space-between; font-size: 11px; color: #606266; margin-top: 5px; padding-top: 5px; border-top: 1px dashed #ddd; }
.z-item { background: #fff; padding: 2px 5px; border-radius: 3px; border: 1px solid #eee; }
</style>