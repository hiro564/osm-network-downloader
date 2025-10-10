import streamlit as st
import osmnx as ox
import pandas as pd
from shapely.geometry import box

st.set_page_config(
    page_title="OSM道路ネットワーク取得",
    page_icon="🗺️",
    layout="wide"
)

st.title("🗺️ OSM道路ネットワーク取得ツール")
st.markdown("OpenStreetMapから道路ネットワークデータを取得してCSV出力")
st.markdown("---")

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

# メイン画面
if st.button("🚀 データ取得開始", type="primary"):
    try:
        with st.spinner("OpenStreetMapからデータを取得中..."):
            # プログレスバー
            progress_bar = st.progress(0)
            status = st.empty()
            
            # 道路ネットワークデータを取得
            status.text("道路ネットワークをダウンロード中...")
            progress_bar.progress(10)
            
            # ポリゴンを作成して取得
            polygon = box(west, south, east, north)
            G = ox.graph_from_polygon(polygon, network_type=network_type)
            
            progress_bar.progress(40)
            status.text(f"取得完了: {len(G.nodes())}ノード, {len(G.edges())}エッジ")
            
            # グラフデータからDataFrame形式に変更
            status.text("データを変換中...")
            progress_bar.progress(60)
            
            gdf_nodes, gdf_edges = ox.graph_to_gdfs(G, nodes=True, edges=True, 
                                                     node_geometry=True, fill_edge_geometry=True)
            
            # DataFrameに変換
            node_df = pd.DataFrame(gdf_nodes)
            edge_df = pd.DataFrame(gdf_edges)
            
            progress_bar.progress(80)
            status.text("CSV生成中...")
            
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
            
            # データプレビュー
            st.subheader("📊 ノードデータ プレビュー")
            st.dataframe(node_df.head(10), use_container_width=True)
            
            st.subheader("📊 エッジデータ プレビュー")
            st.dataframe(edge_df.head(10), use_container_width=True)
            
            # ダウンロードボタン
            st.subheader("📥 ダウンロード")
            col1, col2 = st.columns(2)
            
            with col1:
                st.download_button(
                    label="📥 ノードCSVダウンロード",
                    data=node_csv,
                    file_name=f"{area_name}_Node_{network_type}.csv",
                    mime='text/csv',
                    type="primary"
                )
            
            with col2:
                st.download_button(
                    label="📥 エッジCSVダウンロード",
                    data=edge_csv,
                    file_name=f"{area_name}_Edge_{network_type}.csv",
                    mime='text/csv',
                    type="primary"
                )
            
            # ネットワーク可視化
            st.subheader("🗺️ ネットワーク可視化")
            try:
                fig, ax = ox.plot_graph(G, figsize=(12, 12), node_size=5, 
                                       edge_linewidth=0.5, show=False, close=False)
                st.pyplot(fig)
            except Exception as e:
                st.warning(f"可視化をスキップしました: {e}")
            
    except Exception as e:
        st.error(f"❌ エラーが発生しました")
        st.exception(e)
        st.info("💡 ヒント: 範囲が広すぎるか、データが存在しない可能性があります。範囲を狭めて再試行してください。")

# 使い方
with st.expander("ℹ️ 使い方"):
    st.markdown("""
    ### 📋 使い方
    
    1. **エリア名**を入力（出力ファイル名に使用）
    2. **取得範囲**を緯度経度で指定
       - 北端緯度 > 南端緯度
       - 東端経度 > 西端経度
    3. **ネットワークタイプ**を選択
       - `drive`: 車道のみ
       - `walk`: 歩道のみ
       - `all`: すべての道路
       - `bike`: 自転車道のみ
    4. 「データ取得開始」ボタンをクリック
    5. ノードCSVとエッジCSVをダウンロード
    
    ### 📊 出力データ
    
    **ノードCSV**: 交差点の情報
    - NodeID（インデックス）
    - x（経度）
    - y（緯度）
    - その他のOSM属性
    
    **エッジCSV**: 道路の情報
    - u, v, key（接続ノードID）
    - length（道路の長さ）
    - geometry（道路の形状）
    - その他のOSM属性（道路名、種別など）
    
    ### 💡 座標の例
    
    **東京都心部:**
    - 北: 35.70, 南: 35.65, 東: 139.80, 西: 139.70
    
    **鎌倉市:**
    - 北: 35.36, 南: 35.29, 東: 139.57, 西: 139.48
    
    ### ⚠️ 注意
    - 広範囲の取得には時間がかかります
    - 小さい範囲から試すことをおすすめします
    """)

# フッター
st.markdown("---")
st.markdown("""
<div style='text-align: center; color: #666; padding: 20px;'>
    <p>OpenStreetMapから道路ネットワークデータを取得</p>
    <p>Data © OpenStreetMap contributors</p>
</div>
""", unsafe_allow_html=True)
