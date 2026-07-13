<template>
  <div class="control-panel">
    <div class="panel-header"><i class="el-icon-cpu"></i> Flow Model 检查与运行</div>

    <el-form label-width="120px" size="small">
      <el-form-item label="初始水头">
        <el-input-number
          v-model="localParams.initial_head_default"
          :step="0.1"
          style="width: 100%"
        ></el-input-number>
      </el-form-item>
      <el-form-item label="Kx">
        <el-input-number
          v-model="localParams.kx_default"
          :step="0.1"
          :min="0.0001"
          style="width: 100%"
        ></el-input-number>
      </el-form-item>
      <el-form-item label="Ky">
        <el-input-number
          v-model="localParams.ky_default"
          :step="0.1"
          :min="0.0001"
          style="width: 100%"
        ></el-input-number>
      </el-form-item>
      <el-form-item label="Kz">
        <el-input-number
          v-model="localParams.kz_default"
          :step="0.1"
          :min="0.0001"
          style="width: 100%"
        ></el-input-number>
      </el-form-item>
      <el-form-item label="ICELLTYPE">
        <el-radio-group v-model="localParams.icelltype">
          <el-radio-button :label="0">0</el-radio-button>
          <el-radio-button :label="1">1</el-radio-button>
        </el-radio-group>
      </el-form-item>

      <div class="checker-box" :class="{ ok: checkerRunnable, bad: flowCheck && !checkerRunnable }">
        <div class="checker-title">
          <i :class="checkerRunnable ? 'el-icon-circle-check' : 'el-icon-warning-outline'"></i>
          {{ checkerTitle }}
        </div>
        <div v-if="flowCheck && flowCheck.summary" class="checker-summary">
          CHD {{ flowCheck.summary.chd_cells || 0 }} / WEL {{ flowCheck.summary.wel_cells || 0 }} / K overrides {{ flowCheck.summary.k_overrides || 0 }}
        </div>
        <div v-if="packagePreview" class="checker-summary">
          Packages: {{ packagePreview.packages.join(', ') }}
        </div>
      </div>

      <el-button
        type="primary"
        plain
        style="width: 100%; margin-top: 10px;"
        @click="$emit('save-flow', localParams)"
        :loading="loading"
        icon="el-icon-document-checked"
      >
        保存并检查 Flow Model
      </el-button>

      <el-button
        type="success"
        style="width: 100%; margin-top: 10px; margin-left: 0;"
        @click="runModel"
        :disabled="!canRunFlow || runInProgress"
        :loading="loading || runInProgress"
        icon="el-icon-video-play"
      >
        运行 MODFLOW 6
      </el-button>

      <el-button
        v-if="runInProgress"
        type="danger"
        plain
        style="width: 100%; margin-top: 10px; margin-left: 0;"
        @click="$emit('cancel-run')"
        :loading="cancelling"
        icon="el-icon-close"
      >
        Cancel Run
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
        <span><i class="el-icon-document"></i> 运行日志 / 检查信息</span>
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
import { exportModel } from '../api/results';

export default {
  props: {
    loading: Boolean,
    hasResults: Boolean,
    resultPoints: Array,
    logs: { type: String, default: '' },
    flowCheck: { type: Object, default: null },
    packagePreview: { type: Object, default: null },
    canRunFlow: { type: Boolean, default: false },
    currentRun: { type: Object, default: null },
    polling: { type: Boolean, default: false },
    cancelling: { type: Boolean, default: false }
  },
  data() {
    return {
      localParams: {
        initial_head_default: 9.5,
        kx_default: 10.0,
        ky_default: 10.0,
        kz_default: 1.0,
        icelltype: 0
      },
      simulationLogs: ''
    };
  },
  computed: {
    checkerRunnable() {
      return Boolean(this.flowCheck && this.flowCheck.runnable);
    },
    checkerTitle() {
      if (!this.flowCheck) return '尚未检查 Flow Model';
      return this.checkerRunnable ? 'Flow Model 可运行' : 'Flow Model 存在阻断问题';
    },
    runInProgress() {
      const status = this.currentRun && this.currentRun.status;
      return this.polling || ['queued', 'starting', 'validating', 'compiling', 'writing_input', 'running', 'postprocessing', 'cancel_requested'].includes(status);
    }
  },
  watch: {
    logs(val) {
      this.simulationLogs = val;
    }
  },
  methods: {
    runModel() {
      this.simulationLogs = '';
      this.$emit('run', this.localParams);
    },
    async exportObj() {
      if (!this.resultPoints || this.resultPoints.length === 0) return;
      try {
        this.$message.info('正在生成模型文件...');
        const res = await exportModel(this.resultPoints);
        const url = window.URL.createObjectURL(new Blob([res.data]));
        const link = document.createElement('a');
        link.href = url;
        link.setAttribute('download', 'groundwater_model.obj');
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        this.$message.success('导出成功');
      } catch (e) {
        console.error(e);
        this.$message.error('导出失败');
      }
    }
  }
};
</script>

<style scoped>
.control-panel {
  background: #fff;
  padding: 15px;
  border-radius: 4px;
  border: 1px solid #ebeef5;
}
.panel-header {
  font-weight: 700;
  font-size: 14px;
  margin-bottom: 15px;
  border-bottom: 1px solid #eee;
  padding-bottom: 8px;
  color: #303133;
}
.checker-box {
  border: 1px solid #dcdfe6;
  border-radius: 4px;
  padding: 10px;
  background: #fafafa;
  color: #606266;
}
.checker-box.ok {
  border-color: #67c23a;
  background: #f0f9eb;
}
.checker-box.bad {
  border-color: #f56c6c;
  background: #fef0f0;
}
.checker-title {
  font-size: 13px;
  font-weight: 700;
}
.checker-summary {
  margin-top: 4px;
  font-size: 12px;
  color: #606266;
}
.log-container {
  margin-top: 15px;
  border-top: 1px dashed #ddd;
  padding-top: 10px;
}
.log-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 12px;
  color: #909399;
  margin-bottom: 5px;
}
.log-textarea >>> textarea {
  font-family: Consolas, Monaco, "Courier New", monospace;
  font-size: 11px;
  background-color: #f4f4f5;
  color: #333;
  white-space: pre;
}
</style>
