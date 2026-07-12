# -*- coding: utf-8 -*-
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import numpy as np
import io
import os

# ==========================================
# 页面基础配置
# ==========================================
st.set_page_config(page_title="3D 剖面线高程自动提取系统", layout="wide", page_icon="🌐")

# ==========================================
# 核心缓存：加载 3D 网格数据
# ==========================================
@st.cache_data
def load_mesh_data(excel_path):
    if not os.path.exists(excel_path):
        return None
    df_v = pd.read_excel(excel_path, sheet_name='顶点数据 (Vertices)')
    df_f = pd.read_excel(excel_path, sheet_name='面数据 (Faces)')
    x = df_v['X坐标'].values
    y = df_v['Y坐标'].values
    z = df_v['Z坐标'].values
    i = df_f['顶点1_ID'].values
    j = df_f['顶点2_ID'].values
    k = df_f['顶点3_ID'].values

    # 提取网格线，缓存起来用于3D线框渲染
    x_lines, y_lines, z_lines = [], [], []
    for v1, v2, v3 in zip(i, j, k):
        x_lines.extend([x[v1], x[v2], x[v3], x[v1], None])
        y_lines.extend([y[v1], y[v2], y[v3], y[v1], None])
        z_lines.extend([z[v1], z[v2], z[v3], z[v1], None])

    return x, y, z, i, j, k, x_lines, y_lines, z_lines

# ==========================================
# 前端 UI 布局与侧边栏控制区
# ==========================================
st.title("🌐 3D 网格剖面线顶底板高程自动提取系统")
st.markdown("通过左侧控制面板输入或者**导入剖面线的起止点 TXT 文件**，系统将按照 **1米 步长** 自动对模型进行垂直切片采样，并精准提取对应的顶板和底板高程。")

with st.sidebar:
    st.header("⚙️ 剖面控制点配置 (2点直线)")

    # 1. 导入文本文件按钮
    uploaded_file = st.file_uploader(
        "📂 导入剖面线起止点 (.txt)",
        type=["txt"],
        help="文本文件中需包含 2 行，分别代表起点的 X Y Z 和终点的 X Y Z 坐标（用空格或逗号分隔）"
    )

    # 2. 手动调整/备用面板
    with st.expander("✏️ 手动微调起止点坐标 (未上传文件时生效)"):
        st.markdown("**🏁 起点坐标 (Start Point):**")
        sx = st.number_input("起点 X", value=3746170.0, format="%.2f")
        sy = st.number_input("起点 Y", value=4334270.0, format="%.2f")
        sz = st.number_input("起点 Z", value=1030.0, format="%.2f")

        st.markdown("**🏁 终点坐标 (End Point):**")
        ex = st.number_input("终点 X", value=3746200.0, format="%.2f")
        ey = st.number_input("终点 Y", value=4334310.0, format="%.2f")
        ez = st.number_input("终点 Z", value=1030.0, format="%.2f")

    # 默认使用手动输入参数
    line_endpoints = [[sx, sy, sz], [ex, ey, ez]]

    # 如果检测到文件上传，则解析并覆盖坐标值
    if uploaded_file is not None:
        try:
            stringio = io.StringIO(uploaded_file.getvalue().decode("utf-8"))
            lines = stringio.readlines()
            parsed_points = []
            for line in lines:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                parts = line.replace(',', ' ').split()
                if len(parts) >= 3:
                    parsed_points.append([float(parts[0]), float(parts[1]), float(parts[2])])

            if len(parsed_points) >= 2:
                line_endpoints = [parsed_points[0], parsed_points[1]]
                st.success("✅ 成功从文件导入起止点坐标！")
            else:
                st.error("❌ 文件内必须包含至少 2 行有效的 XYZ 坐标数据！")
                st.warning("⚠️ 已自动退回使用手动微调面板的默认坐标。")
        except Exception as e:
            st.error(f"❌ 文件解析失败: {e}")
            st.warning("⚠️ 已自动退回使用手动微调面板的默认坐标。")

    # 满足要求：在侧边栏页面直观显示当前生效的两个点坐标数据
    st.markdown("### 📍 当前生效的起止点")
    df_endpoints_show = pd.DataFrame(
        line_endpoints,
        columns=['X 坐标', 'Y 坐标', 'Z 坐标'],
        index=['起点 (Start)', '终点 (End)']
    )
    st.table(df_endpoints_show)

# ==========================================
# 后端执行与高程提取核心算法
# ==========================================
data_path = "output_data.xlsx"
mesh_data = load_mesh_data(data_path)

