from langgraph.graph import StateGraph
from langchain_groq.chat_models import ChatGroq
from tools.raster_tool import raster_tool_fn
from tools.vector_tool import vector_tool_fn
from tools.disaster_tool import disaster_safe_tool_fn
from tools.ranking_tool import ranking_tool_fn
from tools.suitability_tool import suitability_tool_fn

import osmnx as ox
import os
import ee
import geemap
import geopandas as gpd
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
os.makedirs("data", exist_ok=True)

# Initialize LLM and Earth Engine
llm = ChatGroq(model="llama3-8b-8192")
ee.Authenticate(auth_mode='notebook')
ee.Initialize()

# ---------------------- Helpers ----------------------

def fetch_boundary(region):
    import re
    clean_region = re.sub(r"[^a-zA-Z0-9\s]", "", region)
    clean_region = re.sub(r"\s+(that|which|with|for|in|near|from)\s.*", "", clean_region).strip()

    path = f"data/{clean_region}_boundary.geojson"
    if not os.path.exists(path):
        try:
            gdf = ox.geocode_to_gdf(clean_region)
            gdf.to_file(path, driver="GeoJSON")
        except Exception as e:
            raise RuntimeError(f"Failed to fetch boundary for '{clean_region}': {e}")
    return path



def fetch_dem(region):
    region_path = fetch_boundary(region)
    dem_path = f"data/srtm_{region}.tif"
    if os.path.exists(dem_path):
        return dem_path

    gdf = gpd.read_file(region_path)
    bounds = gdf.total_bounds  # [minx, miny, maxx, maxy]
    dem = ee.Image("USGS/SRTMGL1_003").clip(ee.Geometry.BBox(*bounds))
    geemap.download_ee_image(dem, filename=dem_path, scale=30, crs='EPSG:4326')
    return dem_path

# ---------------------- Reasoning Node (with LLM) ----------------------

