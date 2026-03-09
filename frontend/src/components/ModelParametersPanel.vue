<template>
  <el-card class="floating-card scrollable-card" shadow="always" :body-style="{padding: '10px'}">
    <div slot="header">
      <span><i class="el-icon-setting"></i> 模型参数与运行 (Step 3-7)</span>
    </div>
    
    <el-collapse :value="activeStep" @input="val => $emit('update:activeStep', val)" accordion>
      
      <el-collapse-item name="3">
        <template slot="title">
          <span class="step-title"><i class="el-icon-s-grid"></i> Step 3: 网格离散化设置</span>
        </template>
        <GridSettings 
          :value="gridConfig" 
          @input="$emit('update:gridConfig', $event)" 
          @preview="$emit('preview-grid', $event)" 
        />
      </el-collapse-item>

      <el-collapse-item name="4">
        <template slot="title">
          <span class="step-title"><i class="el-icon-menu"></i> Step 4: 网格属性 (井/K)</span>
        </template>
        <AttributeManager 
          :wells="wells" 
          :kCells="kCells" 
          @delete-attribute="(val) => $emit('delete-attribute', val)"
          @type-change="(val) => $emit('type-change', val)" 
          @clear-all="$emit('clear-all')" 
        />
      </el-collapse-item>

      <el-collapse-item name="5">
        <template slot="title">
          <span class="step-title"><i class="el-icon-s-operation"></i> Step 5: 源汇项 (RCH/EVT) & 边界</span>
        </template>
        <RchEvtManager @update="(val) => $emit('update-rch-evt', val)" />
        <div style="margin-top: 10px;"></div>
        <BoundaryPanel 
          :selectedIndex="currentSegmentIdx" 
          :configuredData="boundaryConfigs"
          @save="(val) => $emit('save-boundary', val)" 
          @remove="(val) => $emit('remove-boundary', val)" 
        />
      </el-collapse-item>

      <el-collapse-item name="6">
        <template slot="title">
          <span class="step-title" style="color: #409EFF; font-weight: bold;">
            <i class="el-icon-cpu"></i> Step 6: 运行与导出
          </span>
        </template>
        <ControlPanel 
          :loading="loading" 
          :hasResults="resultPoints.length > 0" 
          :resultPoints="resultPoints"
          :logs="currentLogs"
          @run="(val) => $emit('run', val)" 
        />
      </el-collapse-item>

      <el-collapse-item name="7" v-if="resultPoints.length > 0">
        <template slot="title">
          <span class="step-title" style="color: #67C23A; font-weight: bold;">
            <i class="el-icon-pie-chart"></i> Step 7: 结果分析
          </span>
        </template>
        <AnalysisPanel :points="resultPoints" />
      </el-collapse-item>

    </el-collapse>
  </el-card>
</template>

<script>
// 引入原有的组件，将 LayerPanel 换成 GridSettings
import GridSettings from './GridSettings.vue';
import AttributeManager from './AttributeManager.vue';
import RchEvtManager from './RchEvtManager.vue';
import BoundaryPanel from './BoundaryPanel.vue';
import ControlPanel from './ControlPanel.vue';
import AnalysisPanel from './AnalysisPanel.vue';

export default {
  name: 'ModelParametersPanel',
  components: {
    GridSettings, // 注册 GridSettings
    AttributeManager,
    RchEvtManager,
    BoundaryPanel,
    ControlPanel,
    AnalysisPanel
  },
  props: {
    activeStep: { type: String, default: '3' },
    gridConfig: { type: Object, required: true },
    wells: { type: Array, default: () => [] },
    kCells: { type: Array, default: () => [] },
    currentSegmentIdx: { type: Number, default: null },
    boundaryConfigs: { type: Object, default: () => ({}) },
    loading: { type: Boolean, default: false },
    resultPoints: { type: Array, default: () => [] },
    currentLogs: { type: String, default: '' }
  }
};
</script>

<style scoped>
.scrollable-card { display: flex; flex-direction: column; height: 100%; max-height: 100%; overflow: hidden; }
.scrollable-card .el-card__header { flex-shrink: 0; background: #fcfcfc; padding: 12px 15px; }
.scrollable-card .el-card__body { flex-grow: 1; overflow-y: auto; padding: 0 !important; }

/* 手风琴样式微调 */
.el-collapse-item__header {
    padding-left: 15px;
    font-size: 13px;
    font-weight: 500;
}
.step-title { margin-left: 5px; }
.el-collapse-item__content { padding: 15px; }

/* 浮动卡片通用样式 */
.floating-card { 
  background: rgba(255, 255, 255, 0.98) !important; 
  backdrop-filter: blur(10px); 
  border-radius: 8px;
}
</style>