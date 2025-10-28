import streamlit as st
import osmnx as ox
import pandas as pd
from shapely.geometry import box
import numpy as np

# Scratch座標系の定義
SCRATCH_WIDTH = 480
SCRATCH_HEIGHT = 360
SCRATCH_X_MIN = -240
SCRATCH_X_MAX = 240
SCRATCH_Y_MIN = -180
SCRATCH_Y_MAX = 180

st.set_page_config(
    page_title="OSM→Scratch座標変換",
    page_icon="🗺️",
    layout="wide"
)

st.title("🗺️ OSM道路ネットワーク → Scratch座標系変換ツール")
st.markdown("OpenStreetMapのデータをScratch座標系（-240〜240, -180〜180）に変換")
st.markdown("---")

# サイドバー設定
st.sidebar.header("⚙️ 設定")

# エリア名入力
area_name = st.sidebar.text_input("エリア名", value="MyArea", help="出力ファイル名に使用されます")

# プリセット選択
st.sidebar.subheader("📍 プリセット座標")
preset = st.sidebar.selectbox(
    "場所を選択",
    options=[
        "カスタム",
        "東京タワー周辺",
        "渋谷駅周辺", 
        "鎌倉市中心部",
        "京都駅周辺",
        "大阪城周辺"
    ]
)

# プリセット座標
presets = {
    "東京タワー周辺": (35.660, 35.657, 139.747, 139.743),
    "渋谷駅周辺": (35.663, 35.655, 139.704, 139.696),
    "鎌倉市中心部": (35.325, 35.315, 139.555, 139.545),
    "京都駅周辺": (34.991, 34.983, 135.765, 135.757),
    "大阪城周辺": (34.691, 34.683, 135.531, 135.523)
}

# 座標範囲入力
st.sidebar.subheader("📍 取得範囲（緯度経度）")

if preset != "カスタム":
    north, south, east, west = presets[preset]
    st.sidebar.info(f"✅ {preset}を選択中")
else:
    col1, col2 = st.sidebar.columns(2)
    with col1:
        north = st.number_input("北端緯度", value=35.360, format="%.6f")
        south = st.number_input("南端緯度", value=35.290, format="%.6f")
    with col2:
        east = st.number_input("東端経度", value=139.570, format="%.6f")
        west = st.number_input("西端経度", value=139.480, format="%.6f")

# 範囲の表示
st.sidebar.markdown(f"""
**現在の範囲:**
- 北: {north:.6f}
- 南: {south:.6f}
- 東: {east:.6f}
- 西: {west:.6f}
""")

# ネットワークタイプ選択
network_type = st.sidebar.selectbox(
    "ネットワークタイプ",
    options=['drive', 'walk', 'all', 'bike'],
    index=0,
    help="drive: 車道, walk: 歩道, all: 全道路, bike: 自転車道"
)

# 座標変換関数
def latlon_to_scratch(lat, lon, bounds):
    """
    緯度経度をScratch座標系に変換
    
    Args:
        lat: 緯度
        lon: 経度
        bounds: (north, south, east, west)
    
    Returns:
        (x, y): Scratch座標
    """
    north, south, east, west = bounds
    
    # 正規化（0〜1の範囲に）
    x_norm = (lon - west) / (east - west)
    y_norm = (north - lat) / (north - south)  # 緯度は北が大きいので反転
    
    # Scratch座標系にスケーリング
    x_scratch = SCRATCH_X_MIN + x_norm * (SCRATCH_X_MAX - SCRATCH_X_MIN)
    y_scratch = SCRATCH_Y_MIN + y_norm * (SCRATCH_Y_MAX - SCRATCH_Y_MIN)
    
    return round(x_scratch, 2), round(y_scratch, 2)

def convert_to_scratch_format(G, bounds):
    """
    OSMグラフをScratch座標系のDataFrameに変換
    
    Returns:
        nodes_df: ノードデータ (ID, X, Y, Latitude, Longitude)
        edges_df: エッジデータ (FromID, ToID, Distance)
    """
    # ノードデータの作成
    nodes_data = []
    node_id_map = {}  # OSMのノードID → 連番IDのマッピング
    
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
    
    # エッジデータの作成
    edges_data = []
    
    for u, v, data in G.edges(data=True):
        from_id = node_id_map[u]
        to_id = node_id_map[v]
        
        # 距離を計算（メートル単位）
        distance = data.get('length', 0)
        
        edges_data.append({
            'FromID': from_id,
            'ToID': to_id,
            'Distance': round(distance, 2)
        })
        
        # 逆方向も追加（双方向）
        edges_data.append({
            'FromID': to_id,
            'ToID': from_id,
            'Distance': round(distance, 2)
        })
    
    edges_df = pd.DataFrame(edges_data)
    
    return nodes_df, edges_df

# メインエリア
st.header("📊 データ取得と変換")

# Scratch座標系の説明
with st.expander("ℹ️ Scratch座標系について"):
    st.markdown("""
    **Scratch座標系の特徴:**
    - X座標範囲: -240 〜 +240 (画面幅480ピクセル)
    - Y座標範囲: -180 〜 +180 (画面高360ピクセル)
    - 原点(0, 0)は画面中央
    - 右がX正、上がY正
    
    **変換方法:**
    1. 緯度経度を指定範囲内で正規化(0〜1)
    2. Scratch座標系にスケーリング
    3. 小数点第2位まで丸める
    """)

# Google Maps リンク（範囲確認用）
center_lat = (north + south) / 2
center_lon = (east + west) / 2
st.info(f"📍 [Google Mapsで範囲を確認](https://www.google.com/maps/@{center_lat},{center_lon},15z)")

