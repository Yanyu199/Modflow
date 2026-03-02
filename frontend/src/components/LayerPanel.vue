<template>
  <div class="layer-panel">
    <h3>三维地层与钻孔数据</h3>
    
    <div class="upload-section">
      <div class="file-input-wrapper">
        <label for="csv-upload" class="file-label">选择钻孔分层数据 (CSV)</label>
        <input id="csv-upload" type="file" accept=".csv" @change="handleFileChange" ref="fileInput" />
        <span class="file-name" v-if="selectedFile">{{ selectedFile.name }}</span>
      </div>

      <button class="action-btn upload-btn" @click="uploadBoreholes" :disabled="!selectedFile || isUploading">
        {{ isUploading ? '正在解析...' : '第 1 步：上传并解析数据' }}
      </button>
    </div>

    <div v-if="uploadResult" class="result-info">
      <div class="success-msg">✅ 钻孔解析成功 (共 {{ uploadResult.boreholes_count }} 个)</div>
      
      <button class="action-btn preview-btn" @click="$emit('preview-boreholes', uploadResult)" style="margin-top: 10px; width: 100%;">
        <i class="el-icon-view"></i> 第 2 步：在右侧三维中预览钻孔
      </button>
      
      <p class="hint">提示：预览无误后，请前往上方 【Step 2: 网格离散化设置】 设置 XY 密度并生成最终模型。</p>
    </div>

    <div v-if="errorMessage" class="error-msg">❌ {{ errorMessage }}</div>
  </div>
</template>

<script setup>
import { ref } from 'vue';
import axios from 'axios';

const API_BASE_URL = 'http://localhost:5000'; 
const fileInput = ref(null);
const selectedFile = ref(null);
const isUploading = ref(false);
const uploadResult = ref(null);
const errorMessage = ref('');

// ⭐ 声明新增的事件
const emit = defineEmits(['model-ready', 'preview-boreholes']);

const handleFileChange = (e) => {
  errorMessage.value = '';
  if (e.target.files.length > 0) selectedFile.value = e.target.files[0];
};

const uploadBoreholes = async () => {
  if (!selectedFile.value) return;
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
      // 仅传递数据准备好的信号，不再立刻触发网格生成
      emit('model-ready', response.data); 
    } else {
      errorMessage.value = '解析失败: ' + response.data.error;
    }
  } catch (error) {
    errorMessage.value = error.response?.data?.error || '请求出错';
  } finally {
    isUploading.value = false;
  }
};
</script>

<style scoped>
.layer-panel { padding: 15px; background-color: #f8f9fa; border-radius: 8px; border: 1px solid #e9ecef; margin-bottom: 15px; }
h3 { margin-top: 0; margin-bottom: 15px; font-size: 16px; border-bottom: 2px solid #dee2e6; padding-bottom: 8px; }
.upload-section { display: flex; flex-direction: column; gap: 12px; }
.file-input-wrapper { display: flex; align-items: center; gap: 10px; }
.file-label { background-color: #e9ecef; border: 1px solid #ced4da; padding: 6px 12px; border-radius: 4px; cursor: pointer; font-size: 14px; }
input[type="file"] { display: none; }
.file-name { font-size: 12px; max-width: 200px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.action-btn { padding: 8px 16px; border: none; border-radius: 4px; font-weight: bold; cursor: pointer; transition: all 0.2s; }
.upload-btn { background-color: #0d6efd; color: white; }
.upload-btn:hover:not(:disabled) { background-color: #0b5ed7; }
/* 预览按钮的样式 */
.preview-btn { background-color: #198754; color: white; }
.preview-btn:hover { background-color: #157347; }
.result-info { margin-top: 15px; padding: 12px; background-color: #d1e7dd; border: 1px solid #badbcc; border-radius: 6px; }
.success-msg { font-weight: bold; color: #0f5132;}
.hint { margin-top: 10px; font-size: 12px; color: #146c43; }
.error-msg { margin-top: 15px; padding: 10px; background-color: #f8d7da; border-radius: 6px; color: #842029; font-size: 14px; }
</style>