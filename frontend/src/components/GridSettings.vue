<template>
  <div class="grid-settings">
    <el-tabs v-model="activeTab" type="card" size="small">
      
      <el-tab-pane label="X轴" name="x">
        <el-form size="mini" label-position="top">
          <el-form-item label="切分方式">
            <el-radio-group v-model="config.x_mode">
              <el-radio label="size">网格尺寸 (m)</el-radio>
              <el-radio label="count">网格数量 (个)</el-radio>
            </el-radio-group>
          </el-form-item>
          <el-form-item>
            <el-input-number v-model="config.x_val" :min="1" style="width: 100%"></el-input-number>
          </el-form-item>
        </el-form>
      </el-tab-pane>

      <el-tab-pane label="Y轴" name="y">
        <el-form size="mini" label-position="top">
          <el-form-item label="切分方式">
            <el-radio-group v-model="config.y_mode">
              <el-radio label="size">网格尺寸 (m)</el-radio>
              <el-radio label="count">网格数量 (个)</el-radio>
            </el-radio-group>
          </el-form-item>
          <el-form-item>
            <el-input-number v-model="config.y_val" :min="1" style="width: 100%"></el-input-number>
          </el-form-item>
        </el-form>
      </el-tab-pane>

    </el-tabs>

    <div style="font-size:12px; color:#67C23A; margin: 5px 0 10px 0; text-align: center;">
      <i class="el-icon-circle-check"></i> Z 轴地层将由钻孔数据自动识别构建
    </div>

    <div class="actions">
      <el-button type="primary" size="mini" plain style="width: 100%" @click="emitPreview">
        生成 / 更新网格架构
      </el-button>
    </div>
  </div>
</template>

<script>
export default {
  props: { value: Object },
  data() {
    return {
      activeTab: 'x', // 默认打开 X 轴面板
      // 保留后端的 n_layers 和 z_thick 以防报错，但不再通过 UI 让用户手动填
      config: { x_mode: 'size', x_val: 100, y_mode: 'size', y_val: 100, n_layers: 1, z_thick: 10 }
    };
  },
  watch: { config: { deep: true, handler(val) { this.$emit('input', val); } } },
  mounted() { this.$emit('input', this.config); },
  methods: {
    emitPreview() {
      let sz = (this.config.x_mode === 'size') ? this.config.x_val : 50; 
      this.$emit('preview', { size: sz, config: this.config });
    }
  }
};
</script>

<style scoped> 
.grid-settings { padding: 10px; background: #fff; } 
.actions { margin-top: 10px; } 
</style>