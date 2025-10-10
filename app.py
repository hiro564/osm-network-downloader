import streamlit as st
import osmnx as ox
import pandas as pd
import numpy as np
import math
from io import BytesIO

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
area_name = st.sidebar.text_input("エリア名", value="Kamakura_City", help="出力ファイル名に使用されます")

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
    options=['all', 'drive', 'walk', 'bike'],
    index=0,
    help="all: 全道路, drive: 車道のみ, walk: 歩道のみ, bike: 自転車道のみ"
)

# 簡略化オプション
simplify_graph = st.sidebar.checkbox("交差点ノードを間引く", value=True, help="不要なノードを削除してデータを軽量化")

# メイン画面
tab1, tab2, tab3 = st.tabs(["📥 データ取得", "ℹ️ 使い方", "📊 出力例"])

with tab1:
    if st.button("🚀 データ取得開始", type="primary"):
        try:
            with st.spinner("OpenStreetMapからデータを取得中..."):
                progress_bar = st.progress(0)
                status_text = st.empty()
                
                # データ取得
                status_text.text("道路ネットワークをダウンロード中...")
                progress_bar.progress(20)
                
                # 新しいAPI（正しい）
                G = ox.graph_from_bbox(
                bbox=(north, south, east, west),
                network_type=network_type,
                simplify=simplify_graph
                )
                
                progress_bar.progress(40)
                status_text.text(f"取得完了: {len(G.nodes())}ノード, {len(G.edges())}エッジ")
                
                # グラフを簡略化
                if simplify_graph:
                    status_text.text("ノードを統合中...")
                    try:
                        G = ox.simplification.simplify_graph(G)
                    except:
                        pass
                
                progress_bar.progress(60)
                
                # GeoDataFrame変換
                status_text.text("データを変換中...")
                gdf_nodes, gdf_edges = ox.graph_to_gdfs(G, nodes=True, edges=True)
                
                progress_bar.progress(70)
                
                # ノードデータ準備
                nodes_data = []
                for node_id, node_data in gdf_nodes.iterrows():
                    nodes_data.append({
                        'NodeID': node_id,
                        'NodeX': node_data['x'],
                        'NodeY': node_data['y'],
                        'NodeElevation': node_data.get('elevation', 0.0)
                    })
                
                # エッジデータ準備
                edges_data = []
                for (u, v, key), edge_data in gdf_edges.iterrows():
                    try:
                        distance = edge_data.get('length', 0)
                        if isinstance(distance, (list, tuple, np.ndarray)):
                            distance = distance[0] if len(distance) > 0 else 0
                        
                        # 道路幅の取得
                        width = 5.0  # デフォルト
                        if 'width' in edge_data and pd.notna(edge_data['width']):
                            try:
                                width = float(edge_data['width'])
                            except:
                                pass
                        elif 'lanes' in edge_data and pd.notna(edge_data['lanes']):
                            try:
                                lanes = float(edge_data['lanes'])
                                width = lanes * 3.5
                            except:
                                pass
                        
                        edges_data.append({
                            'LinkFrom': u,
                            'LinkTo': v,
                            'LinkDistance': round(float(distance), 2),
                            'LinkWidth': float(width)
                        })
                    except:
                        continue
                
                progress_bar.progress(85)
                status_text.text("最終データを作成中...")
                
                # 最終データ作成
                node_dict = {node['NodeID']: node for node in nodes_data}
                final_data = []
                
                for edge in edges_data:
                    from_node = node_dict.get(edge['LinkFrom'], {})
                    final_data.append({
                        'NodeID': edge['LinkFrom'],
                        'NodeX': from_node.get('NodeX', 0.0),
                        'NodeY': from_node.get('NodeY', 0.0),
                        'LinkFrom': edge['LinkFrom'],
                        'LinkTo': edge['LinkTo'],
                        'LinkDistance': edge['LinkDistance'],
                        'LinkWidth': edge['LinkWidth'],
                        'NodeElevation': from_node.get('NodeElevation', 0.0)
                    })
                
                df_final = pd.DataFrame(final_data)
                
                progress_bar.progress(100)
                status_text.text("✅ 完了！")
                
                # 結果表示
                st.success("🎉 データ取得完了！")
                
                # 統計情報
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("総レコード数", f"{len(df_final):,}")
                with col2:
                    st.metric("ユニークノード", f"{df_final['NodeID'].nunique():,}")
                with col3:
                    st.metric("総リンク数", f"{len(df_final):,}")
                with col4:
                    avg_dist = df_final['LinkDistance'].mean()
                    st.metric("平均距離", f"{avg_dist:.1f}m")
                
                # データプレビュー
                st.subheader("📊 データプレビュー")
                st.dataframe(df_final.head(20), use_container_width=True)
                
                # 統計情報
                st.subheader("📈 統計情報")
                stats_col1, stats_col2 = st.columns(2)
                with stats_col1:
                    st.write("**距離の統計**")
                    st.write(f"- 最小: {df_final['LinkDistance'].min():.2f}m")
                    st.write(f"- 最大: {df_final['LinkDistance'].max():.2f}m")
                    st.write(f"- 平均: {df_final['LinkDistance'].mean():.2f}m")
                    st.write(f"- 中央値: {df_final['LinkDistance'].median():.2f}m")
                
                with stats_col2:
                    st.write("**道路幅の統計**")
                    st.write(f"- 最小: {df_final['LinkWidth'].min():.2f}m")
                    st.write(f"- 最大: {df_final['LinkWidth'].max():.2f}m")
                    st.write(f"- 平均: {df_final['LinkWidth'].mean():.2f}m")
                    st.write(f"- 中央値: {df_final['LinkWidth'].median():.2f}m")
                
                # CSVダウンロード
                csv_data = df_final.to_csv(index=False)
                filename = f"{area_name}_{network_type}_network.csv"
                
                st.download_button(
                    label="📥 CSVファイルをダウンロード",
                    data=csv_data,
                    file_name=filename,
                    mime='text/csv',
                    type="primary"
                )
                
                # ネットワーク可視化
                st.subheader("🗺️ ネットワーク可視化")
                try:
                    fig, ax = ox.plot_graph(G, figsize=(12, 12), node_size=0, 
                                           edge_linewidth=0.5, show=False, close=False)
                    st.pyplot(fig)
                except Exception as e:
                    st.warning(f"可視化に失敗しました: {e}")
                
        except Exception as e:
            st.error(f"❌ エラーが発生しました: {str(e)}")
            st.exception(e)

