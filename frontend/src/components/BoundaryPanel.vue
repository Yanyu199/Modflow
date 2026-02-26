<template>
  <div class="boundary-panel">
    <h3>边界条件设置 </h3>
    
    <div v-if="selectedIndex !== null" class="setting-box">
      <div class="segment-info">
        <span class="highlight">当前选中段 #{{ selectedIndex }}</span>
      </div>
      
      <el-form size="mini" label-width="90px">
        <el-form-item label="边界类型">
          <el-select v-model="form.type" placeholder="请选择" @change="onTypeChange">
            <el-option label="定水头 (CHD)" value="CHD"></el-option>
            <el-option label="河流 (RIV)" value="RIV"></el-option>
            <el-option label="排水沟 (DRN)" value="DRN"></el-option>
            <el-option label="通用水头 (GHB)" value="GHB"></el-option>
          </el-select>
        </el-form-item>

        <el-divider></el-divider>

        <div v-if="form.type === 'CHD'">
          <el-row :gutter="5">
            <el-col :span="12">
              <el-form-item label="起点水头">
                <el-input-number v-model="form.head_start" :step="0.1" :controls="false" style="width:100%"></el-input-number>
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item label="终点水头">
                <el-input-number v-model="form.head_end" :step="0.1" :controls="false" style="width:100%"></el-input-number>
              </el-form-item>
            </el-col>
          </el-row>
        </div>

        <div v-if="form.type === 'RIV'">
          <div class="param-group">
            <span class="group-label">河水位 (Stage)</span>
            <el-row :gutter="5">
              <el-col :span="12"><el-input-number v-model="form.stage_start" placeholder="起点" :controls="false" style="width:100%"></el-input-number></el-col>
              <el-col :span="12"><el-input-number v-model="form.stage_end" placeholder="终点" :controls="false" style="width:100%"></el-input-number></el-col>
            </el-row>
          </div>
          <div class="param-group">
            <span class="group-label">传导系数 (Cond)</span>
            <el-row :gutter="5">
              <el-col :span="12"><el-input-number v-model="form.cond_start" placeholder="起点" :controls="false" style="width:100%"></el-input-number></el-col>
              <el-col :span="12"><el-input-number v-model="form.cond_end" placeholder="终点" :controls="false" style="width:100%"></el-input-number></el-col>
            </el-row>
          </div>
          <div class="param-group">
            <span class="group-label">河底标高 (Rbot)</span>
            <el-row :gutter="5">
              <el-col :span="12"><el-input-number v-model="form.rbot_start" placeholder="起点" :controls="false" style="width:100%"></el-input-number></el-col>
              <el-col :span="12"><el-input-number v-model="form.rbot_end" placeholder="终点" :controls="false" style="width:100%"></el-input-number></el-col>
            </el-row>
          </div>
        </div>

        <div v-if="form.type === 'DRN'">
          <div class="param-group">
            <span class="group-label">排水高程 (Elev)</span>
            <el-row :gutter="5">
              <el-col :span="12"><el-input-number v-model="form.elev_start" :controls="false" style="width:100%"></el-input-number></el-col>
              <el-col :span="12"><el-input-number v-model="form.elev_end" :controls="false" style="width:100%"></el-input-number></el-col>
            </el-row>
          </div>
          <div class="param-group">
            <span class="group-label">传导系数 (Cond)</span>
            <el-row :gutter="5">
              <el-col :span="12"><el-input-number v-model="form.cond_start" :controls="false" style="width:100%"></el-input-number></el-col>
              <el-col :span="12"><el-input-number v-model="form.cond_end" :controls="false" style="width:100%"></el-input-number></el-col>
            </el-row>
          </div>
        </div>

        <div v-if="form.type === 'GHB'">
          <div class="param-group">
            <span class="group-label">边界水头 (Head)</span>
            <el-row :gutter="5">
              <el-col :span="12"><el-input-number v-model="form.bhead_start" :controls="false" style="width:100%"></el-input-number></el-col>
              <el-col :span="12"><el-input-number v-model="form.bhead_end" :controls="false" style="width:100%"></el-input-number></el-col>
            </el-row>
          </div>
          <div class="param-group">
            <span class="group-label">传导系数 (Cond)</span>
            <el-row :gutter="5">
              <el-col :span="12"><el-input-number v-model="form.cond_start" :controls="false" style="width:100%"></el-input-number></el-col>
              <el-col :span="12"><el-input-number v-model="form.cond_end" :controls="false" style="width:100%"></el-input-number></el-col>
            </el-row>
          </div>
        </div>

        <el-button type="primary" size="small" @click="saveSetting" style="width: 100%; margin-top:10px;">
          保存配置
        </el-button>
        <el-button type="text" size="small" @click="clearSetting" style="color: #F56C6C; width: 100%;">
          清除配置
        </el-button>
      </el-form>
    </div>

    <div v-else class="empty-tip">
      <i class="el-icon-edit"></i><br>
      请点击地图上的边界线段
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
      // 默认表单数据结构
      form: this.getDefaultForm()
    };
  },
  watch: {
    selectedIndex(val) {
      if (val !== null && this.configuredData[val]) {
        // 回显数据
        this.form = JSON.parse(JSON.stringify(this.configuredData[val]));
      } else {
        // 重置表单
        this.form = this.getDefaultForm();
      }
    }
  },
  methods: {
    getDefaultForm() {
      return {
        type: 'CHD',
        // CHD params
        head_start: 10, head_end: 10,
        // RIV params
        stage_start: 10, stage_end: 10,
        cond_start: 100, cond_end: 100,
        rbot_start: 5, rbot_end: 5,
        // DRN params
        elev_start: 8, elev_end: 8,
        // GHB params
        bhead_start: 12, bhead_end: 12
      };
    },
    onTypeChange() {
      // 切换类型时，保留部分通用数值体验可能更好，这里暂时不做特殊处理
    },
    saveSetting() {
      this.$emit('save', {
        id: this.selectedIndex,
        ...this.form
      });
      this.$message.success('已保存');
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
</style>