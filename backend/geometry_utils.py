import geopandas as gpd
import json
import zipfile
import os
import tempfile
from pathlib import Path
from shapely.geometry import Polygon, MultiPolygon, LineString, MultiLineString, Point
from shapely.geometry import mapping

from geology_limits import MAX_ZIP_BYTES


def _safe_extract_zip(zip_file, target_dir):
    target_path = Path(target_dir).resolve()
    for member in zip_file.infolist():
        member_path = (target_path / member.filename).resolve()
        if target_path != member_path and target_path not in member_path.parents:
            raise ValueError(f"ZIP 文件包含不安全路径: {member.filename}")
    zip_file.extractall(target_dir)


def _find_first_shapefile(tmpdir):
    shp_files = sorted(
        path for path in Path(tmpdir).rglob("*")
        if path.is_file() and path.suffix.lower() == ".shp"
    )
    if not shp_files:
        raise ValueError("ZIP 中未找到 .shp 文件，请确认 .shp/.shx/.dbf 等文件已一起打包")
    return shp_files[0]


def parse_shapefile_zip(file_obj):
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            zip_path = os.path.join(tmpdir, "shape.zip")
            file_obj.save(zip_path)
            with zipfile.ZipFile(zip_path) as z:
                _safe_extract_zip(z, tmpdir)

            shp_file = _find_first_shapefile(tmpdir)
            gdf = gpd.read_file(shp_file)
            if gdf.empty: raise ValueError("文件为空")

            geom = gdf.geometry.iloc[0]
            polygon = ensure_polygon(geom)
            coords = [{"x": float(x), "y": float(y)} for x, y in polygon.exterior.coords]
            return coords
    except Exception as e:
        raise e


def _crs_metadata(gdf):
    if gdf.crs is None:
        return None
    epsg = gdf.crs.to_epsg()
    return {
        "authority": "EPSG" if epsg else None,
        "code": int(epsg) if epsg else None,
        "wkt": None if epsg else gdf.crs.to_wkt(),
        "axis_order": "xy",
    }


def parse_boundary_shapefile_zip(file_obj):
    if getattr(file_obj, "content_length", None) and file_obj.content_length > MAX_ZIP_BYTES:
        raise ValueError("ZIP 文件超过大小限制")
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            zip_path = os.path.join(tmpdir, "boundary.zip")
            file_obj.save(zip_path)
            if os.path.getsize(zip_path) > MAX_ZIP_BYTES:
                raise ValueError("ZIP 文件超过大小限制")
            with zipfile.ZipFile(zip_path) as z:
                _safe_extract_zip(z, tmpdir)

            shp_file = _find_first_shapefile(tmpdir)
            gdf = gpd.read_file(shp_file)
            if gdf.empty:
                raise ValueError("文件为空")

            geom = gdf.geometry.iloc[0]
            polygon = ensure_polygon(geom)
            feature = {
                "type": "Feature",
                "properties": {},
                "geometry": json.loads(json.dumps(mapping(polygon))),
            }
            return {
                "feature": feature,
                "coords": [{"x": float(x), "y": float(y)} for x, y in polygon.exterior.coords],
                "crs": _crs_metadata(gdf),
                "source": {"kind": "shapefile_zip", "crs_source": "file" if gdf.crs is not None else "missing"},
            }
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
    elif geom.geom_type == 'MultiLineString':
        lines = list(geom.geoms)
        if not lines:
            raise ValueError("空 MultiLineString")
        coords = []
        for line in lines:
            part = list(line.coords)
            if coords and part and coords[-1] == part[0]:
                coords.extend(part[1:])
            else:
                coords.extend(part)
        if len(coords) < 3:
            raise ValueError("MultiLineString 点数不足，无法构成面")
        if coords[0] != coords[-1]: coords.append(coords[0])
        return Polygon(coords)
    else:
        raise ValueError(f"不支持的几何类型: {geom.geom_type}")


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
                _safe_extract_zip(z, tmpdir)

            shp_file = _find_first_shapefile(tmpdir)
            gdf = gpd.read_file(shp_file)

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
