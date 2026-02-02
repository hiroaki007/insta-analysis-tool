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
            with st.spinner(f"{target_id}のデータを解析中..."):
                user_info = cl.user_info_by_username_v1(target_id)
                user_id = user_info.pk

                result = cl.private_request(f"feed/user/{user_id}/", params={"count": count})
                items = result.get("items", [])

                posts = []
                for item in items:
                    caption = item.get("caption") or {}

                    # 画像URLを取得（リール動画の場合はサムネイルを取得）
                    image_url = item.get("thumbnail_url") or (item.get("image_versions2") or {}).get("candidates", [{}])[0].get("url")

                    posts.append({
                        "URL": f"https://www.instagram.com/p/{item.get('code')}/",
                        "画像URL": image_url, # これを追加！
                        "いいね数": item.get("like_count", 0),
                        "コメント数": item.get("comment_count", 0),
                        "本文": caption.get("text", "").replace("\n", ' ')[:50]
                    })
                
                # (前略：データ整形のループが終わったあと)
                df = pd.DataFrame(posts)

                # いいね数が多い順に並び替える方法

                df = df.sort_values(by="いいね数", ascending=False)

                # バズり分析 (修正済)
                avg_likes = df["いいね数"].mean()
                df["判定"] = df["いいね数"].apply(lambda x: "🔥バズり" if x > avg_likes * 1.5 else "")

            with col2:
                st.header("分析結果")
                st.metric("平均いいね数", f"{avg_likes:.1f}")
                
                # グラフの追加
                # --- 追加：上位3件の画像を表示 ---
                st.subheader("🔥 TOP3 投稿のビジュアル")
                top_posts = df.head(3) # 上位3件を抜き出す
                
                # 3つの列を作って横並びにする
                img_cols = st.columns(3)
                for idx, row in enumerate(top_posts.itertuples()):
                    with img_cols[idx]:
                        if row.画像URL:
                            st.image(row.画像URL, caption=f"いいね: {row.いいね数}")
                # ------------------------------
                
                st.subheader("📊 いいね数の推移（折れ線）")
                st.line_chart(df.set_index("URL")["いいね数"])


                st.dataframe(df, use_container_width=True)



                # ダウンロードボタン (修正済)
                csv = df.to_csv(index=False, encoding="utf-8-sig").encode('utf-8-sig')
                st.download_button("結果をCSVで保存", data=csv, file_name=f"{target_id}_res.csv")

        except Exception as e:
            st.error(f"エラーが発生しました: {e}")