<template>
  <div id="app">
    <div class="app-header">
      <span class="app-title">地下水模型模拟平台</span>

      <div class="workflow-nav">
        <el-radio-group v-model="activePage" size="small">
          <el-radio-button label="geology">1 地质体建模</el-radio-button>
          <el-radio-button label="flow">2 水动力场</el-radio-button>
          <el-radio-button label="analysis">3 结果分析</el-radio-button>
        </el-radio-group>
      </div>
      
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
        <el-card v-if="activePage === 'geology'" class="floating-card left-card-scroll" shadow="always" :body-style="{padding: '0px'}">
          <div class="step-header">
            <span><i class="el-icon-map-location"></i> Step 1: 边界与断层</span>
          </div>
          
          <BoundaryMap 
            ref="mapRef" 
            @boundary-loaded="onBoundaryLoaded" 
            @faults-loaded="onFaultsLoaded"
            @grid-clicked="onGridClicked" 
            @segment-selected="onSegmentSelected" 
            :configuredData="boundaryConfigs" 
            :wells="wells" 
            :kCells="kCells"
            :faults="faults"
          />
          
          <div class="step-divider">
             <i class="el-icon-files"></i> Step 2: 钻孔与地层
          </div>
          
          <LayerPanel 
            @model-ready="onModelReady" 
            @preview-boreholes="onPreviewBoreholes"
          />
        </el-card>

        <el-card v-if="activePage === 'flow'" class="floating-card left-card-scroll" shadow="always" :body-style="{padding: '0px'}">
          <div class="step-header">
            <span><i class="el-icon-folder-opened"></i> 地质体模型输入</span>
          </div>

          <div class="flow-intake-panel">
            <el-alert
              v-if="hasGeologyModel"
              title="已加载地质体模型"
              type="success"
              :description="geologySummary"
              show-icon
              :closable="false"
            ></el-alert>
            <el-alert
              v-else
              title="请先完成地质体建模，或上传地质体模型 JSON"
              type="warning"
              show-icon
              :closable="false"
            ></el-alert>

            <el-upload
              action=""
              :auto-upload="false"
              :show-file-list="false"
              :on-change="loadGeologyModel"
              accept=".json"
              class="mt-10"
            >
              <el-button size="small" type="primary" plain icon="el-icon-upload2" style="width: 100%;">
                上传地质体模型
              </el-button>
            </el-upload>

            <el-button size="small" type="text" icon="el-icon-back" class="full-text-btn" @click="activePage = 'geology'">
              返回地质体建模
            </el-button>
          </div>

          <div class="step-divider">
             <i class="el-icon-map-location"></i> 网格与边界选择
          </div>

          <BoundaryMap
            ref="mapRef"
            @boundary-loaded="onBoundaryLoaded"
            @faults-loaded="onFaultsLoaded"
            @grid-clicked="onGridClicked"
            @segment-selected="onSegmentSelected"
            :configuredData="boundaryConfigs"
            :wells="wells"
            :kCells="kCells"
            :faults="faults"
          />
        </el-card>

        <el-card v-if="activePage === 'analysis'" class="floating-card left-card-scroll" shadow="always" :body-style="{padding: '0px'}">
          <div class="step-header">
            <span><i class="el-icon-pie-chart"></i> 结果状态</span>
          </div>
          <div class="flow-intake-panel">
            <el-alert
              v-if="resultPoints.length > 0"
              title="已有水动力场结果"
              :description="`当前结果单元数：${resultPoints.length}`"
              type="success"
              show-icon
              :closable="false"
            ></el-alert>
            <el-alert
              v-else
              title="暂无计算结果"
              description="请先在水动力场页面完成 MODFLOW 6 运行。"
              type="info"
              show-icon
              :closable="false"
            ></el-alert>

            <el-button size="small" type="primary" plain class="mt-10" style="width: 100%;" @click="activePage = 'flow'">
              进入水动力场设置
            </el-button>
          </div>

          <div v-if="currentLogs" class="step-divider">
             <i class="el-icon-document"></i> 最近运行日志
          </div>
          <div v-if="currentLogs" class="log-preview">{{ currentLogs }}</div>
        </el-card>
      </div>

      <div class="layer-right">
        <el-card v-if="activePage === 'geology'" class="floating-card scrollable-card" shadow="always" :body-style="{padding: '10px'}">
          <div slot="header">
            <span><i class="el-icon-s-grid"></i> 地质体网格与导出</span>
          </div>

          <GridSettings
            :value="gridConfig"
            @input="gridConfig = $event"
            @preview="onPreviewGrid"
          />

          <div class="model-summary">
            <div class="summary-title">当前地质体摘要</div>
            <div class="summary-row"><span>边界点数</span><b>{{ boundary ? boundary.length : 0 }}</b></div>
            <div class="summary-row"><span>断层条数</span><b>{{ faults.length }}</b></div>
            <div class="summary-row"><span>钻孔数量</span><b>{{ boreholesData ? boreholesData.length : 0 }}</b></div>
            <div class="summary-row"><span>地层层数</span><b>{{ gridConfig.n_layers || 1 }}</b></div>
          </div>

          <el-button type="success" plain size="small" style="width: 100%; margin-top: 12px;" @click="exportGeologyModel">
            <i class="el-icon-download"></i> 导出地质体模型
          </el-button>
        </el-card>

        <ModelParametersPanel
          v-if="activePage === 'flow'"
          :activeStep.sync="activeStep"
          :gridConfig.sync="gridConfig" 
          :wells="wells"
          :kCells="kCells"
          :currentSegmentIdx="currentSegmentIdx"
          :boundaryConfigs="boundaryConfigs"
          :loading="loading"
          :resultPoints="resultPoints"
          :currentLogs="currentLogs"
          panelTitle="水动力场参数与运行"
          :showGridSettings="false"
          :showAnalysis="false"
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

        <el-card v-if="activePage === 'analysis'" class="floating-card scrollable-card" shadow="always" :body-style="{padding: '10px'}">
          <div slot="header">
            <span><i class="el-icon-pie-chart"></i> 结果分析</span>
          </div>
          <AnalysisPanel v-if="resultPoints.length > 0" :points="resultPoints" />
          <el-empty v-else description="暂无结果，请先运行水动力场模型"></el-empty>
        </el-card>
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
import GridSettings from './components/GridSettings.vue';
import AnalysisPanel from './components/AnalysisPanel.vue';
import axios from 'axios';