with tab2:
    st.markdown("""
    ## 📋 使い方
    
    ### 1️⃣ エリア設定
    - **エリア名**: 出力ファイル名に使用されます（例: Kamakura_City）
    - **取得範囲**: 緯度経度で範囲を指定します
    
    ### 2️⃣ オプション設定
    - **ネットワークタイプ**:
      - `all`: すべての道路
      - `drive`: 車道のみ
      - `walk`: 歩道のみ
      - `bike`: 自転車道のみ
    
    - **交差点ノードを間引く**: 不要なノードを削除してデータを軽量化
    
    ### 3️⃣ データ取得
    - 「データ取得開始」ボタンをクリック
    - OpenStreetMapからデータをダウンロード
    - CSVファイルをダウンロード
    
    ### 📊 出力データの列
    - **NodeID**: ノード（交差点）の一意なID
    - **NodeX**: ノードの経度
    - **NodeY**: ノードの緯度
    - **LinkFrom**: リンク（道路）の始点ノードID
    - **LinkTo**: リンク（道路）の終点ノードID
    - **LinkDistance**: ノード間の距離（メートル）
    - **LinkWidth**: 道路の幅（メートル）
    - **NodeElevation**: ノードの標高
    
    ### 💡 活用例
    - 避難シミュレーション
    - 交通流シミュレーション
    - 最短経路計算
    - ネットワーク解析
    - GIS解析
    
    ### ⚠️ 注意事項
    - 広範囲のデータ取得には時間がかかります
    - OpenStreetMapのサーバーに負荷をかけないよう、適度な範囲で取得してください
    - データ量が多い場合、処理に時間がかかることがあります
    """)

with tab3:
    st.markdown("""
    ## 📊 出力CSVの例
    
    ```csv
    NodeID,NodeX,NodeY,LinkFrom,LinkTo,LinkDistance,LinkWidth,NodeElevation
    123456,139.5234,35.3145,123456,123457,45.23,5.0,12.5
    123457,139.5245,35.3150,123457,123458,38.67,7.0,13.2
    123458,139.5256,35.3155,123458,123459,52.10,5.0,14.1
    ```
    
    ### データの意味
    - 各行が1つのノードとそのノードから出るリンク（道路）を表します
    - 同じノードから複数のリンクが出る場合、複数行になります
    - 距離と幅はメートル単位です
    """)

# フッター
st.markdown("---")
st.markdown("""
<div style='text-align: center; color: #666; padding: 20px;'>
    <p>OpenStreetMapから道路ネットワークデータを取得</p>
    <p>Data © OpenStreetMap contributors</p>
</div>
""", unsafe_allow_html=True)
