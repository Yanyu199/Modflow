# backend/post_process.py
import os
import numpy as np
import flopy


def process_results(work_dir, nlay, nrow, ncol, idomain, top_arrays, bot_arrays, grid_info):
    hds_file = os.path.join(work_dir, "gwf.hds")
    bud_file = os.path.join(work_dir, "gwf.bud")
    head = flopy.utils.HeadFile(hds_file).get_data()
    bud = flopy.utils.CellBudgetFile(bud_file)

    # 获取 MF6 专门输出的比流量数据 (Specific Discharge)
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
            except:
                continue

    origin_x, origin_y = grid_info['origin_x'], grid_info['origin_y']
    delr, delc = grid_info['delr'], grid_info['delc']
    points = []

    for k in range(nlay):
        for i in range(nrow):
            for j in range(ncol):
                if idomain[k, i, j] == 1:
                    t_val = float(top_arrays[k][i, j])
                    b_val = float(bot_arrays[k][i, j])
                    thick = max(0.1, t_val - b_val)

                    # 取出流速 (MF6标准：+qx为东，+qy为北，+qz为上)
                    vx, vy, vz = flow_map.get((k, i, j), (0.0, 0.0, 0.0))

                    # ⭐ 计算三个方向真实的物理过水截面积 (m²)
                    area_x = delc * thick  # 东西向侧面面积
                    area_y = delr * thick  # 南北向侧面面积
                    area_z = delr * delc  # 顶底面面积

                    # 组装 6 个面的通量，规则：正数代表水离开当前网格，负数代表水进入当前网格
                    points.append({
                        "x": origin_x + j * delr + delr / 2,
                        "y": origin_y + (nrow - 1 - i) * delc + delc / 2,
                        "layer": k,
                        "row": i,
                        "col": j,
                        "top": t_val,
                        "bottom": b_val,
                        "head": float(head[k, i, j]),
                        "flows": {
                            "vx": float(vx), "vy": float(vy), "vz": float(vz),
                            "right": vx * area_x,  # 东面 (+X 方向，流出为正)
                            "left": -vx * area_x,  # 西面 (-X 方向，流出为正)
                            "back": vy * area_y,  # 北面 (+Y 方向，流出为正)
                            "front": -vy * area_y,  # 南面 (-Y 方向，流出为正)
                            "top": vz * area_z,  # 顶面 (+Z 方向，流出为正)
                            "bottom": -vz * area_z  # 底面 (-Z 方向，流出为正)
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
        return [[{"x": float(s['x'] + origin_x), "y": float(s['y'] + origin_y), "z": float(s['z'])} for s in path] for
                path in all_paths]
    except:
        return []