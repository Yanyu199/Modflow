<template>
  <div class="boundary-panel">
    <h3>Line Boundary Settings</h3>

    <div v-if="selectedIndex !== null" class="setting-box">
      <div class="segment-info">
        <span class="highlight">Selected segment #{{ selectedIndex }}</span>
      </div>

      <el-alert
        title="RIV is now edited as explicit grid-cell records."
        description="Use the cell attribute editor to create RIV cells with stage, conductance, and river bottom. Line-to-cell river mapping is reserved for a later conceptual-model task."
        type="info"
        :closable="false"
        show-icon
        class="mb-8"
      ></el-alert>

      <el-form size="mini" label-width="90px">
        <el-form-item label="Type">
          <el-select v-model="form.type" placeholder="Select" @change="onTypeChange">
            <el-option label="CHD" value="CHD"></el-option>
            <el-option label="RIV uses cell editor" value="RIV" disabled></el-option>
            <el-option label="DRN (legacy)" value="DRN"></el-option>
            <el-option label="GHB (legacy)" value="GHB"></el-option>
          </el-select>
        </el-form-item>

        <el-divider></el-divider>

        <div v-if="form.type === 'CHD'">
          <el-row :gutter="5">
            <el-col :span="12">
              <el-form-item label="Start head">
                <el-input-number v-model="form.head_start" :step="0.1" :controls="false" style="width:100%"></el-input-number>
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item label="End head">
                <el-input-number v-model="form.head_end" :step="0.1" :controls="false" style="width:100%"></el-input-number>
              </el-form-item>
            </el-col>
          </el-row>
        </div>

        <div v-if="form.type === 'DRN'">
          <div class="param-group">
            <span class="group-label">Elevation</span>
            <el-row :gutter="5">
              <el-col :span="12"><el-input-number v-model="form.elev_start" :controls="false" style="width:100%"></el-input-number></el-col>
              <el-col :span="12"><el-input-number v-model="form.elev_end" :controls="false" style="width:100%"></el-input-number></el-col>
            </el-row>
          </div>
          <div class="param-group">
            <span class="group-label">Conductance</span>
            <el-row :gutter="5">
              <el-col :span="12"><el-input-number v-model="form.cond_start" :controls="false" style="width:100%"></el-input-number></el-col>
              <el-col :span="12"><el-input-number v-model="form.cond_end" :controls="false" style="width:100%"></el-input-number></el-col>
            </el-row>
          </div>
        </div>

        <div v-if="form.type === 'GHB'">
          <div class="param-group">
            <span class="group-label">Boundary head</span>
            <el-row :gutter="5">
              <el-col :span="12"><el-input-number v-model="form.bhead_start" :controls="false" style="width:100%"></el-input-number></el-col>
              <el-col :span="12"><el-input-number v-model="form.bhead_end" :controls="false" style="width:100%"></el-input-number></el-col>
            </el-row>
          </div>
          <div class="param-group">
            <span class="group-label">Conductance</span>
            <el-row :gutter="5">
              <el-col :span="12"><el-input-number v-model="form.cond_start" :controls="false" style="width:100%"></el-input-number></el-col>
              <el-col :span="12"><el-input-number v-model="form.cond_end" :controls="false" style="width:100%"></el-input-number></el-col>
            </el-row>
          </div>
        </div>

        <el-button type="primary" size="small" @click="saveSetting" style="width: 100%; margin-top:10px;">
          Save setting
        </el-button>
        <el-button type="text" size="small" @click="clearSetting" style="color: #F56C6C; width: 100%;">
          Clear setting
        </el-button>
      </el-form>
    </div>

    <div v-else class="empty-tip">
      <i class="el-icon-edit"></i><br>
      Click a boundary segment.
    </div>
  </div>
</template>

<script>
export default {
  props: {
    selectedIndex: Number,
    configuredData: Object
  },
  data() {
    return {
      form: this.getDefaultForm()
    };
  },
  watch: {
    selectedIndex(val) {
      if (val !== null && this.configuredData[val]) {
        this.form = JSON.parse(JSON.stringify(this.configuredData[val]));
        if (this.form.type === 'RIV') this.form = this.getDefaultForm();
      } else {
        this.form = this.getDefaultForm();
      }
    }
  },
  methods: {
    getDefaultForm() {
      return {
        type: 'CHD',
        head_start: 10,
        head_end: 10,
        cond_start: null,
        cond_end: null,
        rbot_start: null,
        rbot_end: null,
        elev_start: 8,
        elev_end: 8,
        bhead_start: 12,
        bhead_end: 12
      };
    },
    onTypeChange() {},
    saveSetting() {
      if (this.form.type === 'RIV') {
        this.$message.warning('RIV must be created from explicit grid cells.');
        return;
      }
      this.$emit('save', {
        id: this.selectedIndex,
        ...this.form
      });
      this.$message.success('Saved');
    },
    clearSetting() {
      this.$emit('remove', this.selectedIndex);
    }
  }
};
</script>

<style scoped>
.boundary-panel { background: #fff; padding: 15px; border-radius: 4px; border: 1px solid #EBEEF5; }
.highlight { color: #409EFF; font-weight: bold; font-size: 14px; }
.empty-tip { text-align: center; color: #909399; padding: 30px 0; }
.param-group { margin-bottom: 8px; background: #f9f9f9; padding: 5px; border-radius: 4px; }
.group-label { font-size: 12px; color: #606266; display: block; margin-bottom: 2px; }
.mb-8 { margin-bottom: 8px; }
</style>
