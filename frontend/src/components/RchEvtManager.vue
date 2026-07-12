<template>
  <div class="rch-evt-manager">
    <div class="header-title">
      <i class="el-icon-s-operation"></i> 源汇项管理 (Step 3)
    </div>
    
    <el-tabs v-model="activeTab" type="border-card" size="mini">
      
      <el-tab-pane label="入渗 (Recharge)" name="rch">
        <div class="tab-content">
          <div class="upload-bar">
            <el-upload
              action="http://localhost:5000/upload-scatter"
              :data="uploadData"
              :show-file-list="false"
              :before-upload="beforeUpload"
              :on-success="onRchSuccess"
              accept=".csv, .xlsx, .xls"
            >
              <el-button size="mini" type="primary" icon="el-icon-upload" :disabled="!projectId">导入散点数据</el-button>
            </el-upload>
            <el-button size="mini" type="text" @click="downloadTemplate">下载模板</el-button>
          </div>
          
          <div class="tip-bar">
            <span class="tip"><i class="el-icon-info"></i> 提示：1个点为全局均匀赋值；多点将自动进行最近邻空间插值。</span>
            <el-switch v-model="showRchContour" active-text="3D等值线显示" size="mini"></el-switch>
          </div>

          <el-table 
            v-if="rchList.length > 0" 
            :data="rchList" 
            height="180" 
            border 
            size="mini" 
            style="width: 100%; margin-top: 5px;"
          >
            <el-table-column type="index" label="ID" width="50" align="center"></el-table-column>
            <el-table-column prop="x" label="X坐标" :formatter="formatCoord"></el-table-column>
            <el-table-column prop="y" label="Y坐标" :formatter="formatCoord"></el-table-column>
            <el-table-column label="入渗率 (m/d)" width="120">
              <template slot-scope="scope">
                <el-input-number 
                  v-model="scope.row.value" 
                  :step="0.0001" 
                  :min="0"
                  size="mini" 
                  style="width: 100%"
                  controls-position="right">
                </el-input-number>
              </template>
            </el-table-column>
          </el-table>
          <div v-else class="empty-text">暂无数据，请导入包含 X, Y, Value 的表格</div>
        </div>
      </el-tab-pane>

      <el-tab-pane label="蒸发 (Evapotranspiration)" name="evt">
        <div class="tab-content">
          <div class="upload-bar">
            <el-upload
              action="http://localhost:5000/upload-scatter"
              :data="uploadData"
              :show-file-list="false"
              :before-upload="beforeUpload"
              :on-success="onEvtSuccess"
              accept=".csv, .xlsx, .xls"
            >
              <el-button size="mini" type="warning" icon="el-icon-upload" :disabled="!projectId">导入散点数据</el-button>
            </el-upload>
            <el-button size="mini" type="text" @click="downloadTemplate">下载模板</el-button>
          </div>

          <div class="tip-bar">
            <span class="tip"><i class="el-icon-info"></i> 提示：1个点为全局均匀赋值；多点将自动进行最近邻空间插值。</span>
            <el-switch v-model="showEvtContour" active-text="3D等值线显示" size="mini"></el-switch>
          </div>

          <el-table 
            v-if="evtList.length > 0" 
            :data="evtList" 
            height="180" 
            border 
            size="mini" 
            style="width: 100%; margin-top: 5px;"
          >
            <el-table-column type="index" label="ID" width="50" align="center"></el-table-column>
            <el-table-column prop="x" label="X坐标" :formatter="formatCoord"></el-table-column>
            <el-table-column prop="y" label="Y坐标" :formatter="formatCoord"></el-table-column>
            <el-table-column label="蒸发率 (m/d)" width="120">
              <template slot-scope="scope">
                <el-input-number 
                  v-model="scope.row.value" 
                  :step="0.0001" 
                  :min="0"
                  size="mini" 
                  style="width: 100%"
                  controls-position="right">
                </el-input-number>
              </template>
            </el-table-column>
          </el-table>
          <div v-else class="empty-text">暂无数据，请导入包含 X, Y, Value 的表格</div>
        </div>
      </el-tab-pane>

    </el-tabs>
  </div>
</template>

<script>
export default {
  name: 'RchEvtManager',
  props: {
    projectId: { type: String, default: null }
  },
  data() {
    return {
      activeTab: 'rch',
      rchList: [],
      evtList: [],
      showRchContour: false,
      showEvtContour: false
    };
  },
  computed: {
    uploadData() {
      return { project_id: this.projectId || '' };
    }
  },
  watch: {
    rchList: { deep: true, handler() { this.emitData(); } },
    evtList: { deep: true, handler() { this.emitData(); } },
    showRchContour() { this.emitData(); },
    showEvtContour() { this.emitData(); }
  },
  methods: {
    beforeUpload() {
      if (!this.projectId) {
        this.$message.warning('请先创建工程');
        return false;
      }
      return true;
    },
    onRchSuccess(res) {
      if (res.success) {
        this.rchList = res.data;
        this.$message.success(`入渗数据导入成功: 解析到 ${res.data.length} 个监测点`);
      } else {
        this.$message.error('导入失败: ' + res.error);
      }
    },
    onEvtSuccess(res) {
      if (res.success) {
        this.evtList = res.data;
        this.$message.success(`蒸发数据导入成功: 解析到 ${res.data.length} 个监测点`);
      } else {
        this.$message.error('导入失败: ' + res.error);
      }
    },
    formatCoord(row, column, cellValue) {
      return Number(cellValue).toFixed(2);
    },
    downloadTemplate() {
      const csvContent = "data:text/csv;charset=utf-8,X,Y,Value\n500000,4500000,0.005\n500100,4500100,0.006";
      const encodedUri = encodeURI(csvContent);
      const link = document.createElement("a");
      link.setAttribute("href", encodedUri);
      link.setAttribute("download", "scatter_template.csv");
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
    },
    emitData() {
      // 向上层抛出数据与渲染开关
      this.$emit('update', {
        rch: this.rchList,
        evt: this.evtList,
        showRchContour: this.showRchContour,
        showEvtContour: this.showEvtContour
      });
    }
  }
};
</script>

<style scoped>
.rch-evt-manager {
  background: #fff;
  border-radius: 4px;
  border: 1px solid #ebeef5;
  margin-bottom: 10px;
  padding: 10px;
}
.header-title {
  font-size: 13px; font-weight: bold; margin-bottom: 10px; color: #303133;
}
.upload-bar {
  display: flex; align-items: center; justify-content: space-between; margin-bottom: 5px;
}
.tip-bar {
  display: flex; align-items: center; justify-content: space-between;
  background: #f0f9eb; padding: 5px 8px; border-radius: 4px; margin-bottom: 5px;
}
.tip { font-size: 11px; color: #67C23A; }
.empty-text { text-align: center; color: #ccc; font-size: 12px; padding: 20px; }
</style>
