<template>
  <div class="viewer-wrapper">
    <ViewerTopBar 
      :zScale.sync="zScale"
      :opacity.sync="opacity"
      :showFlow.sync="showFlow"
      :flowStep.sync="flowStep"
      :showLegend.sync="showLegend"
      @z-change="onZScaleChange"
      @opacity-change="onOpacityChange"
      @flow-change="updateFlowVectors"
    />

    <LayerVisibilityPanel 
      v-if="points.length > 0"
      :visibility="layerVisibility"
      :layerMapping="layerMapping"
      @visibility-change="updateVisibility"
    />

    <LegendPanel 
      :min="minHead" 
      :max="maxHead" 
      :visible="showLegend" 
    />

    <div ref="container" class="three-container">
      <ViewerControls v-if="initialized" :camera="camera" :controls="controls" />
    </div>

    <div 
      v-if="selectedBorehole" 
      class="borehole-tooltip" 
      :style="popupStyle"
    >
      <div class="tooltip-title"><i class="el-icon-location"></i> 钻孔信息</div>
      <div><strong>名称:</strong> <span style="color: #409EFF">{{ selectedBorehole.name }}</span></div>
      <div style="font-size: 12px; color: #666; margin-top: 4px;">当前点击分层 ID: {{ selectedBorehole.layerId }}</div>
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

// 引入所有 UI 子组件
import ViewerTopBar from './ViewerTopBar.vue';
import LayerVisibilityPanel from './LayerVisibilityPanel.vue';
import ViewerControls from './ViewerControls.vue';
import LegendPanel from './LegendPanel.vue';
import CellDetailPanel from './CellDetailPanel.vue';

const LAYER_COLORS = [
  0x8dd3c7, 0xffffb3, 0xbebada, 0xfb8072, 
  0x80b1d3, 0xfdb462, 0xb3de69, 0xfccde5
];

