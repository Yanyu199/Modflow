<template>
  <div class="viewer-wrapper">
    <div class="top-control-bar">
      <span class="control-label">Z轴: {{ zScale }}x</span>
      <el-slider 
        v-model="zScale" 
        :min="1" :max="50" :step="1"
        @input="onZScaleChange" 
        style="width: 100px; display: inline-block; vertical-align: middle; margin: 0 10px;">
      </el-slider>
      
      <el-divider direction="vertical"></el-divider>

      <span class="control-label">透明度: {{ opacity }}</span>
      <el-slider 
        v-model="opacity" 
        :min="0.1" :max="1.0" :step="0.1"
        @input="onOpacityChange" 
        style="width: 100px; display: inline-block; vertical-align: middle; margin: 0 10px;">
      </el-slider>

      <el-divider direction="vertical"></el-divider>

      <el-checkbox 
        v-model="showFlow" 
        border size="mini" 
        @change="updateFlowVectors"
        style="margin-left: 0; margin-right: 10px; background: #fff; padding: 5px 10px; height: 32px;">
        <span style="font-weight: bold; color: #00008B;">流向</span>
      </el-checkbox>

      <div v-if="showFlow" style="display: inline-flex; align-items: center;">
        <span class="control-label">稀疏度: {{ flowStep }}</span>
        <el-slider 
          v-model="flowStep" 
          :min="1" :max="10" :step="1"
          @change="updateFlowVectors" 
          style="width: 80px; display: inline-block; vertical-align: middle; margin: 0 10px;">
        </el-slider>
      </div>

      <el-divider direction="vertical"></el-divider>

      <el-checkbox 
        v-model="showLegend" 
        border size="mini" 
        style="margin-left: 0; background: #fff; padding: 5px 10px; height: 32px;">
        <span style="font-weight: bold; color: #E6A23C;">色带</span>
      </el-checkbox>
    </div>

    <div class="layer-control-panel" v-if="points.length > 0">
      <div class="panel-title"><i class="el-icon-files"></i> 图层显隐控制</div>
      <div class="layer-list">
        <el-checkbox 
          v-for="(vis, idx) in layerVisibility" 
          :key="idx" 
          v-model="layerVisibility[idx]"
          @change="updateVisibility"
        >
          Layer {{ idx }}
        </el-checkbox>
      </div>
    </div>

    <LegendPanel 
      :min="minHead" 
      :max="maxHead" 
      :visible="showLegend" 
    />

    <div ref="container" class="three-container">
      <ViewerControls v-if="initialized" :camera="camera" :controls="controls" />
    </div>

    <CellDetailPanel 
      :cellData="selectedCell" 
      @close="selectedCell = null" 
    />

  </div>
</template>

<script>
import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';
import ViewerControls from './ViewerControls.vue';
// 引入新拆分的组件
import LegendPanel from './LegendPanel.vue';
import CellDetailPanel from './CellDetailPanel.vue';

