import streamlit as st

# Set matplotlib backend first (for Streamlit Cloud)
import matplotlib
matplotlib.use('Agg')  # For non-GUI environments

import matplotlib.pyplot as plt
import matplotlib.patches as patches
import pandas as pd
from shapely.geometry import box
import numpy as np
from PIL import Image
import io
import sys
import traceback

# Scratch coordinate system definition
SCRATCH_WIDTH = 480
SCRATCH_HEIGHT = 360
SCRATCH_X_MIN = -240
SCRATCH_X_MAX = 240
SCRATCH_Y_MIN = -180
SCRATCH_Y_MAX = 180

# Resource limits to prevent crashes
MAX_NODES = 5000
MAX_EDGES = 15000
DOWNLOAD_TIMEOUT = 60  # seconds

st.set_page_config(
    page_title="OSM→Scratch Coordinate Converter",
    page_icon="🗺️",
    layout="wide"
)

st.title("🗺️ OSM Road Network → Scratch Coordinate System Converter")
st.markdown("Convert OpenStreetMap data to Scratch coordinate system (-240~240, -180~180)")
st.markdown("---")

# Sidebar settings
st.sidebar.header("⚙️ Settings")

# Debug info
with st.sidebar.expander("🔍 System Info"):
    st.text(f"Streamlit: {st.__version__}")
    st.text(f"Python: {sys.version.split()[0]}")

# Area name input
area_name = st.sidebar.text_input("Area Name", value="MyArea", help="Used for output file names")

# Preset selection
st.sidebar.subheader("📍 Preset Coordinates")
preset = st.sidebar.selectbox(
    "Select Location",
    options=[
        "Custom",
        "Tokyo Tower Area (Small)",
        "Shibuya Station Area (Small)", 
        "Kamakura City Center (Small)",
        "Kyoto Station Area (Small)",
        "Osaka Castle Area (Small)"
    ]
)

# Preset coordinates (smaller areas to prevent timeout)
presets = {
    "Tokyo Tower Area (Small)": (35.6595, 35.6575, 139.7465, 139.7445),
    "Shibuya Station Area (Small)": (35.6620, 35.6600, 139.7020, 139.7000),
    "Kamakura City Center (Small)": (35.3220, 35.3180, 139.5520, 139.5480),
    "Kyoto Station Area (Small)": (34.9890, 34.9850, 135.7630, 135.7590),
    "Osaka Castle Area (Small)": (34.6890, 34.6850, 135.5290, 135.5250)
}

# Coordinate range input
st.sidebar.subheader("📍 Acquisition Range (Latitude/Longitude)")

if preset != "Custom":
    north, south, east, west = presets[preset]
    st.sidebar.info(f"✅ {preset} selected")
else:
    col1, col2 = st.sidebar.columns(2)
    with col1:
        north = st.number_input("North Latitude", value=35.360, format="%.6f")
        south = st.number_input("South Latitude", value=35.350, format="%.6f")
    with col2:
        east = st.number_input("East Longitude", value=139.560, format="%.6f")
        west = st.number_input("West Longitude", value=139.550, format="%.6f")

# Display range
st.sidebar.markdown(f"""
**Current Range:**
- North: {north:.6f}
- South: {south:.6f}
- East: {east:.6f}
- West: {west:.6f}
""")

# Calculate area size warning
lat_diff = abs(north - south)
lon_diff = abs(east - west)
area_size = lat_diff * lon_diff

if area_size > 0.001:
    st.sidebar.warning(f"⚠️ Large area selected ({area_size:.6f}°²). May take longer or fail.")
    st.sidebar.info("💡 Recommended: < 0.001°² for best results")
elif area_size > 0.0005:
    st.sidebar.info(f"📊 Medium area: {area_size:.6f}°²")
else:
    st.sidebar.success(f"✅ Optimal area size: {area_size:.6f}°²")

# Network type selection
network_type = st.sidebar.selectbox(
    "Network Type",
    options=['drive', 'walk', 'all', 'bike'],
    index=0,
    help="drive: roads, walk: sidewalks, all: all roads, bike: bike paths"
)

