# -*- coding: utf-8 -*-
import os
import pandas as pd

def convert_obj_to_off_and_excel_pandas(obj_path, off_path, excel_path):

    vertices = []
    faces = []

    if not os.path.exists(obj_path):
        print(f"\\n[错误] 找不到输入的 OBJ 文件: '{obj_path}'")
        return False

    print(f"开始解析 OBJ 文件: {obj_path} ...")

    with open(obj_path, 'r', encoding='utf-8', errors='ignore') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue

            parts = line.split()
            if not parts:
                continue

            prefix = parts[0]

            if prefix == 'v':
                x, y, z = float(parts[1]), float(parts[2]), float(parts[3])
                vertices.append((x, y, z))

            elif prefix == 'f':
                face_vertices = []
                for part in parts[1:]:
                    idx_str = part.split('/')[0]
                    if not idx_str:
                        continue
                    idx = int(idx_str)

                    if idx > 0:
                        idx -= 1
                    elif idx < 0:
                        idx = len(vertices) + idx
                    face_vertices.append(idx)

                if len(face_vertices) >= 3:
                    for i in range(1, len(face_vertices) - 1):
                        faces.append((face_vertices[0], face_vertices[i], face_vertices[i+1]))

    # 写入 OFF 文件
    print(f"正在生成 OFF 文件: {off_path} ...")
    with open(off_path, 'w', encoding='utf-8') as f:
        f.write("OFF\n")
        f.write(f"{len(vertices)} {len(faces)} 0\n")
        for v in vertices:
            f.write(f"{v[0]:.6f} {v[1]:.6f} {v[2]:.6f}\n")
        for face in faces:
            f.write(f"3 {face[0]} {face[1]} {face[2]}\n")

    # 使用 Pandas 生成真正的 Excel 文件
    print(f"正在使用 Pandas 生成 Excel 文件: {excel_path} ...")

    # 构造 DataFrame
    df_vertices = pd.DataFrame(vertices, columns=['X坐标', 'Y坐标', 'Z坐标'])
    df_vertices.index.name = '顶点ID'

    df_faces = pd.DataFrame(faces, columns=['顶点1_ID', '顶点2_ID', '顶点3_ID'])
    df_faces.index.name = '三角面ID'

    try:
        # 尝试导出为 .xlsx (需要 openpyxl 库)
        with pd.ExcelWriter(excel_path, engine='openpyxl') as writer:
            df_vertices.to_excel(writer, sheet_name='顶点数据 (Vertices)')
            df_faces.to_excel(writer, sheet_name='面数据 (Faces)')
    except ModuleNotFoundError:
        # 如果没有安装 openpyxl，则退回到导出两个 CSV
        print("\\n[提示] 您的环境未安装 openpyxl，正在退回导出 CSV 格式...")
        df_vertices.to_csv(excel_path.replace('.xlsx', '_vertices.csv'), encoding='utf-8-sig')
        df_faces.to_csv(excel_path.replace('.xlsx', '_faces.csv'), encoding='utf-8-sig')
        print("已导出为两个分开的 CSV 文件。")

    print("-" * 50)
    print("【全部生成成功！】")
    print(f"-> 成功提取: {len(vertices)} 个顶点, {len(faces)} 个三角面")
    print(f"-> 3D模型文件已生成: {off_path}")
    print(f"-> 数据表格已生成: {excel_path}")
    print("-" * 50)
    return True

if __name__ == "__main__":
    INPUT_OBJ_PATH = "1-基本顶.obj"
    OUTPUT_OFF_PATH = "output.off"
    OUTPUT_EXCEL_PATH = "output_data.xlsx"

    convert_obj_to_off_and_excel_pandas(INPUT_OBJ_PATH, OUTPUT_OFF_PATH, OUTPUT_EXCEL_PATH)


with open("off_pandas.py", "w", encoding="utf-8") as f:
    f.write()

print("File generated successfully.")