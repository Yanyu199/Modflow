<template>
  <div class="layer-panel">
    <div class="panel-header">
      <i class="el-icon-files"></i> 地层参数赋值
    </div>
    
    <div class="layer-control">
      <span class="label">操作层级:</span>
      <el-select v-model="currentLayer" size="mini" style="width: 100px;">
        <el-option 
          v-for="i in totalLayers" 
          :key="i-1" 
          :label="`Layer ${i-1}`" 
          :value="i-1">
        </el-option>
      </el-select>
    </div>

    <div class="logic-tip">
      <div v-if="currentLayer < totalLayers - 1">
        <i class="el-icon-info"></i> <b>Layer {{currentLayer}} (普通层):</b><br/>
        请上传 <b>Top (顶板)</b> SHP。<br/>
        <span style="color: #E6A23C;">注意：本层的底板将由 Layer {{currentLayer+1}} 的 Top 自动决定。</span>
      </div>
      <div v-else>
        <i class="el-icon-warning"></i> <b>Layer {{currentLayer}} (最底层):</b><br/>
        请上传 <b>Top (顶板)</b> 和 <b>Bottom (底板)</b> SHP。<br/>
        这是模型的最后封底。
      </div>
    </div>

    <div class="upload-area">
      <div class="upload-row">
        <span class="row-label">Top (顶板):</span>
        <el-upload
          class="upload-inline"
          action="http://localhost:5000/upload-layer"
          :data="{ type: 'top', layer_index: currentLayer }"
          :show-file-list="false"
          :on-success="(res) => onSuccess(res, 'Top')"
          accept=".zip"
        >
          <el-button size="mini" type="primary" plain icon="el-icon-upload2">上传 SHP</el-button>
        </el-upload>
      </div>

      <div class="upload-row" v-if="currentLayer === totalLayers - 1">
        <span class="row-label">Bottom (底板):</span>
        <el-upload
          class="upload-inline"
          action="http://localhost:5000/upload-layer"
          :data="{ type: 'bottom', layer_index: currentLayer }"
          :show-file-list="false"
          :on-success="(res) => onSuccess(res, 'Bottom')"
          accept=".zip"
        >
          <el-button size="mini" type="warning" plain icon="el-icon-upload2">上传 SHP</el-button>
        </el-upload>
      </div>
      
      <div class="mini-tip" v-else>
        * 本层无需上传底板 (由下一层顶板决定)
      </div>
    </div>

    <div style="margin-top: 15px; border-top: 1px dashed #eee; padding-top: 10px;">
        <el-button 
          type="success" 
          size="small" 
          style="width: 100%;" 
          icon="el-icon-refresh"
          :disabled="!hasUploaded"
          @click="triggerUpdate"
        >
          更新模型
        </el-button>
    </div>
    
    <div class="log-box" v-if="lastUpload">
      <i class="el-icon-circle-check"></i> {{ lastUpload }}
    </div>
  </div>
</template>

<script>
export default {
  name: 'LayerPanel',
  props: {
    totalLayers: { type: Number, default: 1 }
  },
  data() {
    return {
      currentLayer: 0,
      lastUpload: '',
      // 追踪当前层是否有新上传
      hasUploaded: false
    };
  },
  watch: {
    totalLayers(val) {
      if (this.currentLayer >= val) this.currentLayer = 0;
      this.hasUploaded = false; // 层数变化重置
    },
    currentLayer() {
      // 切换层级时，重置按钮状态（防止误点）
      // 您也可以选择不重置，取决于是否允许用户随时点更新。
      // 根据需求“上传了...才可以点击”，建议切换后重置为 false，强迫用户在该层操作后才能更新。
      this.hasUploaded = false; 
      this.lastUpload = '';
    }
  },
  methods: {
    onSuccess(res, type) {
      if (res.success) {
        this.lastUpload = `Layer ${res.layer} ${type} 上传成功 (${res.count} 点)`;
        this.$message.success(`Layer ${res.layer} ${type} 数据已导入，请点击“更新模型”`);
        
        // 激活按钮
        this.hasUploaded = true;
        
        // 注意：这里不再自动 emit，而是等待用户点击按钮
      } else {
        this.$message.error("导入失败: " + res.error);
      }
    },
    triggerUpdate() {
      // 用户点击按钮，触发父组件刷新 3D
      this.$emit('layer-changed');
      this.$message.info("正在重新生成三维模型...");
    }
  }
};
</script>

<style scoped>
.layer-panel {
  padding: 12px;
  background: #fff;
  border: 1px solid #ebeef5;
  border-radius: 4px;
  margin-bottom: 10px;
}
.panel-header {
  font-weight: bold;
  font-size: 14px;
  margin-bottom: 12px;
  color: #303133;
  border-bottom: 1px solid #eee;
  padding-bottom: 8px;
}
.layer-control {
  display: flex;
  align-items: center;
  margin-bottom: 12px;
  font-size: 13px;
}
.label { margin-right: 10px; color: #606266; }

.logic-tip {
  background: #f4f4f5;
  color: #909399;
  font-size: 12px;
  padding: 8px;
  border-radius: 4px;
  margin-bottom: 12px;
  line-height: 1.5;
}
.logic-tip b { color: #606266; }

.upload-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
}
.row-label {
  font-size: 12px;
  color: #606266;
  width: 80px;
}
.upload-inline { display: inline-block; }

.mini-tip {
  font-size: 11px;
  color: #c0c4cc;
  margin-top: 4px;
}

.log-box {
  margin-top: 10px;
  font-size: 12px;
  color: #67C23A;
  background: #f0f9eb;
  padding: 6px;
  border-radius: 4px;
}
</style>