# データ取得ボタン
if st.button("🚀 データ取得＆変換開始", type="primary", use_container_width=True):
    try:
        # 入力値の事前検証
        if north <= south:
            st.error("❌ 北端緯度は南端緯度より大きい値を入力してください")
            st.stop()
        if east <= west:
            st.error("❌ 東端経度は西端経度より大きい値を入力してください")
            st.stop()
        
        # プログレスバー
        progress_bar = st.progress(0)
        status = st.empty()
        
        # ポリゴンを作成
        polygon = box(west, south, east, north)
        bounds = (north, south, east, west)
        
        # 道路ネットワークデータを取得
        status.text("📡 道路ネットワークをダウンロード中...")
        progress_bar.progress(20)
        
        G = ox.graph_from_polygon(polygon, network_type=network_type)
        
        progress_bar.progress(50)
        status.text(f"✅ 取得完了: {len(G.nodes())}ノード, {len(G.edges())}エッジ")
        
        # Scratch座標系に変換
        status.text("🔄 Scratch座標系に変換中...")
        progress_bar.progress(70)
        
        nodes_df, edges_df = convert_to_scratch_format(G, bounds)
        
        # CSV生成
        node_csv = nodes_df[['ID', 'X', 'Y', 'Latitude', 'Longitude']].to_csv(index=False)
        edge_csv = edges_df.to_csv(index=False)
        
        progress_bar.progress(100)
        status.text("✅ 変換完了！")
        
        # 結果表示
        st.success("🎉 データ取得・変換完了！")
        
        # 統計情報
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("ノード数", f"{len(nodes_df):,}")
        with col2:
            st.metric("エッジ数", f"{len(edges_df):,}")
        with col3:
            st.metric("X範囲", f"{nodes_df['X'].min():.1f} 〜 {nodes_df['X'].max():.1f}")
        with col4:
            st.metric("Y範囲", f"{nodes_df['Y'].min():.1f} 〜 {nodes_df['Y'].max():.1f}")
        
        # 座標範囲の確認
        st.info(f"""
        **変換情報:**
        - 緯度範囲: {south:.6f} 〜 {north:.6f}
        - 経度範囲: {west:.6f} 〜 {east:.6f}
        - ネットワークタイプ: {network_type}
        - Scratch座標: X({SCRATCH_X_MIN}〜{SCRATCH_X_MAX}), Y({SCRATCH_Y_MIN}〜{SCRATCH_Y_MAX})
        """)
        
        # データプレビュー
        with st.expander("📊 ノードデータ プレビュー (Scratch座標系)"):
            st.dataframe(
                nodes_df[['ID', 'X', 'Y', 'Latitude', 'Longitude']].head(20), 
                use_container_width=True
            )
            
            # 座標の分布
            col1, col2 = st.columns(2)
            with col1:
                st.write("**X座標の分布:**")
                st.write(nodes_df['X'].describe())
            with col2:
                st.write("**Y座標の分布:**")
                st.write(nodes_df['Y'].describe())
        
        with st.expander("📊 エッジデータ プレビュー"):
            st.dataframe(edges_df.head(20), use_container_width=True)
            st.write(f"**総エッジ数:** {len(edges_df):,} (双方向含む)")
            st.write(f"**平均距離:** {edges_df['Distance'].mean():.2f}m")
        
        # サンプルコード表示
        with st.expander("💻 Scratchでの使用例"):
            st.code("""
// ノードデータの読み込み例
リスト「NodeID」に [ID列] を追加
リスト「NodeX」に [X列] を追加
リスト「NodeY」に [Y列] を追加

// エッジデータの読み込み例
リスト「LinkFrom」に [FromID列] を追加
リスト「LinkTo」に [ToID列] を追加

// ノードの座標を取得
[リスト「NodeX」の (ノード番号) 番目] → X座標
[リスト「NodeY」の (ノード番号) 番目] → Y座標

// その座標に移動
(X座標), (Y座標) へ行く
""", language="text")
        
        # ダウンロードボタン
        st.subheader("📥 ダウンロード")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.download_button(
                label="📥 ノードCSV (ID, X, Y, Lat, Lon)",
                data=node_csv,
                file_name=f"{area_name}_Nodes_Scratch.csv",
                mime='text/csv',
                type="primary",
                use_container_width=True
            )
        
        with col2:
            st.download_button(
                label="📥 エッジCSV (FromID, ToID, Distance)",
                data=edge_csv,
                file_name=f"{area_name}_Edges_Scratch.csv",
                mime='text/csv',
                type="primary",
                use_container_width=True
            )
        
        # 詳細データ（緯度経度含む）のダウンロード
        with st.expander("📥 詳細データのダウンロード"):
            full_node_csv = nodes_df.to_csv(index=False)
            st.download_button(
                label="📥 ノード詳細CSV (OSM_ID含む)",
                data=full_node_csv,
                file_name=f"{area_name}_Nodes_Full.csv",
                mime='text/csv',
                use_container_width=True
            )
        
    except Exception as e:
        st.error(f"❌ エラーが発生しました")
        st.exception(e)
        st.info("💡 ヒント: 範囲が広すぎる可能性があります。範囲を狭めて再試行してください。")

# フッター
st.markdown("---")
st.markdown("""
<div style='text-align: center; color: gray;'>
    Made with ❤️ for Scratch programmers | OpenStreetMap © OpenStreetMap contributors
</div>
""", unsafe_allow_html=True)
