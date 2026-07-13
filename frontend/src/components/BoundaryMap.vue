<template>
  <div class="map-container-wrapper">
    <div class="header-actions">
      <el-upload
        :action="`${apiBaseUrl}/upload-shapefile`"
        :data="uploadData"
        :show-file-list="false"
        :http-request="uploadBoundaryFile"
        :before-upload="beforeUpload"
        accept=".zip"
      >
        <el-button type="primary" icon="el-icon-upload" size="small" :disabled="!projectId">上传边界</el-button>
      </el-upload>

      <el-upload
        :action="`${apiBaseUrl}/upload-faults`"
        :data="uploadData"
        :show-file-list="false"
        :on-success="onFaultsUploadSuccess"
        :before-upload="beforeFaultUpload"
        accept=".csv,.xlsx,.xls"
        style="margin-left: 10px;"
      >
        <el-button type="warning" icon="el-icon-data-line" size="small" :disabled="!projectId">上传断层</el-button>
      </el-upload>

      <el-radio-group v-model="mode" size="small" style="margin-left: auto;">
        <el-radio-button label="cell">网格</el-radio-button>
        <el-radio-button label="boundary">边界</el-radio-button>
      </el-radio-group>
    </div>

    <div v-if="mode === 'cell' && gridInfo" class="mode-tip">
      <i class="el-icon-mouse"></i> 点击网格设置属性
    </div>

    <div 
      class="canvas-scroll-box"
      @contextmenu.prevent
      @mousedown="onMouseDown"
      @mousemove="onMouseMove"
      @mouseup="onMouseUp"
      @mouseleave="onMouseUp"
    >
      <div ref="plotDiv" class="plot-div"></div>
    </div>
  </div>
</template>

<script>
import axios from 'axios';
import Plotly from 'plotly.js-dist-min';

