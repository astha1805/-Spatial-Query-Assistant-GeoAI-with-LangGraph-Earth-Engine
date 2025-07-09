import os
import rasterio
import geopandas as gpd
import numpy as np
from shapely.geometry import shape
from rasterio.features import shapes

def disaster_safe_tool_fn(state):
    try:
        mask_path = state["hazard_mask_path"]
        region_path = state["region_path"]
        output_path = f"data/{state['region']}_safe_zones.geojson"
        os.makedirs("data", exist_ok=True)

        with rasterio.open(mask_path) as src:
            mask_data = src.read(1)
            transform = src.transform
            crs = src.crs or "EPSG:4326"

        # Convert safe zones (i.e., where mask == 0)
        mask_bool = (mask_data == 0)
        shapes_gen = shapes(mask_bool.astype(np.uint8), transform=transform)
        safe_shapes = [shape(geom) for geom, val in shapes_gen if val == 1]

        safe_gdf = gpd.GeoDataFrame(geometry=safe_shapes, crs=crs)
        safe_gdf.to_file(output_path, driver="GeoJSON", index=False)

        state["cot_log"].append(f"🛟 Disaster-safe zones saved to {output_path}")
        return {
            **state,
            "disaster_safe_result": {
                "safe_vector": output_path
            },
            "step": "complete"
        }
    except Exception as e:
        state["cot_log"].append(f"❌ Error in disaster_safe_tool_fn: {str(e)}")
        return {
            **state,
            "disaster_safe_result": {
                "safe_vector": None,
                "error": str(e)
            },
            "step": "complete"
        }