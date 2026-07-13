<template>
  <div class="attribute-manager">
    <div class="header">
      <h3>Cell Attributes ({{ totalCount }})</h3>
      <el-button
        v-if="totalCount > 0"
        type="text"
        size="mini"
        class="clear-btn"
        @click="$emit('clear-all')"
      >Clear all</el-button>
    </div>

    <div v-if="totalCount === 0" class="empty-tip">
      No configured cells. Click a grid cell to set WEL, CHD, RIV, or K.
    </div>

    <el-table
      v-else
      :data="combinedList"
      style="width: 100%"
      size="mini"
      height="280"
      border
      stripe
    >
      <el-table-column label="Cell" width="110">
        <template slot-scope="scope">
          <span class="cell-label">L{{ scope.row.layer || 0 }} R{{ scope.row.row }} C{{ scope.row.col }}</span>
          <div v-if="scope.row.cell_id" class="cell-id-mini">{{ scope.row.cell_id }}</div>
        </template>
      </el-table-column>

      <el-table-column label="Type" width="96">
        <template slot-scope="scope">
          <el-select
            v-model="scope.row.type"
            size="mini"
            @change="val => onTypeChange(val, scope.row)"
          >
            <el-option label="WEL" value="well"></el-option>
            <el-option label="K" value="k_cell"></el-option>
            <el-option label="CHD" value="chd"></el-option>
            <el-option label="RIV" value="riv"></el-option>
          </el-select>
        </template>
      </el-table-column>

      <el-table-column label="Values">
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
            v-else-if="scope.row.type === 'chd'"
            v-model="scope.row.dataRef.head"
            :step="0.1"
            size="mini"
            style="width: 100%"
            controls-position="right"
            placeholder="Head"
          ></el-input-number>
          <div v-else class="riv-editor">
            <el-input-number
              v-model="scope.row.dataRef.stage"
              :step="0.1"
              size="mini"
              style="width: 100%"
              controls-position="right"
              placeholder="Stage (m)"
            ></el-input-number>
            <el-input-number
              v-model="scope.row.dataRef.conductance"
              :step="1"
              :min="0.000001"
              size="mini"
              style="width: 100%; margin-top: 4px;"
              controls-position="right"
              placeholder="Conductance (m2/day)"
            ></el-input-number>
            <el-input-number
              v-model="scope.row.dataRef.river_bottom"
              :step="0.1"
              size="mini"
              style="width: 100%; margin-top: 4px;"
              controls-position="right"
              placeholder="River bottom (m)"
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
    kCells: { type: Array, default: () => [] },
    chdCells: { type: Array, default: () => [] },
    rivCells: { type: Array, default: () => [] }
  },
  computed: {
    totalCount() {
      return this.wells.length + this.kCells.length + this.chdCells.length + this.rivCells.length;
    },
    combinedList() {
      const list = [];
      this.wells.forEach(w => {
        list.push(this.rowItem('well', `w-${w.layer || 0}-${w.row}-${w.col}`, w));
      });
      this.kCells.forEach(k => {
        list.push(this.rowItem('k_cell', `k-${k.layer || 0}-${k.row}-${k.col}`, k));
      });
      this.chdCells.forEach(c => {
        list.push(this.rowItem('chd', `chd-${c.layer || 0}-${c.row}-${c.col}`, c));
      });
      this.rivCells.forEach(r => {
        list.push(this.rowItem('riv', `riv-${r.layer || 0}-${r.row}-${r.col}`, r));
      });
      return list.sort((a, b) => (a.layer - b.layer) || (a.row - b.row) || (a.col - b.col));
    }
  },
  methods: {
    rowItem(type, id, ref) {
      return {
        id,
        row: ref.row,
        col: ref.col,
        column: ref.column,
        layer: ref.layer || 0,
        cell_id: ref.cell_id,
        grid_model_id: ref.grid_model_id,
        type,
        dataRef: ref
      };
    },
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
.riv-editor {
  min-width: 0;
}
</style>