if mesh_data is None:
    st.error(f"找不到基础模型文件：{data_path}，请确保运行过之前的代码生成了此 Excel 表格！")
else:
    x, y, z, i, j, k, x_lines, y_lines, z_lines = mesh_data

    p_start, p_end = line_endpoints[0], line_endpoints[1]

    # 1. 计算水平总跨度并按 1米 步长进行离散采样
    horizontal_dist = np.sqrt((p_end[0] - p_start[0])**2 + (p_end[1] - p_start[1])**2)

    if horizontal_dist == 0:
        st.error("❌ 起点和终点的平面投影重合，无法生成剖面线，请重新配置坐标！")
    else:
        # 生成 1 米步长的水平距离序列
        steps = list(np.arange(0, horizontal_dist, 1.0))
        if len(steps) == 0 or steps[-1] < horizontal_dist:
            steps.append(horizontal_dist)

        # 根据水平距离插值计算出每个采样点的 X, Y, Z(基准值)
        sample_points = []
        for d in steps:
            t = d / horizontal_dist
            sx_val = p_start[0] + t * (p_end[0] - p_start[0])
            sy_val = p_start[1] + t * (p_end[1] - p_start[1])
            sz_val = p_start[2] + t * (p_end[2] - p_start[2])
            sample_points.append({'d': d, 'x': sx_val, 'y': sy_val, 'z_base': sz_val})

        sample_x = np.array([s['x'] for s in sample_points])
        sample_y = np.array([s['y'] for s in sample_points])
        num_samples = len(sample_points)

        # 2. 空间相交及射线投影计算 (利用 Numpy 加速过滤)
        with st.spinner("正在以 1m 步长对 3D 网格进行垂直穿透计算，请稍候..."):
            z_collections = [[] for _ in range(num_samples)]

            # 遍历模型中每一个三角面
            for tri_idx in range(len(i)):
                v1_idx, v2_idx, v3_idx = i[tri_idx], j[tri_idx], k[tri_idx]
                v1 = (x[v1_idx], y[v1_idx], z[v1_idx])
                v2 = (x[v2_idx], y[v2_idx], z[v2_idx])
                v3 = (x[v3_idx], y[v3_idx], z[v3_idx])

                # 计算当前三角面的 2D 边界框
                t_min_x, t_max_x = min(v1[0], v2[0], v3[0]), max(v1[0], v2[0], v3[0])
                t_min_y, t_max_y = min(v1[1], v2[1], v3[1]), max(v1[1], v2[1], v3[1])

                # 快速筛选落入该三角面边界框内的采样点
                mask = (sample_x >= t_min_x) & (sample_x <= t_max_x) & (sample_y >= t_min_y) & (sample_y <= t_max_y)
                valid_indices = np.where(mask)[0]

                # 对潜在相交的采样点进行重心坐标精准求交
                for s_idx in valid_indices:
                    sx = sample_x[s_idx]
                    sy = sample_y[s_idx]

                    det = (v2[1] - v3[1]) * (v1[0] - v3[0]) + (v3[0] - v2[0]) * (v1[1] - v3[1])
                    if abs(det) < 1e-7:
                        continue
                    w_a = ((v2[1] - v3[1]) * (sx - v3[0]) + (v3[0] - v2[0]) * (sy - v3[1])) / det
                    w_b = ((v3[1] - v1[1]) * (sx - v3[0]) + (v1[0] - v3[0]) * (sy - v3[1])) / det
                    w_c = 1.0 - w_a - w_b

                    # 允许极小的浮点数数值误差边界
                    tol = -1e-4
                    if w_a >= tol and w_b >= tol and w_c >= tol:
                        w_a, w_b, w_c = max(0.0, w_a), max(0.0, w_b), max(0.0, w_c)
                        s_w = w_a + w_b + w_c
                        if s_w > 0:
                            w_a /= s_w; w_b /= s_w; w_c /= s_w
                        # 精准计算该点穿透该网格面的 Z 轴高程
                        interp_z = w_a * v1[2] + w_b * v2[2] + w_c * v3[2]
                        z_collections[s_idx].append(interp_z)

            # 3. 归纳每个采样点的最大 Z (顶板) 和 最小 Z (底板)
            final_rows = []
            for s_idx, s_pt in enumerate(sample_points):
                z_list = z_collections[s_idx]
                if len(z_list) > 0:
                    top_z = max(z_list)
                    bottom_z = min(z_list)
                    thickness = top_z - bottom_z
                else:
                    top_z = np.nan
                    bottom_z = np.nan
                    thickness = np.nan

                final_rows.append({
                    "累计水平距离(m)": s_pt['d'],
                    "采样点X坐标": s_pt['x'],
                    "采样点Y坐标": s_pt['y'],
                    "顶板高程(m)": top_z,
                    "底板高程(m)": bottom_z,
                    "夹层厚度(m)": thickness
                })

        df_profile = pd.DataFrame(final_rows)
        df_valid = df_profile.dropna(subset=["顶板高程(m)", "底板高程(m)"])

        # ================= 状态状态提示与下载按钮 =================
        if len(df_valid) > 0:
            st.success(f"🎉 沿剖面线成功提取了 **{len(df_valid)}** 个有效采样点的高程数据（总设采样点: {num_samples} 个）。")

            # 生成二进制流导出 Excel
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                df_profile.to_excel(writer, index=False, sheet_name='剖面高程提取数据')
            excel_data = output.getvalue()

            st.download_button(
                label="📥 一键下载剖面顶底板高程表格 (Excel)",
                data=excel_data,
                file_name="extracted_profile_line_elevation.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        else:
            st.warning("⚠️ 剖面线似乎完全穿过了模型外部边界，未捕获到任何网格交点。请在左侧检查起止点坐标是否准确。")

        # =================【全新看板功能】：2D 剖面纵断面图 =================
        st.subheader("📈 2.5D 纵断面高程起伏图 (Cross-Section Profile)")
        if len(df_valid) > 0:
            fig_2d = go.Figure()
            # 绘制顶板曲线
            fig_2d.add_trace(go.Scatter(
                x=df_profile["累计水平距离(m)"], y=df_profile["顶板高程(m)"],
                mode='lines+markers', name='顶板高程 (Roof)',
                line=dict(color='#1f77b4', width=2.5), marker=dict(size=4)
            ))
            # 绘制底板曲线
            fig_2d.add_trace(go.Scatter(
                x=df_profile["累计水平距离(m)"], y=df_profile["底板高程(m)"],
                mode='lines+markers', name='底板高程 (Floor)',
                line=dict(color='#8c564b', width=2.5), marker=dict(size=4)
            ))
            fig_2d.update_layout(
                hovermode="x unified",
                xaxis_title="沿剖面线水平累计距离 (米)",
                yaxis_title="绝对高程 Z (米)",
                margin=dict(l=40, r=40, b=40, t=20),
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
            )
            st.plotly_chart(fig_2d, use_container_width=True)

        # ================= 3D 空间视图 =================
        st.subheader("📊 3D 空间模型及剖面线透视图")
        fig_3d = go.Figure()

        # 图层1：模型实体面
        fig_3d.add_trace(go.Mesh3d(
            x=x, y=y, z=z, i=i, j=j, k=k,
            colorscale='earth', intensity=z, showscale=True, flatshading=True, name='模型表面'
        ))

        # 图层2：网格线框
        fig_3d.add_trace(go.Scatter3d(
            x=x_lines, y=y_lines, z=z_lines,
            mode='lines', line=dict(color='black', width=1), name='网格骨架', hoverinfo='skip'
        ))

        # 图层3：用户输入的 3D 剖面直线段
        line_xyz = np.array([p_start, p_end])
        fig_3d.add_trace(go.Scatter3d(
            x=line_xyz[:, 0], y=line_xyz[:, 1], z=line_xyz[:, 2],
            mode='lines+markers+text',
            line=dict(color='red', width=6),
            marker=dict(size=7, color='yellow'),
            text=["起点 (Start)", "终点 (End)"],
            textposition="top center",
            name='剖面采样线'
        ))

        # 空间等比例展现缩放
        dx, dy, dz = np.ptp(x), np.ptp(y), np.ptp(z)
        max_range = max(dx, dy, dz) if max(dx, dy, dz) != 0 else 1
        x_ratio, y_ratio, z_ratio = dx / max_range, dy / max_range, dz / max_range

        fig_3d.update_layout(
            height=650,
            scene=dict(
                xaxis_title='X (Easting)', yaxis_title='Y (Northing)', zaxis_title='Z (Elevation)',
                aspectmode='manual', aspectratio=dict(x=x_ratio, y=y_ratio, z=z_ratio*2.5) # 适度拉伸Z方便看地层厚度
            ),
            margin=dict(l=0, r=0, b=0, t=0), legend=dict(x=0.02, y=0.95)
        )
        st.plotly_chart(fig_3d, use_container_width=True)

        # ================= 底部表格展示 =================
        st.subheader("📋 采样点详细数据明细 (1m 步长)")
        st.dataframe(df_profile, use_container_width=True, height=300)