export default {
  name: 'Real3DViewer',
  components: { ViewerControls, LegendPanel, CellDetailPanel },
  props: { points: { type: Array, default: () => [] } },
  data() {
    return {
      scene: null, camera: null, renderer: null, controls: null,
      meshes: [], 
      layerVisibility: [], 
      maxLayer: 0,
      initialized: false, animationId: null, clickHandler: null,
      selectedCell: null,
      cellDataMap: {},
      zScale: 5, 
      opacity: 0.9, 
      raycaster: new THREE.Raycaster(),
      mouse: new THREE.Vector2(),
      showFlow: false, 
      flowArrows: [],  
      flowStep: 3, 
      currentCellSize: 50,
      pathLines: [],
      
      minHead: null,
      maxHead: null,
      // ⭐ 新增：控制色带显示的变量
      showLegend: true
    };
  },
  watch: {
    points: {
      handler(newPoints) {
        if (!this.initialized) return;
        this.drawVoxels(newPoints);
        this.selectedCell = null;
      },
      deep: true
    }
  },
  mounted() {
    this.$nextTick(() => {
      this.initThree();
      if (this.points.length > 0) this.drawVoxels(this.points);
    });
  },
  beforeDestroy() {
    if (this.animationId) cancelAnimationFrame(this.animationId);
    if (this.clickHandler && this.$refs.container) this.$refs.container.removeEventListener('click', this.clickHandler);
    if (this.renderer) this.renderer.dispose();
    this.clearArrows();
  },
  methods: {
    onZScaleChange() {
      if (this.points.length > 0) this.drawVoxels(this.points);
    },

    drawPathLines(pathData, cx, cy, zScale) {
    // 先清理旧线条
    this.pathLines.forEach(line => this.scene.remove(line));
    this.pathLines = [];

    if (!pathData) return;

    pathData.forEach(path => {
      const points = path.map(pt => new THREE.Vector3(
        pt.x - cx,
        pt.z * zScale,
        -(pt.y - cy)
      ));
      
      const geometry = new THREE.BufferGeometry().setFromPoints(points);
      const material = new THREE.LineBasicMaterial({ color: 0xff0000, linewidth: 2 });
      const line = new THREE.Line(geometry, material);
      
      this.scene.add(line);
      this.pathLines.push(line);
    });
  },

    onOpacityChange() {
      this.meshes.forEach(mesh => {
        if (mesh.material) {
          mesh.material.opacity = this.opacity;
          mesh.material.transparent = this.opacity < 1.0;
          mesh.material.needsUpdate = true;
        }
      });
      if (this.renderer) this.renderer.render(this.scene, this.camera);
    },

    initThree() {
      const container = this.$refs.container;
      this.scene = new THREE.Scene();
      this.scene.background = new THREE.Color(0xf0f9ff);
      
      this.camera = new THREE.PerspectiveCamera(45, container.clientWidth / container.clientHeight, 1, 500000);
      this.camera.position.set(2000, 2000, 2000); 
      
      this.renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
      this.renderer.setSize(container.clientWidth, container.clientHeight);
      this.renderer.setPixelRatio(window.devicePixelRatio); 
      this.renderer.shadowMap.enabled = true;
      
      container.innerHTML = '';
      container.appendChild(this.renderer.domElement);
      
      this.controls = new OrbitControls(this.camera, this.renderer.domElement);
      this.controls.enableDamping = true;
      
      this.scene.add(new THREE.AmbientLight(0xffffff, 0.6));
      const dirLight = new THREE.DirectionalLight(0xffffff, 0.6);
      dirLight.position.set(500, 2000, 1000);
      dirLight.castShadow = true;
      this.scene.add(dirLight);
      
      this.initialized = true;
      this.setupClickHandler();
      this.animate();
      
      window.addEventListener('resize', () => {
        if(this.camera && this.renderer && this.$refs.container) {
          const w = this.$refs.container.clientWidth;
          const h = this.$refs.container.clientHeight;
          this.camera.aspect = w / h;
          this.camera.updateProjectionMatrix();
          this.renderer.setSize(w, h);
        }
      });
    },

    drawVoxels(points) {
      if (!this.scene) return;
      this.meshes.forEach(m => { this.scene.remove(m); if(m.geometry) m.geometry.dispose(); if(m.material) m.material.dispose(); });
      this.meshes = [];
      this.cellDataMap = {};

      if (!points || points.length === 0) {
        this.minHead = null; 
        this.maxHead = null;
        return;
      }

      const layers = [...new Set(points.map(p => p.layer))].sort((a,b)=>a-b);
      this.maxLayer = Math.max(...layers);
      
      if (this.layerVisibility.length !== this.maxLayer + 1) {
         this.layerVisibility = new Array(this.maxLayer + 1).fill(true);
      }

      const xs = points.map(p => p.x); 
      const ys = points.map(p => p.y); 
      
      const hs = points.filter(p => p.head !== null && p.head !== undefined).map(p => p.head);
      let minH = 0, maxH = 1;
      if (hs.length > 0) {
          minH = Math.min(...hs); 
          maxH = Math.max(...hs);
          this.minHead = minH;
          this.maxHead = maxH;
      } else {
          this.minHead = null;
          this.maxHead = null;
      }

      const minX = Math.min(...xs), maxX = Math.max(...xs);
      const minY = Math.min(...ys), maxY = Math.max(...ys);
      const cx = (minX + maxX) / 2; 
      const cy = (minY + maxY) / 2;
      
      const uniqueX = [...new Set(xs)].sort((a,b)=>a-b);
      let cellSize = 50;
      if (uniqueX.length > 1) {
         let minD = Infinity;
         for(let i=1; i<uniqueX.length; i++) {
            const d = uniqueX[i]-uniqueX[i-1];
            if(d > 0.1 && d < minD) minD = d;
         }
         cellSize = minD;
      }
      this.currentCellSize = cellSize;

      const geometry = new THREE.BoxGeometry(cellSize*0.95, 1, cellSize*0.95);
      
      const material = new THREE.MeshLambertMaterial({ 
        color: 0xffffff,
        transparent: this.opacity < 1.0,
        opacity: this.opacity
      });
      
      const currentZScale = this.zScale;

      layers.forEach(layerIdx => {
         const layerPoints = points.filter(p => p.layer === layerIdx);
         if (layerPoints.length === 0) return;

         const mesh = new THREE.InstancedMesh(geometry, material.clone(), layerPoints.length);
         mesh.userData = { layerIndex: layerIdx };
         
         const dummy = new THREE.Object3D();
         const color = new THREE.Color();
         
         layerPoints.forEach((p, i) => {
            const t_val = p.top; const b_val = p.bottom;
            let thick = t_val - b_val; if (thick < 0.1) thick = 0.1;
            const centerZ = (t_val + b_val) / 2;
            
            dummy.position.set(p.x - cx, centerZ * currentZScale, -(p.y - cy));
            dummy.scale.set(1, thick * currentZScale, 1);
            dummy.updateMatrix();
            mesh.setMatrixAt(i, dummy.matrix);
            
            if (p.head !== null && p.head !== undefined && hs.length > 0) {
               let t = 0.5;
               if (maxH !== minH) t = (p.head - minH) / (maxH - minH);
               
               // ⭐ 修改颜色映射：t=0(Low) -> Red(0.0), t=1(High) -> Blue(0.66)
               // 原公式：0.66 * (1 - t)
               // 新公式：0.66 * t
               color.setHSL(0.66 * t, 0.8, 0.5); 
            } else {
               const baseHue = 0.6; 
               const l = 0.9 - (layerIdx * 0.05); 
               color.setHSL(baseHue, 0.3, l);
            }
            mesh.setColorAt(i, color);
            
            this.cellDataMap[`${layerIdx}_${i}`] = p;
         });
         
         mesh.instanceMatrix.needsUpdate = true;
         mesh.instanceColor.needsUpdate = true;
         mesh.castShadow = true; mesh.receiveShadow = true;
         this.scene.add(mesh);
         this.meshes.push(mesh);
      });
      
      this.updateFlowVectors();
      this.updateVisibility();
    },

    clearArrows() {
      this.flowArrows.forEach(arrow => {
        this.scene.remove(arrow);
        if (arrow.line) { 
           if (arrow.line.geometry) arrow.line.geometry.dispose(); 
           if (arrow.line.material) arrow.line.material.dispose(); 
        }
        if (arrow.cone) { 
           if (arrow.cone.geometry) arrow.cone.geometry.dispose(); 
           if (arrow.cone.material) arrow.cone.material.dispose(); 
        }
      });
      this.flowArrows = [];
    },

    updateFlowVectors() {
      this.clearArrows();

      if (!this.showFlow || !this.points || this.points.length === 0) {
        if(this.renderer) this.renderer.render(this.scene, this.camera);
        return;
      }

      const arrowLen = this.currentCellSize * 0.8 * this.flowStep; 
      const headLen = arrowLen * 0.3;
      const headWidth = headLen * 0.5;
      const arrowColor = 0x00008B; 

      const xs = this.points.map(p => p.x); const ys = this.points.map(p => p.y);
      const minX = Math.min(...xs), maxX = Math.max(...xs);
      const minY = Math.min(...ys), maxY = Math.max(...ys);
      const cx = (minX + maxX) / 2; const cy = (minY + maxY) / 2;
      const step = this.flowStep; 

      this.points.forEach(p => {
        if (!p.flows) return;
        if (p.row % step !== 0 || p.col % step !== 0) return;

        const vx = p.flows.right;
        const vy = p.flows.top * this.zScale; 
        const vz = -p.flows.back;

        const dir = new THREE.Vector3(vx, vy, vz);
        if (dir.lengthSq() < 1e-12) return;
        dir.normalize();

        const centerZ = (p.top + p.bottom) / 2;
        const origin = new THREE.Vector3(
           p.x - cx, 
           centerZ * this.zScale, 
           -(p.y - cy)
        );

        const arrow = new THREE.ArrowHelper(dir, origin, arrowLen, arrowColor, headLen, headWidth);
        arrow.userData = { layerIndex: p.layer };
        this.scene.add(arrow);
        this.flowArrows.push(arrow);
      });

      this.updateVisibility();
    },

    updateVisibility() {
       this.meshes.forEach(mesh => {
          const lIdx = mesh.userData.layerIndex;
          mesh.visible = this.layerVisibility[lIdx];
       });
       
       this.flowArrows.forEach(arrow => {
          const lIdx = arrow.userData.layerIndex;
          arrow.visible = this.layerVisibility[lIdx];
       });
       
       if (this.renderer) this.renderer.render(this.scene, this.camera);
    },

    setupClickHandler() {
      const container = this.$refs.container;
      this.clickHandler = (event) => {
        const rect = container.getBoundingClientRect();
        this.mouse.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
        this.mouse.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;

        this.raycaster.setFromCamera(this.mouse, this.camera);
        const visibleMeshes = this.meshes.filter(m => m.visible);
        if (visibleMeshes.length === 0) return;

        const intersects = this.raycaster.intersectObjects(visibleMeshes);
        if (intersects.length > 0) {
           const hit = intersects[0];
           const lIdx = hit.object.userData.layerIndex;
           const cellData = this.cellDataMap[`${lIdx}_${hit.instanceId}`];
           if (cellData) {
             console.log("🎯 选中网格:", cellData);
             this.selectedCell = cellData;
             this.$message.success(`选中: Layer ${lIdx}, Row ${cellData.row}, Col ${cellData.col}`);
           }
        } else {
           this.selectedCell = null;
        }
      };
      container.addEventListener('click', this.clickHandler);
    },

    animate() {
      this.animationId = requestAnimationFrame(this.animate);
      if (this.controls) this.controls.update();
      if (this.renderer) this.renderer.render(this.scene, this.camera);
    }
  }
};
</script>