# Coordinate conversion function
def latlon_to_scratch(lat, lon, bounds):
    """
    Convert latitude/longitude to Scratch coordinate system
    
    Args:
        lat: Latitude
        lon: Longitude
        bounds: (north, south, east, west)
    
    Returns:
        (x, y): Scratch coordinates
    """
    north, south, east, west = bounds
    
    # Normalize (to 0~1 range)
    x_norm = (lon - west) / (east - west) if (east - west) != 0 else 0.5
    y_norm = (north - lat) / (north - south) if (north - south) != 0 else 0.5
    
    # Scale to Scratch coordinate system
    x_scratch = SCRATCH_X_MIN + x_norm * (SCRATCH_X_MAX - SCRATCH_X_MIN)
    y_scratch = SCRATCH_Y_MIN + y_norm * (SCRATCH_Y_MAX - SCRATCH_Y_MIN)
    
    return round(x_scratch, 2), round(y_scratch, 2)

def convert_to_scratch_format(G, bounds):
    """
    Convert OSM graph to Scratch coordinate system DataFrame
    
    Returns:
        nodes_df: Node data (ID, X, Y, Latitude, Longitude)
        edges_df: Edge data (FromID, ToID, Distance)
    """
    # Create node data
    nodes_data = []
    node_id_map = {}  # Mapping OSM node ID → sequential ID
    
    for i, (osm_id, data) in enumerate(G.nodes(data=True), start=1):
        lat = data['y']
        lon = data['x']
        x_scratch, y_scratch = latlon_to_scratch(lat, lon, bounds)
        
        nodes_data.append({
            'ID': i,
            'X': x_scratch,
            'Y': y_scratch,
            'Latitude': round(lat, 6),
            'Longitude': round(lon, 6),
            'OSM_ID': osm_id
        })
        node_id_map[osm_id] = i
    
    nodes_df = pd.DataFrame(nodes_data)
    
    # Create edge data
    edges_data = []
    
    for u, v, data in G.edges(data=True):
        from_id = node_id_map[u]
        to_id = node_id_map[v]
        
        # Calculate distance (in meters)
        distance = data.get('length', 0)
        
        edges_data.append({
            'FromID': from_id,
            'ToID': to_id,
            'Distance': round(distance, 2)
        })
        
        # Add reverse direction (bidirectional)
        edges_data.append({
            'FromID': to_id,
            'ToID': from_id,
            'Distance': round(distance, 2)
        })
    
    edges_df = pd.DataFrame(edges_data)
    
    return nodes_df, edges_df

def generate_map_image_safe(nodes_df, edges_df, bounds):
    """
    Generate map image with safe error handling
    Uses simple visualization without external tiles to avoid 400 errors
    """
    try:
        # Try to import optional dependencies
        import geopandas as gpd
        from shapely.geometry import LineString
        import contextily as cx
        
        north, south, east, west = bounds

        # Convert edges to GeoDataFrame
        edge_lines = []
        for _, row in edges_df.iterrows():
            from_node = nodes_df[nodes_df['ID'] == row['FromID']].iloc[0]
            to_node = nodes_df[nodes_df['ID'] == row['ToID']].iloc[0]
            edge_lines.append(LineString([
                (from_node['Longitude'], from_node['Latitude']),
                (to_node['Longitude'], to_node['Latitude'])
            ]))
        
        gdf_edges = gpd.GeoDataFrame(geometry=edge_lines, crs="EPSG:4326").to_crs(epsg=3857)

        # Drawing range
        xmin, ymin, xmax, ymax = gdf_edges.total_bounds

        # Create figure
        fig, ax = plt.subplots(figsize=(480/72, 360/72), dpi=72)
        gdf_edges.plot(ax=ax, color='red', linewidth=1.2, alpha=0.8, zorder=2)

        # Try to add basemap (may fail)
        try:
            cx.add_basemap(
                ax,
                crs=gdf_edges.crs,
                source="https://tile.openstreetmap.org/{z}/{x}/{y}.png",
                zoom=16,
                attribution="© OpenStreetMap contributors"
            )
        except Exception as e:
            # Fallback to simple background
            ax.set_facecolor("#f0f0f0")
            st.warning(f"⚠️ Could not load map tiles: {str(e)[:100]}")

        # Fix range
        ax.set_xlim(xmin, xmax)
        ax.set_ylim(ymin, ymax)
        ax.axis("off")
        plt.tight_layout(pad=0)

        # Convert to image
        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=72, bbox_inches='tight', pad_inches=0)
        buf.seek(0)
        img = Image.open(buf).resize((480, 360), Image.Resampling.LANCZOS)
        plt.close(fig)
        return img
        
    except ImportError as e:
        st.warning(f"⚠️ Optional dependencies not available: {e}")
        # Return simple version
        return generate_simple_map_image(nodes_df, edges_df)
    except Exception as e:
        st.warning(f"⚠️ Map generation failed: {str(e)}")
        # Return simple version
        return generate_simple_map_image(nodes_df, edges_df)

