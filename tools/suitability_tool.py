import os
import rasterio
import numpy as np

def suitability_tool_fn(state):
    try:
        criteria_paths = state["criteria_paths"]  # list of raster paths
        weights = state["weights"]                # list of weights
        output_path = f"data/{state['region']}_suitability.tif"
        os.makedirs("data", exist_ok=True)

        if len(criteria_paths) != len(weights):
            raise ValueError("Mismatch between number of criteria paths and weights.")

        weighted_sum = None
        nodata_mask = None

        for path, weight in zip(criteria_paths, weights):
            with rasterio.open(path) as src:
                data = src.read(1).astype(np.float32)
                mask = data == src.nodata if src.nodata is not None else np.isnan(data)

                if weighted_sum is None:
                    weighted_sum = np.zeros_like(data, dtype=np.float32)
                    nodata_mask = mask.copy()
                    meta = src.meta.copy()
                else:
                    nodata_mask |= mask  # combine masks from all layers

                data[mask] = 0  # set nodata to 0 before weighting
                weighted_sum += weight * data

        # Mask nodata before normalization
        valid_data = np.where(~nodata_mask, weighted_sum, np.nan)

        min_val = np.nanmin(valid_data)
        max_val = np.nanmax(valid_data)

        if max_val == min_val:
            norm_data = np.zeros_like(valid_data, dtype=np.float32)
        else:
            norm_data = (valid_data - min_val) / (max_val - min_val)

        # Replace NaNs (from nodata) with 0 or set explicit nodata
        norm_data = np.where(np.isnan(norm_data), 0, norm_data)

        meta.update(dtype='float32', count=1, nodata=0)

        with rasterio.open(output_path, 'w', **meta) as dst:
            dst.write(norm_data, 1)

        state["cot_log"].append(f"Generated suitability map at {output_path}")
        return {
            **state,
            "suitability_output": output_path,
            "step": "complete"
        }

    except Exception as e:
        state["cot_log"].append(f"Error in suitability_tool_fn: {str(e)}")
        return {
            **state,
            "step": "complete",
            "suitability_output": None,
            "error": str(e)
        }