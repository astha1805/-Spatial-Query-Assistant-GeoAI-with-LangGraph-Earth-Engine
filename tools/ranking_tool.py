import os
import rasterio
import geopandas as gpd
from shapely.geometry import Point
import numpy as np

def ranking_tool_fn(state):
    try:
        suitability_path = state["suitability_output"]
        num_top_locations = state.get("top_n", 5)
        output_path = f"data/{state['region']}top{num_top_locations}_locations.geojson"
        os.makedirs("data", exist_ok=True)

        if num_top_locations <= 0:
            raise ValueError("Number of top locations must be greater than zero.")

        with rasterio.open(suitability_path) as src:
            data = src.read(1)
            transform = src.transform
            crs = src.crs or "EPSG:4326"

            # Mask out nodata if set
            if src.nodata is not None:
                data = np.where(data == src.nodata, np.nan, data)

        # Flatten and remove NaNs
        valid_indices = np.flatnonzero(~np.isnan(data))
        if len(valid_indices) < num_top_locations:
            raise ValueError("Not enough valid data points to select top locations.")

        # Find top-N indices
        flat_data = data.ravel()
        top_indices = valid_indices[np.argpartition(flat_data[valid_indices], -num_top_locations)[-num_top_locations:]]
        top_indices = top_indices[np.argsort(flat_data[top_indices])[::-1]]  # sort descending

        coords = [~transform * (idx % data.shape[1], idx // data.shape[1]) for idx in top_indices]
        gdf = gpd.GeoDataFrame(geometry=[Point(xy) for xy in coords], crs=crs)
        gdf.to_file(output_path, driver="GeoJSON", index=False)

        state["cot_log"].append(f"Top {num_top_locations} ranked locations saved at {output_path}")
        return {
            **state,
            "ranking_output": output_path,
            "step": "complete"
        }
    except Exception as e:
        state["cot_log"].append(f"Error in ranking_tool_fn: {str(e)}")
        return {
            **state,
            "ranking_output": None,
            "step": "complete",
            "error": str(e)
        }