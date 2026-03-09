<template>
  <div class="attribute-manager">
    <div class="header">
      <h3>网格属性管理 ({{ totalCount }})</h3>
      <el-button 
        v-if="totalCount > 0" 
        type="text" 
        size="mini" 
        class="clear-btn"
        @click="$emit('clear-all')"
      >清空全部</el-button>
    </div>
    
    <div v-if="totalCount === 0" class="empty-tip">
      暂无已配置的网格，请在地图上点击设置
    </div>

    <el-table
      v-else
      :data="combinedList"
      style="width: 100%"
      size="mini"
      height="250"
      border
      stripe
    >
      <el-table-column label="坐标" width="90">
        <template slot-scope="scope">
          <span style="font-weight:bold; color:#606266">
            R{{ scope.row.row }}, C{{ scope.row.col }}
          </span>
        </template>
      </el-table-column>

      <el-table-column label="类型" width="110">
        <template slot-scope="scope">
          <el-select 
            v-model="scope.row.type" 
            size="mini" 
            @change="(val) => onTypeChange(val, scope.row)"
          >
            <el-option label="水井" value="well"></el-option>
            <el-option label="变K" value="k_cell"></el-option>
          </el-select>
        </template>
      </el-table-column>

      <el-table-column label="参数值">
        <template slot-scope="scope">
          <div v-if="scope.row.type === 'well'">
            <el-input-number 
              v-model="scope.row.dataRef.rate" 
              :step="100" 
              size="mini" 
              style="width: 100%"
              controls-position="right"
              placeholder="抽水率"
            ></el-input-number>
          </div>
          <div v-else>
            <el-input-number 
              v-model="scope.row.dataRef.k_val" 
              :step="0.1" 
              :min="0.0001"
              size="mini" 
              style="width: 100%"
              controls-position="right"
              placeholder="渗透系数"
            ></el-input-number>
          </div>
        </template>
      </el-table-column>

      <el-table-column label="" width="55" align="center">
        <template slot-scope="scope">
          <el-button 
            type="danger" 
            icon="el-icon-delete" 
            circle 
            size="mini" 
            plain
            @click="onDelete(scope.row)"
          ></el-button>
        </template>
      </el-table-column>
    </el-table>
  </div>
</template>

<script>
export default {
  name: 'AttributeManager',
  props: {
    wells: { type: Array, default: () => [] },
    kCells: { type: Array, default: () => [] }
  },
  computed: {
    totalCount() {
      return this.wells.length + this.kCells.length;
    },
    combinedList() {
      const list = [];
      // 收集水井
      this.wells.forEach((w, index) => {
        list.push({
          id: `w-${w.row}-${w.col}`,
          row: w.row, col: w.col, type: 'well', dataRef: w
        });
      });
      // 收集K网格
      this.kCells.forEach((k, index) => {
        list.push({
          id: `k-${k.row}-${k.col}`,
          row: k.row, col: k.col, type: 'k_cell', dataRef: k
        });
      });
      // 按行列排序，方便查看
      return list.sort((a, b) => (a.row - b.row) || (a.col - b.col));
    }
  },
  methods: {
    onDelete(row) {
      this.$emit('delete-attribute', { 
        type: row.type, row: row.row, col: row.col 
      });
    },
    onTypeChange(newType, row) {
      this.$emit('type-change', {
        row: row.row, col: row.col, newType: newType
      });
    }
  }
};
</script>

<style scoped>
.attribute-manager {
  background: #fff; padding: 10px; border-radius: 4px; border: 1px solid #ebeef5; margin-bottom: 10px;
}
.header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 5px; }
h3 { margin: 0; font-size: 14px; color: #303133; }
.empty-tip { font-size: 12px; color: #999; text-align: center; padding: 20px 0; }
.clear-btn { color: #F56C6C; padding: 0; }
</style>
<style>
.el-table .cell {
width: 120px;
}
</style>