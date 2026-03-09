# backend/post_process.py
import os
import numpy as np
import flopy

def process_results(work_dir, nlay, nrow, ncol, idomain, top_arrays, bot_arrays, grid_info):
    hds_file = os.path.join(work_dir, "gwf.hds")
    bud_file = os.path.join(work_dir, "gwf.bud")
    head = flopy.utils.HeadFile(hds_file).get_data()
    bud = flopy.utils.CellBudgetFile(bud_file)
    spdis = []
    try:
        spdis = bud.get_data(text='DATA-SPDIS')[0]
    except:
        try:
            spdis = bud.get_data(text='SPDIS')[0]
        except:
            pass

    flow_map = {}
    if len(spdis) > 0:
        dtype_names = spdis.dtype.names
        key_cid = next((x for x in dtype_names if x.lower() == 'cellid'), None)
        key_node = next((x for x in dtype_names if x.lower() == 'node'), None)
        key_qx = next((x for x in dtype_names if x.lower() == 'qx'), None)
        key_qy = next((x for x in dtype_names if x.lower() == 'qy'), None)
        key_qz = next((x for x in dtype_names if x.lower() == 'qz'), None)

        for item in spdis:
            try:
                vx, vy, vz = item[key_qx], item[key_qy], item[key_qz]
                real_k, real_i, real_j = -1, -1, -1
                if key_cid and isinstance(item[key_cid], tuple):
                    real_k, real_i, real_j = item[key_cid]
                elif key_node:
                    node_idx = int(item[key_node]) - 1
                    real_k = node_idx // (nrow * ncol)
                    rem = node_idx % (nrow * ncol)
                    real_i, real_j = rem // ncol, rem % ncol
                if real_k >= 0:
                    flow_map[(int(real_k), int(real_i), int(real_j))] = (float(vx), float(vy), float(vz))
            except: continue

    origin_x, origin_y, delr, delc = grid_info['origin_x'], grid_info['origin_y'], grid_info['delr'], grid_info['delc']
    points = []
    for k in range(nlay):
        for i in range(nrow):
            for j in range(ncol):
                if idomain[k, i, j] == 1:
                    t_val, b_val = float(top_arrays[k][i, j]), float(bot_arrays[k][i, j])
                    vx, vy, vz = flow_map.get((k, i, j), (0.0, 0.0, 0.0))
                    thick = max(0.1, t_val - b_val)
                    points.append({
                        "x": origin_x + j * delr + delr / 2,
                        "y": origin_y + (nrow - 1 - i) * delc + delc / 2,
                        "layer": k,
                        "row": i,
                        "col": j,
                        "top": t_val,
                        "bottom": b_val,
                        "head": float(head[k, i, j]),

                        # ⭐ 核心修改：修复六个面的净流出量方向映射
                        "flows": {
                            "vx": float(vx), "vy": float(vy), "vz": float(vz),
                            "right": vx * delc * thick,  # 东面 (+X 方向，流出为正)
                            "left": -vx * delc * thick,  # 西面 (-X 方向，流入为正，所以取反)
                            "back": vy * delr * thick,  # 北面 (+Y 方向，流出为正)
                            "front": -vy * delr * thick,  # 南面 (-Y 方向，取反)
                            "top": vz * delr * delc,  # 顶面 (+Z 方向向上，流出为正。原代码此处写反了)
                            "bottom": -vz * delr * delc  # 底面 (-Z 方向向下，取反)
                        }
                    })
    return points

def process_pathlines(work_dir, grid_info):
    """解析 MODPATH 7 粒子路径文件"""
    pth_file = os.path.join(work_dir, "mp.mppth")
    if not os.path.exists(pth_file): return []
    try:
        pobj = flopy.utils.PathlineFile(pth_file)
        origin_x, origin_y = grid_info['origin_x'], grid_info['origin_y']
        all_paths = pobj.get_alldata()
        return [[{"x": float(s['x'] + origin_x), "y": float(s['y'] + origin_y), "z": float(s['z'])} for s in path] for path in all_paths]
    except: return []