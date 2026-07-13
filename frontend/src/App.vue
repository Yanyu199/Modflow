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
        <span class="project-context" :class="{ missing: !currentProject }">
          <i class="el-icon-collection-tag"></i>
          {{ projectContextLabel }}
        </span>
        <el-button type="text" icon="el-icon-setting" class="header-btn" @click="projectDialogVisible = true">
          工程设置
        </el-button>
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
          :projectId="projectId"
          :gridModelId="activeGridModelId"
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
            :chdCells="chdCells"
            :faults="faults"
            :gridCells="gridRenderCells"
            :projectId="projectId"
            :projectCrs="currentProject ? currentProject.crs : null"
          />

          <div class="step-divider">
             <i class="el-icon-files"></i> Step 2: 钻孔与地层
          </div>

          <LayerPanel
            :projectId="projectId"
            :units="currentProject ? currentProject.units : null"
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
              v-if="currentGridModel"
              :title="`当前网格：${currentGridModel.status}`"
              :description="gridSummaryText"
              :type="hasBlockingGridErrors ? 'error' : (currentGridModel.status === 'stale' ? 'warning' : 'info')"
              show-icon
              :closable="false"
              class="mt-10"
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
            :chdCells="chdCells"
            :faults="faults"
            :gridCells="gridRenderCells"
            :projectId="projectId"
            :projectCrs="currentProject ? currentProject.crs : null"
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

          <div v-if="currentRun" class="step-divider">
             <i class="el-icon-data-analysis"></i> 最近运行
          </div>
          <div v-if="currentRun" class="run-summary-panel">
            <div class="summary-row"><span>Run ID</span><b>{{ currentRun.run_id }}</b></div>
            <div class="summary-row"><span>状态</span><b>{{ currentRun.status }}</b></div>
            <div class="summary-row"><span>MF6</span><b>{{ currentRun.mf6 && currentRun.mf6.version ? currentRun.mf6.version : '-' }}</b></div>
            <div class="summary-row"><span>Normal termination</span><b>{{ currentRun.mf6 ? currentRun.mf6.normal_termination : '-' }}</b></div>
            <div class="summary-row"><span>Converged</span><b>{{ currentRun.convergence ? currentRun.convergence.converged : '-' }}</b></div>
            <div v-if="currentRun.water_budget" class="summary-row"><span>Total in</span><b>{{ currentRun.water_budget.total_in }}</b></div>
            <div v-if="currentRun.water_budget" class="summary-row"><span>Total out</span><b>{{ currentRun.water_budget.total_out }}</b></div>
            <div v-if="currentRun.water_budget" class="summary-row"><span>Percent discrepancy</span><b>{{ currentRun.water_budget.percent_discrepancy }}</b></div>
          </div>

          <div class="step-divider">
             <i class="el-icon-time"></i> 运行历史
          </div>
          <div class="run-history-panel">
            <el-button size="mini" type="text" icon="el-icon-refresh" @click="loadRunHistory">刷新运行历史</el-button>
            <el-table
              v-if="runHistory.length > 0"
              :data="runHistory"
              size="mini"
              class="run-history-table"
              @row-click="selectRunSummary"
            >
              <el-table-column prop="run_id" label="Run" min-width="120"></el-table-column>
              <el-table-column prop="status" label="状态" min-width="95"></el-table-column>
              <el-table-column label="误差" min-width="70">
                <template slot-scope="scope">
                  {{ scope.row.water_budget ? scope.row.water_budget.percent_discrepancy : '-' }}
                </template>
              </el-table-column>
            </el-table>
            <el-empty v-else description="暂无运行历史" :image-size="60"></el-empty>
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

          <div v-if="currentGridModel" class="model-summary">
            <div class="summary-title">当前 Grid Model</div>
            <div class="summary-row"><span>状态</span><b>{{ currentGridModel.status }}</b></div>
            <div class="summary-row"><span>网格 ID</span><b>{{ activeGridModelId || '-' }}</b></div>
            <div class="summary-row"><span>维度</span><b>{{ gridSummaryText }}</b></div>
            <div class="summary-row"><span>质量错误</span><b>{{ gridQuality.errors ? gridQuality.errors.length : 0 }}</b></div>
            <div class="summary-row"><span>质量警告</span><b>{{ gridQuality.warnings ? gridQuality.warnings.length : 0 }}</b></div>
          </div>

          <el-alert
            v-if="hasBlockingGridErrors"
            title="网格质量存在阻塞错误，不能进入正式运行"
            type="error"
            show-icon
            :closable="false"
            class="mt-10"
          ></el-alert>

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
          :chdCells="chdCells"
          :flowCheck="flowCheck"
          :packagePreview="packagePreview"
          :canRunFlow="canRunFlow"
          :currentSegmentIdx="currentSegmentIdx"
          :boundaryConfigs="boundaryConfigs"
          :loading="loading"
          :resultPoints="resultPoints"
          :currentLogs="currentLogs"
          :projectId="projectId"
          panelTitle="水动力场参数与运行"
          :showGridSettings="false"
          :showAnalysis="false"
          @preview-grid="onPreviewGrid"
          @layer-changed="onLayerUpdate"
          @delete-attribute="handleAttributeDelete"
          @type-change="handleAttributeTypeChange"
          @clear-all="handleClearAllAttributes"
          @update-rch-evt="handleRchEvtUpdate"
          @save-flow="handleSaveFlowModel"
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
              <el-radio label="chd">CHD</el-radio>
            </el-radio-group>
          </el-form-item>
          <div v-if="tempCell.type === 'well'">
             <el-form-item label="抽水率"><el-input-number v-model="tempCell.rate" :step="100" style="width: 100%"></el-input-number></el-form-item>
          </div>
          <div v-if="tempCell.type === 'k_cell'">
             <el-form-item label="渗透系数 K"><el-input-number v-model="tempCell.k_val" :step="0.1" style="width: 100%"></el-input-number></el-form-item>
          </div>
          <div v-if="tempCell.type === 'chd'">
             <el-form-item label="定水头 Head"><el-input-number v-model="tempCell.head" :step="0.1" style="width: 100%"></el-input-number></el-form-item>
          </div>
        </el-form>
      </div>
      <span slot="footer" class="dialog-footer">
        <el-button type="danger" plain size="small" @click="resetGridCell" style="float: left;">清除</el-button>
        <el-button @click="dialogVisible = false" size="small">取消</el-button>
        <el-button type="primary" @click="saveCellProperty" size="small">保存</el-button>
      </span>
    </el-dialog>

    <ProjectSettingsDialog
      :visible.sync="projectDialogVisible"
      :project="currentProject"
      :hasModelData="hasAnyModelData"
      :submitting="projectSubmitting"
      @submit="saveProjectSettings"
    />
  </div>
