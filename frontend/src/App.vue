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
          :layerMapping="layerMapping"
          @trace-particle="onParticleTraceRequested"
        />
      </div>

      <div class="layer-left">
        <el-card class="floating-card left-card-scroll" shadow="always" :body-style="{padding: '0px'}">
          <div class="step-header">
            <span><i class="el-icon-map-location"></i> Step 1: 几何构建</span>
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
             <i class="el-icon-files"></i> Step 2: 地层结构
          </div>
          
          <LayerPanel 
            @model-ready="onModelReady" 
            @preview-boreholes="onPreviewBoreholes"
          />
        </el-card>
      </div>

      <div class="layer-right">
        <ModelParametersPanel
          :activeStep.sync="activeStep"
          :gridConfig.sync="gridConfig" 
          :wells="wells"
          :kCells="kCells"
          :currentSegmentIdx="currentSegmentIdx"
          :boundaryConfigs="boundaryConfigs"
          :loading="loading"
          :resultPoints="resultPoints"
          :currentLogs="currentLogs"
          @preview-grid="onPreviewGrid"
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
import BoundaryMap from './components/BoundaryMap.vue';
import Result3DViewer from './components/Real3DViewer.vue';
import ModelParametersPanel from './components/ModelParametersPanel.vue';
import LayerPanel from './components/LayerPanel.vue'; 
import axios from 'axios';

export default {
  name: 'App',
  components: { 
    BoundaryMap, 
    Result3DViewer, 
    ModelParametersPanel,
    LayerPanel 
  },
  data() {
    return {
      boundary: null, 
      resultPoints: [], 
      layerMapping: {},
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
    onModelReady(data) {
      if (data.layers_count) this.gridConfig.n_layers = data.layers_count;
      if (data.layer_mapping) this.layerMapping = data.layer_mapping;
      this.$message.success(`钻孔解析成功！请点击“预览钻孔”查看。`);
    },

    onPreviewBoreholes(data) {
      this.resultPoints = []; 
      this.$nextTick(() => {
        if (this.$refs.viewer3d && data.boreholes) {
          this.$refs.viewer3d.drawBoreholes(data.boreholes);
          this.$message.success('已在三维视图中显示钻孔柱子，可点击查看分层详情！');
        }
      });
    },

    saveProject() {
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
             if (this.$refs.mapRef && this.boundary) {
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

    onBoundaryLoaded(data) { 
        this.boundary = data; 
        this.wells = []; this.kCells = []; this.resultPoints = [];
        this.$message.success("边界加载成功，请继续 Step 2");
    },
    
    // 修复点 2：在触发时，手动合并最新的 config 以防数据丢失
    onPreviewGrid(payload) { 
      this.gridConfig = { ...this.gridConfig, ...payload.config };
      if(this.$refs.mapRef) this.$refs.mapRef.previewGrid(payload.size); 
      this.fetchGridPreview();
    },

    async fetchGridPreview() {
      try {
        const res = await axios.post('http://localhost:5000/preview-geometry', {
          project_id: 'default',
          boundary: this.boundary,
          params: this.gridConfig
        });
        if (res.data.success) {
          this.resultPoints = res.data.points;
          
          if (res.data.layer_mapping) {
            this.layerMapping = res.data.layer_mapping; 
          }
          
          if (res.data.boundary_auto && (!this.boundary || this.boundary.length === 0)) {
            this.boundary = res.data.boundary_auto;
            if(this.$refs.mapRef) {
              Object.assign(this.$refs.mapRef, { localBoundary: this.boundary });
              this.$refs.mapRef.drawMap();
            }
          }
          
          this.$nextTick(() => {
            if (res.data.boreholes && this.$refs.viewer3d && this.$refs.viewer3d.drawBoreholes) {
              this.$refs.viewer3d.drawBoreholes(res.data.boreholes);
            }
          });

          this.$message.success('3D 地质网格模型已刷新');
        } else {
          this.$message.warning(res.data.error || '获取网格失败');
        }
      } catch (e) {
        console.error(e);
        this.$message.error(e.response?.data?.error || '请求出错，请检查是否已上传钻孔数据');
      }
    },

    onLayerUpdate() {
      this.fetchGridPreview();
    },

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

    onParticleTraceRequested(cell) {
      this.handleRun({ k: 10.0 }, cell);
    },

    async handleRun(partialParams, mpCell = null) {
      this.loading = true;
      this.currentLogs = '';
      
      const boundaryList = [];
      for (const [idxStr, cfg] of Object.entries(this.boundaryConfigs)) {
        if (this.boundary && this.boundary[idxStr]) {
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
          project_id: 'default', 
          boundary: this.boundary, 
          params: fullParams, 
          boundary_conditions: boundaryList, 
          wells: this.wells, 
          k_cells: this.kCells,
          rch_data: this.rchData,
          evt_data: this.evtData,
          mp_start_cell: mpCell 
        });
        
        if (res.data.success) { 
            this.resultPoints = res.data.points; 
            this.currentLogs = res.data.logs || '';
            this.$message.success(mpCell ? '流线追踪计算完成' : '模拟计算完成'); 
            this.activeStep = '7';
            
            if (res.data.pathlines && res.data.pathlines.length > 0) {
              const xs = this.boundary.map(p => p.x);
              const ys = this.boundary.map(p => p.y);
              const cx = (Math.min(...xs) + Math.max(...xs)) / 2;
              const cy = (Math.min(...ys) + Math.max(...ys)) / 2;
              
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
  background: linear-gradient(90deg, #2b303b, #434a56); 
  color: white; line-height: 50px; padding: 0 20px;
  font-weight: 500; z-index: 100; box-shadow: 0 2px 8px rgba(0,0,0,0.25); 
  display: flex; justify-content: space-between; align-items: center;
}

.header-tools { display: flex; align-items: center; }
.header-btn { color: #e4e7ed !important; font-size: 14px; margin-left: 10px; }
.header-btn:hover { color: #409EFF !important; }

.main-layout { position: relative; width: 100vw; height: 100vh; overflow: hidden; background: #eef2f5; }
.layer-3d { position: absolute; top: 0; left: 0; width: 100%; height: 100%; z-index: 1; }

.layer-left { 
  position: absolute; top: 65px; left: 20px; bottom: 20px; width: 420px; z-index: 10; 
  display: flex; flex-direction: column; pointer-events: none; 
}
.left-card-scroll { display: flex; flex-direction: column; height: 100%; overflow: hidden; border: none; }
.left-card-scroll .el-card__body { flex-grow: 1; overflow-y: auto; padding: 0; }

.step-header {
  background: #f5f7fa; padding: 12px 15px; font-size: 14px; font-weight: bold; 
  color: #303133; border-bottom: 1px solid #e4e7ed;
}

.step-divider {
  background: #fdfdfd; padding: 12px 15px; font-size: 14px; font-weight: bold; 
  color: #303133; border-top: 1px solid #ebeef5; border-bottom: 1px solid #ebeef5;
  box-shadow: inset 0 2px 4px rgba(0,0,0,0.02);
}

.layer-right { 
  position: absolute; top: 65px; right: 20px; bottom: 20px; width: 400px; z-index: 10; 
  display: flex; flex-direction: column; pointer-events: none;
}
.layer-left .el-card, .layer-right .el-card { pointer-events: auto; }

.floating-card { 
  background: rgba(255, 255, 255, 0.95) !important; 
  backdrop-filter: blur(12px); 
  border-radius: 8px; 
  box-shadow: 0 8px 16px rgba(0,0,0,0.08) !important;
}

.center-tip { position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); z-index: 5; opacity: 0.9; }
</style>