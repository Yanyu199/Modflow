<template>
  <div id="app">
    <div class="app-header">
      <span class="app-title">地下水模型模拟平台</span>
      
      <div class="header-tools">
        <el-button type="text" icon="el-icon-download" class="header-btn" @click="saveProject">
          保存项目
        </el-button>
        <el-upload
          action=""
          :auto-upload="false"
          :show-file-list="false"
          :on-change="loadProject"
          accept=".json"
          style="display: inline-block; margin-left: 15px;"
        >
          <el-button type="text" icon="el-icon-upload2" class="header-btn">
            加载项目
          </el-button>
        </el-upload>
      </div>
    </div>
    
    <div class="main-layout">
      
      <div class="layer-3d">
        <Result3DViewer 
          ref="viewer3d" 
          :points="resultPoints" 
          @trace-particle="onParticleTraceRequested"
        />
      </div>

      <div class="layer-left">
        <el-card class="floating-card left-card-scroll" shadow="always" :body-style="{padding: '0px'}">
          <div slot="header" class="clearfix">
            <span><i class="el-icon-map-location"></i> 几何构建 (Step 1-2)</span>
          </div>
          
          <BoundaryMap 
            ref="mapRef" 
            @boundary-loaded="onBoundaryLoaded" 
            @grid-clicked="onGridClicked" 
            @segment-selected="onSegmentSelected" 
            :configuredData="boundaryConfigs" 
            :wells="wells" 
            :kCells="kCells" 
          />
          
          <div class="step-divider">
             Step 2: 网格离散化设置
          </div>
          
          <GridSettings v-model="gridConfig" @preview="onPreviewGrid" />
        </el-card>
      </div>

      <div class="layer-right" v-if="boundary">
        <ModelParametersPanel
          :activeStep.sync="activeStep"
          :gridConfig="gridConfig"
          :wells="wells"
          :kCells="kCells"
          :currentSegmentIdx="currentSegmentIdx"
          :boundaryConfigs="boundaryConfigs"
          :loading="loading"
          :resultPoints="resultPoints"
          :currentLogs="currentLogs"
          @layer-changed="onLayerUpdate"
          @delete-attribute="handleAttributeDelete"
          @type-change="handleAttributeTypeChange"
          @clear-all="handleClearAllAttributes"
          @update-rch-evt="handleRchEvtUpdate"
          @save-boundary="onBoundaryConfigSave"
          @remove-boundary="onBoundaryConfigRemove"
          @run="handleRun"
        />
      </div>

      <div class="center-tip" v-else>
        <el-alert 
          title="请先在左侧完成 Step 1: 上传边界 Shapefile" 
          type="info" 
          center 
          show-icon 
          :closable="false"
          effect="dark">
        </el-alert>
      </div>
    </div>

    <el-dialog title="网格属性设置" :visible.sync="dialogVisible" width="350px" :append-to-body="true">
      <div v-if="tempCell">
        <p style="color:#999; font-size:12px;">坐标: [R{{tempCell.row}}, C{{tempCell.col}}]</p>
        <el-form size="small" label-position="top">
          <el-form-item label="所在层级 (Layer)">
             <el-input-number v-model="tempCell.layer" :min="0" :max="(gridConfig.n_layers || 1) - 1" style="width: 100%"></el-input-number>
          </el-form-item>
          <el-form-item label="类型">
            <el-radio-group v-model="tempCell.type">
              <el-radio label="well">水井</el-radio>
              <el-radio label="k_cell">变K</el-radio>
            </el-radio-group>
          </el-form-item>
          <div v-if="tempCell.type === 'well'">
             <el-form-item label="抽水率"><el-input-number v-model="tempCell.rate" :step="100" style="width: 100%"></el-input-number></el-form-item>
          </div>
          <div v-if="tempCell.type === 'k_cell'">
             <el-form-item label="渗透系数 K"><el-input-number v-model="tempCell.k_val" :step="0.1" style="width: 100%"></el-input-number></el-form-item>
          </div>
        </el-form>
      </div>
      <span slot="footer" class="dialog-footer">
        <el-button type="danger" plain size="small" @click="resetGridCell" style="float: left;">清除</el-button>
        <el-button @click="dialogVisible = false" size="small">取消</el-button>
        <el-button type="primary" @click="saveCellProperty" size="small">保存</el-button>
      </span>
    </el-dialog>
  </div>
