import streamlit as st
import osmnx as ox
import pandas as pd
from shapely.geometry import box
import matplotlib.pyplot as plt
import requests
from PIL import Image
import io
import math
from io import BytesIO

st.set_page_config(
    page_title="OSM道路ネットワーク＆タイル地図取得",
    page_icon="🗺️",
    layout="wide"
)

st.title("🗺️ OSM道路ネットワーク＆タイル地図取得ツール")
st.markdown("OpenStreetMapから道路ネットワークデータとタイル地図画像を取得")
st.markdown("---")

# タイル座標計算関数
def deg2num(lat_deg, lon_deg, zoom):
    """緯度経度からタイル座標を計算"""
    lat_rad = math.radians(lat_deg)
    n = 2.0 ** zoom
    xtile = int((lon_deg + 180.0) / 360.0 * n)
    ytile = int((1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * n)
    return (xtile, ytile)

def num2deg(xtile, ytile, zoom):
    """タイル座標から緯度経度を計算"""
    n = 2.0 ** zoom
    lon_deg = xtile / n * 360.0 - 180.0
    lat_rad = math.atan(math.sinh(math.pi * (1 - 2 * ytile / n)))
    lat_deg = math.degrees(lat_rad)
    return (lat_deg, lon_deg)

def get_tile_image(zoom, x, y, tile_server='cartodb'):
    """指定されたタイルを取得"""
    if tile_server == 'cartodb':
        url = f'https://cartodb-basemaps-a.global.ssl.fastly.net/light_all/{zoom}/{x}/{y}.png'
    else:
        url = f'https://tile.openstreetmap.org/{zoom}/{x}/{y}.png'
    
    try:
        headers = {'User-Agent': 'OSM Tile Fetcher'}
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            return Image.open(BytesIO(response.content))
        else:
            return None
    except Exception as e:
        st.warning(f"タイル取得失敗 ({zoom}/{x}/{y}): {e}")
        return None

def create_map_from_tiles(north, south, east, west, zoom, width=480, height=360, tile_server='cartodb'):
    """タイルを組み合わせて地図画像を作成"""
    
    # タイル座標を計算
    x_min, y_max = deg2num(north, west, zoom)
    x_max, y_min = deg2num(south, east, zoom)
    
    # タイルサイズ
    tile_size = 256
    
    # 必要なタイル数
    x_tiles = x_max - x_min + 1
    y_tiles = y_max - y_min + 1
    
    # タイル画像を結合
    map_width = x_tiles * tile_size
    map_height = y_tiles * tile_size
    
    map_image = Image.new('RGB', (map_width, map_height))
    
    # タイルをダウンロードして配置
    for x in range(x_min, x_max + 1):
        for y in range(y_min, y_max + 1):
            tile = get_tile_image(zoom, x, y, tile_server)
            if tile:
                x_offset = (x - x_min) * tile_size
                y_offset = (y - y_min) * tile_size
                map_image.paste(tile, (x_offset, y_offset))
    
    # 実際の座標範囲に対応する領域を切り出し
    # 左上のタイルの左上座標
    nw_lat, nw_lon = num2deg(x_min, y_min, zoom)
    # 右下のタイルの右下座標
    se_lat, se_lon = num2deg(x_max + 1, y_max + 1, zoom)
    
    # ピクセル座標を計算
    x_ratio = map_width / (se_lon - nw_lon)
    y_ratio = map_height / (nw_lat - se_lat)
    
    crop_x1 = int((west - nw_lon) * x_ratio)
    crop_y1 = int((nw_lat - north) * y_ratio)
    crop_x2 = int((east - nw_lon) * x_ratio)
    crop_y2 = int((nw_lat - south) * y_ratio)
    
    # クロップ
    cropped_image = map_image.crop((crop_x1, crop_y1, crop_x2, crop_y2))
    
    # 指定されたサイズにリサイズ
    resized_image = cropped_image.resize((width, height), Image.Resampling.LANCZOS)
    
    return resized_image

# サイドバー設定
st.sidebar.header("⚙️ 設定")

# エリア名入力
area_name = st.sidebar.text_input("エリア名", value="MyArea", help="出力ファイル名に使用されます")

# 座標範囲入力
st.sidebar.subheader("📍 取得範囲（緯度経度）")
col1, col2 = st.sidebar.columns(2)
with col1:
    north = st.number_input("北端緯度", value=35.3600, format="%.6f")
    south = st.number_input("南端緯度", value=35.2900, format="%.6f")
with col2:
    east = st.number_input("東端経度", value=139.5700, format="%.6f")
    west = st.number_input("西端経度", value=139.4800, format="%.6f")

# ネットワークタイプ選択
network_type = st.sidebar.selectbox(
    "ネットワークタイプ",
    options=['drive', 'walk', 'all', 'bike'],
    index=0,
    help="drive: 車道, walk: 歩道, all: 全道路, bike: 自転車道"
)

# 地図画像設定
st.sidebar.subheader("🖼️ タイル地図設定")
zoom_level = st.sidebar.slider("ズームレベル", min_value=10, max_value=19, value=16, 
                                help="数値が大きいほど詳細な地図")
image_width = st.sidebar.number_input("画像幅 (px)", value=480, min_value=100, max_value=2000)
image_height = st.sidebar.number_input("画像高さ (px)", value=360, min_value=100, max_value=2000)

tile_server = st.sidebar.selectbox(
    "タイルサーバー",
    options=['cartodb', 'osm'],
    index=0,
    help="cartodb: 明るく見やすい, osm: 標準OpenStreetMap"
)

# データ取得オプション
st.sidebar.subheader("📦 取得データ")
get_network = st.sidebar.checkbox("道路ネットワークCSV", value=True)
get_tile_map = st.sidebar.checkbox("タイル地図画像", value=True)

# メイン画面
if st.button("🚀 データ取得開始", type="primary"):
    try:
        with st.spinner("OpenStreetMapからデータを取得中..."):
            # プログレスバー
            progress_bar = st.progress(0)
            status = st.empty()
            
            # ポリゴンを作成
            polygon = box(west, south, east, north)
            
            # 道路ネットワークデータを取得
            if get_network:
                status.text("道路ネットワークをダウンロード中...")
                progress_bar.progress(10)
                
                G = ox.graph_from_polygon(polygon, network_type=network_type)
                
                progress_bar.progress(30)
                status.text(f"取得完了: {len(G.nodes())}ノード, {len(G.edges())}エッジ")
                
                # CSVデータ生成
                status.text("データを変換中...")
                progress_bar.progress(50)
                
                gdf_nodes, gdf_edges = ox.graph_to_gdfs(G, nodes=True, edges=True, 
                                                         node_geometry=True, fill_edge_geometry=True)
                
                # DataFrameに変換
                node_df = pd.DataFrame(gdf_nodes)
                edge_df = pd.DataFrame(gdf_edges)
                
                # CSV生成
                node_csv = node_df.to_csv(index=True)
                edge_csv = edge_df.to_csv(index=True)
            
            # タイル地図画像生成
            if get_tile_map:
                status.text(f"タイル地図を生成中（ズーム{zoom_level}）...")
                progress_bar.progress(60)
                
                tile_map_image = create_map_from_tiles(
                    north, south, east, west, 
                    zoom_level, image_width, image_height, tile_server
                )
                
                # PNG保存用
                img_buffer = io.BytesIO()
                tile_map_image.save(img_buffer, format='PNG')
                img_bytes = img_buffer.getvalue()
                
                progress_bar.progress(90)
            
            progress_bar.progress(100)
            status.text("✅ 完了！")
            
            # 結果表示
            st.success("🎉 データ取得完了！")
            
            # 統計情報
            if get_network:
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("ノード数", f"{len(node_df):,}")
                with col2:
                    st.metric("エッジ数", f"{len(edge_df):,}")
                with col3:
                    st.metric("ノード列数", len(node_df.columns))
                with col4:
                    st.metric("エッジ列数", len(edge_df.columns))
            
            # タイル地図画像表示
            if get_tile_map:
                st.subheader("🗺️ 生成されたタイル地図画像")
                st.image(tile_map_image, caption=f"{area_name} - {image_width}×{image_height}px (Zoom {zoom_level})", 
                        use_column_width=True)
                
                # 座標情報表示
                st.info(f"""
                **座標範囲:**
                - 北端: {north}
                - 南端: {south}
                - 東端: {east}
                - 西端: {west}
                - ズームレベル: {zoom_level}
                - サイズ: {image_width}×{image_height}px
                - タイルサーバー: {tile_server}
                """)
            
            # データプレビュー
            if get_network:
                with st.expander("📊 ノードデータ プレビュー"):
                    st.dataframe(node_df.head(10), use_container_width=True)
                
                with st.expander("📊 エッジデータ プレビュー"):
                    st.dataframe(edge_df.head(10), use_container_width=True)
            
            # ダウンロードボタン
            st.subheader("📥 ダウンロード")
            
            download_cols = st.columns(3)
            
            if get_network:
                with download_cols[0]:
                    st.download_button(
                        label="📥 ノードCSV",
                        data=node_csv,
                        file_name=f"{area_name}_Node_{network_type}.csv",
                        mime='text/csv',
                        type="primary"
                    )
                
                with download_cols[1]:
                    st.download_button(
                        label="📥 エッジCSV",
                        data=edge_csv,
                        file_name=f"{area_name}_Edge_{network_type}.csv",
                        mime='text/csv',
                        type="primary"
                    )
            
            if get_tile_map:
                with download_cols[2]:
                    st.download_button(
                        label="📥 タイル地図 (PNG)",
                        data=img_bytes,
                        file_name=f"{area_name}_TileMap_zoom{zoom_level}_{image_width}x{image_height}.png",
                        mime='image/png',
                        type="primary"
                    )
            
    except Exception as e:
        st.error(f"❌ エラーが発生しました")
        st.exception(e)
        st.info("💡 ヒント: 範囲が広すぎるか、データが存在しない可能性があります。範囲を狭めて再試行してください。")
