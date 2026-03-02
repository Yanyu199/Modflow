<template>
  <div class="layer-control-panel" v-if="visibility.length > 0">
    <div class="panel-title"><i class="el-icon-files"></i> 图层显隐控制</div>
    <div class="layer-list">
      <el-checkbox 
        v-for="(vis, idx) in localVisibility" 
        :key="idx" 
        v-model="localVisibility[idx]"
        @change="handleChange"
      >
        Layer {{ idx }} (原分层ID: {{ layerMapping[idx] !== undefined ? layerMapping[idx] : idx + 1 }})
      </el-checkbox>
    </div>
  </div>
</template>

<script>
export default {
  name: 'LayerVisibilityPanel',
  props: {
    visibility: { type: Array, required: true },
    layerMapping: { type: Object, default: () => ({}) }
  },
  data() {
    return {
      localVisibility: [...this.visibility]
    };
  },
  watch: {
    visibility(newVal) {
      this.localVisibility = [...newVal];
    }
  },
  methods: {
    handleChange() {
      // 触发更新事件并将新的数组传递给父组件
      this.$emit('update:visibility', this.localVisibility);
      this.$emit('visibility-change', this.localVisibility);
    }
  }
};
</script>

<style scoped>
.layer-control-panel {
  position: absolute; bottom: 20px; left: 480px;
  background: rgba(255, 255, 255, 0.9); padding: 10px; border-radius: 6px;
  box-shadow: 0 2px 12px rgba(0,0,0,0.15); max-height: 200px; overflow-y: auto; z-index: 20;
  pointer-events: auto;
}
.panel-title { font-weight: bold; font-size: 13px; margin-bottom: 5px; border-bottom: 1px solid #eee; padding-bottom: 5px; }
.layer-list { display: flex; flex-direction: column; }
.layer-list .el-checkbox { margin-right: 0; margin-bottom: 2px; }
</style>