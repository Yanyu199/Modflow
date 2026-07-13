<template>
  <transition name="el-fade-in">
    <div class="flow-panel-compact" v-if="cellData">
      <div class="panel-header">
        <span class="cell-title">
          <i class="el-icon-location"></i>
          L{{ cellData.layer }}-R{{ cellData.row }}-C{{ cellData.col }}
        </span>
        <span class="close-btn" @click="$emit('close')">x</span>
      </div>

      <div class="panel-body">
        <div v-if="cellData.cell_id" class="detail-row block">
          <span class="label">cell_id</span>
          <span class="value cell-id-text">{{ cellData.cell_id }}</span>
        </div>

        <div class="detail-row">
          <span class="label">Center X/Y</span>
          <span class="value">
            {{ fmtCoord(cellData.center ? cellData.center.x : cellData.x) }},
            {{ fmtCoord(cellData.center ? cellData.center.y : cellData.y) }}
          </span>
        </div>
        <div class="detail-row">
          <span class="label">Top / Bottom</span>
          <span class="value">{{ fmt(cellData.top) }} / {{ fmt(cellData.bottom) }}</span>
        </div>
        <div class="detail-row">
          <span class="label">Thickness</span>
          <span class="value">{{ fmt(cellData.thickness) }}</span>
        </div>
        <div class="detail-row">
          <span class="label">idomain</span>
          <span class="value">{{ cellData.idomain }} · {{ cellData.active ? 'active' : 'inactive' }}</span>
        </div>

        <div class="head-row" v-if="cellData.head !== null && cellData.head !== undefined">
          <span class="label">Head</span>
          <span class="value highlight">{{ fmt(cellData.head) }} m</span>
        </div>

        <div class="flow-list-container" v-if="cellData.flows">
          <div class="grid-label">
            单元六向净流出量 (m3/d)
            <br>
            <span class="hint">正数表示流出，负数表示流入</span>
          </div>

          <div class="flow-item" v-for="item in flowItems" :key="item.key">
            <span class="dir">{{ item.label }}</span>
            <span :class="['val', cellData.flows[item.key] > 0 ? 'out' : 'in']">
              {{ fmt(cellData.flows[item.key]) }}
            </span>
          </div>
        </div>

        <div class="action-row">
          <el-button
            type="primary"
            size="mini"
            style="width: 100%"
            :disabled="!cellData.active"
            @click="$emit('trace-particle', cellData)"
          >
            <i class="el-icon-share"></i> 从该单元追踪流线
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
  data() {
    return {
      flowItems: [
        { key: 'right', label: 'Right' },
        { key: 'left', label: 'Left' },
        { key: 'front', label: 'Front' },
        { key: 'back', label: 'Back' },
        { key: 'top', label: 'Top' },
        { key: 'bottom', label: 'Bottom' }
      ]
    };
  },
  methods: {
    fmt(val) {
      if (val === undefined || val === null) return '-';
      const num = Number(val);
      if (!isFinite(num)) return '-';
      if (Math.abs(num) < 1e-10) return '0.00';
      const prefix = num > 0 ? '+' : '';
      if (Math.abs(num) < 0.01 || Math.abs(num) > 100000) return prefix + num.toExponential(2);
      return prefix + num.toFixed(2);
    },
    fmtCoord(val) {
      if (val === undefined || val === null) return '-';
      const num = Number(val);
      if (!isFinite(num)) return '-';
      return num.toFixed(2);
    }
  }
};
</script>

<style scoped>
.flow-panel-compact {
  position: absolute;
  bottom: 20px;
  right: 410px;
  width: 280px;
  background: rgba(255, 255, 255, 0.98);
  border-radius: 8px;
  box-shadow: 0 4px 20px rgba(0,0,0,0.25);
  font-family: 'Roboto Mono', Consolas, monospace;
  z-index: 30;
  display: flex;
  flex-direction: column;
  border: 1px solid #ebeef5;
  pointer-events: auto;
}
.panel-header {
  background: #409EFF;
  color: #fff;
  padding: 10px 12px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 13px;
  font-weight: bold;
  border-top-left-radius: 8px;
  border-top-right-radius: 8px;
}
.close-btn { cursor: pointer; font-size: 18px; line-height: 1; }
.close-btn:hover { color: #ffd04b; }
.panel-body { padding: 12px; font-size: 13px; color: #333; }
.detail-row {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 8px;
}
.detail-row.block { display: block; }
.label { color: #606266; }
.value { color: #303133; font-weight: 600; text-align: right; }
.cell-id-text {
  display: block;
  margin-top: 2px;
  font-size: 10px;
  line-height: 1.25;
  color: #606266;
  word-break: break-all;
  text-align: left;
}
.head-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin: 10px 0 12px;
  border-top: 1px dashed #eee;
  border-bottom: 1px dashed #eee;
  padding: 8px 0;
}
.highlight { color: #409EFF; font-weight: bold; font-size: 15px; }
.flow-list-container {
  background: #f8f9fa;
  padding: 10px;
  border-radius: 6px;
  border: 1px solid #e4e7ed;
}
.grid-label {
  text-align: center;
  font-weight: bold;
  color: #606266;
  margin-bottom: 10px;
  font-size: 12px;
  line-height: 1.4;
  border-bottom: 1px solid #ebeef5;
  padding-bottom: 6px;
}
.hint { font-size: 10px; color: #E6A23C; }
.flow-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 4px 0;
  font-size: 12px;
  border-bottom: 1px dashed #f0f0f0;
}
.flow-item:last-child { border-bottom: none; }
.flow-item .dir { color: #909399; }
.flow-item .val { font-family: Consolas, monospace; font-weight: bold; }
.flow-item .val.out { color: #F56C6C; }
.flow-item .val.in { color: #67C23A; }
.action-row { margin-top: 15px; }
</style>
