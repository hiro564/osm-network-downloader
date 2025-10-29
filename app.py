import streamlit as st

import matplotlib
matplotlib.use('Agg')

import matplotlib.pyplot as plt
import pandas as pd
from shapely.geometry import box, LineString
from PIL import Image
import io
import sys
import traceback

# 定数設定
MAX_NODES = 5000
MAX_EDGES = 15000
DOWNLOAD_TIMEOUT = 60

# Streamlit設定
st.set_page_config(
    page_title="OSM Road Network Downloader",
    page_icon="🗺️",
    layout="wide"
)

st.title("🗺️ OSM Road Network Downloader (CSV + Map Image)")
st.markdown("Download OpenStreetMap road network data as CSV (Lat/Lon) and visualize it on a white-background 480×360 image.")
st.markdown("---")

# Sidebar
st.sidebar.header("⚙️ Settings")

area_name = st.sidebar.text_input("Area Name", value="MyArea")

# Presetエリア
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

presets = {
    "Tokyo Tower Area (Small)": (35.6595, 35.6575, 139.7465, 139.7445),
    "Shibuya Station Area (Small)": (35.6620, 35.6600, 139.7020, 139.7000),
    "Kamakura City Center (Small)": (35.3220, 35.3180, 139.5520, 139.5480),
    "Kyoto Station Area (Small)": (34.9890, 34.9850, 135.7630, 135.7590),
    "Osaka Castle Area (Small)": (34.6890, 34.6850, 135.5290, 135.5250)
}

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

# エリアサイズ確認
lat_diff = abs(north - south)
lon_diff = abs(east - west)
area_size = lat_diff * lon_diff
if area_size > 0.001:
    st.sidebar.warning(f"⚠️ Large area selected ({area_size:.6f}°²). May take longer.")
elif area_size > 0.0005:
    st.sidebar.info(f"📊 Medium area: {area_size:.6f}°²")
else:
    st.sidebar.success(f"✅ Optimal area size: {area_size:.6f}°²")

# ネットワーク種別
network_type = st.sidebar.selectbox(
    "Network Type",
    options=['drive', 'walk', 'all', 'bike'],
    index=0
)

# --- 関数定義 ---
def download_osm_data_safe(polygon, network_type, timeout=DOWNLOAD_TIMEOUT):
    """OSMデータ安全取得"""
    try:
        import osmnx as ox
        G = ox.graph_from_polygon(polygon, network_type=network_type, simplify=True, retain_all=False)
        return G
    except Exception as e:
        st.error(f"OSM download failed: {e}")
        return None

def convert_to_csv_data(G):
    """OSMノード・エッジをCSVデータ化（緯度経度ベース）"""
    try:
        # ノード情報
        nodes = []
        node_id_map = {}
        for i, (node_id, data) in enumerate(G.nodes(data=True), start=1):
            nodes.append({
                "ID": i,
                "Latitude": data["y"],
                "Longitude": data["x"],
                "OSM_ID": node_id
            })
            node_id_map[node_id] = i
        nodes_df = pd.DataFrame(nodes)

        # エッジ情報
        edges = []
        for u, v, data in G.edges(data=True):
            dist = data.get("length", 0)
            edges.append({
                "FromID": node_id_map[u],
                "ToID": node_id_map[v],
                "Distance": round(dist, 2)
            })
            # 双方向追加
            edges.append({
                "FromID": node_id_map[v],
                "ToID": node_id_map[u],
                "Distance": round(dist, 2)
            })
        edges_df = pd.DataFrame(edges)

        return nodes_df, edges_df
    except Exception as e:
        st.error(f"CSV conversion failed: {e}")
        return pd.DataFrame(), pd.DataFrame()

