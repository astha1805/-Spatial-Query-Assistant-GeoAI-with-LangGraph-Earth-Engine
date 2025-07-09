import os
from rasterio.mask import mask
import rasterio
import geopandas as gpd
from shapely.geometry import mapping, shape
import numpy as np
from rasterio.features import shapes

def raster_tool_fn(state):
    try:
        region_path = state["region_path"]
        dem_path = state["dem_path"]
        threshold = state["threshold"]
        comparison = state.get("comparison", "below")

        os.makedirs("data", exist_ok=True)

        region = gpd.read_file(region_path)
        with rasterio.open(dem_path) as src:
            # Reproject region to match DEM CRS if needed
            if region.crs != src.crs:
                region = region.to_crs(src.crs)

            geom = [mapping(region.unary_union)]
            clipped, transform = mask(src, geom, crop=True)
            meta = src.meta.copy()

            nodata = src.nodata if src.nodata is not None else -32768
            elevation_data = clipped[0].astype(np.float32)
            elevation_data[np.isclose(elevation_data, nodata)] = np.nan  # safer than equality

            # Apply threshold
            if comparison == "above":
                mask_arr = (elevation_data > threshold).astype(np.uint8)
            else:
                mask_arr = (elevation_data < threshold).astype(np.uint8)

            # Save raster mask
            meta.update({
                "height": mask_arr.shape[0],
                "width": mask_arr.shape[1],
                "transform": transform,
                "dtype": "uint8",
                "count": 1,
                "nodata": 0
            })

            raster_out_path = f"data/{state['region']}mask{comparison}_{threshold}m.tif"
            with rasterio.open(raster_out_path, "w", **meta) as dst:
                dst.write(mask_arr, 1)

            # Convert to vector polygons
            results = (
                {"properties": {"value": v}, "geometry": s}
                for s, v in shapes(mask_arr, transform=transform)
                if v == 1
            )
            geoms = [shape(feature["geometry"]) for feature in results]

            if not geoms:
                state["cot_log"].append(f"No areas found {comparison} {threshold}m.")
                return {
                    **state,
                    "raster_result": {
                        "status": "empty",
                        "message": f"No areas found {comparison} {threshold}m."
                    },
                    "step": "complete"
                }

            vector_output = gpd.GeoDataFrame(geometry=geoms, crs=region.crs)
            vector_out_path = f"data/{state['region']}mask{comparison}_{threshold}m.geojson"
            vector_output.to_file(vector_out_path, driver="GeoJSON", index=False)

        # Log
        state["cot_log"].append(f"Masked raster saved to {raster_out_path}")
        state["cot_log"].append(f"Vectorized thresholded areas saved to {vector_out_path}")

        return {
            **state,
            "raster_result": {
                "status": "success",
                "raster_output": raster_out_path,
                "vectorized_output": vector_out_path
            },
            "step": "complete"
        }

    except Exception as e:
        state["cot_log"].append(f"Error in raster_tool_fn: {str(e)}")
        return {
            **state,
            "raster_result": {"status": "error", "error_msg": str(e)},
            "step": "complete"
        }