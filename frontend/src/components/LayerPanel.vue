<template>
  <div class="layer-panel-modern">
    
    <div class="upload-bar">
      <el-upload
        action=""
        :auto-upload="false"
        :on-change="handleFileChange"
        :show-file-list="false"
        accept=".csv"
        class="upload-component"
      >
        <el-button size="small" type="primary" plain icon="el-icon-folder-opened">导入钻孔 CSV</el-button>
      </el-upload>
      <span class="tip" v-if="!selectedFile"><i class="el-icon-info"></i> 需含坐标与分层</span>
      <span class="tip file-selected" v-else><i class="el-icon-document"></i> {{ selectedFile.name }}</span>
    </div>

    <el-button 
      type="primary" 
      size="small"
      class="full-btn mt-10" 
      @click="uploadBoreholes" 
      :loading="isUploading" 
      :disabled="!selectedFile"
    >
      <i class="el-icon-cpu"></i> {{ isUploading ? '正在解析地层数据...' : '解析地层并构建模型' }}
    </el-button>

    <transition name="el-fade-in-linear">
      <div v-if="uploadResult" class="result-box mt-10">
        <el-alert
          title="地层解析成功"
          :description="`共识别 ${uploadResult.boreholes_count} 个钻孔，地层 Z 轴已自动映射。`"
          type="success"
          show-icon
          :closable="false"
        ></el-alert>

        <el-button 
          type="success" 
          plain
          size="small"
          class="full-btn mt-10" 
          @click="$emit('preview-boreholes', uploadResult)" 
        >
          <i class="el-icon-view"></i> 在三维视图中预览钻孔
        </el-button>
      </div>
    </transition>

    <el-alert
      v-if="errorMessage"
      :title="errorMessage"
      type="error"
      show-icon
      class="mt-10"
    ></el-alert>
  </div>
</template>

<script setup>
import { ref } from 'vue';
import axios from 'axios';

const API_BASE_URL = 'http://localhost:5000'; 
const selectedFile = ref(null);
const isUploading = ref(false);
const uploadResult = ref(null);
const errorMessage = ref('');

const emit = defineEmits(['model-ready', 'preview-boreholes']);

const handleFileChange = (file) => {
  errorMessage.value = '';
  selectedFile.value = file.raw;
};

const uploadBoreholes = async () => {
  if (!selectedFile.value) return;

  // 使用 FileReader 读取 CSV 文本内容，用于保存进项目 JSON 中
  const reader = new FileReader();
  reader.onload = async (e) => {
    const csvContent = e.target.result;

    const formData = new FormData();
    formData.append('file', selectedFile.value);
    formData.append('project_id', 'default'); 

    isUploading.value = true;
    uploadResult.value = null;
    errorMessage.value = '';

    try {
      const response = await axios.post(`${API_BASE_URL}/upload-boreholes`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });
      if (response.data.success) {
        uploadResult.value = response.data;
        // 把后端的返回值和纯文本 csvContent 一起发给 App.vue
        emit('model-ready', { ...response.data, rawCsv: csvContent }); 
      } else {
        errorMessage.value = '解析失败: ' + response.data.error;
      }
    } catch (error) {
      errorMessage.value = error.response?.data?.error || '请求出错';
    } finally {
      isUploading.value = false;
    }
  };
  
  // 触发读取文件
  reader.readAsText(selectedFile.value);
};
</script>

<style scoped>
.layer-panel-modern { padding: 12px; }

/* 与 Step 5 同款的操作条样式 */
.upload-bar {
  display: flex; align-items: center; justify-content: space-between;
  background: #f4f4f5; padding: 8px 10px; border-radius: 4px; border: 1px solid #e4e7ed;
}
.upload-component { line-height: 1; }
.tip { font-size: 11px; color: #909399; max-width: 150px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.file-selected { color: #409EFF; font-weight: bold; }

/* 统一的按钮间距 */
.full-btn { width: 100%; letter-spacing: 1px; font-weight: bold; }
.mt-10 { margin-top: 10px; }
.result-box { animation: fadeIn 0.4s; }
</style>