export default {
  name: 'App',
  components: { 
    BoundaryMap, 
    Result3DViewer, 
    ModelParametersPanel,
    LayerPanel,
    GridSettings,
    AnalysisPanel
  },
  data() {
    return {
      activePage: 'geology',
      boundary: null, 
      faults: [], // 新增：保存断层数据
      resultPoints: [], 
      layerMapping: {},
      loading: false,
      gridConfig: { x_mode: 'size', x_val: 1000, y_mode: 'size', y_val: 1000, n_layers: 1, z_thick: 10 },
      currentSegmentIdx: null, 
      boundaryConfigs: {}, 
      wells: [], 
      kCells: [], 
      dialogVisible: false, 
      tempCell: null,
      rchData: [], 
      evtData: [],
      activeStep: '3',
      currentLogs: '',
      rawCsvContent: null,
      boreholesData: null
    };
  },
  computed: {
    hasGeologyModel() {
      return Boolean(this.rawCsvContent && this.layerMapping && Object.keys(this.layerMapping).length > 0);
    },
    geologySummary() {
      const boundaryCount = this.boundary ? this.boundary.length : 0;
      const boreholeCount = this.boreholesData ? this.boreholesData.length : 0;
      return `边界点 ${boundaryCount}，钻孔 ${boreholeCount}，地层 ${this.gridConfig.n_layers || 1} 层，断层 ${this.faults.length} 条`;
    }
  },
  watch: {
    activePage() {
      if (this.activePage === 'flow' && this.activeStep === '3') {
        this.activeStep = '4';
      }
      this.syncVisibleMap();
    }
  },
  methods: {
    getMapGridSize() {
      if (!this.boundary || this.boundary.length === 0) return 50;
      if (this.gridConfig.x_mode === 'size') {
        return this.gridConfig.x_val;
      } else {
        const xs = this.boundary.map(p => p.x);
        const minX = Math.min(...xs);
        const maxX = Math.max(...xs);
        return (maxX - minX) / (this.gridConfig.x_val || 1);
      }
    },
    onModelReady(data) {
      if (data.layers_count) this.gridConfig.n_layers = data.layers_count;
      if (data.layer_mapping) this.layerMapping = data.layer_mapping;
      this.rawCsvContent = data.rawCsv;
      this.boreholesData = data.boreholes;
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

    downloadJsonFile(data, filename) {
      const dataStr = JSON.stringify(data, null, 2);
      const blob = new Blob([dataStr], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = filename;
      link.click();
      URL.revokeObjectURL(url);
    },

    buildGeologyModelPayload() {
      return {
        schema_version: 'geology_model_v1',
        exported_at: new Date().toISOString(),
        boundary: this.boundary,
        faults: this.faults,
        gridConfig: this.gridConfig,
        layerMapping: this.layerMapping,
        rawCsvContent: this.rawCsvContent,
        boreholesData: this.boreholesData,
        units: {
          length: 'meters',
          time: 'days'
        }
      };
    },

    exportGeologyModel() {
      if (!this.rawCsvContent || !this.layerMapping || Object.keys(this.layerMapping).length === 0) {
        this.$message.warning('请先导入并解析钻孔数据，再导出地质体模型');
        return;
      }
      this.downloadJsonFile(
        this.buildGeologyModelPayload(),
        `geology_model_${new Date().toISOString().slice(0,10)}.json`
      );
      this.$message.success('地质体模型已导出');
    },

    async restoreBackendGeologyFromCsv() {
      if (!this.rawCsvContent) return;
      const blob = new Blob([this.rawCsvContent], { type: 'text/csv' });
      const formData = new FormData();
      formData.append('file', blob, 'recovered_boreholes.csv');
      formData.append('project_id', 'default');
      await axios.post('http://localhost:5000/upload-boreholes', formData);
    },

    syncVisibleMap() {
      this.$nextTick(() => {
        if (this.$refs.mapRef && this.boundary) {
          this.$refs.mapRef.boundary = this.boundary;
          this.$refs.mapRef.drawMap();
          this.$refs.mapRef.previewGrid(this.getMapGridSize());
        }
        if (this.boreholesData && this.$refs.viewer3d) {
          this.$refs.viewer3d.drawBoreholes(this.boreholesData);
        }
      });
    },

    saveProject() {
      const projectData = {
        boundary: this.boundary,
        faults: this.faults, // 保存时包含断层
        gridConfig: this.gridConfig,
        boundaryConfigs: this.boundaryConfigs,
        wells: this.wells,
        kCells: this.kCells,
        rchData: this.rchData,
        evtData: this.evtData,
        layerMapping: this.layerMapping,
        rawCsvContent: this.rawCsvContent,
        boreholesData: this.boreholesData
      };
      
      this.downloadJsonFile(projectData, `project_${new Date().toISOString().slice(0,10)}.json`);
      this.$message.success("项目已保存到本地");
    },

    loadGeologyModel(file) {
      if (!file || !file.raw) return;
      const reader = new FileReader();
      reader.onload = async (e) => {
        try {
          const json = JSON.parse(e.target.result);
          const model = json.schema_version === 'geology_model_v1' ? json : json.geologyModel || json;

          this.boundary = model.boundary || null;
          this.faults = model.faults || [];
          if (model.gridConfig) this.gridConfig = model.gridConfig;
          this.layerMapping = model.layerMapping || {};
          this.rawCsvContent = model.rawCsvContent || null;
          this.boreholesData = model.boreholesData || null;

          this.boundaryConfigs = {};
          this.wells = [];
          this.kCells = [];
          this.rchData = [];
          this.evtData = [];
          this.resultPoints = [];
          this.currentLogs = '';
          this.currentSegmentIdx = null;
          this.activeStep = '4';

          if (this.rawCsvContent) {
            this.$message.info('正在恢复后端地质模型...');
            await this.restoreBackendGeologyFromCsv();
          }

          this.syncVisibleMap();
          if (this.rawCsvContent) await this.fetchGridPreview();
          this.$message.success('地质体模型已加载，可以开始配置水动力场');
        } catch (err) {
          console.error(err);
          this.$message.error('地质体模型文件解析失败，或后端地质模型恢复失败');
        }
      };
      reader.readAsText(file.raw);
    },

    loadProject(file) {
      if (!file || !file.raw) return;
      const reader = new FileReader();
      
      reader.onload = async (e) => {
        try {
          const json = JSON.parse(e.target.result);
          if (json.boundary) this.boundary = json.boundary;
          if (json.faults) this.faults = json.faults; // 加载时恢复断层
          if (json.gridConfig) this.gridConfig = json.gridConfig;
          if (json.boundaryConfigs) this.boundaryConfigs = json.boundaryConfigs;
          if (json.wells) this.wells = json.wells;
          if (json.kCells) this.kCells = json.kCells;
          if (json.rchData) this.rchData = json.rchData;
          if (json.evtData) this.evtData = json.evtData;
          
          if (json.layerMapping) this.layerMapping = json.layerMapping;
          if (json.rawCsvContent) this.rawCsvContent = json.rawCsvContent;
          if (json.boreholesData) this.boreholesData = json.boreholesData;

          this.resultPoints = [];
          this.currentLogs = '';
          this.activeStep = '3';

          if (this.rawCsvContent) {
              this.$message.info("正在唤醒 3D 地质模型，请稍候...");
              await this.restoreBackendGeologyFromCsv();
          }

          this.$message.success("项目加载成功！");

          this.syncVisibleMap();
          this.fetchGridPreview();
        } catch (err) {
          console.error(err);
          this.$message.error("无法解析项目文件，或后端地质重建失败");
        }
      };
      reader.readAsText(file.raw);
    },

    onBoundaryLoaded(data) { 
        this.boundary = data; 
        this.wells = []; this.kCells = []; this.resultPoints = [];
        this.$message.success("边界加载成功");
    },

    // 新增：断层加载成功回调
    onFaultsLoaded(data) {
        this.faults = data;
        this.$message.success(`成功载入 ${data.length} 条断层线`);
        // 如果已经上传过钻孔并生成了网格，自动刷新3D网格预览
        if (this.rawCsvContent) {
            this.fetchGridPreview();
        }
    },
    
    onPreviewGrid(payload) { 
      this.gridConfig = { ...this.gridConfig, ...payload.config };
      if(this.$refs.mapRef)
      this.$refs.mapRef.previewGrid(this.getMapGridSize()); 
      this.fetchGridPreview();
    },

    async fetchGridPreview() {
      try {
        const res = await axios.post('http://localhost:5000/preview-geometry', {
          project_id: 'default',
          boundary: this.boundary,
          params: this.gridConfig,
          faults: this.faults // 携带断层数据传给后端进行切分插值
        });
        if (res.data.success) {
          this.resultPoints = res.data.points;
          
          if (res.data.layer_mapping) {
            this.layerMapping = res.data.layer_mapping; 
          }
          
          if (res.data.boundary_auto && (!this.boundary || this.boundary.length === 0)) {
            this.boundary = res.data.boundary_auto;
            if(this.$refs.mapRef) {
              this.$refs.mapRef.boundary = this.boundary;
              this.$refs.mapRef.drawMap();
            }
          }
          
          this.$nextTick(() => {
            if (res.data.boreholes && this.$refs.viewer3d && this.$refs.viewer3d.drawBoreholes) {
              this.$refs.viewer3d.drawBoreholes(res.data.boreholes);
            }
          });

          this.$message.success('3D 地质网格模型已刷新（包含断层特征）');
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
      if (this.activePage !== 'flow') return;
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
        if (this.activePage !== 'flow') return;
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
          mp_start_cell: mpCell,
          faults: this.faults // 在引擎计算时包含断层
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
.app-title { flex: 0 0 auto; font-size: 16px; white-space: nowrap; }
.workflow-nav { flex: 1 1 auto; min-width: 0; display: flex; justify-content: center; }
.workflow-nav .el-radio-button__inner {
  background: rgba(255,255,255,0.08);
  border-color: rgba(255,255,255,0.18);
  color: #dce3ea;
}
.workflow-nav .el-radio-button__orig-radio:checked + .el-radio-button__inner {
  background: #409EFF;
  border-color: #409EFF;
  color: #fff;
  box-shadow: -1px 0 0 0 #409EFF;
}
.workflow-nav .el-radio-button:first-child .el-radio-button__inner {
  border-left-color: rgba(255,255,255,0.18);
}

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

.scrollable-card { display: flex; flex-direction: column; height: 100%; max-height: 100%; overflow: hidden; }
.scrollable-card .el-card__header { flex-shrink: 0; background: #fcfcfc; padding: 12px 15px; }
.scrollable-card .el-card__body { flex-grow: 1; overflow-y: auto; padding: 0 !important; }

.floating-card { 
  background: rgba(255, 255, 255, 0.95) !important; 
  backdrop-filter: blur(12px); 
  border-radius: 8px; 
  box-shadow: 0 8px 16px rgba(0,0,0,0.08) !important;
}

.flow-intake-panel { padding: 12px 15px; }
.mt-10 { margin-top: 10px; }
.full-text-btn { width: 100%; margin-top: 8px; text-align: left; }

.model-summary {
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid #ebeef5;
}
.summary-title {
  color: #303133;
  font-size: 13px;
  font-weight: 600;
  margin-bottom: 8px;
}
.summary-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  color: #606266;
  font-size: 12px;
  line-height: 26px;
}
.summary-row b { color: #303133; font-weight: 600; }

.log-preview {
  margin: 12px 15px;
  padding: 10px;
  max-height: 260px;
  overflow: auto;
  white-space: pre-wrap;
  word-break: break-word;
  color: #303133;
  background: #f7f9fb;
  border: 1px solid #e4e7ed;
  border-radius: 6px;
  font-size: 12px;
  line-height: 1.5;
}

@media (max-width: 1200px) {
  .layer-left { width: 360px; }
  .layer-right { width: 360px; }
  .workflow-nav .el-radio-button__inner { padding-left: 10px; padding-right: 10px; }
}

.center-tip { position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); z-index: 5; opacity: 0.9; }
</style>