def generate_simple_map_image(nodes_df, edges_df):
    """
    Generate simple road network image (480x360 pixels)
    No external dependencies, roads only display
    
    Returns:
        PIL Image: 480x360 pixel image
    """
    try:
        # Set figure size precisely
        fig, ax = plt.subplots(figsize=(480/72, 360/72), dpi=72)
        
        # Match Scratch coordinate system
        ax.set_xlim(SCRATCH_X_MIN, SCRATCH_X_MAX)
        ax.set_ylim(SCRATCH_Y_MIN, SCRATCH_Y_MAX)
        ax.set_aspect('equal')
        
        # White background
        ax.set_facecolor('white')
        fig.patch.set_facecolor('white')
        
        # Hide axes
        ax.axis('off')
        
        # Draw edges (roads) - avoid duplicates
        edge_dict = {}
        for _, row in edges_df.iterrows():
            from_id = row['FromID']
            to_id = row['ToID']
            edge_key = tuple(sorted([from_id, to_id]))
            
            if edge_key not in edge_dict:
                edge_dict[edge_key] = True
                
                from_node = nodes_df[nodes_df['ID'] == from_id].iloc[0]
                to_node = nodes_df[nodes_df['ID'] == to_id].iloc[0]
                
                ax.plot([from_node['X'], to_node['X']], 
                       [from_node['Y'], to_node['Y']], 
                       color='black', linewidth=2, alpha=1.0, zorder=1)
        
        # Save without margins
        plt.subplots_adjust(left=0, right=1, top=1, bottom=0)
        
        # Save image to byte stream
        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=72, bbox_inches='tight', 
                    pad_inches=0, facecolor='white')
        buf.seek(0)
        
        # Convert to PIL Image
        img = Image.open(buf)
        
        # Resize to exactly 480x360
        img = img.resize((480, 360), Image.Resampling.LANCZOS)
        
        plt.close(fig)
        
        return img
        
    except Exception as e:
        st.error(f"Failed to generate image: {str(e)}")
        # Return blank image as last resort
        return Image.new('RGB', (480, 360), color='white')

def download_osm_data_safe(polygon, network_type, timeout=DOWNLOAD_TIMEOUT):
    """
    Safely download OSM data with timeout and error handling
    """
    try:
        import osmnx as ox
        
        # Download with timeout protection
        st.info(f"⏱️ Timeout set to {timeout} seconds")
        
        G = ox.graph_from_polygon(
            polygon, 
            network_type=network_type,
            simplify=True,
            retain_all=False
        )
        
        return G
        
    except ImportError:
        st.error("❌ OSMnx library not installed. Please add 'osmnx' to requirements.txt")
        return None
    except Exception as e:
        error_msg = str(e)
        if "timeout" in error_msg.lower():
            st.error("⏱️ Download timed out. Please try a smaller area.")
        elif "404" in error_msg or "400" in error_msg:
            st.error("🌐 Network error. The OSM server may be temporarily unavailable.")
        else:
            st.error(f"❌ Failed to download OSM data: {error_msg[:200]}")
        return None

# Main area
st.header("📊 Data Acquisition and Conversion")

# Scratch coordinate system explanation
with st.expander("ℹ️ About Scratch Coordinate System"):
    st.markdown("""
    **Scratch Coordinate System Features:**
    - X coordinate range: -240 ~ +240 (screen width 480 pixels)
    - Y coordinate range: -180 ~ +180 (screen height 360 pixels)
    - Origin (0, 0) is at screen center
    - Right is positive X, up is positive Y
    
    **Conversion Method:**
    1. Normalize latitude/longitude within specified range (0~1)
    2. Scale to Scratch coordinate system
    3. Round to 2 decimal places
    
    **Resource Limits:**
    - Max nodes: {MAX_NODES:,}
    - Max edges: {MAX_EDGES:,}
    - Download timeout: {DOWNLOAD_TIMEOUT}s
    """.format(MAX_NODES=MAX_NODES, MAX_EDGES=MAX_EDGES, DOWNLOAD_TIMEOUT=DOWNLOAD_TIMEOUT))

# Important notes
st.info("""
💡 **Tips for Success:**
- Start with small areas (use presets)
- If download fails, try a smaller area
- Network type 'drive' is usually fastest
- Avoid peak hours for better performance
""")

# Google Maps link (for range confirmation)
center_lat = (north + south) / 2
center_lon = (east + west) / 2
st.markdown(f"📍 [Check range on Google Maps](https://www.google.com/maps/@{center_lat},{center_lon},15z)")

