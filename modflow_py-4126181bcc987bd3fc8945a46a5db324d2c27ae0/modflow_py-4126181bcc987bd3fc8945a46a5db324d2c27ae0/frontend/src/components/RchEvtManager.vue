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
              action="http://localhost:5000/upload-zone"
              :show-file-list="false"
              :on-success="onRchSuccess"
              accept=".zip"
            >
              <el-button size="mini" type="primary" icon="el-icon-upload">导入分区SHP</el-button>
            </el-upload>
            <span class="tip">SHP属性需含 'rate' 或 'val'</span>
          </div>

          <el-table 
            v-if="rchList.length > 0" 
            :data="rchList" 
            height="180" 
            border 
            size="mini" 
            style="width: 100%; margin-top: 5px;"
          >
            <el-table-column prop="id" label="ID" width="50"></el-table-column>
            <el-table-column label="入渗率 (m/d)">
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
            <el-table-column label="查看" width="50" align="center">
              <template slot-scope="scope">
                <el-button type="text" icon="el-icon-view" @click="previewZone(scope.row, '入渗分区')"></el-button>
              </template>
            </el-table-column>
          </el-table>
          <div v-else class="empty-text">暂无数据</div>
        </div>
      </el-tab-pane>

      <el-tab-pane label="蒸发 (Evapotranspiration)" name="evt">
        <div class="tab-content">
          <div class="upload-bar">
            <el-upload
              action="http://localhost:5000/upload-zone"
              :show-file-list="false"
              :on-success="onEvtSuccess"
              accept=".zip"
            >
              <el-button size="mini" type="warning" icon="el-icon-upload">导入分区SHP</el-button>
            </el-upload>
            <span class="tip">SHP属性需含 'rate' 或 'val'</span>
          </div>

          <el-table 
            v-if="evtList.length > 0" 
            :data="evtList" 
            height="180" 
            border 
            size="mini" 
            style="width: 100%; margin-top: 5px;"
          >
            <el-table-column prop="id" label="ID" width="50"></el-table-column>
            <el-table-column label="蒸发率 (m/d)">
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
            <el-table-column label="查看" width="50" align="center">
              <template slot-scope="scope">
                <el-button type="text" icon="el-icon-view" @click="previewZone(scope.row, '蒸发分区')"></el-button>
              </template>
            </el-table-column>
          </el-table>
          <div v-else class="empty-text">暂无数据</div>
        </div>
      </el-tab-pane>

    </el-tabs>

    <el-dialog :title="dialogTitle" :visible.sync="dialogVisible" width="300px" append-to-body>
      <div v-if="currentZone" class="zone-info">
        <p><strong>分区 ID:</strong> {{ currentZone.id }}</p>
        <p><strong>顶点数量:</strong> {{ currentZone.coords.length }}</p>
        <p><strong>当前设定值:</strong> {{ currentZone.value }} m/d</p>
        <div class="info-note">
          <i class="el-icon-info"></i> 系统将在运行时自动匹配该多边形覆盖的网格，并应用上述数值。
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<script>
export default {
  name: 'RchEvtManager',
  data() {
    return {
      activeTab: 'rch',
      rchList: [],
      evtList: [],
      dialogVisible: false,
      currentZone: null,
      dialogTitle: ''
    };
  },
  watch: {
    // 数据变动时通知父组件
    rchList: { deep: true, handler() { this.emitData(); } },
    evtList: { deep: true, handler() { this.emitData(); } }
  },
  methods: {
    onRchSuccess(res) {
      if (res.success) {
        this.rchList = res.zones;
        this.$message.success(`入渗分区导入成功: ${res.zones.length} 个`);
      } else {
        this.$message.error('导入失败');
      }
    },
    onEvtSuccess(res) {
      if (res.success) {
        this.evtList = res.zones;
        this.$message.success(`蒸发分区导入成功: ${res.zones.length} 个`);
      } else {
        this.$message.error('导入失败');
      }
    },
    previewZone(zone, title) {
      this.currentZone = zone;
      this.dialogTitle = title;
      this.dialogVisible = true;
    },
    emitData() {
      this.$emit('update', {
        rch: this.rchList,
        evt: this.evtList
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
.tip { font-size: 10px; color: #999; }
.empty-text { text-align: center; color: #ccc; font-size: 12px; padding: 20px; }
.zone-info p { margin: 5px 0; font-size: 13px; }
.info-note { background: #f0f9eb; color: #67C23A; padding: 8px; font-size: 12px; margin-top: 10px; border-radius: 4px; line-height: 1.4; }
</style>