def generate_road_image(G):
    """道路ネットワークを白背景で描画 (480x360)"""
    try:
        # ノード情報
        node_data = [(data['x'], data['y']) for node, data in G.nodes(data=True)]
        nodes_df = pd.DataFrame(node_data, columns=["Lon", "Lat"])

        # エッジ情報
        edge_lines = []
        for u, v, data in G.edges(data=True):
            u_data = G.nodes[u]
            v_data = G.nodes[v]
            edge_lines.append(LineString([(u_data['x'], u_data['y']), (v_data['x'], v_data['y'])]))

        # 範囲設定
        lon_min, lat_min, lon_max, lat_max = (
            nodes_df["Lon"].min(),
            nodes_df["Lat"].min(),
            nodes_df["Lon"].max(),
            nodes_df["Lat"].max(),
        )

        # 図作成
        fig, ax = plt.subplots(figsize=(480/72, 360/72), dpi=72)
        ax.set_facecolor("white")
        fig.patch.set_facecolor("white")
        ax.axis("off")

        # 道路描画
        for line in edge_lines:
            x, y = line.xy
            ax.plot(x, y, color="black", linewidth=1.2, alpha=0.9)

        ax.set_xlim(lon_min, lon_max)
        ax.set_ylim(lat_min, lat_max)
        plt.tight_layout(pad=0)

        # 画像に変換
        buf = io.BytesIO()
        plt.savefig(buf, format="png", dpi=72, bbox_inches="tight", pad_inches=0, facecolor="white")
        buf.seek(0)
        img = Image.open(buf).resize((480, 360), Image.Resampling.LANCZOS)
        plt.close(fig)
        return img
    except Exception as e:
        st.error(f"Image generation failed: {e}")
        return Image.new("RGB", (480, 360), color="white")

# --- メイン処理 ---
st.header("📊 Data Acquisition and Conversion")

if st.button("🚀 Start Download & Conversion", type="primary", use_container_width=True):
    if north <= south or east <= west:
        st.error("Invalid coordinate range.")
        st.stop()
    if area_size > 0.002:
        st.error("Area too large! Please select <0.002°².")
        st.stop()

    progress = st.progress(0)
    polygon = box(west, south, east, north)

    progress.progress(10)
    st.info("📡 Downloading OSM data...")
    G = download_osm_data_safe(polygon, network_type)
    if G is None:
        st.error("Download failed.")
        st.stop()

    progress.progress(50)
    st.success(f"✅ Download complete: {len(G.nodes()):,} nodes, {len(G.edges()):,} edges")

    progress.progress(70)
    st.info("🔄 Converting data to CSV format...")
    nodes_df, edges_df = convert_to_csv_data(G)

    progress.progress(80)
    st.info("🎨 Generating road network image...")
    img = generate_road_image(G)

    progress.progress(100)
    st.success("🎉 Conversion complete!")

    # 結果表示
    st.image(img, caption="Road Network (480×360px, white background)", use_container_width=True)

    # CSVプレビュー
    with st.expander("📊 Node Data Preview"):
        st.dataframe(nodes_df.head(20))
    with st.expander("📊 Edge Data Preview"):
        st.dataframe(edges_df.head(20))

    # ダウンロードボタン
    st.subheader("📥 Download")
    col1, col2, col3 = st.columns(3)
    with col1:
        node_csv = nodes_df.to_csv(index=False)
        st.download_button(
            label="📥 Node CSV (Lat/Lon)",
            data=node_csv,
            file_name=f"{area_name}_Nodes.csv",
            mime="text/csv",
            use_container_width=True
        )
    with col2:
        edge_csv = edges_df.to_csv(index=False)
        st.download_button(
            label="📥 Edge CSV (FromID, ToID, Distance)",
            data=edge_csv,
            file_name=f"{area_name}_Edges.csv",
            mime="text/csv",
            use_container_width=True
        )
    with col3:
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        st.download_button(
            label="📥 Road Network Image (PNG)",
            data=buf.getvalue(),
            file_name=f"{area_name}_RoadNetwork.png",
            mime="image/png",
            use_container_width=True
        )

# Footer
st.markdown("---")
st.markdown("""
<div style='text-align:center; color:gray; font-size:0.9em;'>
    <p>Made with ❤️ using OpenStreetMap data</p>
    <p>Data © <a href="https://www.openstreetmap.org/copyright" target="_blank">OpenStreetMap contributors</a></p>
</div>
""", unsafe_allow_html=True)
