import geopandas as gpd
import zipfile
import os
import tempfile
import shutil
from pathlib import Path
from shapely.geometry import Polygon, MultiPolygon, LineString, MultiLineString, Point


# ==========================================
# 1. 保留您原有的边界解析函数 (绝对不改动)
# ==========================================
def parse_shapefile_zip(file_obj):
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            zip_path = os.path.join(tmpdir, "shape.zip")
            file_obj.save(zip_path)
            with zipfile.ZipFile(zip_path) as z:
                z.extractall(tmpdir)

            shp_files = list(Path(tmpdir).glob("*.shp"))
            if not shp_files: raise ValueError("无 .shp 文件")

            gdf = gpd.read_file(shp_files[0])
            if gdf.empty: raise ValueError("文件为空")

            geom = gdf.geometry.iloc[0]
            polygon = ensure_polygon(geom)
            coords = [{"x": float(x), "y": float(y)} for x, y in polygon.exterior.coords]
            return coords
    except Exception as e:
        raise e


def ensure_polygon(geom):
    if geom.geom_type == 'Polygon':
        return geom
    elif geom.geom_type == 'MultiPolygon':
        return geom.geoms[0]
    elif geom.geom_type == 'LineString':
        coords = list(geom.coords)
        if coords[0] != coords[-1]: coords.append(coords[0])
        return Polygon(coords)
    else:
        raise ValueError(f"不支持的几何类型: {geom.geom_type}")


# ==========================================
# 2. 保留您原有的高程提取函数 (绝对不改动)
# ==========================================
def extract_xyz_from_zip(file_obj):
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            zip_path = os.path.join(tmpdir, "layer.zip")
            file_obj.save(zip_path)
            with zipfile.ZipFile(zip_path) as z:
                z.extractall(tmpdir)

            shp_files = list(Path(tmpdir).glob("*.shp"))
            if not shp_files: raise ValueError("无 .shp 文件")

            gdf = gpd.read_file(shp_files[0])

            # 1. 寻找高程字段
            possible_cols = ['ELEV', 'elev', 'Z', 'z', 'HEIGHT', 'height', 'VAL', 'val', 'Contour']
            z_col = next((c for c in possible_cols if c in gdf.columns), None)

            if not z_col:
                if gdf.geometry.has_z.any():
                    points = []
                    for geom in gdf.geometry:
                        if isinstance(geom, (LineString, MultiLineString)):
                            for coord in geom.coords:
                                if len(coord) >= 3: points.append((coord[0], coord[1], coord[2]))
                        elif isinstance(geom, Point):
                            if len(geom.coords[0]) >= 3: points.append(geom.coords[0])
                    return points
                else:
                    raise ValueError(f"未找到高程字段。请确保属性表中包含以下字段之一: {possible_cols}")

            # 2. 提取 XYZ
            xyz_list = []
            for idx, row in gdf.iterrows():
                z_val = float(row[z_col])
                geom = row.geometry

                if geom.geom_type in ['LineString', 'MultiLineString']:
                    if geom.geom_type == 'LineString':
                        parts = [geom]
                    else:
                        parts = geom.geoms

                    for part in parts:
                        for x, y in part.coords:
                            xyz_list.append((x, y, z_val))

                elif geom.geom_type == 'Point':
                    xyz_list.append((geom.x, geom.y, z_val))

            return xyz_list

    except Exception as e:
        print(f"解析高程文件失败: {e}")
        raise e


# ==========================================
# 3. ⭐ 新增：解析入渗/蒸发分区 SHP
# ==========================================
def parse_zone_shapefile(file_obj):
    """
    解析面状 Shapefile，返回每个多边形的坐标和属性值(rate/value)
    """
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            zip_path = os.path.join(tmpdir, "zone.zip")
            file_obj.save(zip_path)
            with zipfile.ZipFile(zip_path) as z:
                z.extractall(tmpdir)

            shp_files = list(Path(tmpdir).glob("*.shp"))
            if not shp_files: raise ValueError("无 .shp 文件")

            gdf = gpd.read_file(shp_files[0])

            # 自动探测数值字段
            possible_cols = ['rate', 'RATE', 'value', 'VALUE', 'val', 'VAL', 'rch', 'evt', 'RCH', 'EVT']
            val_col = next((c for c in possible_cols if c in gdf.columns), None)

            zones = []
            for idx, row in gdf.iterrows():
                try:
                    poly = ensure_polygon(row.geometry)
                    # 提取外圈坐标用于前端绘图
                    coords = [{"x": float(x), "y": float(y)} for x, y in poly.exterior.coords]

                    # 获取默认值，如果没有字段默认给 0.0001
                    default_val = float(row[val_col]) if val_col else 0.0001

                    zones.append({
                        "id": idx,
                        "coords": coords,
                        "value": default_val
                    })
                except Exception as ex:
                    print(f"Skipping invalid geometry in zone {idx}: {ex}")
                    continue

            return zones
    except Exception as e:
        raise e