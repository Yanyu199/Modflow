<template>
  <el-dialog
    :title="isEditing ? '工程设置' : '创建工程'"
    :visible="visible"
    width="520px"
    :show-close="isEditing"
    :close-on-click-modal="isEditing"
    :close-on-press-escape="isEditing"
    @close="$emit('update:visible', false)"
  >
    <el-alert
      title="项目 CRS 和单位会作为地质体、网格和水动力模型的统一上下文。当前版本不做自动单位转换。"
      type="info"
      show-icon
      :closable="false"
      class="mb-12"
    />

    <el-form label-position="top" size="small">
      <el-form-item label="项目名称">
        <el-input v-model="form.name" placeholder="例如：示范矿区地下水模型" />
      </el-form-item>

      <el-form-item label="项目描述">
        <el-input v-model="form.description" type="textarea" :rows="2" placeholder="可选" />
      </el-form-item>

      <el-row :gutter="12">
        <el-col :span="12">
          <el-form-item label="CRS Authority">
            <el-select v-model="form.crs.authority" style="width: 100%;">
              <el-option label="EPSG" value="EPSG" />
            </el-select>
          </el-form-item>
        </el-col>
        <el-col :span="12">
          <el-form-item label="EPSG Code">
            <el-input-number v-model="form.crs.code" :min="1" :step="1" controls-position="right" style="width: 100%;" />
          </el-form-item>
        </el-col>
      </el-row>

      <el-form-item label="坐标轴顺序">
        <el-radio-group v-model="form.crs.axis_order">
          <el-radio-button label="xy">XY</el-radio-button>
        </el-radio-group>
      </el-form-item>

      <el-row :gutter="12">
        <el-col :span="12">
          <el-form-item label="水平长度单位">
            <el-select v-model="form.units.horizontal_length" style="width: 100%;">
              <el-option label="m" value="m" />
            </el-select>
          </el-form-item>
        </el-col>
        <el-col :span="12">
          <el-form-item label="垂直长度单位">
            <el-select v-model="form.units.vertical_length" style="width: 100%;">
              <el-option label="m" value="m" />
            </el-select>
          </el-form-item>
        </el-col>
      </el-row>

      <el-row :gutter="12">
        <el-col :span="12">
          <el-form-item label="时间单位">
            <el-select v-model="form.units.time" style="width: 100%;">
              <el-option label="day" value="day" />
            </el-select>
          </el-form-item>
        </el-col>
        <el-col :span="12">
          <el-form-item label="流量单位">
            <el-select v-model="form.units.flow" style="width: 100%;">
              <el-option label="m3/day" value="m3/day" />
            </el-select>
          </el-form-item>
        </el-col>
      </el-row>

      <el-row :gutter="12">
        <el-col :span="12">
          <el-form-item label="模型类型">
            <el-select v-model="form.model_settings.model_type" style="width: 100%;">
              <el-option label="地下水流" value="groundwater_flow" />
            </el-select>
          </el-form-item>
        </el-col>
        <el-col :span="12">
          <el-form-item label="流态">
            <el-select v-model="form.model_settings.flow_regime" style="width: 100%;">
              <el-option label="稳定流" value="steady" />
            </el-select>
          </el-form-item>
        </el-col>
      </el-row>
    </el-form>

    <span slot="footer" class="dialog-footer">
      <el-button v-if="isEditing" size="small" @click="$emit('update:visible', false)">取消</el-button>
      <el-button type="primary" size="small" :loading="submitting" @click="submit">
        {{ isEditing ? '保存设置' : '创建项目' }}
      </el-button>
    </span>
  </el-dialog>
</template>

<script>
const defaultForm = () => ({
  name: '',
  description: '',
  crs: {
    authority: 'EPSG',
    code: 32650,
    wkt: null,
    axis_order: 'xy'
  },
  units: {
    horizontal_length: 'm',
    vertical_length: 'm',
    time: 'day',
    flow: 'm3/day'
  },
  model_settings: {
    model_type: 'groundwater_flow',
    flow_regime: 'steady'
  },
  references: {
    geology_model_id: null,
    flow_model_id: null
  },
  metadata: {}
});

export default {
  name: 'ProjectSettingsDialog',
  props: {
    visible: { type: Boolean, default: false },
    project: { type: Object, default: null },
    hasModelData: { type: Boolean, default: false },
    submitting: { type: Boolean, default: false }
  },
  data() {
    return {
      form: defaultForm()
    };
  },
  computed: {
    isEditing() {
      return Boolean(this.project);
    }
  },
  watch: {
    visible(value) {
      if (value) this.resetForm();
    },
    project: {
      deep: true,
      handler() {
        if (this.visible) this.resetForm();
      }
    }
  },
  methods: {
    resetForm() {
      const base = defaultForm();
      if (this.project) {
        this.form = {
          ...base,
          ...this.project,
          crs: { ...base.crs, ...(this.project.crs || {}) },
          units: { ...base.units, ...(this.project.units || {}) },
          model_settings: { ...base.model_settings, ...(this.project.model_settings || {}) },
          references: { ...base.references, ...(this.project.references || {}) },
          metadata: { ...(this.project.metadata || {}) }
        };
      } else {
        this.form = base;
      }
    },
    hasContextChanged(payload) {
      if (!this.project) return false;
      return JSON.stringify(payload.crs) !== JSON.stringify(this.project.crs)
        || JSON.stringify(payload.units) !== JSON.stringify(this.project.units);
    },
    async submit() {
      const payload = {
        name: this.form.name,
        description: this.form.description || '',
        crs: this.form.crs,
        units: this.form.units,
        model_settings: this.form.model_settings,
        references: this.form.references,
        metadata: this.form.metadata
      };
      if (!payload.name || !payload.name.trim()) {
        this.$message.warning('请输入项目名称');
        return;
      }
      if (this.isEditing && this.hasModelData && this.hasContextChanged(payload)) {
        try {
          await this.$confirm(
            '当前项目已有地质、网格或水动力数据。修改 CRS 或单位不会重新解释已有数值，可能导致现有数据失效。是否继续？',
            '确认修改工程上下文',
            { type: 'warning' }
          );
        } catch (e) {
          return;
        }
      }
      this.$emit('submit', payload);
    }
  }
};
</script>

<style scoped>
.mb-12 { margin-bottom: 12px; }
</style>
