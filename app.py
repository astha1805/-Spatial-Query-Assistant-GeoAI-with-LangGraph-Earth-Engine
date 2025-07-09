import streamlit as st
import geopandas as gpd
import folium
from streamlit_folium import st_folium
from main import app  # Your LangGraph workflow
import os

st.set_page_config(page_title="🧠 Spatial LLM Map", layout="wide")
st.title("🗺 Spatial Query Assistant")

# Initialize session state
if "final" not in st.session_state:
    st.session_state.final = None

query = st.text_input("🔍 Ask your spatial query:", placeholder="e.g., Show me areas safe from flooding in Surat")

# Run the query
if st.button("Run Query") and query.strip():
    with st.spinner("🧠 Processing your query..."):
        state = {"query": query, "cot_log": []}
        st.session_state.final = app.invoke(state)

# Retrieve result
final = st.session_state.final

if final:
    st.subheader("🤖 Chain of Thought")
    for step in final.get("cot_log", []):
        st.markdown(f"- {step}")

    st.subheader("📦 Final Output State")
    st.json({k: v for k, v in final.items() if k != "cot_log"})

    # Determine map path and title
    map_path = final.get("map_path")
    map_title = final.get("map_title", "🗺 Spatial Result")
    style_fn = None
    legend_html = ""

    # 🧪 Debugging Information
    st.subheader("🧪 Debugging Information")
    st.write("🧭 Map Path from state:", map_path)
    st.write("📂 File Exists:", os.path.exists(map_path) if map_path else False)
    if os.path.exists("data"):
        st.write("📁 Files in /data/:", os.listdir("data"))
    else:
        st.write("🚫 'data' directory not found!")

    if map_path and os.path.exists(map_path):
        # Conditional styling and legend
        if "safe_zones" in map_path:
            map_title = "🛡 Disaster Safe Zones"

            def style_fn(feature):
                return {"fillColor": "#ff4848", "color": "#cc0000", "weight": 2, "fillOpacity": 0.5}

            legend_html = """
            <div style="position: fixed;
                        bottom: 30px; left: 30px; width: 180px; height: 60px;
                        background-color: white; border:2px solid grey; z-index:9999; font-size:13px;
                        padding: 10px;">
                <b>Legend</b><br>
                <i style="background:#ff4d4d; width: 12px; height: 12px; float: left; margin-right: 5px; opacity: 0.7;"></i> Safe Zone
            </div>
            """

        elif "suitability" in map_path:
            map_title = "✅ Suitable Areas"

            def style_fn(feature):
                return {"fillColor": "#4CAF50", "color": "#2E7D32", "weight": 2, "fillOpacity": 0.5}

            legend_html = """
            <div style="position: fixed;
                        bottom: 30px; left: 30px; width: 180px; height: 60px;
                        background-color: white; border:2px solid grey; z-index:9999; font-size:13px;
                        padding: 10px;">
                <b>Legend</b><br>
                <i style="background:#4CAF50; width: 12px; height: 12px; float: left; margin-right: 5px; opacity: 0.7;"></i> Suitable Area
            </div>
            """

        elif "buffered" in map_path:
            map_title = "🟢 Buffered Region"

        elif "mask" in map_path:
            map_title = "🌄 Elevation Masked Area"

        # Display map
        try:
            gdf = gpd.read_file(map_path)
            if not gdf.empty:
                bounds = gdf.total_bounds
                m = folium.Map(
                    location=[(bounds[1] + bounds[3]) / 2, (bounds[0] + bounds[2]) / 2],
                    zoom_start=7
                )

                folium.GeoJson(
                    gdf,
                    name="Geo Output",
                    style_function=style_fn if style_fn else None
                ).add_to(m)


                if legend_html:
                    m.get_root().html.add_child(folium.Element(legend_html))

                st.subheader(map_title)
                st_folium(m, width=800, height=500)
            else:
                st.warning("⚠ GeoDataFrame is empty.")
        except Exception as e:
            st.error(f"❌ Error displaying map: {e}")
    else:
        st.warning("⚠ No map output available.")

    # Download buttons (for raster and DEM)
    if final.get("dem_path") and os.path.exists(final["dem_path"]):
        st.download_button("📥 Download DEM", open(final["dem_path"], "rb"), file_name=os.path.basename(final["dem_path"]))

    if final.get("suitability_output") and os.path.exists(final["suitability_output"]):
        st.download_button("📥 Download Suitability Raster", open(final["suitability_output"], "rb"), file_name=os.path.basename(final["suitability_output"]))

    if final.get("raster_result", {}).get("raster_output") and os.path.exists(final["raster_result"]["raster_output"]):
        st.download_button("📥 Download Masked Raster", open(final["raster_result"]["raster_output"], "rb"),
                           file_name=os.path.basename(final["raster_result"]["raster_output"]))