export default {
  name: 'Real3DViewer',
  components: { 
    ViewerTopBar, 
    LayerVisibilityPanel, 
    ViewerControls, 
    LegendPanel, 
    CellDetailPanel 
  },
  props: { 
    points: { type: Array, default: () => [] },
    layerMapping: { type: Object, default: () => ({}) } 
  },
  data() {
    return {
      // --- Three.js 核心对象 ---
      scene: null, camera: null, renderer: null, controls: null,
      meshes: [], boreholeGroup: null, flowArrows: [], pathLines: [],
      
      // --- 渲染状态数据 ---
      layerVisibility: [], 
      maxLayer: 0,
      initialized: false, animationId: null, clickHandler: null,
      currentBoreholes: [], cellDataMap: {},
      cx: 0, cy: 0, currentCellSize: 50,
      
      // --- 用户交互配置 (与子组件双向绑定) ---
      zScale: 5, 
      opacity: 0.6, 
      showFlow: false, 
      flowStep: 3, 
      showLegend: true,

      // --- 数据结果极值 ---
      minHead: null, maxHead: null,

      // --- 射线交互所需 ---
      raycaster: new THREE.Raycaster(),
      mouse: new THREE.Vector2(),
      selectedCell: null,
      selectedBorehole: null,
      popupStyle: { top: '0px', left: '0px' }
    };
  },
  watch: {
    points: {
      handler(newPoints) {
        if (!this.initialized) return;
        this.drawVoxels(newPoints);
        this.selectedCell = null;
        this.selectedBorehole = null;
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
    if (this.boreholeGroup) this.scene.remove(this.boreholeGroup);
  },
  methods: {
    onZScaleChange() {
      if (this.points.length > 0) this.drawVoxels(this.points);
      if (this.currentBoreholes.length > 0) this.drawBoreholes(this.currentBoreholes);
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

    updateVisibility(newVisibility) {
       if (newVisibility) this.layerVisibility = newVisibility;
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

    // -----------------------------------------------------------------
    // ⬇️ 以下均为原封不动的 Three.js 核心绘图算法 (未作修改，仅折叠呈现) ⬇️
    // -----------------------------------------------------------------

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
        this.minHead = null; this.maxHead = null;
        return;
      }

      const layers = [...new Set(points.map(p => p.layer))].sort((a,b)=>a-b);
      this.maxLayer = Math.max(...layers);
      
      if (this.layerVisibility.length !== this.maxLayer + 1) {
         this.layerVisibility = new Array(this.maxLayer + 1).fill(true);
      }

      const xs = points.map(p => p.x); const ys = points.map(p => p.y); 
      const hs = points.filter(p => p.head !== null && p.head !== undefined).map(p => p.head);
      let minH = 0, maxH = 1;
      if (hs.length > 0) {
          minH = Math.min(...hs); maxH = Math.max(...hs);
          this.minHead = minH; this.maxHead = maxH;
      } else {
          this.minHead = null; this.maxHead = null;
      }

      const minX = Math.min(...xs), maxX = Math.max(...xs);
      const minY = Math.min(...ys), maxY = Math.max(...ys);
      
      this.cx = (minX + maxX) / 2; this.cy = (minY + maxY) / 2;
      
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
      const material = new THREE.MeshLambertMaterial({ color: 0xffffff, transparent: this.opacity < 1.0, opacity: this.opacity });
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
            
            dummy.position.set(p.x - this.cx, centerZ * currentZScale, -(p.y - this.cy));
            dummy.scale.set(1, thick * currentZScale, 1);
            dummy.updateMatrix();
            mesh.setMatrixAt(i, dummy.matrix);
            
            if (p.head !== null && p.head !== undefined && hs.length > 0) {
               let t = 0.5;
               if (maxH !== minH) t = (p.head - minH) / (maxH - minH);
               color.setHSL(0.66 * t, 0.8, 0.5); 
            } else {
               color.setHex(LAYER_COLORS[layerIdx % LAYER_COLORS.length]); 
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

drawBoreholes(boreholes) {
      if (!this.scene) return;
      this.currentBoreholes = boreholes;

      if (this.boreholeGroup) {
        this.scene.remove(this.boreholeGroup);
      }
      this.boreholeGroup = new THREE.Group();

      if (!this.points || this.points.length === 0) {
         if (boreholes && boreholes.length > 0) {
             let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
             boreholes.forEach(bh => {
                 if (bh.x < minX) minX = bh.x;
                 if (bh.x > maxX) maxX = bh.x;
                 if (bh.y < minY) minY = bh.y;
                 if (bh.y > maxY) maxY = bh.y;
             });
             this.cx = (minX + maxX) / 2;
             this.cy = (minY + maxY) / 2;

             let maxSpan = Math.max(maxX - minX, maxY - minY);
             this.currentCellSize = (maxSpan / 20) || 50;

             if (this.controls && this.camera) {
                 this.controls.target.set(0, 0, 0); 
                 this.camera.position.set(maxSpan * 0.8, maxSpan * 0.8, maxSpan * 0.8);
                 this.controls.update();
             }
         }
      }

      const radius = (this.currentCellSize || 50) * 0.15; 
      const radialSegments = 32; 
      
      // ⭐ 核心优化：只创建一个纯粹的水平“圆环边框”，抛弃会画竖线的 EdgesGeometry
      const circleGeo = new THREE.CircleGeometry(radius, radialSegments);
      const edgeGeo = new THREE.EdgesGeometry(circleGeo);
      edgeGeo.rotateX(Math.PI / 2); // 将圆环放平 (平行于 XZ 面)
      const lineMat = new THREE.LineBasicMaterial({ color: 0x333333, linewidth: 1 });

      boreholes.forEach(bh => {
        bh.layers.forEach((layer) => {
          const height = layer.top - layer.bottom;
          if (height <= 0.01) return; 

          // 依然保留 0.99 的高度收缩以防止相邻面的缝隙干扰
          const displayHeight = height * this.zScale * 0.99;
          const geo = new THREE.CylinderGeometry(radius, radius, displayHeight, radialSegments);
          
          const colorIndex = layer.layer_idx !== undefined ? layer.layer_idx : (layer.layer_id - 1);
          const mat = new THREE.MeshLambertMaterial({ 
            color: LAYER_COLORS[colorIndex % LAYER_COLORS.length], 
            transparent: false,
            opacity: 1.0,
            polygonOffset: true,
            polygonOffsetFactor: 1, 
            polygonOffsetUnits: 1
          });
          
          const mesh = new THREE.Mesh(geo, mat);
          mesh.userData = { type: 'borehole', name: bh.name, layer_id: layer.layer_id };

          // ⭐ 仅把圆环添加到圆柱的顶部和底部
          const topRing = new THREE.LineSegments(edgeGeo, lineMat);
          topRing.position.y = displayHeight / 2;
          mesh.add(topRing);

          const bottomRing = new THREE.LineSegments(edgeGeo, lineMat);
          bottomRing.position.y = -displayHeight / 2;
          mesh.add(bottomRing);

          const centerZ = layer.bottom + height / 2;
          mesh.position.set(bh.x - this.cx, centerZ * this.zScale, -(bh.y - this.cy)); 
          
          this.boreholeGroup.add(mesh);
        });
      });
      
      this.scene.add(this.boreholeGroup);
      if (this.renderer) this.renderer.render(this.scene, this.camera);
    },

    drawPathLines(pathData, cx, cy, zScale) {
      this.pathLines.forEach(line => this.scene.remove(line));
      this.pathLines = [];
      if (!pathData) return;

      pathData.forEach(path => {
        const points = path.map(pt => new THREE.Vector3(
          pt.x - cx, pt.z * zScale, -(pt.y - cy)
        ));
        const geometry = new THREE.BufferGeometry().setFromPoints(points);
        const material = new THREE.LineBasicMaterial({ color: 0xff0000, linewidth: 2 });
        const line = new THREE.Line(geometry, material);
        this.scene.add(line);
        this.pathLines.push(line);
      });
    },

    clearArrows() {
      this.flowArrows.forEach(arrow => {
        this.scene.remove(arrow);
        if (arrow.line) { if (arrow.line.geometry) arrow.line.geometry.dispose(); if (arrow.line.material) arrow.line.material.dispose(); }
        if (arrow.cone) { if (arrow.cone.geometry) arrow.cone.geometry.dispose(); if (arrow.cone.material) arrow.cone.material.dispose(); }
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
      const step = this.flowStep; 

      this.points.forEach(p => {
        if (!p.flows) return;
        if (p.row % step !== 0 || p.col % step !== 0) return;

        const vx = p.flows.right; const vy = p.flows.top * this.zScale; const vz = -p.flows.back;
        const dir = new THREE.Vector3(vx, vy, vz);
        if (dir.lengthSq() < 1e-12) return;
        dir.normalize();

        const centerZ = (p.top + p.bottom) / 2;
        const origin = new THREE.Vector3(p.x - this.cx, centerZ * this.zScale, -(p.y - this.cy));

        const arrow = new THREE.ArrowHelper(dir, origin, arrowLen, arrowColor, headLen, headWidth);
        arrow.userData = { layerIndex: p.layer };
        this.scene.add(arrow);
        this.flowArrows.push(arrow);
      });

      this.updateVisibility(); // 确保新画的箭头符合当前的隐藏状态
    },

setupClickHandler() {
      const container = this.$refs.container;
      this.clickHandler = (event) => {
        const rect = container.getBoundingClientRect();
        this.mouse.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
        this.mouse.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;

        this.raycaster.setFromCamera(this.mouse, this.camera);
        
        let clickTargets = this.meshes.filter(m => m.visible);
        if (this.boreholeGroup && this.boreholeGroup.children.length > 0) {
           clickTargets = clickTargets.concat(this.boreholeGroup.children);
        }

        if (clickTargets.length === 0) return;

        const intersects = this.raycaster.intersectObjects(clickTargets, true);
        
        if (intersects.length > 0) {
           const hit = intersects[0];
           
           let hitObj = hit.object;
           // 如果点到了钻孔的黑色边线，向上找它的父级（圆柱体）
           if (hitObj.type === 'LineSegments') {
               hitObj = hitObj.parent;
           }
           
           if (hitObj.userData && hitObj.userData.type === 'borehole') {
              // 1. 点击到了钻孔实体
              const bhName = hitObj.userData.name;
              if (this.selectedBorehole && this.selectedBorehole.name === bhName && this.selectedBorehole.layerId === hitObj.userData.layer_id) {
                  this.selectedBorehole = null; 
              } else {
                  this.selectedBorehole = { name: bhName, layerId: hitObj.userData.layer_id };
                  this.popupStyle = { left: (event.clientX) + 'px', top: (event.clientY - 60) + 'px' };
              }
              this.selectedCell = null; 
           } else {
               // 2. ⭐ 点击到了网格 (恢复六向水量弹窗)
               const lIdx = hitObj.userData.layerIndex;
               // 注意这里：恢复使用 hit.instanceId 获取网格索引
               const cellData = this.cellDataMap[`${lIdx}_${hit.instanceId}`];
               if (cellData) { 
                   this.selectedCell = cellData; 
               }
               this.selectedBorehole = null; 
           }
        } else {
           this.selectedCell = null;
           this.selectedBorehole = null;
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

/* 仅保留无法抽离的局部悬浮样式 */
.borehole-tooltip {
  position: fixed; 
  background: rgba(255, 255, 255, 0.98);
  padding: 10px 15px;
  border-radius: 6px;
  border: 1px solid #ebeef5;
  box-shadow: 0 4px 16px rgba(0,0,0,0.15);
  pointer-events: none; 
  z-index: 100;
  font-size: 13px;
  color: #333;
  transform: translate(-50%, -100%); 
  transition: top 0.1s, left 0.1s;
}
.tooltip-title {
  font-weight: bold;
  font-size: 14px;
  margin-bottom: 6px;
  padding-bottom: 4px;
  border-bottom: 1px solid #eee;
  color: #303133;
}
</style>