export default {
  name: 'BoundaryMap',
  props: {
    configuredData: Object,
    wells: Array,
    kCells: Array,
    faults: Array, // 新增：接收断层数据
    gridCells: { type: Array, default: () => [] },
    projectId: { type: String, default: null },
    projectCrs: { type: Object, default: null }
  },
  data() {
    return {
      boundary: [],
      mode: 'cell',
      selectedSegmentIndex: null,
      gridLines: null,
      centerPoints: null,
      backendGridCells: [],
      gridInfo: null,
      clickedCell: null,
      pendingBoundaryFile: null,
      pendingBoundaryContext: null,
      dragState: { isDragging: false, startX: 0, startY: 0, startRangeX: null, startRangeY: null }
    };
  },
  computed: {
    apiBaseUrl() {
      return 'http://localhost:5000';
    },
    uploadData() {
      return { project_id: this.projectId || '' };
    }
  },
  watch: {
    mode() { this.clickedCell = null; this.drawMap(); },
    configuredData: { deep: true, handler() { this.drawMap(); } },
    wells: { deep: true, handler() { this.drawMap(); } },
    kCells: { deep: true, handler() { this.drawMap(); } },
    faults: { deep: true, handler() { this.drawMap(); } }, // 监听断层数据变化重绘地图
    gridCells: {
      immediate: true,
      deep: true,
      handler(cells) {
        this.applyGridRenderData(cells || []);
      }
    }
  },
  mounted() {
    window.addEventListener('resize', this.onResize);
  },
  beforeDestroy() {
    window.removeEventListener('resize', this.onResize);
  },
  methods: {
    onResize() {
      if(this.boundary && this.boundary.length > 0) {
        Plotly.Plots.resize(this.$refs.plotDiv);
      }
    },
    beforeUpload(file) {
      if (!this.projectId) {
        this.$message.warning('请先创建工程');
        return false;
      }
      const ok = file.name.toLowerCase().endsWith('.zip');
      if (!ok) this.$message.error('请上传包含 Shapefile 的 .zip 文件');
      if (ok) {
        this.pendingBoundaryFile = file;
        this.pendingBoundaryContext = this.currentUploadContext();
      }
      return ok;
    },
    normalizedProjectCrs() {
      if (!this.projectCrs) return null;
      return {
        authority: this.projectCrs.authority || null,
        code: this.projectCrs.code === undefined ? null : this.projectCrs.code,
        wkt: this.projectCrs.wkt || null,
        axis_order: this.projectCrs.axis_order || 'xy'
      };
    },
    currentUploadContext() {
      return {
        project_id: this.projectId || '',
        project_crs: this.normalizedProjectCrs()
      };
    },
    contextSignature(context) {
      return JSON.stringify(context || this.currentUploadContext());
    },
    async uploadBoundaryFile(options) {
      const uploadContext = this.pendingBoundaryContext || this.currentUploadContext();
      const formData = new FormData();
      formData.append('file', options.file, options.file.name || 'boundary.zip');
      formData.append('project_id', uploadContext.project_id);
      try {
        const response = await axios.post(`${this.apiBaseUrl}/upload-shapefile`, formData);
        this.handleBoundaryUploadResponse(response.data, options.file, uploadContext);
        if (options.onSuccess) options.onSuccess(response.data, options.file);
      } catch (error) {
        const payload = error.response && error.response.data ? error.response.data : null;
        if (this.handleBoundaryUploadResponse(payload, options.file, uploadContext)) {
          return;
        }
        if (options.onError) options.onError(error, options.file);
        this.$message.error((payload && payload.error) || '边界上传失败，请检查后端服务和 ZIP 文件');
      }
    },
    handleBoundaryUploadResponse(res, file, uploadContext) {
      if (res && res.success) {
        this.applyBoundaryUploadResult(res);
        return true;
      }
      if (res && res.code === 'shapefile_crs_missing') {
        this.confirmMissingCrsAndRetry(file || this.pendingBoundaryFile, uploadContext || this.pendingBoundaryContext);
        return true;
      }
      return false;
    },
    onUploadSuccess(res) {
      if (!this.handleBoundaryUploadResponse(res, this.pendingBoundaryFile, this.pendingBoundaryContext)) {
        this.$message.error((res && res.error) || '边界解析失败');
      }
    },
    onUploadError(err) {
      const payload = err && err.response && err.response.data ? err.response.data : null;
      if (this.handleBoundaryUploadResponse(payload, this.pendingBoundaryFile, this.pendingBoundaryContext)) {
        return;
      }
      this.$message.error('边界上传失败，请检查后端服务和 ZIP 文件');
    },
    applyBoundaryUploadResult(res) {
      this.boundary = res.data;
      this.gridLines = null; this.centerPoints = null; this.gridInfo = null; this.clickedCell = null;
      this.$emit('boundary-loaded', {
        coords: this.boundary,
        geology_model: res.geology_model,
        diagnostics: res.diagnostics,
        boundary_feature: res.boundary_feature,
        shapefile_crs: res.shapefile_crs
      });
      this.drawMap();
    },
    async confirmMissingCrsAndRetry(file, uploadContext) {
      if (!file) {
        this.$message.error('Shapefile 缺少 CRS，请补充 .prj 后重试');
        return;
      }
      const confirmedContext = uploadContext || this.pendingBoundaryContext || this.currentUploadContext();
      try {
        await this.$confirm(
          '该 Shapefile 缺少 .prj/CRS 信息。是否确认按当前工程 CRS 导入？请只在你确定该文件坐标系与当前工程一致时继续。',
          '确认坐标系',
          {
            confirmButtonText: '按当前工程 CRS 导入',
            cancelButtonText: '取消',
            type: 'warning'
          }
        );
      } catch (e) {
        return;
      }
      if (this.contextSignature(confirmedContext) !== this.contextSignature(this.currentUploadContext())) {
        this.$message.warning('当前工程或 CRS 已改变，请重新上传并确认 CRS');
        return;
      }
      const formData = new FormData();
      formData.append('file', file, file.name || 'boundary.zip');
      formData.append('project_id', confirmedContext.project_id);
      formData.append('assume_project_crs', 'true');
      try {
        const response = await axios.post(`${this.apiBaseUrl}/upload-shapefile`, formData);
        if (response.data && response.data.success) {
          this.applyBoundaryUploadResult(response.data);
          this.$message.success('已按当前工程 CRS 导入边界');
        } else {
          this.$message.error(response.data?.error || '边界解析失败');
        }
      } catch (error) {
        this.$message.error(error.response?.data?.error || '边界上传失败');
      }
    },
    // 新增：断层文件上传前校验
    beforeFaultUpload(file) { 
      if (!this.projectId) {
        this.$message.warning('请先创建工程');
        return false;
      }
      const ext = file.name.split('.').pop().toLowerCase();
      return ['csv', 'xlsx', 'xls'].includes(ext);
    },
    // 新增：断层文件上传成功回调
    onFaultsUploadSuccess(res) {
      if (res.success) {
        this.$emit('faults-loaded', {
          faults: res.faults,
          geology_model: res.geology_model,
          diagnostics: res.diagnostics
        });
      } else {
        this.$message.error(res.error || "断层解析失败");
      }
    },
    onMouseDown(e) {
      if (e.button === 2) {
        const layout = this.$refs.plotDiv._fullLayout;
        if (!layout) return;
        this.dragState.isDragging = true;
        this.dragState.startX = e.clientX;
        this.dragState.startY = e.clientY;
        this.dragState.startRangeX = [...layout.xaxis.range];
        this.dragState.startRangeY = [...layout.yaxis.range];
        this.$refs.plotDiv.style.cursor = 'grabbing';
      }
    },
    onMouseMove(e) {
      if (!this.dragState.isDragging) return;
      const layout = this.$refs.plotDiv._fullLayout;
      const dx = e.clientX - this.dragState.startX;
      const dy = e.clientY - this.dragState.startY;
      const moveX = (dx / layout.xaxis._length) * (this.dragState.startRangeX[1] - this.dragState.startRangeX[0]);
      const moveY = (dy / layout.yaxis._length) * (this.dragState.startRangeY[1] - this.dragState.startRangeY[0]);
      Plotly.relayout(this.$refs.plotDiv, {
        'xaxis.range': [this.dragState.startRangeX[0] - moveX, this.dragState.startRangeX[1] - moveX],
        'yaxis.range': [this.dragState.startRangeY[0] + moveY, this.dragState.startRangeY[1] + moveY]
      });
    },
    onMouseUp() {
      if (this.dragState.isDragging) {
        this.dragState.isDragging = false;
        this.$refs.plotDiv.style.cursor = this.mode === 'cell' ? 'crosshair' : 'default';
      }
    },
    isPointInPolygon(point, vs) {
        const x = point.x, y = point.y;
        let inside = false;
        for (let i = 0, j = vs.length - 1; i < vs.length; j = i++) {
            const xi = vs[i].x, yi = vs[i].y;
            const xj = vs[j].x, yj = vs[j].y;
            const intersect = ((yi > y) !== (yj > y)) && (x < (xj - xi) * (y - yi) / (yj - yi) + xi);
            if (intersect) inside = !inside;
        }
        return inside;
    },
    applyGridRenderData(cells) {
      this.backendGridCells = Array.isArray(cells) ? cells : [];
      if (this.backendGridCells.length === 0) {
        this.gridLines = null;
        this.centerPoints = null;
        this.gridInfo = null;
        this.clickedCell = null;
        this.drawMap();
        return;
      }

      const gridX = [];
      const gridY = [];
      const centerX = [];
      const centerY = [];
      const cellRefs = [];
      const cellsById = {};
      let nrow = 0;
      let ncol = 0;

      this.backendGridCells
        .filter(cell => cell.layer === 0 && cell.footprint && cell.footprint.length > 0)
        .forEach(cell => {
          cell.footprint.forEach(point => {
            gridX.push(point.x);
            gridY.push(point.y);
          });
          gridX.push(null);
          gridY.push(null);
          centerX.push(cell.x);
          centerY.push(cell.y);
          cellRefs.push(cell);
          cellsById[cell.cell_id] = cell;
          nrow = Math.max(nrow, (cell.row || 0) + 1);
          ncol = Math.max(ncol, (cell.col || cell.column || 0) + 1);
        });

      this.gridLines = { x: gridX, y: gridY };
      this.centerPoints = { x: centerX, y: centerY, cells: cellRefs };
      this.gridInfo = { backend: true, nrow, ncol, cellsById };
      this.drawMap();
    },
    previewGrid(inputCellSize) {
      if (!this.boundary || this.boundary.length === 0) return;
      
      const xs = this.boundary.map(p => p.x); const ys = this.boundary.map(p => p.y);
      const minX = Math.min(...xs), maxX = Math.max(...xs);
      const minY = Math.min(...ys), maxY = Math.max(...ys);
      const width = maxX - minX; 
      const height = maxY - minY;

      const ncol = Math.max(5, Math.ceil(width / inputCellSize));
      const nrow = Math.max(5, Math.ceil(height / inputCellSize));
      
      const delr = width / ncol;
      const delc = height / nrow;

      this.gridInfo = { minX, maxX, minY, maxY, delr, delc, ncol, nrow };
      
      const gridX = []; const gridY = [];
      const centerX = []; const centerY = [];

      for (let i = 0; i < nrow; i++) {
        for (let j = 0; j < ncol; j++) {
          const cellLeft = minX + j * delr; 
          const cellTop = maxY - i * delc;
          const cellBottom = maxY - (i + 1) * delc;
          const cx = cellLeft + delr / 2; 
          const cy = cellTop - delc / 2;

          if (this.isPointInPolygon({x: cx, y: cy}, this.boundary)) {
            gridX.push(cellLeft, cellLeft + delr, cellLeft + delr, cellLeft, cellLeft, null);
            gridY.push(cellBottom, cellBottom, cellTop, cellTop, cellBottom, null);
            centerX.push(cx); centerY.push(cy);
          }
        }
      }
      this.gridLines = { x: gridX, y: gridY };
      this.centerPoints = { x: centerX, y: centerY };
      this.drawMap();
    },
    clearGrid() {
      this.gridLines = null; this.centerPoints = null; this.clickedCell = null;
      this.drawMap();
    },
    findRenderedCell(selection) {
      if (!selection) return null;
      if (selection.cell_id) {
        return this.backendGridCells.find(cell => cell.cell_id === selection.cell_id) || null;
      }
      return this.backendGridCells.find(cell => (
        cell.layer === (selection.layer || 0)
        && cell.row === selection.row
        && (cell.col === selection.col || cell.column === selection.col)
      )) || null;
    },
    footprintTrace(cell, options) {
      if (!cell || !cell.footprint || cell.footprint.length === 0) return null;
      return {
        x: cell.footprint.map(point => point.x),
        y: cell.footprint.map(point => point.y),
        mode: 'lines',
        fill: options.fill ? 'toself' : undefined,
        fillcolor: options.fillcolor,
        line: { color: options.color, width: options.width || 1 },
        hoverinfo: options.text ? 'text' : 'skip',
        text: options.text || undefined
      };
    },
    drawMap() {
      if (
        (!this.boundary || this.boundary.length === 0)
        && (!this.faults || this.faults.length === 0)
        && (!this.backendGridCells || this.backendGridCells.length === 0)
      ) return;
      const traces = [];

      // 1. 网格
      if (this.gridLines) {
        traces.push({
          x: this.gridLines.x, y: this.gridLines.y, mode: 'lines', 
          name: '网格', line: { color: 'rgba(0,0,0, 0.1)', width: 0.5 }, hoverinfo: 'skip'
        });
      }
      // 2. 幽灵点
      if (this.centerPoints && this.mode === 'cell') {
        traces.push({
          x: this.centerPoints.x, y: this.centerPoints.y, mode: 'markers',
          marker: { size: 20, opacity: 0 },
          customdata: this.centerPoints.cells || null,
          hoverinfo: 'none',
          name: 'GhostGrid'
        });
      }
      // 3. 边界
      if (this.boundary && this.boundary.length > 0) {
        const bx = this.boundary.map(p => p.x); const by = this.boundary.map(p => p.y);
        traces.push({ x: bx, y: by, mode: 'lines', name: '边界', line: { color: '#333', width: 2 }, hoverinfo: 'none' });
      }

      // 新增：4. 渲染断层线
      if (this.faults && this.faults.length > 0) {
        this.faults.forEach((faultLine, idx) => {
          const fx = faultLine.map(p => p.x);
          const fy = faultLine.map(p => p.y);
          traces.push({
            x: fx, y: fy,
            mode: 'lines+markers',
            name: `断层 F${idx + 1}`,
            line: { color: '#E02020', width: 3, dash: 'dot' },
            marker: { size: 6, color: '#E02020' },
            hoverinfo: 'name'
          });
        });
      }

      // 5. 属性渲染 (KCells & Wells)
      if (this.kCells && this.gridInfo) {
        const { minX, maxY, delr, delc } = this.gridInfo;
        this.kCells.forEach(cell => {
            const rendered = this.findRenderedCell(cell);
            const trace = this.footprintTrace(rendered, {
              fill: true,
              fillcolor: 'rgba(64, 158, 255, 0.6)',
              color: '#409EFF',
              text: `K=${cell.k_val}`
            });
            if (trace) {
              traces.push(trace);
              return;
            }
            if (this.gridInfo.backend) return;
            const x0 = minX + cell.col * delr;
            const y1 = maxY - cell.row * delc;
            const y0 = maxY - (cell.row + 1) * delc;
            traces.push({
                x: [x0, x0 + delr, x0 + delr, x0, x0], y: [y0, y0, y1, y1, y0],
                mode: 'lines', fill: 'toself', fillcolor: 'rgba(64, 158, 255, 0.6)',
                line: { color: '#409EFF', width: 1 }, hoverinfo: 'text', text: `K=${cell.k_val}`
            });
        });
      }
      if (this.wells && this.gridInfo) {
        const { minX, maxY, delr, delc } = this.gridInfo;
        this.wells.forEach(w => {
            const rendered = this.findRenderedCell(w);
            const trace = this.footprintTrace(rendered, {
              fill: true,
              fillcolor: 'rgba(255, 200, 0, 0.7)',
              color: '#E6A23C',
              text: `Well Q=${w.rate}`
            });
            if (trace) {
              traces.push(trace);
              return;
            }
            if (this.gridInfo.backend) return;
            const x0 = minX + w.col * delr;
            const y1 = maxY - w.row * delc;
            const y0 = maxY - (w.row + 1) * delc;
            traces.push({
                x: [x0, x0 + delr, x0 + delr, x0, x0], y: [y0, y0, y1, y1, y0],
                mode: 'lines', fill: 'toself', fillcolor: 'rgba(255, 200, 0, 0.7)',
                line: { color: '#E6A23C', width: 1 }, hoverinfo: 'text', text: `Well Q=${w.rate}`
            });
        });
      }
      if (this.clickedCell && this.gridInfo) {
        const rendered = this.findRenderedCell(this.clickedCell);
        const trace = this.footprintTrace(rendered, {
          color: '#FF0000',
          width: 3
        });
        if (trace) {
          traces.push(trace);
        } else if (!this.gridInfo.backend) {
        const { minX, maxY, delr, delc } = this.gridInfo;
        const c = this.clickedCell;
        const x0 = minX + c.col * delr; 
        const y1 = maxY - c.row * delc;
        const y0 = maxY - (c.row + 1) * delc;
        traces.push({
            x: [x0, x0 + delr, x0 + delr, x0, x0], y: [y0, y0, y1, y1, y0],
            mode: 'lines', line: { color: '#FF0000', width: 3 }, hoverinfo: 'skip'
        });
        }
      }

      // 6. 边界条件渲染
      if (this.configuredData && this.boundary && this.boundary.length > 0) {
        const typeColors = { 'CHD': '#F56C6C', 'RIV': '#409EFF', 'DRN': '#E6A23C', 'GHB': '#67C23A' };
        for (const segId in this.configuredData) {
          const cfg = this.configuredData[segId]; const idx = parseInt(segId);
          if (idx < this.boundary.length - 1) {
             const p1 = this.boundary[idx]; const p2 = this.boundary[idx+1];
             traces.push({
               x: [p1.x, p2.x], y: [p1.y, p2.y], mode: 'lines+markers',
               line: { color: typeColors[cfg.type]||'#000', width: 4 }, marker: {size:6, color:typeColors[cfg.type]},
               name: cfg.type, hoverinfo: 'text', text: `${cfg.type} #${idx}`
             });
          }
        }
      }
      if (this.selectedSegmentIndex !== null && this.mode === 'boundary') {
         const idx = this.selectedSegmentIndex;
         const p1 = this.boundary[idx]; const p2 = this.boundary[idx+1];
         traces.push({ x: [p1.x, p2.x], y: [p1.y, p2.y], mode: 'lines', line: { color: '#F56C6C', width: 6 }, opacity: 0.9 });
      }

      const layout = {
        title: '', hovermode: 'closest', dragmode: false, uirevision: 'true',
        autosize: true,
        margin: { t: 10, b: 10, l: 10, r: 10 }, 
        showlegend: false,
        yaxis: { scaleanchor: "x", scaleratio: 1, showgrid: false, zeroline: false },
        xaxis: { showgrid: false, zeroline: false }
      };
      
      const config = { responsive: true, scrollZoom: true, displayModeBar: false };
      Plotly.react(this.$refs.plotDiv, traces, layout, config);
      this.$refs.plotDiv.removeAllListeners('plotly_click');
      this.$refs.plotDiv.on('plotly_click', this.onMapClick);
      this.$refs.plotDiv.style.cursor = this.mode === 'cell' ? 'crosshair' : 'default';
    },

    onMapClick(data) {
       let clickX, clickY;
       if (data.points && data.points.length > 0) {
           clickX = data.points[0].x; clickY = data.points[0].y;
       } else if (data.event) {
          const layout = this.$refs.plotDiv._fullLayout;
          const rect = this.$refs.plotDiv.getBoundingClientRect();
          const mouseX = data.event.clientX - rect.left;
          const mouseY = data.event.clientY - rect.top;
          try {
             clickX = layout.xaxis.p2c(mouseX - layout.margin.l);
             clickY = layout.yaxis.p2c(mouseY - layout.margin.t);
          } catch(e) {}
       }
       if (clickX === undefined) return;

       if (this.mode === 'cell') {
           const clickedBackendCell = data.points
             && data.points[0]
             && data.points[0].customdata
             ? data.points[0].customdata
             : null;
           if (clickedBackendCell) {
             this.clickedCell = clickedBackendCell;
             this.drawMap();
             this.$emit('grid-clicked', clickedBackendCell);
             return;
           }
           if (this.gridInfo) {
             const { minX, maxY, delr, delc, ncol, nrow } = this.gridInfo;
             if (this.gridInfo.backend) return;
             const col = Math.floor((clickX - minX) / delr);
             const row = Math.floor((maxY - clickY) / delc);

             if (col >= 0 && col < ncol && row >= 0 && row < nrow) {
                const centerX = minX + col * delr + delr / 2;
                const centerY = maxY - row * delc - delc / 2;
                this.clickedCell = { row, col };
                this.drawMap();
                this.$emit('grid-clicked', { row, col, x: centerX, y: centerY });
             }
           }
       } else {
           if (!this.boundary) return;
           let minDist = Infinity; let closestIdx = -1;
           const pts = this.boundary;
           for (let i = 0; i < pts.length - 1; i++) {
             const p1 = pts[i]; const p2 = pts[i+1];
             const d = this.pointToSegmentDistance(clickX, clickY, p1.x, p1.y, p2.x, p2.y);
             if (d < minDist) { minDist = d; closestIdx = i; }
           }
           const layout = this.$refs.plotDiv._fullLayout;
           const mapWidth = layout.xaxis.range[1] - layout.xaxis.range[0];
           if (minDist < mapWidth * 0.08) {
             this.selectedSegmentIndex = closestIdx;
             this.$emit('segment-selected', { index: closestIdx });
             this.drawMap(); 
           }
       }
    },
    pointToSegmentDistance(px, py, x1, y1, x2, y2) {
      const A = px - x1; const B = py - y1; const C = x2 - x1; const D = y2 - y1;
      const dot = A * C + B * D; const len_sq = C * C + D * D;
      let param = -1; if (len_sq !== 0) param = dot / len_sq;
      let xx, yy;
      if (param < 0) { xx = x1; yy = y1; } else if (param > 1) { xx = x2; yy = y2; } else { xx = x1 + param * C; yy = y1 + param * D; }
      const dx = px - xx; const dy = py - yy;
      return Math.sqrt(dx * dx + dy * dy);
    }
  }
};
</script>

<style scoped>
.map-container-wrapper { 
  background: #fff; border-radius: 4px; border: 1px solid #ddd;
  position: relative; user-select: none; 
}
.header-actions { padding: 10px; border-bottom: 1px solid #eee; display: flex; align-items: center; }
.canvas-scroll-box { 
  width: 100%; 
  height: 350px; 
  position: relative; 
  overflow: hidden; 
}
.plot-div { 
  width: 100%; 
  height: 100%; 
}
.mode-tip {
  position: absolute; top: 60px; right: 20px; z-index: 10;
  background: rgba(255,255,255,0.9); padding: 5px 10px; border: 1px solid #409EFF; color: #409EFF; pointer-events: none;
  font-size: 12px;
}
</style>