</template>

<script>
// 引入组件
import BoundaryMap from './components/BoundaryMap.vue';
import GridSettings from './components/GridSettings.vue';
import Result3DViewer from './components/Real3DViewer.vue';
import ModelParametersPanel from './components/ModelParametersPanel.vue';

import axios from 'axios';

export default {
  name: 'App',
  components: { 
    BoundaryMap, 
    GridSettings, 
    Result3DViewer, 
    ModelParametersPanel 
  },
  data() {
    return {
      boundary: null, 
      resultPoints: [], 
      loading: false,
      gridConfig: { x_mode: 'size', x_val: 50, y_mode: 'size', y_val: 50, n_layers: 1, z_thick: 10 },
      currentSegmentIdx: null, 
      boundaryConfigs: {}, 
      wells: [], 
      kCells: [], 
      dialogVisible: false, 
      tempCell: null,
      rchData: [], 
      evtData: [],
      activeStep: '3',
      currentLogs: ''
    };
  },
  methods: {
    // === 1. 项目保存与加载逻辑 ===
    saveProject() {
      if (!this.boundary) {
        this.$message.warning("当前没有可保存的项目数据");
        return;
      }
      const projectData = {
        boundary: this.boundary,
        gridConfig: this.gridConfig,
        boundaryConfigs: this.boundaryConfigs,
        wells: this.wells,
        kCells: this.kCells,
        rchData: this.rchData,
        evtData: this.evtData
      };
      
      const dataStr = JSON.stringify(projectData, null, 2);
      const blob = new Blob([dataStr], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      
      const link = document.createElement('a');
      link.href = url;
      link.download = `project_${new Date().toISOString().slice(0,10)}.json`;
      link.click();
      URL.revokeObjectURL(url);
      this.$message.success("项目已保存到本地");
    },

    loadProject(file) {
      if (!file || !file.raw) return;
      const reader = new FileReader();
      reader.onload = (e) => {
        try {
          const json = JSON.parse(e.target.result);
          
          if (json.boundary) this.boundary = json.boundary;
          if (json.gridConfig) this.gridConfig = json.gridConfig;
          if (json.boundaryConfigs) this.boundaryConfigs = json.boundaryConfigs;
          if (json.wells) this.wells = json.wells;
          if (json.kCells) this.kCells = json.kCells;
          if (json.rchData) this.rchData = json.rchData;
          if (json.evtData) this.evtData = json.evtData;

          this.resultPoints = [];
          this.currentLogs = '';
          this.activeStep = '3';

          this.$message.success("项目加载成功！");
          
          this.$nextTick(() => {
             if (this.$refs.mapRef) {
                 this.$refs.mapRef.drawMap();
                 let sz = (this.gridConfig.x_mode === 'size') ? this.gridConfig.x_val : 50; 
                 this.$refs.mapRef.previewGrid(sz);
             }
             this.fetchGridPreview();
          });
        } catch (err) {
          console.error(err);
          this.$message.error("无法解析项目文件，格式错误");
        }
      };
      reader.readAsText(file.raw);
    },

    // === 2. 左侧几何与网格逻辑 ===
    onBoundaryLoaded(data) { 
        this.boundary = data; 
        this.wells = []; this.kCells = []; this.resultPoints = [];
        this.$message.success("边界加载成功，请继续 Step 2");
    },
    
    onPreviewGrid(payload) { 
      if(this.$refs.mapRef) this.$refs.mapRef.previewGrid(payload.size); 
      this.fetchGridPreview();
    },

    async fetchGridPreview() {
      if (!this.boundary) return;
      try {
        const res = await axios.post('http://localhost:5000/preview-geometry', {
          boundary: this.boundary,
          params: this.gridConfig
        });
        if (res.data.success) {
          this.resultPoints = res.data.points;
          this.$message.success('3D 网格模型已刷新');
        }
      } catch (e) {
        console.error(e);
      }
    },

    onLayerUpdate() {
      this.fetchGridPreview();
    },

    // === 3. 交互逻辑 (左侧点击 -> 弹窗 -> 数据更新) ===
    onGridClicked(data) {
      const existingWell = this.wells.find(w => w.row === data.row && w.col === data.col);
      const existingK = this.kCells.find(k => k.row === data.row && k.col === data.col);
      this.tempCell = {
        row: data.row, col: data.col, x: data.x, y: data.y,
        layer: existingWell ? (existingWell.layer || 0) : (existingK ? (existingK.layer || 0) : 0),
        type: existingK ? 'k_cell' : 'well', 
        rate: existingWell ? existingWell.rate : -1000,
        k_val: existingK ? existingK.k_val : 10.0
      };
      this.dialogVisible = true;
      this.activeStep = '4';
    },
    resetGridCell() {
      const { row, col } = this.tempCell;
      this.wells = this.wells.filter(w => !(w.row === row && w.col === col));
      this.kCells = this.kCells.filter(k => !(k.row === row && k.col === col));
      this.dialogVisible = false;
    },
    saveCellProperty() {
      const { row, col, type, rate, k_val, layer, x, y } = this.tempCell;
      this.wells = this.wells.filter(w => !(w.row === row && w.col === col && w.layer === layer));
      this.kCells = this.kCells.filter(k => !(k.row === row && k.col === col && k.layer === layer));
      if (type === 'well') this.wells.push({ row, col, layer, rate, x, y });
      else this.kCells.push({ row, col, layer, k_val, x, y });
      this.dialogVisible = false;
    },

    // === 4. 右侧面板事件处理 ===
    onSegmentSelected(data) { 
        this.currentSegmentIdx = data.index; 
        this.activeStep = '5';
    },
    onBoundaryConfigSave(cfg) { this.$set(this.boundaryConfigs, cfg.id, cfg); },
    onBoundaryConfigRemove(id) { this.$delete(this.boundaryConfigs, id); },
    
    handleAttributeDelete({ type, row, col, layer }) {
      if (type === 'well') this.wells = this.wells.filter(w => !(w.row === row && w.col === col && (layer === undefined || w.layer === layer)));
      else this.kCells = this.kCells.filter(k => !(k.row === row && k.col === col && (layer === undefined || k.layer === layer)));
    },
    handleClearAllAttributes() { this.wells = []; this.kCells = []; },
    handleAttributeTypeChange({ row, col, newType, layer }) {
      this.handleAttributeDelete({ type: newType === 'well' ? 'k_cell' : 'well', row, col, layer });
       if (newType === 'well') this.wells.push({ row, col, layer: layer||0, rate: -1000 });
       else this.kCells.push({ row, col, layer: layer||0, k_val: 10.0 });
    },
    handleRchEvtUpdate(data) {
      this.rchData = data.rch;
      this.evtData = data.evt;
    },

    // === 5. 核心运行逻辑与粒子追踪 ===
    
    // ⭐ 新增：响应点击面板后的追踪事件
    onParticleTraceRequested(cell) {
      // 重新运行模拟并加入追踪起始点参数
      this.handleRun({ k: 10.0 }, cell);
    },

    async handleRun(partialParams, mpCell = null) {
      this.loading = true;
      this.currentLogs = '';
      
      const boundaryList = [];
      for (const [idxStr, cfg] of Object.entries(this.boundaryConfigs)) {
        if (this.boundary[idxStr]) {
          boundaryList.push({ 
            p1: this.boundary[idxStr], 
            p2: this.boundary[parseInt(idxStr)+1], 
            ...cfg 
          });
        }
      }
      
      const fullParams = { ...partialParams, ...this.gridConfig };
      
      try {
        const res = await axios.post('http://localhost:5000/run-model', {
          boundary: this.boundary, 
          params: fullParams, 
          boundary_conditions: boundaryList, 
          wells: this.wells, 
          k_cells: this.kCells,
          rch_data: this.rchData,
          evt_data: this.evtData,
          mp_start_cell: mpCell // ⭐ 传入粒子追踪起始单元
        });
        
        if (res.data.success) { 
            this.resultPoints = res.data.points; 
            this.currentLogs = res.data.logs || '';
            this.$message.success(mpCell ? '流线追踪计算完成' : '模拟计算完成'); 
            this.activeStep = '7';
            
            // ⭐ 如果返回了流线数据，调用 3D 组件进行绘制
            if (res.data.pathlines && res.data.pathlines.length > 0) {
              const xs = this.boundary.map(p => p.x);
              const ys = this.boundary.map(p => p.y);
              const cx = (Math.min(...xs) + Math.max(...xs)) / 2;
              const cy = (Math.min(...ys) + Math.max(...ys)) / 2;
              
              // 确保 3D 组件已经加载
              this.$nextTick(() => {
                if (this.$refs.viewer3d) {
                  this.$refs.viewer3d.drawPathLines(
                    res.data.pathlines, 
                    cx, 
                    cy, 
                    this.$refs.viewer3d.zScale
                  );
                }
              });
            }
        } else {
            if (res.data.logs) this.currentLogs = res.data.logs;
            this.$message.error('模拟失败，请查看日志');
        }
      } catch (err) { 
          this.$message.error('错误: ' + (err.response?.data?.error || err.message)); 
      } 
      finally { this.loading = false; }
    }
  }
};
</script>

<style>
body { margin: 0; padding: 0; overflow: hidden; font-family: "Helvetica Neue", Helvetica, "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", "微软雅黑", Arial, sans-serif; }

.app-header { 
  position: absolute; top: 0; left: 0; width: 100%; height: 50px; 
  background: linear-gradient(90deg, #303133, #545c64); 
  color: white; line-height: 50px; padding-left: 20px; padding-right: 20px;
  font-weight: bold; z-index: 100; box-shadow: 0 2px 4px rgba(0,0,0,0.2); 
  letter-spacing: 1px;
  display: flex; justify-content: space-between; align-items: center;
}

.header-tools { display: flex; align-items: center; }
.header-btn { color: #fff !important; font-size: 14px; font-weight: normal; }
.header-btn:hover { color: #409EFF !important; }

.main-layout { position: relative; width: 100vw; height: 100vh; overflow: hidden; background: #f0f9ff; }
.layer-3d { position: absolute; top: 0; left: 0; width: 100%; height: 100%; z-index: 1; }

.layer-left { 
  position: absolute; top: 60px; left: 20px; bottom: 20px; width: 420px; z-index: 10; 
  display: flex; flex-direction: column; pointer-events: none; 
}
.left-card-scroll { display: flex; flex-direction: column; height: 100%; max-height: 100%; overflow: hidden; }
.left-card-scroll .el-card__body { flex-grow: 1; overflow-y: auto; padding: 0; }

.step-divider {
    background: #f5f7fa; 
    padding: 10px; 
    font-size: 13px; 
    font-weight: bold; 
    color: #606266;
    border-top: 1px solid #ebeef5;
    border-bottom: 1px solid #ebeef5;
}

.layer-right { 
  position: absolute; top: 60px; right: 20px; bottom: 20px; width: 400px; z-index: 10; 
  display: flex; flex-direction: column; pointer-events: none;
}
/* 使子组件能够接收鼠标事件 */
.layer-left .el-card, .layer-right .el-card { pointer-events: auto; }

.floating-card { 
  background: rgba(255, 255, 255, 0.98) !important; 
  backdrop-filter: blur(10px); 
  border-radius: 8px;
}

.center-tip { position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); z-index: 5; opacity: 0.9; }
</style>