<template>
  <el-dialog 
    :visible.sync="internalVisible" 
    :title="content.title"
    width="600px"
    custom-class="detail-modal"
    append-to-body
    center
  >
    <div class="modal-body-content">
      <div v-for="(section, idx) in content.sections" :key="idx" class="section-block">
        <h4 class="section-header">
          <i class="el-icon-collection-tag"></i> {{ section.header }}
        </h4>
        <p v-if="section.text" class="section-text">{{ section.text }}</p>
        <ul v-if="section.points" class="section-list">
          <li v-for="(point, pIdx) in section.points" :key="pIdx">{{ point }}</li>
        </ul>
      </div>
    </div>
    <span slot="footer" class="dialog-footer">
      <el-button type="primary" @click="internalVisible = false" round>关 闭</el-button>
    </span>
  </el-dialog>
</template>

<script>
export default {
  name: 'DetailModal',
  props: { visible: Boolean, content: Object },
  computed: {
    internalVisible: {
      get() { return this.visible; },
      set(val) { this.$emit('update:visible', val); }
    }
  }
};
</script>

<style>
/* 针对弹窗的全局样式覆盖 */
.detail-modal .el-dialog__header { border-bottom: 1px solid #eee; padding: 20px; }
.detail-modal .el-dialog__title { font-weight: bold; color: #303133; }
.detail-modal .el-dialog__body { padding: 20px 30px; max-height: 60vh; overflow-y: auto; }
</style>
<style scoped>
.section-block { margin-bottom: 25px; }
.section-header { color: #303133; margin-bottom: 10px; font-size: 16px; border-left: 4px solid #409EFF; padding-left: 10px; }
.section-text { color: #606266; line-height: 1.6; font-size: 14px; white-space: pre-wrap; }
.section-list { padding-left: 20px; margin: 5px 0; }
.section-list li { color: #606266; line-height: 1.8; font-size: 14px; margin-bottom: 5px; }
</style>