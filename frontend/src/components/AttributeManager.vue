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
      暂无已配置的网格，请在地图上点击设置 WEL、CHD 或 K。
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
      <el-table-column label="坐标" width="110">
        <template slot-scope="scope">
          <span class="cell-label">L{{ scope.row.layer || 0 }} R{{ scope.row.row }} C{{ scope.row.col }}</span>
          <div v-if="scope.row.cell_id" class="cell-id-mini">{{ scope.row.cell_id }}</div>
        </template>
      </el-table-column>

      <el-table-column label="类型" width="110">
        <template slot-scope="scope">
          <el-select
            v-model="scope.row.type"
            size="mini"
            @change="val => onTypeChange(val, scope.row)"
          >
            <el-option label="WEL" value="well"></el-option>
            <el-option label="K" value="k_cell"></el-option>
            <el-option label="CHD" value="chd"></el-option>
          </el-select>
        </template>
      </el-table-column>

      <el-table-column label="参数值">
        <template slot-scope="scope">
          <el-input-number
            v-if="scope.row.type === 'well'"
            v-model="scope.row.dataRef.rate"
            :step="100"
            size="mini"
            style="width: 100%"
            controls-position="right"
            placeholder="Q"
          ></el-input-number>
          <el-input-number
            v-else-if="scope.row.type === 'k_cell'"
            v-model="scope.row.dataRef.k_val"
            :step="0.1"
            :min="0.0001"
            size="mini"
            style="width: 100%"
            controls-position="right"
            placeholder="K"
          ></el-input-number>
          <el-input-number
            v-else
            v-model="scope.row.dataRef.head"
            :step="0.1"
            size="mini"
            style="width: 100%"
            controls-position="right"
            placeholder="Head"
          ></el-input-number>
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
    kCells: { type: Array, default: () => [] },
    chdCells: { type: Array, default: () => [] }
  },
  computed: {
    totalCount() {
      return this.wells.length + this.kCells.length + this.chdCells.length;
    },
    combinedList() {
      const list = [];
      this.wells.forEach(w => {
        list.push({
          id: `w-${w.layer || 0}-${w.row}-${w.col}`,
          row: w.row,
          col: w.col,
          column: w.column,
          layer: w.layer || 0,
          cell_id: w.cell_id,
          grid_model_id: w.grid_model_id,
          type: 'well',
          dataRef: w
        });
      });
      this.kCells.forEach(k => {
        list.push({
          id: `k-${k.layer || 0}-${k.row}-${k.col}`,
          row: k.row,
          col: k.col,
          column: k.column,
          layer: k.layer || 0,
          cell_id: k.cell_id,
          grid_model_id: k.grid_model_id,
          type: 'k_cell',
          dataRef: k
        });
      });
      this.chdCells.forEach(c => {
        list.push({
          id: `chd-${c.layer || 0}-${c.row}-${c.col}`,
          row: c.row,
          col: c.col,
          column: c.column,
          layer: c.layer || 0,
          cell_id: c.cell_id,
          grid_model_id: c.grid_model_id,
          type: 'chd',
          dataRef: c
        });
      });
      return list.sort((a, b) => (a.layer - b.layer) || (a.row - b.row) || (a.col - b.col));
    }
  },
  methods: {
    onDelete(row) {
      this.$emit('delete-attribute', {
        type: row.type,
        row: row.row,
        col: row.col,
        column: row.column,
        layer: row.layer,
        cell_id: row.cell_id,
        grid_model_id: row.grid_model_id
      });
    },
    onTypeChange(newType, row) {
      this.$emit('type-change', {
        row: row.row,
        col: row.col,
        column: row.column,
        layer: row.layer,
        cell_id: row.cell_id,
        grid_model_id: row.grid_model_id,
        type: row.type,
        newType
      });
    }
  }
};
</script>

<style scoped>
.attribute-manager {
  background: #fff;
  padding: 10px;
  border-radius: 4px;
  border: 1px solid #ebeef5;
  margin-bottom: 10px;
}
.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 5px;
}
h3 {
  margin: 0;
  font-size: 14px;
  color: #303133;
}
.empty-tip {
  font-size: 12px;
  color: #999;
  text-align: center;
  padding: 20px 0;
}
.clear-btn {
  color: #f56c6c;
  padding: 0;
}
.cell-label {
  font-weight: 700;
  color: #606266;
}
.cell-id-mini {
  color: #909399;
  font-size: 10px;
  line-height: 1.2;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
