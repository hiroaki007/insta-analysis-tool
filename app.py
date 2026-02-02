import streamlit as st
import pandas as pd
from instagrapi import Client
import os 
import time
from dotenv import load_dotenv

load_dotenv()
USERNAME = os.getenv("INSTA_USERNAME")
PASSWORD = os.getenv("INSTA_PASSWORD")

st.set_page_config(page_title="Insta Analytics", layout="wide")

@st.cache_resource
def get_client():
    cl = Client()
    cl.login(USERNAME, PASSWORD)
    return cl

st.title("📸 インスタリサーチ＆ダッシュボード")

col1, col2 = st.columns([1, 2])

with col1:
    st.header("設定")
    target_id = st.text_input("競合IDを入力", placeholder="nintendo_jp")
    count = st.slider("取得件数", 5, 30, 10)
    start_btn = st.button("リサーチ開始")

if start_btn:
    if not target_id:
        st.error("ターゲットIDを入力してください")
    else:
        try:
            cl = get_client()
            # 入力されたIDをカンマで分割してリストにする（空白は除去）
            target_list = [i.strip() for i in target_id.split(",")]
            
            all_posts = [] # 全員のデータを貯める箱

            for target in target_list:
                with st.spinner(f"{target} のデータを取得中..."):
                    # ID取得
                    user_info = cl.user_info_by_username_v1(target)
                    user_id = user_info.pk
                    
                    # 投稿取得
                    result = cl.private_request(f"feed/user/{user_id}/", params={"count": count})
                    items = result.get("items", [])
                    
                    for item in items:
                        caption = item.get("caption") or {}
                        image_url = item.get("thumbnail_url") or (item.get("image_versions2") or {}).get("candidates", [{}])[0].get("url")
                        
                        all_posts.append({
                            "アカウント": target, # 誰の投稿か判別用
                            "URL": f"https://www.instagram.com/p/{item.get('code')}/",
                            "画像URL": image_url,
                            "いいね数": item.get("like_count", 0),
                            "コメント数": item.get("comment_count", 0),
                            "本文": caption.get("text", "").replace("\n", ' ')[:50]
                        })
                    time.sleep(2) # 連続アクセスでブロックされないための休憩

            df = pd.DataFrame(all_posts)
            
            # 並び替え（全体の中でいいねが多い順）
            df = df.sort_values(by="いいね数", ascending=False)
            avg_likes = df["いいね数"].mean()
            df["判定"] = df["いいね数"].apply(lambda x: "🔥バズり" if x > avg_likes * 1.5 else "")

            with col2:
                st.header("分析レポート")

                # タブを作成して表示を分ける
                tab1, tab2, tab3 = st.tabs(["📊 比較分析", "📜 投稿一覧", "🔥 バズビジュアル"])

                with tab1:
                    st.subheader("アカウント別・平均いいね比較")
                    comparison_df = df.groupby("アカウント")["いいね数"].mean()
                    st.bar_chart(comparison_df)
                    
                    st.subheader("投稿順のいいね推移")
                    # indexをリセットして全体の推移を見やすくする
                    st.line_chart(df["いいね数"])

                with tab2:
                    st.subheader("全投稿データ一覧")
                    # どのアカウントの投稿か分かる状態で表を表示
                    st.dataframe(df, use_container_width=True)
                    
                    # ダウンロードボタンもここに配置
                    csv = df.to_csv(index=False, encoding="utf-8-sig").encode('utf-8-sig')
                    st.download_button("CSVを保存", data=csv, file_name="all_research_res.csv")

                with tab3:
                    st.subheader("全体の上位投稿")
                    top_posts = df.head(6) # せっかくなので上位6件表示
                    
                    # 3列×2段で表示する工夫
                    cols = st.columns(3)
                    for idx, row in enumerate(top_posts.itertuples()):
                        with cols[idx % 3]:
                            if row.画像URL:
                                st.image(row.画像URL, caption=f"【{row.アカウント}】 いいね:{row.いいね数}")
        
        except Exception as e:
            st.error(f"エラーが発生しました: {e}")