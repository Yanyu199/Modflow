<!-- src/components/ViewerControls.vue -->
<template>
  <div class="viewer-controls">
    <el-button size="mini" @click="resetView">🔄 重置视角</el-button>
    <el-button size="mini" @click="topView">⬆️ 俯视</el-button>
    <el-button size="mini" @click="frontView">👁️ 正视</el-button>
    <el-button size="mini" @click="togglePan" :type="panEnabled ? 'primary' : ''">
      {{ panEnabled ? '✅ 平移开启' : '🔲 平移关闭' }}
    </el-button>
    <el-button size="mini" @click="toggleRotate" :type="autoRotate ? 'primary' : ''">
      {{ autoRotate ? '⏸️ 自动旋转' : '▶️ 自动旋转' }}
    </el-button>
  </div>
</template>

<script>
export default {
  name: 'ViewerControls',
  props: {
    camera: {
      type: Object,
      required: true
    },
    controls: {
      type: Object,
      required: true
    }
  },
  data() {
    return {
      panEnabled: true,
      autoRotate: false
    };
  },
  watch: {
    autoRotate(newVal) {
      this.controls.autoRotate = newVal;
      if (newVal) {
        this.controls.autoRotateSpeed = 1.0;
      }
    }
  },
  methods: {
    resetView() {
      // 恢复初始视角
      this.camera.position.set(500, 1000, 500);
      this.camera.lookAt(500, 500, 0);
      this.controls.reset();
    },
    topView() {
      this.camera.position.set(500, 1500, 500);
      this.camera.lookAt(500, 500, 0);
      this.controls.update();
    },
    frontView() {
      this.camera.position.set(500, 500, 1200);
      this.camera.lookAt(500, 500, 0);
      this.controls.update();
    },
    togglePan() {
      this.panEnabled = !this.panEnabled;
      this.controls.enablePan = this.panEnabled;
    },
    toggleRotate() {
      this.autoRotate = !this.autoRotate;
    }
  }
};
</script>

<style scoped>
.viewer-controls {
  position: absolute;
  top: 10px;
  right: 10px;
  z-index: 10;
  background: rgba(255, 255, 255, 0.85);
  padding: 8px;
  border-radius: 6px;
  box-shadow: 0 2px 6px rgba(0,0,0,0.2);
}
.viewer-controls .el-button {
  margin: 2px;
}
</style>