def reasoning_node(state):
    import re
    query = state.get("query", "").lower()
    state["cot_log"].append(f"Received query: '{query}'")

    # Extract region
    match = re.search(r'(?:in|around|near|buffer)\s+([a-zA-Z ,]+)', query)
    region = match.group(1).strip() if match else "India"
    state["region"] = region.replace(" ", "_")
    state["cot_log"].append(f"Extracted region: '{region}'")

    # Fetch region boundary and DEM
    region_path = fetch_boundary(region)
    state["cot_log"].append(f"Fetched boundary: {region_path}")
    dem_path = fetch_dem(region)
    state["cot_log"].append(f"Fetched DEM: {dem_path}")

    # Optional: Extract top_n for ranking
    match_n = re.search(r'(top|best)\s+(\d+)', query)
    if match_n:
        state["top_n"] = int(match_n.group(2))
        state["cot_log"].append(f"Extracted top_n: {state['top_n']}")

    # Optional: Extract buffer distance
    match_buffer = re.search(r'buffer\s+(\d{2,5})\s*m?', query)
    buffer_distance = int(match_buffer.group(1)) if match_buffer else 1000
    if match_buffer:
        state["cot_log"].append(f"Extracted buffer distance: {buffer_distance}m")

    # Optional: Extract threshold for elevation
    match_thresh = re.search(r'(?:above|below|under|over|greater than|less than)?\s*(\d{2,5})\s*m?', query)
    threshold = int(match_thresh.group(1)) if match_thresh else 50
    comparison = "below"  # default
    if "above" in query or "greater than" in query or "over" in query:
        comparison = "above"
    elif "below" in query or "less than" in query or "under" in query:
        comparison = "below"

    # Routing logic
    if "rank" in query or "top" in query:
        state["cot_log"].append("Routing to ranking_analysis")
        return {
            **state,
            "suitability_output": f"data/{state['region']}_suitability.tif",
            "map_path": f"data/{state['region']}_top_{state.get('top_n', 5)}_locations.geojson",
            "map_title": "📍 Top Ranked Locations",
            "step": "ranking_analysis"
        }
    
    elif any(term in query for term in ["disaster", "hazard", "safe zone", "safe areas", "risk", "safe"]):
        state["cot_log"].append("Routing to disaster_safe_analysis")

        # Extract threshold
        match_thresh = re.search(r'(?:below|under|less than)\\s*(\\d{2,5})\\s*m?', query)
        threshold = int(match_thresh.group(1)) if match_thresh else 50
        comparison = "below"
        
        # You can allow 'above' threshold hazard detection too, if needed
        if "above" in query or "greater than" in query or "over" in query:
            comparison = "above"
            threshold = int(match_thresh.group(1)) if match_thresh else 50

        state["threshold"] = threshold
        state["comparison"] = comparison
        state["cot_log"].append(f"Extracted hazard threshold: {comparison} {threshold}m")

        # Path to hazard mask (make it dynamic)
        hazard_mask_path = f"data/{state['region']}_mask_{comparison}_{threshold}m.tif"
        state["hazard_mask_path"] = hazard_mask_path
        state["region_path"] = region_path

        # Check if hazard mask exists; if not, you could optionally generate it
        if not os.path.exists(hazard_mask_path):
            state["cot_log"].append(f"⚠ Hazard mask file does not exist: {hazard_mask_path}")
            return {
                **state,
                "step": "complete",
                "error": f"Hazard mask not found: {hazard_mask_path}"
            }

        return {
            **state,
            "map_path": f"data/{state['region']}_safe_zones.geojson",
            "map_title": "🛟 Disaster Safe Zones",
            "step": "disaster_safe_analysis"
        }

    elif "suitable" in query or "suitability" in query:
        state["cot_log"].append("Routing to suitability_analysis")
        return {
            **state,
            "region_path": region_path,
            "dem_path": dem_path,
            "map_path": f"data/{state['region']}_suitability.tif",
            "map_title": "🗺️ Suitability Map",
            "step": "suitability_analysis"
        }

    elif any(term in query for term in ["elevation", "height", "meters", "m", "above", "below", "less than", "greater than"]):
        state["cot_log"].append(f"Extracted threshold: {threshold}m")
        state["cot_log"].append(f"Comparison direction: {comparison}")
        return {
            **state,
            "region_path": region_path,
            "dem_path": dem_path,
            "threshold": threshold,
            "comparison": comparison,
            "map_path": f"data/{state['region']}_mask_{comparison}_{threshold}m.geojson",
            "map_title": f"🌄 Elevation {comparison.title()} {threshold}m",
            "step": "raster_analysis"
        }

    

    else:
        state["cot_log"].append("Routing to vector_analysis")
        return {
            **state,
            "vector_path": region_path,
            "buffer_distance": buffer_distance,
            "map_path": f"data/{state['region']}_buffered.geojson",
            "map_title": "📏 Buffered Region",
            "step": "vector_analysis"
        }

# ---------------------- Final Node ----------------------

def observation_node(state):
    state["cot_log"].append("✅ Workflow complete")
    return {**state, "step": "complete"}

# ---------------------- LangGraph Setup ----------------------

workflow = StateGraph(state_schema=dict)
workflow.add_node("reasoning", reasoning_node)
workflow.add_node("raster_analysis", raster_tool_fn)
workflow.add_node("vector_analysis", vector_tool_fn)
workflow.add_node("suitability_analysis", suitability_tool_fn)
workflow.add_node("ranking_analysis", ranking_tool_fn)
workflow.add_node("disaster_safe_analysis", disaster_safe_tool_fn)
workflow.add_node("observe", observation_node)

workflow.set_entry_point("reasoning")
workflow.add_conditional_edges("reasoning", lambda s: s["step"])
workflow.add_edge("raster_analysis", "observe")
workflow.add_edge("vector_analysis", "observe")
workflow.add_edge("suitability_analysis", "observe")
workflow.add_edge("ranking_analysis", "observe")
workflow.add_edge("disaster_safe_analysis", "observe")
workflow.add_conditional_edges("observe", lambda s: s["step"])

app = workflow.compile()

if __name__ == "__main__":
    query = input("🧠 Ask your spatial query: ")
    state = {"query": query, "cot_log": []}
    final = app.invoke(state)

    print("\n🧩 Chain of Thought:")
    for step in final.get("cot_log", []):
        print(" -", step)

    print("\n📦 Final Output State:")
    print({k: v for k, v in final.items() if k != "cot_log"})
