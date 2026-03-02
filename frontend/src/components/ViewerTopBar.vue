<template>
  <div class="top-control-bar">
    <span class="control-label">Z轴: {{ localZScale }}x</span>
    <el-slider 
      v-model="localZScale" 
      :min="1" :max="50" :step="1"
      @input="$emit('update:zScale', localZScale); $emit('z-change')" 
      style="width: 100px; display: inline-block; vertical-align: middle; margin: 0 10px;">
    </el-slider>
    
    <el-divider direction="vertical"></el-divider>

    <span class="control-label">透明度: {{ localOpacity }}</span>
    <el-slider 
      v-model="localOpacity" 
      :min="0.1" :max="1.0" :step="0.1"
      @input="$emit('update:opacity', localOpacity); $emit('opacity-change')" 
      style="width: 100px; display: inline-block; vertical-align: middle; margin: 0 10px;">
    </el-slider>

    <el-divider direction="vertical"></el-divider>

    <el-checkbox 
      v-model="localShowFlow" 
      border size="mini" 
      @change="$emit('update:showFlow', localShowFlow); $emit('flow-change')"
      style="margin-left: 0; margin-right: 10px; background: #fff; padding: 5px 10px; height: 32px;">
      <span style="font-weight: bold; color: #00008B;">流向</span>
    </el-checkbox>

    <div v-if="localShowFlow" style="display: inline-flex; align-items: center;">
      <span class="control-label">稀疏度: {{ localFlowStep }}</span>
      <el-slider 
        v-model="localFlowStep" 
        :min="1" :max="10" :step="1"
        @change="$emit('update:flowStep', localFlowStep); $emit('flow-change')" 
        style="width: 80px; display: inline-block; vertical-align: middle; margin: 0 10px;">
      </el-slider>
    </div>

    <el-divider direction="vertical"></el-divider>

    <el-checkbox 
      v-model="localShowLegend" 
      border size="mini" 
      @change="$emit('update:showLegend', localShowLegend)"
      style="margin-left: 0; background: #fff; padding: 5px 10px; height: 32px;">
      <span style="font-weight: bold; color: #E6A23C;">色带</span>
    </el-checkbox>
  </div>
</template>

<script>
export default {
  name: 'ViewerTopBar',
  props: {
    zScale: Number,
    opacity: Number,
    showFlow: Boolean,
    flowStep: Number,
    showLegend: Boolean
  },
  data() {
    return {
      localZScale: this.zScale,
      localOpacity: this.opacity,
      localShowFlow: this.showFlow,
      localFlowStep: this.flowStep,
      localShowLegend: this.showLegend
    };
  },
  watch: {
    zScale(val) { this.localZScale = val; },
    opacity(val) { this.localOpacity = val; },
    showFlow(val) { this.localShowFlow = val; },
    flowStep(val) { this.localFlowStep = val; },
    showLegend(val) { this.localShowLegend = val; }
  }
};
</script>

<style scoped>
.top-control-bar {
  position: absolute; 
  top: 70px; 
  left: 50%; 
  transform: translateX(-50%);
  background: rgba(255, 255, 255, 0.95); 
  padding: 8px 15px; 
  border-radius: 20px;
  box-shadow: 0 2px 10px rgba(0,0,0,0.1); 
  z-index: 90; 
  display: flex; 
  align-items: center; 
  white-space: nowrap;
  pointer-events: auto; 
}
.control-label { font-size: 13px; font-weight: bold; color: #333; margin-right: 5px;}
</style>