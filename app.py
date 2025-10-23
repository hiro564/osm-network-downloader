import streamlit as st
import osmnx as ox
import pandas as pd
from shapely.geometry import box
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from PIL import Image
import io

st.set_page_config(
    page_title="OSM道路ネットワーク＆地図画像取得",
    page_icon="🗺️",
    layout="wide"
)

st.title("🗺️ OSM道路ネットワーク＆地図画像取得ツール")
st.markdown("OpenStreetMapから道路ネットワークデータと地図画像を取得")
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

# 地図画像設定
st.sidebar.subheader("🖼️ 地図画像設定")
image_width = st.sidebar.number_input("画像幅 (px)", value=480, min_value=100, max_value=2000)
image_height = st.sidebar.number_input("画像高さ (px)", value=360, min_value=100, max_value=2000)
dpi = st.sidebar.slider("解像度 (DPI)", min_value=50, max_value=300, value=100)

# データ取得オプション
st.sidebar.subheader("📦 取得データ")
get_network = st.sidebar.checkbox("道路ネットワークCSV", value=True)
get_image = st.sidebar.checkbox("地図画像", value=True)

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
            if get_network or get_image:
                status.text("道路ネットワークをダウンロード中...")
                progress_bar.progress(10)
                
                G = ox.graph_from_polygon(polygon, network_type=network_type)
                
                progress_bar.progress(30)
                status.text(f"取得完了: {len(G.nodes())}ノード, {len(G.edges())}エッジ")
            
            # 建物データを取得
            if get_image:
                status.text("建物データをダウンロード中...")
                progress_bar.progress(40)
                
                try:
                    buildings = ox.features_from_polygon(polygon, tags={'building': True})
                    status.text(f"建物データ取得完了: {len(buildings)}件")
                except Exception as e:
                    st.warning(f"建物データの取得に失敗: {e}")
                    buildings = None
                
                progress_bar.progress(50)
            
            # CSVデータ生成
            if get_network:
                status.text("データを変換中...")
                progress_bar.progress(60)
                
                gdf_nodes, gdf_edges = ox.graph_to_gdfs(G, nodes=True, edges=True, 
                                                         node_geometry=True, fill_edge_geometry=True)
                
                # DataFrameに変換
                node_df = pd.DataFrame(gdf_nodes)
                edge_df = pd.DataFrame(gdf_edges)
                
                # CSV生成
                node_csv = node_df.to_csv(index=True)
                edge_csv = edge_df.to_csv(index=True)
            
            # 地図画像生成
            if get_image:
                status.text("地図画像を生成中...")
                progress_bar.progress(70)
                
                # 画像サイズ計算
                fig_width = image_width / dpi
                fig_height = image_height / dpi
                
                # 図を作成
                fig, ax = plt.subplots(figsize=(fig_width, fig_height), dpi=dpi)
                
                # 建物を描画
                if buildings is not None and len(buildings) > 0:
                    buildings.plot(ax=ax, facecolor='#CCCCCC', edgecolor='#999999', 
                                   linewidth=0.5, alpha=0.7, zorder=1)
                
                # 道路を描画
                ox.plot_graph(G, ax=ax, node_size=0, edge_color='#666666', 
                             edge_linewidth=1.5, bgcolor='white', show=False, close=False)
                
                # 軸を非表示
                ax.set_xlim([west, east])
                ax.set_ylim([south, north])
                ax.axis('off')
                plt.tight_layout(pad=0)
                
                # 画像をバッファに保存
                buf = io.BytesIO()
                plt.savefig(buf, format='png', dpi=dpi, bbox_inches='tight', pad_inches=0)
                buf.seek(0)
                map_image = Image.open(buf)
                
                # 画像をリサイズ（正確なサイズに）
                map_image = map_image.resize((image_width, image_height), Image.Resampling.LANCZOS)
                
                # PNG保存用
                img_buffer = io.BytesIO()
                map_image.save(img_buffer, format='PNG')
                img_bytes = img_buffer.getvalue()
                
                plt.close(fig)
                
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
            
            # 地図画像表示
            if get_image:
                st.subheader("🗺️ 生成された地図画像")
                st.image(map_image, caption=f"{area_name} - {image_width}×{image_height}px", use_column_width=True)
                
                # 座標情報表示
                st.info(f"""
                **座標範囲:**
                - 北端: {north}
                - 南端: {south}
                - 東端: {east}
                - 西端: {west}
                - サイズ: {image_width}×{image_height}px
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
            
            if get_image:
                with download_cols[2]:
                    st.download_button(
                        label="📥 地図画像 (PNG)",
                        data=img_bytes,
                        file_name=f"{area_name}_Map_{image_width}x{image_height}.png",
                        mime='image/png',
                        type="primary"
                    )
            
    except Exception as e:
        st.error(f"❌ エラーが発生しました")
        st.exception(e)
        st.info("💡 ヒント: 範囲が広すぎるか、データが存在しない可能性があります。範囲を狭めて再試行してください。")
