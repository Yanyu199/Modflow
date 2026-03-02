# backend/geometry_tools.py
import numpy as np
from shapely.geometry import Polygon, Point
from scipy.interpolate import griddata


def generate_grid_info(params, boundary_coords):
    """
    根据边界和参数生成网格基础信息：行列数、步长、坐标网格、活动网格矩阵
    """
    # 1. 边界解析
    coords = [(pt["x"], pt["y"]) for pt in boundary_coords]
    polygon = Polygon(coords)
    if not polygon.is_valid: polygon = polygon.buffer(0)
    minx, miny, maxx, maxy = polygon.bounds
    Lx, Ly = maxx - minx, maxy - miny

    # 2. 计算行列数
    if params.get("x_mode") == "count":
        ncol = int(params.get("x_val", 20))
        delr = Lx / ncol
    else:
        size_x = float(params.get("x_val", 50.0))
        ncol = max(1, int(np.ceil(Lx / size_x)))
        delr = Lx / ncol

    if params.get("y_mode") == "count":
        nrow = int(params.get("y_val", 20))
        delc = Ly / nrow
    else:
        size_y = float(params.get("y_val", 50.0))
        nrow = max(1, int(np.ceil(Ly / size_y)))
        delc = Ly / nrow

    origin_x, origin_y = minx, miny

    # 3. 生成 IDOMAIN (活动网格)
    active_2d = np.zeros((nrow, ncol), dtype=int)
    grid_centers = [[None for _ in range(ncol)] for _ in range(nrow)]

    for i in range(nrow):
        for j in range(ncol):
            x_c = origin_x + j * delr + delr / 2
            y_c = origin_y + (nrow - 1 - i) * delc + delc / 2
            pt = Point(x_c, y_c)
            grid_centers[i][j] = pt
            if polygon.contains(pt):
                active_2d[i, j] = 1

    # 4. 生成插值用的网格坐标 (使用 linspace 修复精度问题)
    x_centers = np.linspace(origin_x + delr / 2, origin_x + Lx - delr / 2, ncol)
    y_centers = np.linspace(origin_y + Ly - delc / 2, origin_y + delc / 2, nrow)
    grid_x, grid_y = np.meshgrid(x_centers, y_centers)

    return {
        "ncol": ncol, "nrow": nrow,
        "delr": delr, "delc": delc,
        "origin_x": origin_x, "origin_y": origin_y,
        "Lx": Lx, "Ly": Ly,
        "active_2d": active_2d,
        "grid_centers": grid_centers,
        "grid_x": grid_x, "grid_y": grid_y,
        "polygon": polygon
    }
def map_zones_to_grid(zones, nrow, ncol, active_2d, grid_centers):
    """
    将矢量分区 (RCH/EVT) 映射到网格数组
    """
    array_out = np.zeros((nrow, ncol))
    if not zones:
        return array_out

    for zone in zones:
        try:
            poly_pts = [(p['x'], p['y']) for p in zone['coords']]
            if len(poly_pts) < 3: continue
            poly = Polygon(poly_pts)
            val = float(zone['value'])

            # 简单的包含判断 (性能优化点：可先用 bounds 筛选)
            minx, miny, maxx, maxy = poly.bounds
            for i in range(nrow):
                for j in range(ncol):
                    if active_2d[i, j] == 1:
                        pt = grid_centers[i][j]
                        # 快速包围盒预判
                        if pt.x < minx or pt.x > maxx or pt.y < miny or pt.y > maxy:
                            continue
                        if poly.contains(pt):
                            array_out[i, j] = val
        except:
            continue
    return array_out