<template>
  <div class="grid-settings-modern">
    <el-alert
      title="地层 Z 轴将由钻孔数据自动接管"
      type="info"
      show-icon
      :closable="false"
      class="mb-10"
    ></el-alert>

    <div class="grid-controls">
      <div class="axis-panel">
        <div class="axis-header">X 轴切分设置</div>
        <el-radio-group v-model="config.x_mode" size="mini" class="mode-toggle">
          <el-radio-button label="size">尺寸(m)</el-radio-button>
          <el-radio-button label="count">数量(个)</el-radio-button>
        </el-radio-group>
        <el-input-number v-model="config.x_val" :min="1" size="mini" controls-position="right" class="num-input"></el-input-number>
      </div>

      <div class="axis-panel">
        <div class="axis-header">Y 轴切分设置</div>
        <el-radio-group v-model="config.y_mode" size="mini" class="mode-toggle">
          <el-radio-button label="size">尺寸(m)</el-radio-button>
          <el-radio-button label="count">数量(个)</el-radio-button>
        </el-radio-group>
        <el-input-number v-model="config.y_val" :min="1" size="mini" controls-position="right" class="num-input"></el-input-number>
      </div>
    </div>

    <el-button type="primary" size="small" class="full-btn" @click="emitPreview">
      <i class="el-icon-s-grid"></i> 生成 / 更新三维网格
    </el-button>
  </div>
</template>

<script>
export default {
  props: { value: Object },
  data() {
    return {
      config: { x_mode: 'size', x_val: 1000, y_mode: 'size', y_val: 1000, n_layers: 1, z_thick: 10 }
    };
  },
  watch: {
    // 修复点 3：必须监听外部传入的 value，以接收解析钻孔后自动变更的层数
    value: {
      immediate: true,
      deep: true,
      handler(val) {
        if (val && JSON.stringify(val) !== JSON.stringify(this.config)) {
          this.config = { ...this.config, ...val };
        }
      }
    },
    config: { 
      deep: true, 
      handler(val) { 
        this.$emit('input', val); 
      } 
    } 
  },
  methods: {
    emitPreview() {
      let sz = (this.config.x_mode === 'size') ? this.config.x_val : 1000; 
      this.$emit('preview', { size: sz, config: this.config });
    }
  }
};
</script>

<style scoped> 
.grid-settings-modern { padding: 5px; } 
.mb-10 { margin-bottom: 12px; }

.grid-controls { display: flex; gap: 10px; margin-bottom: 12px; }
.axis-panel { 
  flex: 1; border: 1px solid #e4e7ed; border-radius: 6px; padding: 10px; 
  background-color: #fafbfc; text-align: center; transition: all 0.3s ease;
}
.axis-panel:hover { border-color: #dcdfe6; box-shadow: 0 2px 8px rgba(0,0,0,0.05); }

.axis-header { font-size: 12px; font-weight: bold; color: #606266; margin-bottom: 10px; }

.mode-toggle { display: flex; width: 100%; margin-bottom: 10px; }
.mode-toggle >>> .el-radio-button { flex: 1; }
.mode-toggle >>> .el-radio-button__inner { width: 100%; padding: 6px 0; font-size: 11px; }

.num-input { width: 100%; }

.full-btn { width: 100%; font-weight: bold; letter-spacing: 1px; }
</style>