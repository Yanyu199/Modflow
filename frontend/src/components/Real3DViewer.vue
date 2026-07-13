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

    <div v-if="selectedBorehole" class="info-tooltip" :style="popupStyle">
      <div class="tooltip-title"><i class="el-icon-location"></i> 钻孔信息</div>
      <div><strong>名称:</strong> <span style="color: #409EFF">{{ selectedBorehole.name }}</span></div>
      <div style="font-size: 12px; color: #666; margin-top: 4px;">分层 ID: {{ selectedBorehole.layerId }}</div>
    </div>

    <div v-if="selectedSurfaceData" class="info-tooltip" :style="surfacePopupStyle">
      <div class="tooltip-title"><i class="el-icon-cloudy-and-sunny"></i> 源汇项信息</div>
      <div><strong>类型:</strong> {{ selectedSurfaceData.type }}</div>
      <div><strong>数值:</strong> <span style="color: #F56C6C; font-weight:bold;">{{ selectedSurfaceData.val.toFixed(6) }}</span> m/d</div>
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
import axios from 'axios';

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
    layerMapping: { type: Object, default: () => ({}) },
    // 新增接收父组件传来的散点数据和开关
    rchData: { type: Array, default: () => [] },
    evtData: { type: Array, default: () => [] },
    showRchContour: { type: Boolean, default: false },
    showEvtContour: { type: Boolean, default: false },
    projectId: { type: String, default: null },
    gridModelId: { type: String, default: null }
  },
  data() {
    return {
      scene: null, camera: null, renderer: null, controls: null,
      meshes: [], boreholeGroup: null, flowArrows: [], pathLines: [],
      layerVisibility: [], maxLayer: 0,
      initialized: false, animationId: null, clickHandler: null,
      currentBoreholes: [], cellDataMap: {},
      cx: 0, cy: 0, currentCellSize: 50,
      
      zScale: 5, opacity: 0.6, showFlow: false, flowStep: 3, showLegend: true,
      minHead: null, maxHead: null,

      raycaster: new THREE.Raycaster(),
      mouse: new THREE.Vector2(),
      selectedCell: null,
      selectedBorehole: null,
      popupStyle: { top: '0px', left: '0px' },
      
      // 新增：用于显示源汇项浮窗
      selectedSurfaceData: null,
      surfacePopupStyle: { top: '0px', left: '0px' }
    };
  },
  watch: {
    points: {
      handler(newPoints) {
        if (!this.initialized) return;
        this.drawVoxels(newPoints);
        this.selectedCell = null;
        this.selectedBorehole = null;
        this.selectedSurfaceData = null;
      },
      deep: true
    },
    // 监听源汇项开关和数据的变化
    showRchContour() { this.updateSurfaceColors(); },
    showEvtContour() { this.updateSurfaceColors(); },
    rchData: { deep: true, handler() { if(this.showRchContour) this.updateSurfaceColors(); } },
    evtData: { deep: true, handler() { if(this.showEvtContour) this.updateSurfaceColors(); } }
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
      
      // 绘图结束后，如果是处于源汇项视图，立即刷新等值线颜色
      if (this.showRchContour || this.showEvtContour) {
        this.updateSurfaceColors();
      }
    },

    // 🌟 新增核心功能：在表层 (Layer 0) 进行空间插值与渲染
    updateSurfaceColors() {
      if (!this.scene) return;
      // 仅作用于顶层网格
      const layer0Mesh = this.meshes.find(m => m.userData.layerIndex === 0);
      if (!layer0Mesh) return;

      const color = new THREE.Color();

      // 如果两个开关都关闭，恢复原始网格水头颜色或默认颜色
      if (!this.showRchContour && !this.showEvtContour) {
         const hs = this.points.filter(p => p.head !== null && p.head !== undefined).map(p => p.head);
         const minH = hs.length > 0 ? Math.min(...hs) : null;
         const maxH = hs.length > 0 ? Math.max(...hs) : null;

         this.points.filter(p => p.layer === 0).forEach((p, i) => {
            if (p.head !== null && p.head !== undefined && hs.length > 0) {
               let t = 0.5;
               if (maxH !== minH) t = (p.head - minH) / (maxH - minH);
               color.setHSL(0.66 * t, 0.8, 0.5);
            } else {
               color.setHex(LAYER_COLORS[0]);
            }
            layer0Mesh.setColorAt(i, color);
         });
         layer0Mesh.instanceColor.needsUpdate = true;
         if (this.renderer) this.renderer.render(this.scene, this.camera);
         return;
      }

      // 获取当前激活的数据源
      const activeData = this.showRchContour ? this.rchData : this.evtData;
      if (!activeData || activeData.length === 0) return;

      // 计算极值，用于构建热力图渐变
      let minV = Infinity, maxV = -Infinity;
      activeData.forEach(d => {
         if(d.value < minV) minV = d.value;
         if(d.value > maxV) maxV = d.value;
      });

      this.points.filter(p => p.layer === 0).forEach((p, i) => {
         // 1. 最近邻插值 (Nearest Neighbor) 计算该网格的值
         let nearestVal = activeData[0].value;
         if (activeData.length > 1) {
            let minDist = Infinity;
            activeData.forEach(d => {
               let dist = Math.pow(p.x - d.x, 2) + Math.pow(p.y - d.y, 2);
               if (dist < minDist) { minDist = dist; nearestVal = d.value; }
            });
         }

         // 2. 将计算结果挂载到 cellDataMap，供点击事件读取
         const cellObj = this.cellDataMap[`0_${i}`];
         if (cellObj) {
            if (this.showRchContour) cellObj.rch_value = nearestVal;
            if (this.showEvtContour) cellObj.evt_value = nearestVal;
         }

         // 3. 热力图映射 (从蓝到红渐变)
         let t = 0.5;
         if (maxV !== minV) {
             t = (nearestVal - minV) / (maxV - minV);
         }
         // HSL 色相: 0.66 (蓝) 到 0.0 (红)
         color.setHSL((1 - t) * 0.66, 0.8, 0.5);
         layer0Mesh.setColorAt(i, color);
      });

      layer0Mesh.instanceColor.needsUpdate = true;
      if (this.renderer) this.renderer.render(this.scene, this.camera);
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
      
      const circleGeo = new THREE.CircleGeometry(radius, radialSegments);
      const edgeGeo = new THREE.EdgesGeometry(circleGeo);
      edgeGeo.rotateX(Math.PI / 2); 
      const lineMat = new THREE.LineBasicMaterial({ color: 0x333333, linewidth: 1 });

      boreholes.forEach(bh => {
        bh.layers.forEach((layer) => {
          const height = layer.top - layer.bottom;
          if (height <= 0.01) return; 

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
      
      const arrowLen = this.currentCellSize * 0.6; 
      const headLen = arrowLen * 0.35;
      const headWidth = headLen * 0.5;
      const arrowColor = 0x00008B; 
      const step = this.flowStep; 

      this.points.forEach(p => {
        if (!p.flows) return;
        if (p.row % step !== 0 || p.col % step !== 0) return;

        const qx = ( (p.flows.right || 0) - (p.flows.left || 0) ) / 2;
        const qy = ( (p.flows.back || 0) - (p.flows.front || 0) ) / 2;
        const qz = ( (p.flows.top || 0) - (p.flows.bottom || 0) ) / 2;
        const dx = this.currentCellSize; 
        const dy = this.currentCellSize; 
        const dz = Math.max(0.1, p.top - p.bottom); 

        const vx_real = qx / (dy * dz);
        const vy_real = qz / (dx * dy);  
        const vz_real = -qy / (dx * dz);
        
        const vx = vx_real;
        const vy = vy_real * this.zScale;
        const vz = vz_real;
        
        const dir = new THREE.Vector3(vx, vy, vz);
        if (dir.lengthSq() < 1e-15) return; 
        
        dir.normalize(); 

        const centerZ = (p.top + p.bottom) / 2;
        const cellCenter = new THREE.Vector3(p.x - this.cx, centerZ * this.zScale, -(p.y - this.cy));
        const origin = cellCenter.clone().addScaledVector(dir, -arrowLen * 0.5);

        const arrow = new THREE.ArrowHelper(dir, origin, arrowLen, arrowColor, headLen, headWidth);
        arrow.userData = { layerIndex: p.layer };
        
        this.scene.add(arrow);
        this.flowArrows.push(arrow);
      });

      this.updateVisibility(); 
    },

    async selectGridCell(cellData) {
      if (!cellData) return;
      if (!this.projectId || !this.gridModelId || !cellData.cell_id) {
        this.selectedCell = cellData;
        return;
      }
      try {
        const response = await axios.get(
          `http://localhost:5000/projects/${this.projectId}/grids/${this.gridModelId}/cells/${encodeURIComponent(cellData.cell_id)}`
        );
        const detail = response.data.cell || {};
        this.selectedCell = {
          ...detail,
          head: cellData.head !== undefined ? cellData.head : detail.head,
          flows: cellData.flows || detail.flows,
          rch_value: cellData.rch_value,
          evt_value: cellData.evt_value
        };
      } catch (err) {
        this.selectedCell = cellData;
      }
    },

    setupClickHandler() {
      const container = this.$refs.container;
      this.clickHandler = async (event) => {
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
           if (hitObj.type === 'LineSegments') hitObj = hitObj.parent;
           
           if (hitObj.userData && hitObj.userData.type === 'borehole') {
              // 点击到了钻孔
              const bhName = hitObj.userData.name;
              if (this.selectedBorehole && this.selectedBorehole.name === bhName && this.selectedBorehole.layerId === hitObj.userData.layer_id) {
                  this.selectedBorehole = null; 
              } else {
                  this.selectedBorehole = { name: bhName, layerId: hitObj.userData.layer_id };
                  this.popupStyle = { left: (event.clientX) + 'px', top: (event.clientY - 60) + 'px' };
              }
              this.selectedCell = null; 
              this.selectedSurfaceData = null;
           } else {
               // ⭐ 点击到了网格
               const lIdx = hitObj.userData.layerIndex;
               const cellData = this.cellDataMap[`${lIdx}_${hit.instanceId}`];
               
               if (cellData) { 
                   // 判断：如果是源汇项查看模式，且点中了表层 (Layer 0)
                   if ((this.showRchContour || this.showEvtContour) && lIdx === 0) {
                       this.selectedSurfaceData = {
                           val: this.showRchContour ? cellData.rch_value : cellData.evt_value,
                           type: this.showRchContour ? '入渗率' : '蒸发率'
                       };
                       this.surfacePopupStyle = { left: event.clientX + 'px', top: (event.clientY - 60) + 'px' };
                       this.selectedCell = null; // 隐藏默认的大水量面板
                   } else {
                       // 正常模式，弹出六面水量框
                       await this.selectGridCell(cellData);
                       this.selectedSurfaceData = null;
                   }
               }
               this.selectedBorehole = null; 
           }
        } else {
           this.selectedCell = null;
           this.selectedBorehole = null;
           this.selectedSurfaceData = null;
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

/* 悬浮信息框通用样式 (给钻孔和源汇项复用) */
.info-tooltip {
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
