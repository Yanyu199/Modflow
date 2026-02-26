# backend/export_utils.py
import io


def generate_obj_string(points):
    """
    将网格点数据转换为 OBJ 格式字符串
    points: List of dict, 包含 x, y, top, bottom, delr(可选), delc(可选) 等
    注意：我们输出的是真实的地理坐标 (X, Z, -Y) 以适配常见3D软件的Y轴向上习惯，
    或者是保持 (X, Z, Y) 取决于需求。这里保持真实物理坐标 (x, y, z)。
    """
    output = io.StringIO()
    output.write("# MODFLOW 3D Model Export\n")
    output.write(f"# Total Cells: {len(points)}\n")

    vertex_count = 1

    # 假设所有网格大小一致，取第一个点的尺寸，如果points里没有尺寸，默认50
    # 在 modflow_engine 中返回的 points 通常包含 x,y,top,bottom
    # 我们需要网格尺寸来计算8个顶点。这里估算或需要前端传参。
    # 为了精确，我们利用 points 数据的分布推算，或者假设后端 grid_info 可用。
    # 现阶段我们根据相邻点简单推算，或者使用固定大小。
    # 更稳妥的方式：后端 process_results 应该把 dx, dy 带上。
    # 这里我们使用一个简单的逻辑：计算 voxel 的半宽。

    # 为了保证逻辑独立且不修改过多旧代码，我们假设 dx=dy=50 (默认)
    # 或者我们动态计算一下最小间距。
    xs = sorted(list(set([p['x'] for p in points])))
    ys = sorted(list(set([p['y'] for p in points])))

    dx = 50.0
    dy = 50.0

    if len(xs) > 1:
        dx = abs(xs[1] - xs[0])
    if len(ys) > 1:
        dy = abs(ys[1] - ys[0])

    hx = dx / 2.0
    hy = dy / 2.0

    for p in points:
        cx, cy = p['x'], p['y']
        top, bot = p['top'], p['bottom']

        # 修正：防止极薄层导致几何错误
        if top - bot < 0.01:
            bot = top - 0.01

        # 定义立方体的8个顶点
        # OBJ 通常 Y 轴向上，但在地理信息中 Z 是高程。
        # 这里我们输出 (x, z, -y) 以便在 Blender/Three.js 等标准 3D 软件中直接观看（Y-up）
        # 或者输出原始 (x, y, z) (Z-up)。
        # 考虑到通用性，我们输出原始 (x, y, z)，让用户软件自己处理旋转。

        # Bottom face
        v1 = (cx - hx, cy - hy, bot)
        v2 = (cx + hx, cy - hy, bot)
        v3 = (cx + hx, cy + hy, bot)
        v4 = (cx - hx, cy + hy, bot)

        # Top face
        v5 = (cx - hx, cy - hy, top)
        v6 = (cx + hx, cy - hy, top)
        v7 = (cx + hx, cy + hy, top)
        v8 = (cx - hx, cy + hy, top)

        verts = [v1, v2, v3, v4, v5, v6, v7, v8]

        for v in verts:
            output.write(f"v {v[0]:.4f} {v[1]:.4f} {v[2]:.4f}\n")

        # 定义6个面 (quads)
        # f v1 v2 v3 v4
        # 索引从1开始
        base = vertex_count

        # Bottom (4 3 2 1) - 逆时针
        output.write(f"f {base + 3} {base + 2} {base + 1} {base + 0}\n")
        # Top (5 6 7 8)
        output.write(f"f {base + 4} {base + 5} {base + 6} {base + 7}\n")
        # Front (1 2 6 5) -> y-min
        output.write(f"f {base + 0} {base + 1} {base + 5} {base + 4}\n")
        # Back (3 4 8 7) -> y-max
        output.write(f"f {base + 2} {base + 3} {base + 7} {base + 6}\n")
        # Left (4 1 5 8) -> x-min
        output.write(f"f {base + 3} {base + 0} {base + 4} {base + 7}\n")
        # Right (2 3 7 6) -> x-max
        output.write(f"f {base + 1} {base + 2} {base + 6} {base + 5}\n")

        vertex_count += 8

    return output.getvalue()