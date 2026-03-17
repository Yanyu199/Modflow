# backend/geological_builder.py
import pandas as pd
import numpy as np
from scipy.interpolate import Rbf, griddata
import pyvista as pv
from shapely.geometry import Point, LineString, box
from shapely.ops import split


class GeologicalModeler:
    def __init__(self, file):
        filename = file.filename.lower() if hasattr(file, 'filename') else ''
        if filename.endswith('.xlsx') or filename.endswith('.xls'):
            self.df = pd.read_excel(file)
        else:
            self.df = pd.read_csv(file)

        self.boreholes = {}
        self.layers = []
        self.surfaces = {}

    def get_frontend_data(self):
        layer_mapping = {i: int(layer_id) for i, layer_id in enumerate(self.layers)}
        bh_list = []
        for name in self.boreholes.keys():
            bh_data = self.df[self.df['钻孔名称'] == name]
            layers = []
            for _, row in bh_data.iterrows():
                l_id = int(row['分层ID'])
                layers.append({
                    "layer_id": l_id,
                    "layer_idx": self.layers.index(l_id),
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
        bh_df = self.df[['钻孔名称', 'X', 'Y', 'Z']].drop_duplicates(subset=['钻孔名称']).set_index('钻孔名称')
        for idx, row in bh_df.iterrows():
            self.boreholes[idx] = {'X': row['X'], 'Y': row['Y'], 'Z': row.get('Z', 0)}

        if 'Top' not in self.df.columns or 'Bottom' not in self.df.columns:
            self.df = self.df.sort_values(by=['钻孔名称', '分层ID'])
            self.df['cum_thick'] = self.df.groupby('钻孔名称')['分层厚度'].cumsum()
            self.df['Bottom'] = self.df['Z'] - self.df['cum_thick']
            self.df['Top'] = self.df['Bottom'] + self.df['分层厚度']

        self.layers = sorted(self.df['分层ID'].unique())

    def _get_virtual_elevation(self, bh_name, target_layer_id):
        bh_data = self.df[self.df['钻孔名称'] == bh_name].sort_values('分层ID')
        upper_layers = bh_data[bh_data['分层ID'] < target_layer_id]
        lower_layers = bh_data[bh_data['分层ID'] > target_layer_id]

        if not upper_layers.empty:
            return upper_layers.iloc[-1]['Bottom']
        elif not lower_layers.empty:
            return lower_layers.iloc[0]['Top']
        else:
            return 0

    def interpolate_surfaces(self, grid_x, grid_y, faults=None):
        print(f"\n--- 🌊 地质插值引擎启动 ---")
        blocks = []
        min_x, max_x = np.nanmin(grid_x), np.nanmax(grid_x)
        min_y, max_y = np.nanmin(grid_y), np.nanmax(grid_y)
        # 扩大包围盒，确保囊括所有网格
        domain_box = box(min_x - 5000, min_y - 5000, max_x + 5000, max_y + 5000)

        # --- 1. 根据断层线划分断块 ---
        if faults and len(faults) > 0:
            current_polys = [domain_box]
            for idx, fault_pts in enumerate(faults):
                if len(fault_pts) < 2: continue

                # ⭐ 核心修复 1：采用射线延长法。仅沿首尾两端的切线方向无限延长，绝对不改变中间弯折点的位置！
                pts = [(p['x'], p['y']) for p in fault_pts]
                dist = 500000  # 向两端射出 500 公里，像利剑一样切透整个模型

                x0, y0 = pts[0]
                x1, y1 = pts[1]
                L1 = np.hypot(x0 - x1, y0 - y1)
                if L1 > 0:
                    pts[0] = (x0 + (x0 - x1) / L1 * dist, y0 + (y0 - y1) / L1 * dist)

                xn, yn = pts[-1]
                xpn, ypn = pts[-2]
                Ln = np.hypot(xn - xpn, yn - ypn)
                if Ln > 0:
                    pts[-1] = (xn + (xn - xpn) / Ln * dist, yn + (yn - ypn) / Ln * dist)

                line = LineString(pts)

                new_polys = []
                for poly in current_polys:
                    split_res = split(poly, line)
                    for geom in split_res.geoms:
                        new_polys.append(geom)
                current_polys = new_polys

            blocks = current_polys
            print(f"✅ 断层切割成功: {len(faults)} 条断层将研究区切成了 {len(blocks)} 个物理断块！")
        else:
            blocks = [domain_box]

        # --- 2. 独立插值所有顶底板 ---
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

            grid_top = np.zeros_like(grid_x)
            grid_bot = np.zeros_like(grid_y)

            for block_poly in blocks:
                b_pts_x, b_pts_y, b_pts_top, b_pts_bot = [], [], [], []
                for bx, by, bt, bb in zip(pts_x, pts_y, pts_top, pts_bot):
                    # 使用 intersects 防止落在边界线上的孔被漏掉
                    if block_poly.intersects(Point(bx, by)):
                        b_pts_x.append(bx)
                        b_pts_y.append(by)
                        b_pts_top.append(bt)
                        b_pts_bot.append(bb)

                # 生成当前断块的网格掩码 (Mask)
                mask = np.zeros_like(grid_x, dtype=bool)
                b_minx, b_miny, b_maxx, b_maxy = block_poly.bounds
                for i in range(grid_x.shape[0]):
                    for j in range(grid_x.shape[1]):
                        gx, gy = grid_x[i, j], grid_y[i, j]
                        if b_minx <= gx <= b_maxx and b_miny <= gy <= b_maxy:
                            if block_poly.intersects(Point(gx, gy)):
                                mask[i, j] = True

                if not np.any(mask):
                    continue  # 该断块内没有网格，直接跳过

                target_pts = np.column_stack((grid_x[mask], grid_y[mask]))

                # ⭐ 核心修复 2：根据断块内点数量，智能选择算法，死守高程台阶绝不平滑！
                if len(b_pts_x) >= 3:
                    # 断块内钻孔充足，使用本断块数据进行 RBF 平滑
                    rbf_top = Rbf(b_pts_x, b_pts_y, b_pts_top, function='thin_plate')
                    rbf_bot = Rbf(b_pts_x, b_pts_y, b_pts_bot, function='thin_plate')
                    grid_top[mask] = rbf_top(grid_x[mask], grid_y[mask])
                    grid_bot[mask] = rbf_bot(grid_x[mask], grid_y[mask])
                elif len(b_pts_x) > 0:
                    # 断块内仅有 1-2 个孔，改用最近邻，保持断块悬崖状
                    pts_arr = np.column_stack((b_pts_x, b_pts_y))
                    grid_top[mask] = griddata(pts_arr, b_pts_top, target_pts, method='nearest')
                    grid_bot[mask] = griddata(pts_arr, b_pts_bot, target_pts, method='nearest')
                else:
                    # 断块内完全没有钻孔！使用全局孔的最近邻，直接“抓取”隔壁断块的硬高程
                    pts_arr = np.column_stack((pts_x, pts_y))
                    grid_top[mask] = griddata(pts_arr, pts_top, target_pts, method='nearest')
                    grid_bot[mask] = griddata(pts_arr, pts_bot, target_pts, method='nearest')

            # 强制裁切极值
            max_z = np.nanmax(pts_top) + 5.0
            min_z = np.nanmin(pts_bot) - 5.0
            grid_top = np.clip(grid_top, min_z, max_z)
            grid_bot = np.clip(grid_bot, min_z, max_z)

            # 清洗剧毒 NaN
            mean_top = np.nanmean(pts_top) if len(pts_top) > 0 else 0
            mean_bot = np.nanmean(pts_bot) if len(pts_bot) > 0 else -10
            grid_top = np.nan_to_num(grid_top, nan=mean_top)
            grid_bot = np.nan_to_num(grid_bot, nan=mean_bot)

            self.surfaces[layer_id] = {'Top': grid_top, 'Bottom': grid_bot}

        # --- 3. 自上而下“压路机”推平算法 ---
        if not self.layers:
            return self.surfaces

        first_layer_id = self.layers[0]
        current_top = self.surfaces[first_layer_id]['Top']
        current_bot = np.minimum(self.surfaces[first_layer_id]['Bottom'], current_top - 0.1)

        self.surfaces[first_layer_id]['Top'] = current_top
        self.surfaces[first_layer_id]['Bottom'] = current_bot

        for i in range(1, len(self.layers)):
            layer_id = self.layers[i]
            self.surfaces[layer_id]['Top'] = current_bot.copy()
            raw_bot = self.surfaces[layer_id]['Bottom']
            new_bot = np.minimum(raw_bot, current_bot - 0.1)
            self.surfaces[layer_id]['Bottom'] = new_bot
            current_bot = new_bot

        return self.surfaces

    def build_3d_volume(self, grid_x, grid_y):
        pass