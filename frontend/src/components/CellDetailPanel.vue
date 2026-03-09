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
        
        <div class="head-row">
           <span class="label">水头 (Head):</span>
           <span class="value highlight">{{ cellData.head.toFixed(2) }} m</span>
        </div>

        <div class="flow-list-container" v-if="cellData.flows">
          <div class="grid-label">
            单元六向净流出量 (m³/d)<br/>
            <span style="font-size: 10px; color: #E6A23C;">(正数代表流出，负数代表流入)</span>
          </div>
          
          <div class="flow-item">
            <span class="dir"><i class="el-icon-right"></i> 东面 (Right):</span>
            <span :class="['val', cellData.flows.right > 0 ? 'out' : 'in']">{{ fmt(cellData.flows.right) }}</span>
          </div>
          <div class="flow-item">
            <span class="dir"><i class="el-icon-back"></i> 西面 (Left):</span>
            <span :class="['val', cellData.flows.left > 0 ? 'out' : 'in']">{{ fmt(cellData.flows.left) }}</span>
          </div>
          <div class="flow-item">
            <span class="dir"><i class="el-icon-bottom"></i> 南面 (Front):</span>
            <span :class="['val', cellData.flows.front > 0 ? 'out' : 'in']">{{ fmt(cellData.flows.front) }}</span>
          </div>
          <div class="flow-item">
            <span class="dir"><i class="el-icon-top"></i> 北面 (Back):</span>
            <span :class="['val', cellData.flows.back > 0 ? 'out' : 'in']">{{ fmt(cellData.flows.back) }}</span>
          </div>
          <div class="flow-item">
            <span class="dir"><i class="el-icon-upload2"></i> 顶面 (Top):</span>
            <span :class="['val', cellData.flows.top > 0 ? 'out' : 'in']">{{ fmt(cellData.flows.top) }}</span>
          </div>
          <div class="flow-item">
            <span class="dir"><i class="el-icon-download"></i> 底面 (Bottom):</span>
            <span :class="['val', cellData.flows.bottom > 0 ? 'out' : 'in']">{{ fmt(cellData.flows.bottom) }}</span>
          </div>
        </div>

        <div style="margin-top: 15px;">
          <el-button type="primary" size="mini" style="width: 100%" @click="$emit('trace-particle', cellData)">
            <i class="el-icon-share"></i> 从该点追踪流线
          </el-button>
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
      if (isNaN(num) || Math.abs(num) < 1e-10) return '0.00'; // 忽略极小计算误差
      // 为了好看，自动加上正号前缀，让正负对齐
      const prefix = num > 0 ? '+' : '';
      if (Math.abs(num) < 0.01 || Math.abs(num) > 100000) return prefix + num.toExponential(2);
      return prefix + num.toFixed(2);
    }
  }
};
</script>

<style scoped>
.flow-panel-compact {
  position: absolute; bottom: 20px; right: 410px; width: 260px;
  background: rgba(255, 255, 255, 0.98); 
  border-radius: 8px; box-shadow: 0 4px 20px rgba(0,0,0,0.25);
  font-family: 'Roboto Mono', monospace; z-index: 30;
  display: flex; flex-direction: column; border: 1px solid #ebeef5;
  pointer-events: auto;
}
.panel-header { background: #409EFF; color: #fff; padding: 10px 12px; display: flex; justify-content: space-between; align-items: center; font-size: 13px; font-weight: bold; border-top-left-radius: 8px; border-top-right-radius: 8px; }
.close-btn { cursor: pointer; font-size: 18px; line-height: 1; }
.close-btn:hover { color: #ffd04b; }
.panel-body { padding: 12px; font-size: 13px; color: #333; }
.head-row { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; border-bottom: 1px dashed #eee; padding-bottom: 8px;}
.highlight { color: #409EFF; font-weight: bold; font-size: 15px; }

.flow-list-container { background: #f8f9fa; padding: 10px; border-radius: 6px; border: 1px solid #e4e7ed; }
.grid-label { text-align: center; font-weight: bold; color: #606266; margin-bottom: 10px; font-size: 12px; line-height: 1.4; border-bottom: 1px solid #ebeef5; padding-bottom: 6px;}
.flow-item { display: flex; justify-content: space-between; align-items: center; padding: 4px 0; font-size: 12px; border-bottom: 1px dashed #f0f0f0;}
.flow-item:last-child { border-bottom: none; }
.flow-item .dir { color: #909399; }
.flow-item .val { font-family: Consolas, monospace; font-weight: bold; }
.flow-item .val.out { color: #F56C6C; } /* 流出用红色警告色 */
.flow-item .val.in { color: #67C23A; }  /* 流入用绿色安全色 */
</style>