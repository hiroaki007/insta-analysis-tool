import streamlit as st
import pandas as pd
from instagrapi import Client
import os 
import time
from dotenv import load_dotenv

# .envの読み込み
load_dotenv()
USERNAME = os.getenv("INSTA_USERNAME")
PASSWORD = os.getenv("INSTA_PASSWORD")
MASTER_PASSWORD = os.getenv("APP_ACCESS_PASSWORD", "default_pass")

st.set_page_config(page_title="Insta Analytics", layout="wide")

# --- 1. キャッシュ・リソース管理 ---

@st.cache_resource
def get_instagram_client(username, password):
    """Instagramへのログインを1回だけに制限する"""
    cl = Client()
    # VPS環境での安定性を高めるための設定
    cl.delay_range = [1, 3] 
    cl.login(username, password)
    return cl

@st.cache_data(ttl=3600)  # 1時間は同じIDの結果をキャッシュから出す
def fetch_user_data(_cl, target_username, count):
    """特定のユーザーの投稿データを取得する（通信部分を分離）"""
    # ユーザー情報の取得
    user_info = _cl.user_info_by_username_v1(target_username)
    user_id = user_info.pk
    
    # 投稿取得
    result = _cl.private_request(f"feed/user/{user_id}/", params={"count": count})
    items = result.get("items", [])
    
    posts = []
    for item in items:
        caption = item.get("caption") or {}
        image_url = item.get("thumbnail_url") or (item.get("image_versions2") or {}).get("candidates", [{}])[0].get("url")
        
        posts.append({
            "アカウント": target_username,
            "URL": f"https://www.instagram.com/p/{item.get('code')}/",
            "画像URL": image_url,
            "いいね数": item.get("like_count", 0),
            "コメント数": item.get("comment_count", 0),
            "本文": caption.get("text", "").replace("\n", ' ')[:50]
        })
    return posts

# --- 2. パスワード認証機能 ---

def check_password():
    if "password_correct" not in st.session_state:
        st.session_state["password_correct"] = False

    if st.session_state["password_correct"]:
        return True

    st.title("🔐 Client Access Only")
    password = st.text_input("アクセスパスワードを入力してください", type="password")
    if st.button("ログイン"):
        if password == MASTER_PASSWORD:
            st.session_state["password_correct"] = True
            st.rerun()
        else:
            st.error("パスワードが違います")
    return False

if not check_password():
    st.stop()

# --- 3. メインアプリ画面 ---

st.title("📸 インスタリサーチ＆ダッシュボード")

# セッション状態の初期化（結果を保持するため）
if "all_results" not in st.session_state:
    st.session_state["all_results"] = None

col1, col2 = st.columns([1, 2])

with col1:
    st.header("設定")
    # フォームにすることで入力中のリロードを防ぐ
    with st.form("search_form"):
        target_id = st.text_input("競合IDを入力 (カンマ区切り可)", placeholder="nintendo_jp, sony")
        count = st.slider("取得件数", 5, 30, 10)
        start_btn = st.form_submit_button("リサーチ開始")

if start_btn:
    if not target_id:
        st.error("ターゲットIDを入力してください")
    else:
        try:
            # 修正：定義した関数名を正しく呼ぶ
            cl = get_instagram_client(USERNAME, PASSWORD)
            target_list = [i.strip() for i in target_id.split(",")]
            
            all_posts = []
            for target in target_list:
                with st.spinner(f"{target} のデータを取得中..."):
                    # キャッシュ化した関数を呼び出し
                    posts = fetch_user_data(cl, target, count)
                    all_posts.extend(posts)
                    time.sleep(1) # VPSブロック回避用

            # 結果をセッションに保存
            df = pd.DataFrame(all_posts)
            if not df.empty:
                df = df.sort_values(by="いいね数", ascending=False)
                avg_likes = df["いいね数"].mean()
                df["判定"] = df["いいね数"].apply(lambda x: "🔥バズり" if x > avg_likes * 1.5 else "")
                st.session_state["all_results"] = df
            
        except Exception as e:
            st.error(f"エラーが発生しました: {e}")

# --- 4. 分析レポート表示エリア ---

if st.session_state["all_results"] is not None:
    df = st.session_state["all_results"]
    
    with col2:
        st.header("分析レポート")
        tab1, tab2, tab3 = st.tabs(["📊 比較分析", "📜 投稿一覧", "🔥 バズビジュアル"])

        with tab1:
            st.subheader("アカウント別・平均いいね比較")
            comparison_df = df.groupby("アカウント")["いいね数"].mean()
            st.bar_chart(comparison_df)
            
            st.subheader("投稿順のいいね推移")
            st.line_chart(df["いいね数"])

        with tab2:
            st.subheader("全投稿データ一覧")
            st.dataframe(df, use_container_width=True)
            csv = df.to_csv(index=False, encoding="utf-8-sig").encode('utf-8-sig')
            st.download_button("CSVを保存", data=csv, file_name="all_research_res.csv")

        with tab3:
            st.subheader("全体の上位投稿")
            top_posts = df.head(9)
            cols = st.columns(3)
            for idx, row in enumerate(top_posts.itertuples()):
                with cols[idx % 3]:
                    if row.画像URL:
                        st.image(row.画像URL, caption=f"【{row.アカウント}】 いいね:{row.いいね数}")