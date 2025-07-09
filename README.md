# -Spatial Query Assistant GeoAI with LangGraph and Earth Engine
This project is a natural language-powered spatial analysis tool that enables users to ask complex geospatial questions like:

“Show me areas in Gujarat below 50 meters elevation”
“Give me a 1km buffer around Shimla”
“Which areas in Chennai are safe from flooding?”

It uses a LangGraph-based reasoning engine built on top of ChatGroq + LangChain and integrates with Earth Engine, raster/vector GIS tools, and OpenStreetMap data.

# 🌟 Features

🗺 Natural language query interpretation using LLM (LLaMA3 via ChatGroq)

🛰 Elevation-based raster analysis (via Google Earth Engine)

📍 Vector buffer and spatial operations (via GeoPandas & OSMnx)

🌧 Flood-safe zone extraction using raster masks

✅ Suitability and ranking toolkits for spatial planning

🧩 Chain-of-thought logging for explainable reasoning

📍 Interactive map rendering using Folium in Streamlit

# 📥 Sample Queries

“Give me areas below 50m in Kerala”

“Show flood-safe areas in Chennai”

“Top 5 suitable regions for housing in Uttarakhand”

“Buffer 1km around Pune city center”

🔁 How It Works
LLM parses query → extracts intent, region, parameters
Chooses relevant tool (raster/vector/suitability/disaster-safe)
Downloads boundary & DEM from OSM/Google Earth Engine
Executes geospatial logic (e.g., masking, buffering, ranking)
Displays results with download + map output