# Data acquisition button
if st.button("🚀 Start Data Acquisition & Conversion", type="primary", use_container_width=True):
    
    # Input validation
    if north <= south:
        st.error("❌ North latitude must be greater than south latitude")
        st.stop()
    if east <= west:
        st.error("❌ East longitude must be greater than west longitude")
        st.stop()
    
    # Area size check
    if area_size > 0.002:
        st.error("❌ Area too large! Please select an area < 0.002°²")
        st.info(f"Current area: {area_size:.6f}°²")
        st.stop()
    
    try:
        # Progress bar
        progress_bar = st.progress(0)
        status = st.empty()
        
        # Create polygon
        polygon = box(west, south, east, north)
        bounds = (north, south, east, west)
        
        # Download road network data
        status.text("📡 Downloading road network from OpenStreetMap...")
        progress_bar.progress(10)
        
        G = download_osm_data_safe(polygon, network_type)
        
        if G is None:
            st.error("❌ Failed to download data. Please try again with a smaller area.")
            st.stop()
        
        progress_bar.progress(40)
        
        # Check data size
        num_nodes = len(G.nodes())
        num_edges = len(G.edges())
        
        status.text(f"✅ Download complete: {num_nodes} nodes, {num_edges} edges")
        
        if num_nodes > MAX_NODES:
            st.error(f"❌ Too many nodes! ({num_nodes:,} > {MAX_NODES:,})")
            st.info("Please select a smaller area or try 'drive' network type")
            st.stop()
        
        if num_edges > MAX_EDGES:
            st.error(f"❌ Too many edges! ({num_edges:,} > {MAX_EDGES:,})")
            st.info("Please select a smaller area")
            st.stop()
        
        # Convert to Scratch coordinate system
        status.text("🔄 Converting to Scratch coordinate system...")
        progress_bar.progress(60)
        
        nodes_df, edges_df = convert_to_scratch_format(G, bounds)
        
        progress_bar.progress(70)
        
        # Generate images
        status.text("🎨 Generating map images...")
        
        simple_map_image = generate_simple_map_image(nodes_df, edges_df)
        progress_bar.progress(85)
        
        map_image = generate_map_image_safe(nodes_df, edges_df, bounds)
        progress_bar.progress(95)
        
        # Generate CSV
        node_csv = nodes_df[['ID', 'X', 'Y', 'Latitude', 'Longitude']].to_csv(index=False)
        edge_csv = edges_df.to_csv(index=False)
        
        # Convert images to byte stream
        img_buf = io.BytesIO()
        map_image.save(img_buf, format='PNG')
        img_bytes = img_buf.getvalue()
        
        simple_img_buf = io.BytesIO()
        simple_map_image.save(simple_img_buf, format='PNG')
        simple_img_bytes = simple_img_buf.getvalue()
        
        progress_bar.progress(100)
        status.text("✅ Conversion complete!")
        
        # Display results
        st.success("🎉 Data acquisition and conversion complete!")
        
        # Statistics
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Node Count", f"{len(nodes_df):,}")
        with col2:
            st.metric("Edge Count", f"{len(edges_df):,}")
        with col3:
            st.metric("X Range", f"{nodes_df['X'].min():.1f} ~ {nodes_df['X'].max():.1f}")
        with col4:
            st.metric("Y Range", f"{nodes_df['Y'].min():.1f} ~ {nodes_df['Y'].max():.1f}")
        
        # Coordinate range confirmation
        st.info(f"""
        **Conversion Information:**
        - Latitude range: {south:.6f} ~ {north:.6f}
        - Longitude range: {west:.6f} ~ {east:.6f}
        - Network type: {network_type}
        - Scratch coordinates: X({SCRATCH_X_MIN}~{SCRATCH_X_MAX}), Y({SCRATCH_Y_MIN}~{SCRATCH_Y_MAX})
        - Image size: 480 x 360 pixels
        """)
        
        # Map image display
        st.subheader("🗺️ Generated Map Images")
        
        tab1, tab2 = st.tabs(["🎨 Simple Version (Recommended)", "📊 With Background Map"])
        
        with tab1:
            st.image(simple_map_image, caption="Road Network (roads only)", use_container_width=True)
            st.caption("✅ Simple display with roads only. Best for Scratch background image")
        
        with tab2:
            st.image(map_image, caption="Road Network (with map background)", use_container_width=True)
            st.caption("📍 With geographic context (may show gray background if tiles unavailable)")
        
        # Data preview
        with st.expander("📊 Node Data Preview (Scratch Coordinate System)"):
            st.dataframe(
                nodes_df[['ID', 'X', 'Y', 'Latitude', 'Longitude']].head(20), 
                use_container_width=True
            )
            
            # Coordinate distribution
            col1, col2 = st.columns(2)
            with col1:
                st.write("**X Coordinate Distribution:**")
                st.write(nodes_df['X'].describe())
            with col2:
                st.write("**Y Coordinate Distribution:**")
                st.write(nodes_df['Y'].describe())
        
        with st.expander("📊 Edge Data Preview"):
            st.dataframe(edges_df.head(20), use_container_width=True)
            st.write(f"**Total Edge Count:** {len(edges_df):,} (including bidirectional)")
            st.write(f"**Average Distance:** {edges_df['Distance'].mean():.2f}m")
            st.write(f"**Total Distance:** {edges_df['Distance'].sum()/2:.2f}m (one direction)")
        
        # Sample code display
        with st.expander("💻 Usage Example in Scratch"):
            st.code("""
// Example of loading node data
Add [ID column] to list "NodeID"
Add [X column] to list "NodeX"
Add [Y column] to list "NodeY"

// Example of loading edge data
Add [FromID column] to list "LinkFrom"
Add [ToID column] to list "LinkTo"

// Get node coordinates
[Item (node number) of list "NodeX"] → X coordinate
[Item (node number) of list "NodeY"] → Y coordinate

// Move to that coordinate
Go to x: (X coordinate) y: (Y coordinate)

// Draw a line between connected nodes
Pen down
Repeat for each edge:
  Go to node [FromID]
  Go to node [ToID]
Pen up
""", language="text")
        
        # Download buttons
        st.subheader("📥 Download")
        
        # CSV download
        st.markdown("**📊 CSV Data**")
        col1, col2 = st.columns(2)
        
        with col1:
            st.download_button(
                label="📥 Node CSV (ID, X, Y, Lat, Lon)",
                data=node_csv,
                file_name=f"{area_name}_Nodes_Scratch.csv",
                mime='text/csv',
                type="primary",
                use_container_width=True
            )
        
        with col2:
            st.download_button(
                label="📥 Edge CSV (FromID, ToID, Distance)",
                data=edge_csv,
                file_name=f"{area_name}_Edges_Scratch.csv",
                mime='text/csv',
                type="primary",
                use_container_width=True
            )
        
        # Image download
        st.markdown("**🖼️ Map Images (480x360px)**")
        col1, col2 = st.columns(2)
        
        with col1:
            st.download_button(
                label="📥 Simple Version (PNG) - Recommended",
                data=simple_img_bytes,
                file_name=f"{area_name}_Map_Simple.png",
                mime='image/png',
                type="primary",
                use_container_width=True
            )
        
        with col2:
            st.download_button(
                label="📥 With Background Map (PNG)",
                data=img_bytes,
                file_name=f"{area_name}_Map_With_Background.png",
                mime='image/png',
                type="secondary",
                use_container_width=True
            )
        
        # Detailed data download
        with st.expander("📥 Download Detailed Data"):
            full_node_csv = nodes_df.to_csv(index=False)
            st.download_button(
                label="📥 Detailed Node CSV (including OSM_ID)",
                data=full_node_csv,
                file_name=f"{area_name}_Nodes_Full.csv",
                mime='text/csv',
                use_container_width=True
            )
            
            st.markdown("---")
            st.markdown("**About OSM_ID:** Original OpenStreetMap node identifiers for reference")
        
    except Exception as e:
        st.error(f"❌ An unexpected error occurred")
        
        # Show detailed error in expander
        with st.expander("🔍 Error Details (for debugging)"):
            st.code(traceback.format_exc())
        
        st.info("""
        💡 **Troubleshooting Tips:**
        - Try selecting a smaller area
        - Use one of the preset locations
        - Try 'drive' network type instead of 'all'
        - Check your internet connection
        - Wait a few minutes and try again (server may be busy)
        """)

# Footer
st.markdown("---")
st.markdown("""
<div style='text-align: center; color: gray; font-size: 0.9em;'>
    <p>Made with ❤️ for Scratch programmers</p>
    <p>Data © <a href="https://www.openstreetmap.org/copyright" target="_blank">OpenStreetMap contributors</a></p>
    <p style='font-size: 0.8em; margin-top: 10px;'>
        ⚠️ If you experience connection issues, try reducing the area size or using preset locations
    </p>
</div>
""", unsafe_allow_html=True)