</template>

<script>
import BoundaryMap from './components/BoundaryMap.vue';
import Result3DViewer from './components/Real3DViewer.vue';
import ModelParametersPanel from './components/ModelParametersPanel.vue';
import LayerPanel from './components/LayerPanel.vue';
import GridSettings from './components/GridSettings.vue';
import AnalysisPanel from './components/AnalysisPanel.vue';
import ProjectSettingsDialog from './components/ProjectSettingsDialog.vue';
import axios from 'axios';

export default {
  name: 'App',
  components: {
    BoundaryMap,
    Result3DViewer,
    ModelParametersPanel,
    LayerPanel,
    GridSettings,
    AnalysisPanel,
    ProjectSettingsDialog
  },
  data() {
    return {
      currentProject: null,
      currentGeologyModel: null,
      currentGridModel: null,
      gridQuality: {},
      gridRenderCells: [],
      activeGridModelId: null,
      projectDialogVisible: true,
      projectSubmitting: false,
      pendingLegacyProjectState: null,
      activePage: 'geology',
      boundary: null,
      faults: [], // 新增：保存断层数据
      resultPoints: [],
      layerMapping: {},
      loading: false,
      gridConfig: {
        x_mode: 'size',
        x_val: 1000,
        y_mode: 'size',
        y_val: 1000,
        n_layers: 1,
        z_thick: 10,
        rotation: 0,
        minimum_thickness: 0.1,
        minimum_boundary_overlap: 0.1
      },
      currentSegmentIdx: null,
      boundaryConfigs: {},
      wells: [],
      kCells: [],
      chdCells: [],
      currentFlowModel: null,
      flowCheck: null,
      packagePreview: null,
      flowSettings: {
        initial_head_default: 9.5,
        kx_default: 10.0,
        ky_default: 10.0,
        kz_default: 1.0,
        icelltype: 0
      },
      dialogVisible: false,
      tempCell: null,
      rchData: [],
      evtData: [],
      activeStep: '3',
      currentLogs: '',
      currentRun: null,
      runHistory: [],
      rawCsvContent: null,
      boreholesData: null
    };
  },
  computed: {
    projectId() {
      return this.currentProject ? this.currentProject.project_id : null;
    },
    hasAnyModelData() {
      return Boolean(
        this.boundary
        || this.currentGeologyModel
        || this.currentGridModel
        || this.rawCsvContent
        || this.faults.length > 0
        || this.wells.length > 0
        || this.kCells.length > 0
        || this.chdCells.length > 0
        || Object.keys(this.boundaryConfigs).length > 0
        || this.resultPoints.length > 0
        || this.currentRun
      );
    },
    projectContextLabel() {
      if (!this.currentProject) return '未创建工程';
      const crs = this.currentProject.crs || {};
      const units = this.currentProject.units || {};
      return `${this.currentProject.name} | EPSG:${crs.code} | ${units.horizontal_length}/${units.time}, ${units.flow}`;
    },
    hasGeologyModel() {
      return Boolean(
        this.currentGeologyModel
        && this.currentGeologyModel.diagnostics
        && this.currentGeologyModel.diagnostics.valid
      );
    },
    geologySummary() {
      if (this.currentGeologyModel && this.currentGeologyModel.diagnostics) {
        const summary = this.currentGeologyModel.diagnostics.summary || {};
        return `边界 ${summary.boundary_count || 0} 个，钻孔 ${summary.borehole_count || 0} 个，地层 ${summary.formation_count || 0} 层，断层 ${summary.fault_count || 0} 条`;
      }
      const boundaryCount = this.boundary ? this.boundary.length : 0;
      const boreholeCount = this.boreholesData ? this.boreholesData.length : 0;
      return `边界点 ${boundaryCount}，钻孔 ${boreholeCount}，地层 ${this.gridConfig.n_layers || 1} 层，断层 ${this.faults.length} 条`;
    },
    hasBlockingGridErrors() {
      return Boolean(
        this.currentGridModel
        && (
          this.currentGridModel.status === 'invalid'
          || this.currentGridModel.status === 'stale'
          || (this.gridQuality.errors && this.gridQuality.errors.length > 0)
        )
      );
    },
    gridSummaryText() {
      if (!this.currentGridModel || !this.currentGridModel.geometry) return '未生成网格';
      const geometry = this.currentGridModel.geometry;
      const active = this.gridQuality.summary ? this.gridQuality.summary.active_cell_count : null;
      const base = `${geometry.nlay} 层 x ${geometry.nrow} 行 x ${geometry.ncol} 列`;
      return active === null || active === undefined ? base : `${base}，活动单元 ${active}`;
    },
    canRunFlow() {
      return Boolean(
        this.currentFlowModel
        && this.flowCheck
        && this.flowCheck.runnable
        && !this.hasBlockingGridErrors
      );
    }
  },
  watch: {
    activePage() {
      if (this.activePage === 'flow' && this.activeStep === '3') {
        this.activeStep = '4';
      }
      if (this.activePage === 'analysis') {
        this.loadRunHistory();
      }
      this.syncVisibleMap();
    },
    wells: { deep: true, handler() { this.invalidateFlowModel(); } },
    kCells: { deep: true, handler() { this.invalidateFlowModel(); } },
    chdCells: { deep: true, handler() { this.invalidateFlowModel(); } }
  },
  mounted() {
    if (!this.currentProject) {
      this.projectDialogVisible = true;
    }
  },
  methods: {
    ensureProjectContext(actionLabel = '继续操作') {
      if (this.currentProject && this.projectId) return true;
      this.projectDialogVisible = true;
      this.$message.warning(`${actionLabel}前请先创建工程，明确 CRS 和单位`);
      return false;
    },
    async saveProjectSettings(payload) {
      this.projectSubmitting = true;
      try {
        let response;
        if (this.currentProject) {
          response = await axios.put(`http://localhost:5000/projects/${this.projectId}`, payload);
        } else {
          response = await axios.post('http://localhost:5000/projects', payload);
        }
        if (response.data.success) {
          this.currentProject = response.data.project;
          this.projectDialogVisible = false;
          this.$message.success(this.pendingLegacyProjectState ? '工程已创建，正在导入旧项目数据' : '工程上下文已保存');
          if (this.pendingLegacyProjectState) {
            const state = this.pendingLegacyProjectState;
            this.pendingLegacyProjectState = null;
            await this.applyProjectState(state, { restoreBackend: true });
          }
        } else {
          this.$message.error(response.data.error || '工程保存失败');
        }
      } catch (err) {
        this.$message.error(err.response?.data?.error || '工程保存失败');
      } finally {
        this.projectSubmitting = false;
      }
    },
    async ensureBackendProject(project) {
      if (!project || !project.project_id) throw new Error('项目文件缺少 project_id');
      try {
        const createRes = await axios.post('http://localhost:5000/projects', project);
        this.currentProject = createRes.data.project;
      } catch (err) {
        if (err.response && err.response.status === 409) {
          const updateRes = await axios.put(`http://localhost:5000/projects/${project.project_id}`, project);
          this.currentProject = updateRes.data.project;
        } else {
          throw err;
        }
      }
    },
    showGeologyDiagnostics(diagnostics) {
      const warningCount = diagnostics && diagnostics.warnings ? diagnostics.warnings.length : 0;
      if (warningCount > 0) {
        this.$message.warning(`地质模型已加载，但存在 ${warningCount} 条诊断警告，请在后续检查中复核`);
      }
    },
    boundaryCoordsFromModel(model) {
      const boundary = model && model.boundary;
      const geometry = boundary && boundary.geometry;
      if (!geometry || !geometry.coordinates) return null;
      const ring = geometry.type === 'MultiPolygon'
        ? geometry.coordinates[0] && geometry.coordinates[0][0]
        : geometry.coordinates[0];
      if (!Array.isArray(ring)) return null;
      return ring.map(point => ({ x: Number(point[0]), y: Number(point[1]) }));
    },
    faultLinesFromModel(model) {
      if (!model || !Array.isArray(model.faults)) return [];
      return model.faults.map(fault => {
        const geometry = fault.geometry || {};
        const coords = geometry.type === 'MultiLineString'
          ? (geometry.coordinates[0] || [])
          : (geometry.coordinates || []);
        return coords.map(point => ({ x: Number(point[0]), y: Number(point[1]) }));
      }).filter(line => line.length > 0);
    },
    boreholesFromModel(model) {
      if (!model || !Array.isArray(model.boreholes)) return [];
      const formations = (model.stratigraphy && model.stratigraphy.formations) || [];
      return model.boreholes.map(borehole => ({
        name: borehole.borehole_id,
        x: borehole.x,
        y: borehole.y,
        layers: (borehole.intervals || []).map(interval => {
          const layerIndex = formations.findIndex(item => item.formation_id === interval.formation_id);
          const formation = layerIndex >= 0 ? formations[layerIndex] : null;
          return {
            layer_id: formation ? (formation.source_layer_id || formation.order) : interval.formation_id,
            layer_idx: layerIndex >= 0 ? layerIndex : 0,
            top: interval.top_elevation,
            bottom: interval.bottom_elevation,
            lithology: interval.lithology || ''
          };
        })
      }));
    },
    applyNormalizedGeologyModel(model) {
      if (!model) return;
      this.currentGeologyModel = model;
      this.clearGridModelState();
      const formations = (model.stratigraphy && model.stratigraphy.formations) || [];
      this.layerMapping = {};
      formations.forEach((formation, index) => {
        this.$set(this.layerMapping, index, formation.source_layer_id || formation.order);
      });
      if (formations.length > 0) this.gridConfig.n_layers = formations.length;

      const boundary = this.boundaryCoordsFromModel(model);
      if (boundary) this.boundary = boundary;
      this.faults = this.faultLinesFromModel(model);
      this.boreholesData = this.boreholesFromModel(model);
      this.showGeologyDiagnostics(model.diagnostics);
    },
    clearGridModelState(clearPoints = true) {
      this.currentGridModel = null;
      this.gridQuality = {};
      this.gridRenderCells = [];
      this.activeGridModelId = null;
      if (clearPoints) {
        this.resultPoints = [];
        this.currentRun = null;
      }
      this.invalidateFlowModel();
    },
    buildGridApiConfig() {
      const cfg = this.gridConfig || {};
      const sizeFromAxis = (axis) => {
        const mode = cfg[`${axis}_mode`];
        const value = Number(cfg[`${axis}_val`] || 1);
        if (mode !== 'count') return Math.max(value, 1);
        if (!this.boundary || this.boundary.length === 0) return Math.max(value, 1);
        const coords = this.boundary.map(point => Number(point[axis]));
        const span = Math.max(...coords) - Math.min(...coords);
        return Math.max(span / Math.max(value, 1), 1);
      };
      return {
        grid_type: 'structured_dis',
        cell_size: {
          x: sizeFromAxis('x'),
          y: sizeFromAxis('y')
        },
        rotation: Number(cfg.rotation || 0),
        minimum_thickness: Number(cfg.minimum_thickness || 0.1),
        pinchout_policy: cfg.pinchout_policy || 'deactivate',
        boundary_activation_rule: 'cell_intersection',
        minimum_boundary_overlap: Number(
          cfg.minimum_boundary_overlap === undefined ? 0.1 : cfg.minimum_boundary_overlap
        )
      };
    },
    applyGridModel(model) {
      if (!model) return;
      this.currentGridModel = model;
      this.activeGridModelId = model.grid_model_id;
      this.gridQuality = model.quality || {};
      this.invalidateFlowModel();
      if (this.currentProject) {
        const references = { ...(this.currentProject.references || {}), grid_model_id: model.grid_model_id };
        this.currentProject = { ...this.currentProject, references };
      }
    },
    async loadGridRenderData(gridModelId) {
      const response = await axios.get(
        `http://localhost:5000/projects/${this.projectId}/grids/${gridModelId}/render-data`
      );
      if (response.data.success) {
        this.gridRenderCells = response.data.points || [];
        this.resultPoints = response.data.points || [];
        this.gridQuality = response.data.quality || this.gridQuality || {};
        if (this.currentGridModel) {
          this.currentGridModel = {
            ...this.currentGridModel,
            status: response.data.status || this.currentGridModel.status,
            quality: this.gridQuality
          };
        }
      }
      return response.data;
    },
    async persistGeologyModelToBackend(model) {
      if (!this.ensureProjectContext('导入地质体模型')) return null;
      const validateRes = await axios.post(
        `http://localhost:5000/projects/${this.projectId}/geology-models/validate`,
        model
      );
      const normalized = validateRes.data.geology_model;
      const createRes = await axios.post(
        `http://localhost:5000/projects/${this.projectId}/geology-models`,
        normalized
      );
      const saved = createRes.data.geology_model;
      this.applyNormalizedGeologyModel(saved);
      return saved;
    },
    async applyProjectState(state, options = {}) {
      if (state.boundary) this.boundary = state.boundary;
      if (state.faults) this.faults = state.faults;
      if (state.gridConfig) this.gridConfig = state.gridConfig;
      if (state.boundaryConfigs) this.boundaryConfigs = state.boundaryConfigs;
      if (state.wells) this.wells = state.wells;
      if (state.kCells) this.kCells = state.kCells;
      if (state.chdCells) this.chdCells = state.chdCells;
      if (state.flowSettings) this.flowSettings = { ...this.flowSettings, ...state.flowSettings };
      if (state.rchData) this.rchData = state.rchData;
      if (state.evtData) this.evtData = state.evtData;
      if (state.layerMapping) this.layerMapping = state.layerMapping;
      if (state.rawCsvContent) this.rawCsvContent = state.rawCsvContent;
      if (state.boreholesData) this.boreholesData = state.boreholesData;
      if (state.geology_model) this.applyNormalizedGeologyModel(state.geology_model);
      else this.clearGridModelState();

      this.resultPoints = [];
      this.currentLogs = '';
      this.currentRun = null;
      this.activeStep = '3';

      if (options.restoreBackend && this.rawCsvContent) {
        this.$message.info("正在恢复后端地质模型，请稍候...");
        await this.restoreBackendGeologyFromCsv();
      }
      this.syncVisibleMap();
      if (this.rawCsvContent) await this.fetchGridPreview();
    },
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
      if (data.geology_model) this.applyNormalizedGeologyModel(data.geology_model);
      else this.clearGridModelState();
      this.$message.success(`钻孔解析成功！请点击“预览钻孔”查看。`);
    },

    onPreviewBoreholes(data) {
      this.resultPoints = [];
      this.currentRun = null;
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
      return this.currentGeologyModel ? JSON.parse(JSON.stringify(this.currentGeologyModel)) : null;
    },

    exportGeologyModel() {
      if (!this.ensureProjectContext('导出地质体模型')) return;
      const payload = this.buildGeologyModelPayload();
      if (!payload) {
        this.$message.warning('请先完成并通过后端验证地质体模型，再导出');
        return;
      }
      this.downloadJsonFile(
        payload,
        `geology_model_${new Date().toISOString().slice(0,10)}.json`
      );
      this.$message.success('地质体模型已导出');
    },

    async restoreBackendGeologyFromCsv() {
      if (!this.ensureProjectContext('恢复后端地质模型')) return;
      if (!this.rawCsvContent) return;
      const blob = new Blob([this.rawCsvContent], { type: 'text/csv' });
      const formData = new FormData();
      formData.append('file', blob, 'recovered_boreholes.csv');
      formData.append('project_id', this.projectId);
      const response = await axios.post('http://localhost:5000/upload-boreholes', formData);
      if (response.data && response.data.geology_model) {
        this.applyNormalizedGeologyModel(response.data.geology_model);
      }
    },

    syncVisibleMap() {
      this.$nextTick(() => {
        if (this.$refs.mapRef && this.boundary) {
          this.$refs.mapRef.boundary = this.boundary;
          this.$refs.mapRef.drawMap();
        }
        if (this.boreholesData && this.$refs.viewer3d) {
          this.$refs.viewer3d.drawBoreholes(this.boreholesData);
        }
      });
    },

    saveProject() {
      if (!this.ensureProjectContext('保存项目')) return;
      const projectData = {
        bundle_schema: 'modflow_project_bundle',
        bundle_version: '1.0',
        exported_at: new Date().toISOString(),
        project: this.currentProject,
        geology_model: this.currentGeologyModel ? JSON.parse(JSON.stringify(this.currentGeologyModel)) : null,
        state: {
          gridConfig: this.gridConfig,
          boundaryConfigs: this.boundaryConfigs,
          wells: this.wells,
          kCells: this.kCells,
          chdCells: this.chdCells,
          flowSettings: this.flowSettings,
          rchData: this.rchData,
          evtData: this.evtData,
          activeGridModelId: this.activeGridModelId
        }
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
          const model = json.schema_name === 'geology_model'
            ? json
            : (json.geology_model || json.geologyModel || null);

          if (model && model.schema_name === 'geology_model') {
            await this.persistGeologyModelToBackend(model);
            this.boundaryConfigs = {};
            this.wells = [];
            this.kCells = [];
            this.chdCells = [];
            this.invalidateFlowModel();
            this.rchData = [];
            this.evtData = [];
            this.resultPoints = [];
            this.currentLogs = '';
            this.currentRun = null;
            this.currentSegmentIdx = null;
            this.activeStep = '4';
            this.syncVisibleMap();
            if (this.currentGeologyModel) await this.fetchGridPreview();
            this.$message.success('地质体模型已通过后端验证并加载');
            return;
          }

          const legacyModel = json.schema_version === 'geology_model_v1' ? json : model || json;
          if (!this.currentProject && legacyModel.project_context) {
            await this.ensureBackendProject(legacyModel.project_context);
          }
          if (!this.ensureProjectContext('加载地质体模型')) return;

          this.boundary = legacyModel.boundary || null;
          this.faults = legacyModel.faults || [];
          if (legacyModel.gridConfig) this.gridConfig = legacyModel.gridConfig;
          this.layerMapping = legacyModel.layerMapping || {};
          this.rawCsvContent = legacyModel.rawCsvContent || null;
          this.boreholesData = legacyModel.boreholesData || null;

          this.boundaryConfigs = {};
          this.wells = [];
          this.kCells = [];
          this.chdCells = [];
          this.invalidateFlowModel();
          this.rchData = [];
          this.evtData = [];
          this.resultPoints = [];
          this.currentLogs = '';
          this.currentRun = null;
          this.currentSegmentIdx = null;
          this.activeStep = '4';

          if (this.rawCsvContent) {
            this.$message.info('正在通过 legacy CSV 恢复后端地质模型...');
            await this.restoreBackendGeologyFromCsv();
          } else {
            throw new Error('旧地质模型缺少可迁移的标准 geology_model 或 rawCsvContent');
          }

          this.syncVisibleMap();
          if (this.currentGeologyModel) await this.fetchGridPreview();
          this.$message.success('地质体模型已加载，可以开始配置水动力场');
        } catch (err) {
          console.error(err);
          this.$message.error(err.response?.data?.error || err.message || '地质体模型文件解析失败，或后端地质模型恢复失败');
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
          if (json.bundle_schema === 'modflow_project_bundle' && json.project) {
            await this.ensureBackendProject(json.project);
            if (json.geology_model) {
              await this.persistGeologyModelToBackend(json.geology_model);
            } else {
              this.currentGeologyModel = null;
            }
            if (json.state) await this.applyProjectState(json.state, { restoreBackend: false });
            this.syncVisibleMap();
            if (this.currentGeologyModel) await this.fetchGridPreview();
            this.$message.success("项目加载成功！");
            return;
          }

          if (json.schema_name === 'modflow_project_bundle' && json.project && json.state) {
            await this.ensureBackendProject(json.project);
            await this.applyProjectState(json.state, { restoreBackend: true });
            this.$message.success("项目加载成功！");
            return;
          }

          if (!this.currentProject) {
            this.pendingLegacyProjectState = json;
            this.projectDialogVisible = true;
            this.$message.warning("旧项目文件缺少正式 Project Schema，请先补充 CRS 和单位创建工程");
            return;
          }
          try {
            await this.$confirm(
              '旧项目文件缺少正式 Project Schema，将导入到当前工程上下文中，不会自动猜测 CRS 或单位。是否继续？',
              '导入旧项目',
              { type: 'warning' }
            );
          } catch (e) {
            return;
          }
          await this.applyProjectState(json, { restoreBackend: true });
          this.$message.success("旧项目数据已导入当前工程");
        } catch (err) {
          console.error(err);
          this.$message.error("无法解析项目文件，或后端地质重建失败");
        }
      };
      reader.readAsText(file.raw);
    },

    onBoundaryLoaded(data) {
        const payload = Array.isArray(data) ? { coords: data } : (data || {});
        this.boundary = payload.coords || [];
        if (payload.geology_model) this.applyNormalizedGeologyModel(payload.geology_model);
        else this.clearGridModelState();
        this.wells = []; this.kCells = []; this.chdCells = []; this.resultPoints = []; this.currentRun = null;
        this.invalidateFlowModel();
        this.$message.success("边界加载成功");
    },

    // 新增：断层加载成功回调
    onFaultsLoaded(data) {
        const payload = Array.isArray(data) ? { faults: data } : (data || {});
        this.faults = payload.faults || [];
        if (payload.geology_model) this.applyNormalizedGeologyModel(payload.geology_model);
        else this.clearGridModelState();
        this.$message.success(`成功载入 ${this.faults.length} 条断层线`);
        // 如果已经上传过钻孔并生成了网格，自动刷新3D网格预览
        if (this.hasGeologyModel) {
            this.fetchGridPreview();
        }
    },

    async onPreviewGrid(payload) {
      if (!this.ensureProjectContext('预览网格')) return;
      this.gridConfig = { ...this.gridConfig, ...((payload && payload.config) || {}) };
      if (this.activeGridModelId && (this.wells.length > 0 || this.kCells.length > 0 || this.chdCells.length > 0)) {
        try {
          await this.$confirm(
            '重新生成 Grid Model 会产生新的 cell_id，当前 WEL、CHD 和 K 单元选择将被清空。是否继续？',
            '重新生成网格',
            { type: 'warning' }
          );
        } catch (e) {
          return;
        }
        this.wells = [];
        this.kCells = [];
        this.chdCells = [];
        this.invalidateFlowModel();
      }
      await this.fetchGridPreview();
    },

    async fetchGridPreview() {
      if (!this.ensureProjectContext('预览网格')) return;
      if (!this.hasGeologyModel) {
        this.$message.warning('请先完成并保存有效的地质体模型');
        return;
      }
      try {
        const res = await axios.post(
          `http://localhost:5000/projects/${this.projectId}/grids`,
          this.buildGridApiConfig()
        );
        if (res.data.success) {
          this.applyGridModel(res.data.grid_model);
          await this.loadGridRenderData(res.data.grid_model_id);

          this.$nextTick(() => {
            if (this.boreholesData && this.$refs.viewer3d && this.$refs.viewer3d.drawBoreholes) {
              this.$refs.viewer3d.drawBoreholes(this.boreholesData);
            }
          });

          if (this.hasBlockingGridErrors) {
            this.$message.warning('Grid Model 已生成，但存在阻塞质量问题，请查看质量报告');
          } else {
            this.$message.success('Grid Model 已由后端生成并刷新');
          }
        } else {
          this.$message.warning(res.data.error || '获取网格失败');
        }
      } catch (e) {
        console.error(e);
        this.$message.error(e.response?.data?.error || '请求出错，请检查地质体模型和网格配置');
      }
    },

    onLayerUpdate() {
      this.fetchGridPreview();
    },

    isSameGridCell(a, b) {
      if (!a || !b) return false;
      if (a.cell_id && b.cell_id) return a.cell_id === b.cell_id;
      return a.row === b.row && a.col === b.col && (a.layer || 0) === (b.layer || 0);
    },

    invalidateFlowModel() {
      this.currentFlowModel = null;
      this.flowCheck = null;
      this.packagePreview = null;
    },

    onGridClicked(data) {
      if (this.activePage !== 'flow') return;
      if (!data || !data.cell_id) {
        this.$message.warning('请先使用后端 Grid Model 生成网格，再选择单元');
        return;
      }
      const probe = { ...data, layer: data.layer || 0 };
      const existingWell = this.wells.find(w => this.isSameGridCell(w, probe));
      const existingK = this.kCells.find(k => this.isSameGridCell(k, probe));
      const existingChd = this.chdCells.find(c => this.isSameGridCell(c, probe));
      this.tempCell = {
        cell_id: data.cell_id,
        grid_model_id: data.grid_model_id || this.activeGridModelId,
        row: data.row, col: data.col, column: data.column !== undefined ? data.column : data.col, x: data.x, y: data.y,
        layer: existingWell ? (existingWell.layer || 0) : (existingK ? (existingK.layer || 0) : (existingChd ? (existingChd.layer || 0) : 0)),
        type: existingChd ? 'chd' : (existingK ? 'k_cell' : 'well'),
        rate: existingWell ? existingWell.rate : -1000,
        k_val: existingK ? existingK.k_val : 10.0,
        head: existingChd ? existingChd.head : 10.0
      };
      this.dialogVisible = true;
      this.activeStep = '4';
    },
    resetGridCell() {
      const target = this.tempCell;
      this.wells = this.wells.filter(w => !this.isSameGridCell(w, target));
      this.kCells = this.kCells.filter(k => !this.isSameGridCell(k, target));
      this.chdCells = this.chdCells.filter(c => !this.isSameGridCell(c, target));
      this.invalidateFlowModel();
      this.dialogVisible = false;
    },
    saveCellProperty() {
      const { cell_id, grid_model_id, row, col, column, type, rate, k_val, head, layer, x, y } = this.tempCell;
      const target = { cell_id, row, col, layer };
      this.wells = this.wells.filter(w => !this.isSameGridCell(w, target));
      this.kCells = this.kCells.filter(k => !this.isSameGridCell(k, target));
      this.chdCells = this.chdCells.filter(c => !this.isSameGridCell(c, target));
      const base = { cell_id, grid_model_id, row, col, column: column !== undefined ? column : col, layer, x, y };
      if (type === 'well') this.wells.push({ ...base, rate });
      else if (type === 'k_cell') this.kCells.push({ ...base, k_val });
      else this.chdCells.push({ ...base, head });
      this.invalidateFlowModel();
      this.dialogVisible = false;
    },

    onSegmentSelected(data) {
        if (this.activePage !== 'flow') return;
        this.currentSegmentIdx = data.index;
        this.activeStep = '5';
    },
    onBoundaryConfigSave(cfg) { this.$set(this.boundaryConfigs, cfg.id, cfg); },
    onBoundaryConfigRemove(id) { this.$delete(this.boundaryConfigs, id); },

    handleAttributeDelete(target) {
      if (target.type === 'well') this.wells = this.wells.filter(w => !this.isSameGridCell(w, target));
      else if (target.type === 'k_cell') this.kCells = this.kCells.filter(k => !this.isSameGridCell(k, target));
      else this.chdCells = this.chdCells.filter(c => !this.isSameGridCell(c, target));
      this.invalidateFlowModel();
    },
    handleClearAllAttributes() { this.wells = []; this.kCells = []; this.chdCells = []; this.invalidateFlowModel(); },
    handleAttributeTypeChange(rowData) {
      const { newType } = rowData;
      const source = this.wells.find(item => this.isSameGridCell(item, rowData))
        || this.kCells.find(item => this.isSameGridCell(item, rowData))
        || this.chdCells.find(item => this.isSameGridCell(item, rowData))
        || rowData;
      this.handleAttributeDelete({ ...rowData, type: rowData.type });
      const base = {
        cell_id: source.cell_id,
        grid_model_id: source.grid_model_id || this.activeGridModelId,
        row: source.row,
        col: source.col,
        column: source.column !== undefined ? source.column : source.col,
        layer: source.layer || 0,
        x: source.x,
        y: source.y
      };
      if (newType === 'well') this.wells.push({ ...base, rate: -1000 });
      else if (newType === 'k_cell') this.kCells.push({ ...base, k_val: 10.0 });
      else this.chdCells.push({ ...base, head: 10.0 });
      this.invalidateFlowModel();
    },
    handleRchEvtUpdate(data) {
      this.rchData = data.rch;
      this.evtData = data.evt;
    },

    onParticleTraceRequested(cell) {
      this.handleRun({ k: 10.0 }, cell);
    },

    buildFlowModelPayload(partialParams = {}) {
      const geometry = this.currentGridModel && this.currentGridModel.geometry ? this.currentGridModel.geometry : {};
      const nlay = Number(geometry.nlay || this.gridConfig.n_layers || 1);
      const kx = Number(partialParams.kx_default ?? partialParams.k ?? this.flowSettings.kx_default);
      const ky = Number(partialParams.ky_default ?? partialParams.k ?? this.flowSettings.ky_default);
      const kz = Number(partialParams.kz_default ?? this.flowSettings.kz_default);
      const initialHead = Number(partialParams.initial_head_default ?? this.flowSettings.initial_head_default);
      const icelltype = Number(partialParams.icelltype ?? this.flowSettings.icelltype);
      this.flowSettings = {
        initial_head_default: initialHead,
        kx_default: kx,
        ky_default: ky,
        kz_default: kz,
        icelltype
      };
      const kOverrides = this.kCells
        .filter(cell => cell.cell_id)
        .map(cell => ({ cell_id: cell.cell_id, value: Number(cell.k_val) }));
      return {
        project_id: this.projectId,
        grid_model_id: this.activeGridModelId,
        simulation: {
          type: 'steady',
          stress_periods: [{ perlen: 1.0, nstp: 1, tsmult: 1.0, steady: true }],
          time_units: 'DAYS'
        },
        initial_conditions: {
          mode: 'default_with_overrides',
          default: initialHead,
          overrides: []
        },
        hydraulic_properties: {
          icelltype: { mode: 'per_layer', values: Array.from({ length: nlay }, () => icelltype) },
          kx: { default: kx, overrides: kOverrides },
          ky: { default: ky, overrides: kOverrides },
          kz: { default: kz, overrides: kOverrides }
        },
        boundaries: {
          chd: this.chdCells.length > 0 ? [{
            boundary_id: 'selected_chd_cells',
            name: 'Selected CHD cells',
            cells: this.chdCells
              .filter(cell => cell.cell_id)
              .map(cell => ({ cell_id: cell.cell_id, head: Number(cell.head) }))
          }] : [],
          wel: this.wells
            .filter(cell => cell.cell_id)
            .map((cell, index) => ({
              well_id: `well_${index + 1}`,
              name: `Well ${index + 1}`,
              cell_id: cell.cell_id,
              rate: Number(cell.rate)
            }))
        },
        solver: {
          complexity: 'COMPLEX',
          outer_maximum: 100,
          inner_maximum: 100,
          outer_dvclose: 1.0e-8,
          inner_dvclose: 1.0e-8,
          linear_acceleration: 'BICGSTAB'
        },
        output_control: {
          save_head: true,
          save_budget: true,
          print_budget: true,
          head_file: 'gwf.hds',
          budget_file: 'gwf.bud'
        }
      };
    },

    async saveFlowModelToBackend(partialParams = {}) {
      const payload = this.buildFlowModelPayload(partialParams);
      const validateRes = await axios.post(
        `http://localhost:5000/projects/${this.projectId}/flow-models/validate`,
        payload
      );
      this.flowCheck = validateRes.data.checker;
      if (!this.flowCheck || !this.flowCheck.runnable) {
        const errors = this.flowCheck && this.flowCheck.diagnostics ? this.flowCheck.diagnostics.errors || [] : [];
        this.currentLogs = errors.map(item => `${item.code}: ${item.message}`).join('\n');
        this.$message.error('Flow Model 检查未通过，请先补齐 CHD/WEL/K/IC 配置');
        return null;
      }
      const response = this.currentFlowModel && this.currentFlowModel.flow_model_id
        ? await axios.put(
          `http://localhost:5000/projects/${this.projectId}/flow-models/${this.currentFlowModel.flow_model_id}`,
          payload
        )
        : await axios.post(`http://localhost:5000/projects/${this.projectId}/flow-models`, payload);
      this.currentFlowModel = response.data.flow_model;
      this.flowCheck = response.data.checker;
      if (this.currentProject && this.currentFlowModel) {
        const references = { ...(this.currentProject.references || {}), flow_model_id: this.currentFlowModel.flow_model_id };
        this.currentProject = { ...this.currentProject, references };
      }
      const preview = await axios.get(
        `http://localhost:5000/projects/${this.projectId}/flow-models/${this.currentFlowModel.flow_model_id}/package-preview`
      );
      this.packagePreview = preview.data.package_preview;
      return this.currentFlowModel;
    },

    async handleSaveFlowModel(partialParams) {
      if (!this.ensureProjectContext('保存 Flow Model')) return;
      if (!this.activeGridModelId || this.hasBlockingGridErrors) {
        this.$message.warning('请先生成可运行的 Grid Model');
        return;
      }
      this.loading = true;
      try {
        const model = await this.saveFlowModelToBackend(partialParams);
        if (model) this.$message.success('Flow Model 已保存并通过检查');
      } catch (err) {
        this.$message.error('Flow Model 保存失败: ' + (err.response?.data?.error || err.message));
      } finally {
        this.loading = false;
      }
    },

    async loadRunHistory() {
      if (!this.projectId) return;
      try {
        const res = await axios.get(`http://localhost:5000/projects/${this.projectId}/runs?limit=10`);
        if (res.data.success) {
          this.runHistory = res.data.runs || [];
          if (!this.currentRun && this.runHistory.length > 0) {
            this.currentRun = this.runHistory[0];
          }
        }
      } catch (err) {
        this.$message.warning('运行历史读取失败: ' + (err.response?.data?.error || err.message));
      }
    },

    async selectRunSummary(row) {
      if (!row || !row.run_id || !this.projectId) return;
      try {
        const res = await axios.get(`http://localhost:5000/projects/${this.projectId}/runs/${row.run_id}/summary`);
        if (res.data.success) {
          this.currentRun = res.data.run;
          this.currentLogs = this.formatRunSummary(this.currentRun);
        }
      } catch (err) {
        this.$message.warning('运行详情读取失败: ' + (err.response?.data?.error || err.message));
      }
    },

    formatRunSummary(run) {
      if (!run) return '';
      const budget = run.water_budget || {};
      const error = run.error ? `${run.error.code}: ${run.error.message}` : '';
      return [
        `Run: ${run.run_id}`,
        `Status: ${run.status}`,
        `MF6 return code: ${run.mf6 ? run.mf6.return_code : '-'}`,
        `Normal termination: ${run.mf6 ? run.mf6.normal_termination : '-'}`,
        `Converged: ${run.convergence ? run.convergence.converged : '-'}`,
        `Water budget in/out: ${budget.total_in} / ${budget.total_out}`,
        `Percent discrepancy: ${budget.percent_discrepancy}`,
        error
      ].filter(Boolean).join('\n');
    },

    async handleRun(partialParams, mpCell = null) {
      if (!this.ensureProjectContext('运行模型')) return;
      if (!this.activeGridModelId) {
        this.$message.warning('请先生成 Grid Model');
        return;
      }
      if (this.hasBlockingGridErrors) {
        this.$message.error('当前 Grid Model 存在阻塞错误或已过期，请重新生成后再运行');
        return;
      }
      this.loading = true;
      this.currentLogs = '';

      try {
        const flowModel = await this.saveFlowModelToBackend(partialParams);
        if (!flowModel) return;
        if (mpCell) {
          this.$message.info('当前正式 Run API 尚未接入 MODPATH，先执行地下水流场运行');
        }
        const res = await axios.post(`http://localhost:5000/projects/${this.projectId}/runs`, {
          flow_model_id: flowModel.flow_model_id
        });

        this.currentRun = res.data.run || null;
        this.currentLogs = res.data.logs || this.formatRunSummary(this.currentRun);
        await this.loadRunHistory();
        if (res.data.success && ['completed', 'completed_with_warnings'].includes(res.data.status)) {
            this.resultPoints = res.data.points || [];
            this.$message.success(res.data.status === 'completed_with_warnings' ? '模拟完成，但存在警告' : '模拟计算完成');
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
            const errorCode = res.data.error && res.data.error.code ? res.data.error.code : res.data.status;
            this.$message.error(`模拟失败：${errorCode}`);
        }
      } catch (err) {
          const data = err.response && err.response.data ? err.response.data : null;
          if (data && data.run) {
            this.currentRun = data.run;
            this.currentLogs = data.logs || this.formatRunSummary(data.run);
            await this.loadRunHistory();
          }
          const errorCode = data && data.error && data.error.code ? data.error.code : (data && data.code ? data.code : err.message);
          this.$message.error('错误: ' + errorCode);
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
.project-context {
  display: inline-flex;
  align-items: center;
  max-width: 320px;
  padding: 0 10px;
  height: 28px;
  line-height: 28px;
  border: 1px solid rgba(255,255,255,0.22);
  border-radius: 4px;
  color: #e4e7ed;
  font-size: 12px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.project-context i { margin-right: 5px; }
.project-context.missing {
  color: #f6c36a;
  border-color: rgba(246,195,106,0.45);
}
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

.run-summary-panel,
.run-history-panel {
  margin: 12px 15px;
  padding: 10px;
  background: #fff;
  border: 1px solid #ebeef5;
  border-radius: 6px;
}

.run-history-table {
  margin-top: 6px;
  width: 100%;
  font-size: 12px;
}

@media (max-width: 1200px) {
  .layer-left { width: 360px; }
  .layer-right { width: 360px; }
  .workflow-nav .el-radio-button__inner { padding-left: 10px; padding-right: 10px; }
}

.center-tip { position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); z-index: 5; opacity: 0.9; }
</style>
