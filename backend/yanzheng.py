import pandas as pd
import plotly.graph_objects as go
import os

def plot_interactive_mesh(excel_path):
    if not os.path.exists(excel_path):
        print(f"找不到文件: {excel_path}")
        return

    print("正在读取顶点和网格数据...")
    # 1. 读取数据
    df_v = pd.read_excel(excel_path, sheet_name='顶点数据 (Vertices)')
    df_f = pd.read_excel(excel_path, sheet_name='面数据 (Faces)')

    x = df_v['X坐标'].values
    y = df_v['Y坐标'].values
    z = df_v['Z坐标'].values

    # Plotly 需要把面拆分成三个顶点索引的数组 (i, j, k)
    i = df_f['顶点1_ID'].values
    j = df_f['顶点2_ID'].values
    k = df_f['顶点3_ID'].values

    print("数据读取完毕，正在生成丝滑的交互式 3D 模型...")

    # 2. 创建 3D 网格对象
    fig = go.Figure(data=[
        go.Mesh3d(
            x=x, y=y, z=z,
            i=i, j=j, k=k,
            colorscale='Viridis', # 颜色映射
            intensity=z,          # 根据 Z 轴高度上色
            showscale=True,       # 显示颜色条
            flatshading=True,     # 开启平面着色，让网格棱角更分明
            opacity=1.0           # 透明度
        )
    ])

    # 3. 设置交互视角和布局参数
    fig.update_layout(
        title="交互式 3D 网格查看器 (纯鼠标控制)",
        scene=dict(
            xaxis_title='X (Easting)',
            yaxis_title='Y (Northing)',
            zaxis_title='Z (Elevation)',
            # 自动调整 X/Y/Z 的比例，防止模型被压扁
            aspectmode='data'
        ),
        margin=dict(l=0, r=0, b=0, t=40) # 去除多余白边
    )

    # 4. 在默认浏览器中全屏打开！
    fig.show()

if __name__ == "__main__":
    plot_interactive_mesh("output_data.xlsx")