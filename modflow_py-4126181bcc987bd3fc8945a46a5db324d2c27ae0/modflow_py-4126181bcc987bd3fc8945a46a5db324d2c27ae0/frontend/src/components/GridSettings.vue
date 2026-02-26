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

      <el-tab-pane label="Z轴 (垂向)" name="z">
        <el-form size="mini" label-position="top">
          <el-form-item label="1. 搭建多少层 (Layers)">
            <el-input-number v-model="config.n_layers" :min="1" :max="20" style="width: 100%"></el-input-number>
          </el-form-item>
          <el-form-item label="2. 默认单层厚度 (m)">
            <el-input-number v-model="config.z_thick" :min="0.1" :step="1" style="width: 100%"></el-input-number>
            <div style="font-size:12px; color:#999; line-height:1.2; margin-top:5px;">
              * 此为初始厚度。后续可通过"地层管理"导入SHP自动计算精确顶底板高程。
            </div>
          </el-form-item>
        </el-form>
      </el-tab-pane>

    </el-tabs>

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
      activeTab: 'z',
      config: { x_mode: 'size', x_val: 1000, y_mode: 'size', y_val: 1000, n_layers: 5, z_thick: 100 }
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
<style scoped> .grid-settings { padding: 10px; background: #fff; } .actions { margin-top: 10px; } </style>