<template>
  <div class="analysis-panel">
    <div class="header">
      <span><i class="el-icon-pie-chart"></i> 结果分析 (Step 6)</span>
      <el-button type="primary" size="mini" plain @click="showDialog = true">打开图表分析器</el-button>
    </div>

    <el-dialog 
      title="模拟结果深度分析" 
      :visible.sync="showDialog" 
      width="85%" 
      append-to-body 
      top="5vh"
    >
      <el-tabs v-model="activeMode" type="card">
        
        <el-tab-pane label="平面等值线 (Contours)" name="contour">
          <div class="toolbar">
            <span>选择层级: </span>
            <el-select v-model="selectedLayer" size="small" placeholder="Layer">
              <el-option v-for="l in layers" :key="l" :label="'Layer ' + l" :value="l"></el-option>
            </el-select>
            <el-button type="success" size="small" icon="el-icon-refresh" @click="drawContour">生成图表</el-button>
          </div>
          <div id="contour-div" class="chart-container"></div>
        </el-tab-pane>

        <el-tab-pane label="剖面流场 (Profile)" name="profile">
          <div class="toolbar">
            <span class="label">切分方向:</span>
            <el-radio-group v-model="sliceMode" size="small">
              <el-radio label="row">切行 (X方向)</el-radio>
              <el-radio label="col">切列 (Y方向)</el-radio>
            </el-radio-group>
            
            <span class="label" style="margin-left: 15px;">索引号:</span>
            <el-input-number v-model="sliceIndex" :min="0" size="small"></el-input-number>
            
            <el-button type="success" size="small" icon="el-icon-video-play" @click="drawProfile">生成剖面</el-button>
          </div>
          <div id="profile-div" class="chart-container"></div>
        </el-tab-pane>

      </el-tabs>
    </el-dialog>
  </div>
</template>

<script>
import Plotly from 'plotly.js-dist-min';

export default {
  name: 'AnalysisPanel',
  props: {
    points: { type: Array, default: () => [] }
  },
  data() {
    return {
      showDialog: false,
      activeMode: 'contour',
      selectedLayer: 0,
      sliceMode: 'row',
      sliceIndex: 10
    };
  },
  computed: {
    layers() {
      if (!this.points || this.points.length === 0) return [];
      const distinct = [...new Set(this.points.map(p => p.layer))];
      return distinct.sort((a, b) => a - b);
    }
  },
  methods: {
    // 绘制平面等值线
    drawContour() {
      if (this.points.length === 0) return;
      const layerData = this.points.filter(p => p.layer === this.selectedLayer);
      
      if (layerData.length === 0) {
        this.$message.warning("该层无数据");
        return;
      }

      const x = layerData.map(p => p.x);
      const y = layerData.map(p => p.y);
      const z = layerData.map(p => p.head);

      const trace = {
        x: x,
        y: y,
        z: z,
        type: 'contour',
        colorscale: 'Jet',
        contours: {
          coloring: 'heatmap',
          showlabels: true,
          labelfont: { size: 12, color: 'white' }
        },
        colorbar: { title: 'Head (m)' }
      };

      const layout = {
        title: `Layer ${this.selectedLayer} 水头等值线图`,
        xaxis: { title: 'X (m)' },
        yaxis: { title: 'Y (m)', scaleanchor: 'x' },
        margin: { t: 40, b: 40, l: 40, r: 40 }
      };

      this.$nextTick(() => {
        Plotly.newPlot('contour-div', [trace], layout);
      });
    },

    // 绘制剖面图
    drawProfile() {
      if (this.points.length === 0) return;
      let data = [];
      let xKey = '', uKey = '', wKey = '';

      if (this.sliceMode === 'row') {
        data = this.points.filter(p => p.row === this.sliceIndex);
        xKey = 'x'; // 横坐标是物理X
        uKey = 'vx'; // 水平流速
        wKey = 'vz'; // 垂直流速
      } else {
        data = this.points.filter(p => p.col === this.sliceIndex);
        xKey = 'y'; // 横坐标是物理Y
        uKey = 'vy';
        wKey = 'vz';
      }

      if (data.length === 0) {
        this.$message.warning("该剖面无数据 (索引可能越界)");
        return;
      }

      const x = [];
      const y = []; // 实际上是 Z (高程)
      const head = [];
      const u = [];
      const w = [];

      data.forEach(p => {
        const centerZ = (p.top + p.bottom) / 2;
        x.push(p[xKey]);
        y.push(centerZ);
        head.push(p.head);
        
        // 流速
        u.push(p.flows[uKey]);
        // 垂直流速通常很小，夸张显示以便观察
        w.push(p.flows[wKey] * 10); 
      });

      // 1. 背景热力点 (显示水头)
      const traceHead = {
        x: x, y: y,
        mode: 'markers',
        marker: {
          color: head,
          colorscale: 'Jet',
          size: 14,
          symbol: 'square',
          colorbar: { title: 'Head (m)' }
        },
        type: 'scatter',
        name: 'Head',
        hovertemplate: 'X: %{x:.1f}<br>Z: %{y:.1f}<br>Head: %{marker.color:.2f} m<extra></extra>'
      };

      // 2. 模拟流速箭头 (使用 annotations)
      const annotations = [];
      // 为了防止太密，隔点采样
      for (let i = 0; i < x.length; i++) {
        const velMag = Math.sqrt(u[i]**2 + w[i]**2);
        if (velMag > 1e-6) {
           // 简单的箭头缩放
           const scale = 500; 
           annotations.push({
             x: x[i] + u[i] * scale,
             y: y[i] + w[i] * scale,
             ax: x[i],
             ay: y[i],
             xref: 'x', yref: 'y', axref: 'x', ayref: 'y',
             showarrow: true,
             arrowhead: 2,
             arrowsize: 1,
             arrowwidth: 1.5,
             arrowcolor: '#333'
           });
        }
      }

      const layout = {
        title: `剖面图 (${this.sliceMode}=${this.sliceIndex})`,
        xaxis: { title: 'Distance (m)' },
        yaxis: { title: 'Elevation (m)', scaleanchor: 'x', scaleratio: 10 }, // 垂直方向夸张
        annotations: annotations,
        showlegend: false,
        hovermode: 'closest'
      };

      this.$nextTick(() => {
        Plotly.newPlot('profile-div', [traceHead], layout);
      });
    }
  }
};
</script>

<style scoped>
.analysis-panel {
  background: #fff; padding: 10px; border-radius: 4px; border: 1px solid #ebeef5; margin-bottom: 10px;
}
.header {
  display: flex; justify-content: space-between; align-items: center; font-size: 13px; font-weight: bold; color: #303133;
}
.toolbar {
  background: #f5f7fa; padding: 10px; border-radius: 4px; margin-bottom: 10px; display: flex; align-items: center;
}
.label { margin-right: 10px; font-size: 12px; }
.chart-container {
  width: 100%; height: 500px; border: 1px solid #eee;
}
</style>