<style scoped>
.viewer-wrapper { width: 100%; height: 100%; position: relative; overflow: hidden; }
.three-container { width: 100%; height: 100%; background: #f0f9ff; cursor: default; }

.top-control-bar {
  position: absolute; 
  top: 70px; 
  left: 50%; 
  transform: translateX(-50%);
  background: rgba(255, 255, 255, 0.95); 
  padding: 8px 15px; 
  border-radius: 20px;
  box-shadow: 0 2px 10px rgba(0,0,0,0.1); 
  z-index: 90; 
  display: flex; 
  align-items: center; 
  white-space: nowrap;
  pointer-events: auto; 
}
.control-label { font-size: 13px; font-weight: bold; color: #333; margin-right: 5px;}

.layer-control-panel {
  position: absolute; bottom: 20px; left: 480px;
  background: rgba(255, 255, 255, 0.9); padding: 10px; border-radius: 6px;
  box-shadow: 0 2px 12px rgba(0,0,0,0.15); max-height: 200px; overflow-y: auto; z-index: 20;
  pointer-events: auto;
}
.panel-title { font-weight: bold; font-size: 13px; margin-bottom: 5px; border-bottom: 1px solid #eee; padding-bottom: 5px; }
.layer-list { display: flex; flex-direction: column; }
.layer-list .el-checkbox { margin-right: 0; margin-bottom: 2px; }
</style>