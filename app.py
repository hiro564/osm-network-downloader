import streamlit as st
import osmnx as ox
import pandas as pd
from shapely.geometry import box

st.set_page_config(
    page_title="OSM道路ネットワーク取得",
    page_icon="🗺️",
    layout="wide"
)

st.title("🗺️ OSM道路ネットワークデータ取得ツール")
st.markdown("OpenStreetMapから道路ネットワークデータ（CSV形式）を取得")
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

# メインエリア
st.header("📊 データ取得")

# Google Maps リンク（範囲確認用）
center_lat = (north + south) / 2
center_lon = (east + west) / 2
st.info(f"📍 [Google Mapsで範囲を確認](https://www.google.com/maps/@{center_lat},{center_lon},15z)")

# データ取得ボタン
if st.button("🚀 データ取得開始", type="primary", use_container_width=True):
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
        
        # 道路ネットワークデータを取得
        status.text("道路ネットワークをダウンロード中...")
        progress_bar.progress(20)
        
        G = ox.graph_from_polygon(polygon, network_type=network_type)
        
        progress_bar.progress(50)
        status.text(f"取得完了: {len(G.nodes())}ノード, {len(G.edges())}エッジ")
        
        # CSVデータ生成
        status.text("データを変換中...")
        progress_bar.progress(70)
        
        gdf_nodes, gdf_edges = ox.graph_to_gdfs(G, nodes=True, edges=True, 
                                                 node_geometry=True, fill_edge_geometry=True)
        
        # DataFrameに変換
        node_df = pd.DataFrame(gdf_nodes)
        edge_df = pd.DataFrame(gdf_edges)
        
        # CSV生成
        node_csv = node_df.to_csv(index=True)
        edge_csv = edge_df.to_csv(index=True)
        
        progress_bar.progress(100)
        status.text("✅ 完了！")
        
        # 結果表示
        st.success("🎉 データ取得完了！")
        
        # 統計情報
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("ノード数", f"{len(node_df):,}")
        with col2:
            st.metric("エッジ数", f"{len(edge_df):,}")
        with col3:
            st.metric("ノード列数", len(node_df.columns))
        with col4:
            st.metric("エッジ列数", len(edge_df.columns))
        
        # 座標情報表示
        st.info(f"""
        **取得範囲:**
        - 北端: {north}
        - 南端: {south}
        - 東端: {east}
        - 西端: {west}
        - ネットワークタイプ: {network_type}
        """)
        
        # データプレビュー
        with st.expander("📊 ノードデータ プレビュー"):
            st.dataframe(node_df.head(10), use_container_width=True)
        
        with st.expander("📊 エッジデータ プレビュー"):
            st.dataframe(edge_df.head(10), use_container_width=True)
        
        # ダウンロードボタン
        st.subheader("📥 ダウンロード")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.download_button(
                label="📥 ノードCSV",
                data=node_csv,
                file_name=f"{area_name}_Node_{network_type}.csv",
                mime='text/csv',
                type="primary",
                use_container_width=True
            )
        
        with col2:
            st.download_button(
                label="📥 エッジCSV",
                data=edge_csv,
                file_name=f"{area_name}_Edge_{network_type}.csv",
                mime='text/csv',
                type="primary",
                use_container_width=True
            )
        
    except Exception as e:
        st.error(f"❌ エラーが発生しました")
        st.exception(e)
        st.info("💡 ヒント: 範囲が広すぎる可能性があります。範囲を狭めて再試行してください。")
