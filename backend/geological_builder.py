# backend/geological_builder.py
import pandas as pd
import numpy as np
from scipy.interpolate import Rbf
import pyvista as pv


class GeologicalModeler:
    def __init__(self, csv_file_stream):
        # 接收从 Flask 传来的文件流
        self.df = pd.read_csv(csv_file_stream)
        self.boreholes = {}
        self.layers = []
        self.surfaces = {}  # 存储 {layer_id: {'Top': ndarray, 'Bottom': ndarray}}

    def get_frontend_data(self):
        """将钻孔数据结构化，提取给前端用于 Three.js 三维展示"""
        # 建立网格索引(0起步) 到 钻孔分层ID(1起步) 的映射关系
        layer_mapping = {i: int(layer_id) for i, layer_id in enumerate(self.layers)}

        bh_list = []
        for name in self.boreholes.keys():
            bh_data = self.df[self.df['钻孔名称'] == name]
            layers = []
            for _, row in bh_data.iterrows():
                l_id = int(row['分层ID'])
                layers.append({
                    "layer_id": l_id,
                    "layer_idx": self.layers.index(l_id),  # ⭐ 生成绝对对应的 0, 1, 2 索引给前端控制颜色
                    "top": float(row['Top']),
                    "bottom": float(row['Bottom']),
                    "lithology": str(row['含水层岩性'])
                })
            bh_list.append({
                "name": str(name),
                "x": float(self.boreholes[name]['X']),
                "y": float(self.boreholes[name]['Y']),
                "layers": layers
            })

        return {
            "layers_count": len(self.layers),
            "layer_mapping": layer_mapping,
            "boreholes": bh_list
        }

    def preprocess_data(self):
        """数据预处理：严格按照 分层ID 从小到大作为自上而下的地层顺序，并推算真实高程"""

        # 1. 提取各个钻孔的基础坐标和孔口标高(Z)
        bh_df = self.df[['钻孔名称', 'X', 'Y', 'Z']].drop_duplicates(subset=['钻孔名称']).set_index('钻孔名称')
        for idx, row in bh_df.iterrows():
            self.boreholes[idx] = {'X': row['X'], 'Y': row['Y'], 'Z': row.get('Z', 0)}

        # 2. ⭐ 核心修复：正确推算每一层的 Top 和 Bottom (自上而下累计)
        if 'Top' not in self.df.columns or 'Bottom' not in self.df.columns:
            # 必须按孔名和分层ID(1,2,3...)排序，保证自上而下计算
            self.df = self.df.sort_values(by=['钻孔名称', '分层ID'])

            # 使用 Pandas 快速计算每个钻孔内部的“累计厚度”
            self.df['cum_thick'] = self.df.groupby('钻孔名称')['分层厚度'].cumsum()

            # 这一层的底板 = 孔口标高 - 累计到这一层的总厚度
            self.df['Bottom'] = self.df['Z'] - self.df['cum_thick']

            # 这一层的顶板 = 底板 + 自己的厚度
            self.df['Top'] = self.df['Bottom'] + self.df['分层厚度']

        # 3. 按照分层ID排列地层层序
        self.layers = sorted(self.df['分层ID'].unique())
        print(f"严格按照分层ID排列的真实地层层序 (自上而下): {self.layers}")

    def _get_virtual_elevation(self, bh_name, target_layer_id):
        """【尖灭处理核心算法】获取缺失地层在指定钻孔中的虚拟高程点"""
        bh_data = self.df[self.df['钻孔名称'] == bh_name].sort_values('分层ID')

        # 寻找该钻孔中位于目标层之上、之下最近的层
        upper_layers = bh_data[bh_data['分层ID'] < target_layer_id]
        lower_layers = bh_data[bh_data['分层ID'] > target_layer_id]

        if not upper_layers.empty:
            # 向上寻找，依附于上覆地层的底板
            return upper_layers.iloc[-1]['Bottom']
        elif not lower_layers.empty:
            # 向下寻找，依附于下伏地层的顶板
            return lower_layers.iloc[0]['Top']
        else:
            return 0

    def interpolate_surfaces(self, grid_x, grid_y):
        """
        进行RBF曲面插值并处理尖灭，采用极限裁切和严苛的自上而下拓扑推平算法
        """
        import numpy as np
        from scipy.interpolate import Rbf

        # 1. 独立插值所有顶底板
        for layer_id in self.layers:
            layer_data = self.df[self.df['分层ID'] == layer_id]
            present_bhs = layer_data['钻孔名称'].tolist()

            pts_x, pts_y, pts_top, pts_bot = [], [], [], []

            for _, row in layer_data.iterrows():
                pts_x.append(row['X'])
                pts_y.append(row['Y'])
                pts_top.append(row['Top'])
                pts_bot.append(row['Bottom'])

            for bh_name, bh_coords in self.boreholes.items():
                if bh_name not in present_bhs:
                    virtual_z = self._get_virtual_elevation(bh_name, layer_id)
                    pts_x.append(bh_coords['X'])
                    pts_y.append(bh_coords['Y'])
                    pts_top.append(virtual_z)
                    pts_bot.append(virtual_z)

            # 恢复使用最稳定、不易抛出数学错误的 thin_plate
            rbf_top = Rbf(pts_x, pts_y, pts_top, function='thin_plate')
            rbf_bot = Rbf(pts_x, pts_y, pts_bot, function='thin_plate')

            grid_top = rbf_top(grid_x, grid_y)
            grid_bot = rbf_bot(grid_x, grid_y)

            # ⭐ 防弹级修复 1：获取物理极值，强制裁切 (Clipping)
            # 强行把所有扭曲飞升的网格面，拍回到钻孔的合理标高范围内！
            max_z = np.nanmax(pts_top) + 5.0  # 允许最高比孔口高5米
            min_z = np.nanmin(pts_bot) - 5.0  # 允许最低比孔底深5米

            grid_top = np.clip(grid_top, min_z, max_z)
            grid_bot = np.clip(grid_bot, min_z, max_z)

            # ⭐ 防弹级修复 2：清洗剧毒数据 (NaN)，避免 MF6 引擎崩溃
            mean_top = np.nanmean(pts_top) if len(pts_top) > 0 else 0
            mean_bot = np.nanmean(pts_bot) if len(pts_bot) > 0 else -10
            grid_top = np.nan_to_num(grid_top, nan=mean_top)
            grid_bot = np.nan_to_num(grid_bot, nan=mean_bot)

            self.surfaces[layer_id] = {'Top': grid_top, 'Bottom': grid_bot}

        # 2. ⭐ 自上而下“压路机”推平算法
        if not self.layers:
            return self.surfaces

        # 先锁定最顶层（地表）
        first_layer_id = self.layers[0]
        current_top = self.surfaces[first_layer_id]['Top']
        # 强制第一层的底板不能高于顶板 (至少留 0.1m)
        current_bot = np.minimum(self.surfaces[first_layer_id]['Bottom'], current_top - 0.1)

        self.surfaces[first_layer_id]['Top'] = current_top
        self.surfaces[first_layer_id]['Bottom'] = current_bot

        # 从第二层开始，严格按照上一层的底板往下夯实
        for i in range(1, len(self.layers)):
            layer_id = self.layers[i]

            # 规则A：当前层的顶板，必须【绝对等于】上一层的底板 (无缝拼接)
            self.surfaces[layer_id]['Top'] = current_bot.copy()

            # 规则B：当前层的底板，必须低于自己的顶板至少 0.1m
            raw_bot = self.surfaces[layer_id]['Bottom']
            new_bot = np.minimum(raw_bot, current_bot - 0.1)

            self.surfaces[layer_id]['Bottom'] = new_bot

            # 把当前的底板作为基准，继续压下一层
            current_bot = new_bot

        return self.surfaces

    def build_3d_volume(self, grid_x, grid_y):
        """构建 PyVista 三维网格用于独立可视化或导出"""
        plotter = pv.Plotter()
        colors = ['#8dd3c7', '#ffffb3', '#bebada', '#fb8072', '#80b1d3']
        nx, ny = grid_x.shape

        for idx, layer_id in enumerate(self.layers):
            top_grid = self.surfaces[layer_id]['Top']
            bot_grid = self.surfaces[layer_id]['Bottom']

            # 将上下表面组合为 PyVista 的 StructuredGrid 体素
            points = np.empty((nx * ny * 2, 3))
            points[:nx * ny, 0] = grid_x.ravel()
            points[:nx * ny, 1] = grid_y.ravel()
            points[:nx * ny, 2] = bot_grid.ravel()
            points[nx * ny:, 0] = grid_x.ravel()
            points[nx * ny:, 1] = grid_y.ravel()
            points[nx * ny:, 2] = top_grid.ravel()

            grid = pv.StructuredGrid()
            grid.points = points
            grid.dimensions = [nx, ny, 2]

            lithology = self.df[self.df['分层ID'] == layer_id]['含水层岩性'].iloc[0]
            plotter.add_mesh(grid, color=colors[idx % len(colors)], opacity=0.8,
                             show_edges=False, label=f"Layer {layer_id}: {lithology}")

        plotter.add_legend()
        plotter.show_grid()
        return plotter