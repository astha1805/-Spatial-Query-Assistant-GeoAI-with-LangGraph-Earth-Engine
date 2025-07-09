import os
import geopandas as gpd

def vector_tool_fn(state):
    try:
        vector_path = state.get("vector_path")
        buffer_distance = state.get("buffer_distance", 1000)

        if not vector_path or not os.path.exists(vector_path):
            raise ValueError("Missing or invalid 'vector_path' in state.")

        import geopandas as gpd

        gdf = gpd.read_file(vector_path)
        if gdf.empty:
            raise ValueError("Input vector file contains no features.")

        gdf = gdf[gdf.is_valid]
        if gdf.empty:
            raise ValueError("All geometries were invalid after validation.")

        if gdf.crs is None:
            gdf.set_crs("EPSG:4326", inplace=True)

        gdf_proj = gdf.to_crs(epsg=3857)
        buffered = gdf_proj.buffer(buffer_distance)
        result = gpd.GeoDataFrame(geometry=buffered).set_crs(gdf_proj.crs).to_crs("EPSG:4326")

        out_path = f"data/{state['region']}_buffered.geojson"
        result.to_file(out_path, driver="GeoJSON")

        state["cot_log"].append(
            f"Buffered {len(result)} valid features by {buffer_distance}m and saved to {out_path}"
        )

        return {
            **state,
            "vector_result": {"status": "success", "vector_output": out_path},
            "step": "complete"
        }

    except Exception as e:
        state["cot_log"].append(f"Error in vector_tool_fn: {str(e)}")
        return {
            **state,
            "vector_result": {"status": "error", "error_msg": str(e)},
            "step": "complete"
        }