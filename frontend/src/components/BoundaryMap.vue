<template>
  <div class="map-container-wrapper">
    <div class="header-actions">
      <el-upload
        action="http://localhost:5000/upload-shapefile"
        :show-file-list="false"
        :on-success="onUploadSuccess"
        :before-upload="beforeUpload"
        accept=".zip"
      >
        <el-button type="primary" icon="el-icon-upload" size="small">1. 上传边界 (Step 1)</el-button>
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
import Plotly from 'plotly.js-dist-min';

export default {
  name: 'BoundaryMap',
  props: {
    configuredData: Object,
    wells: Array,
    kCells: Array
  },
  data() {
    return {
      boundary: [],
      mode: 'cell',
      selectedSegmentIndex: null,
      gridLines: null,
      centerPoints: null,
      gridInfo: null,
      clickedCell: null,
      dragState: { isDragging: false, startX: 0, startY: 0, startRangeX: null, startRangeY: null }
    };
  },
  watch: {
    mode() { this.clickedCell = null; this.drawMap(); },
    configuredData: { deep: true, handler() { this.drawMap(); } },
    wells: { deep: true, handler() { this.drawMap(); } },
    kCells: { deep: true, handler() { this.drawMap(); } }
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
    beforeUpload(file) { return file.name.endsWith('.zip'); },
    onUploadSuccess(res) {
      if (res.success) {
        this.boundary = res.data;
        this.gridLines = null; this.centerPoints = null; this.gridInfo = null; this.clickedCell = null;
        this.$emit('boundary-loaded', this.boundary);
        this.drawMap();
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
    drawMap() {
      if (!this.boundary || this.boundary.length === 0) return;
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
          marker: { size: 20, opacity: 0 }, hoverinfo: 'none', name: 'GhostGrid'
        });
      }
      // 3. 边界
      const bx = this.boundary.map(p => p.x); const by = this.boundary.map(p => p.y);
      traces.push({ x: bx, y: by, mode: 'lines', name: '边界', line: { color: '#333', width: 2 }, hoverinfo: 'none' });

      // 4. 属性渲染
      if (this.kCells && this.gridInfo) {
        const { minX, maxY, delr, delc } = this.gridInfo;
        this.kCells.forEach(cell => {
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

      // 边界条件
      if (this.configuredData) {
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
           if (this.gridInfo) {
             const { minX, maxY, delr, delc, ncol, nrow } = this.gridInfo;
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

/* 调整后的高度：350px 适应悬浮窗口 */
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