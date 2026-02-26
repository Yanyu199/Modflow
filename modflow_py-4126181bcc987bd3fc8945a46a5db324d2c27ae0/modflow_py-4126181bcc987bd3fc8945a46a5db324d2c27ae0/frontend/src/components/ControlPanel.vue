<template>
  <div class="control-panel">
    <div class="panel-header"><i class="el-icon-cpu"></i> 运行与导出 (Step 6)</div>
    
    <el-form label-width="110px" size="small">
      <el-form-item label="渗透系数 (K)">
        <el-input-number v-model="localParams.k" :step="0.1" :min="0.1" style="width: 100%"></el-input-number>
      </el-form-item>

      <el-button 
        type="primary" 
        style="width: 100%; margin-top: 10px;" 
        @click="runModel"
        :loading="loading"
        icon="el-icon-video-play"
      >
        运行模拟 (Run)
      </el-button>
      
      <el-button 
        v-if="hasResults"
        type="success" 
        plain
        style="width: 100%; margin-top: 10px; margin-left: 0;" 
        @click="exportObj"
        icon="el-icon-download"
      >
        导出 3D 模型 (.obj)
      </el-button>
    </el-form>

    <div v-if="simulationLogs" class="log-container">
      <div class="log-header">
        <span><i class="el-icon-document"></i> 运行日志 / 错误详情</span>
        <el-button type="text" size="mini" @click="simulationLogs = ''">清除</el-button>
      </div>
      <el-input 
        type="textarea" 
        :rows="8" 
        readonly 
        v-model="simulationLogs"
        class="log-textarea"
      ></el-input>
    </div>
  </div>
</template>

<script>
import axios from 'axios';

export default {
  props: { 
    loading: Boolean,
    hasResults: Boolean,
    resultPoints: Array,
    // 接收来自父组件的日志
    logs: { type: String, default: '' } 
  },
  data() {
    return {
      localParams: { k: 10.0 },
      simulationLogs: '' // 本地副本，方便监控变化
    };
  },
  watch: {
    // 监听 prop 变化并同步
    logs(val) {
      this.simulationLogs = val;
    }
  },
  methods: {
    runModel() {
      this.simulationLogs = ''; // 再次运行时清空旧日志
      this.$emit('run', this.localParams);
    },
    async exportObj() {
      if (!this.resultPoints || this.resultPoints.length === 0) return;
      try {
        this.$message.info("正在生成模型文件...");
        const res = await axios.post('http://localhost:5000/export-model', {
          points: this.resultPoints
        }, { responseType: 'blob' });
        const url = window.URL.createObjectURL(new Blob([res.data]));
        const link = document.createElement('a');
        link.href = url;
        link.setAttribute('download', 'groundwater_model.obj');
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        this.$message.success("导出成功！");
      } catch (e) {
        console.error(e);
        this.$message.error("导出失败");
      }
    }
  }
};
</script>

<style scoped>
.control-panel { background: #fff; padding: 15px; border-radius: 4px; border: 1px solid #ebeef5; }
.panel-header { font-weight: bold; font-size: 14px; margin-bottom: 15px; border-bottom: 1px solid #eee; padding-bottom: 8px; color: #303133; }

.log-container { margin-top: 15px; border-top: 1px dashed #ddd; padding-top: 10px; }
.log-header { display: flex; justify-content: space-between; align-items: center; font-size: 12px; color: #909399; margin-bottom: 5px; }
/* 强制使用等宽字体，更像终端 */
.log-textarea >>> textarea {
  font-family: "Consolas", "Monaco", "Courier New", monospace;
  font-size: 11px;
  background-color: #f4f4f5;
  color: #333;
  white-space: pre;
}
</style>