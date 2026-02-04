import streamlit as st
import pandas as pd
from instagrapi import Client
import os 
import time
import datetime
from dotenv import load_dotenv

# .envの読み込み
load_dotenv()
USERNAME = os.getenv("INSTA_USERNAME")
PASSWORD = os.getenv("INSTA_PASSWORD")
MASTER_PASSWORD = os.getenv("APP_ACCESS_PASSWORD", "default_pass")

st.set_page_config(page_title="Insta Analytics - Insco", layout="wide")

# --- 1. キャッシュ・リソース管理 ---

@st.cache_resource
def get_instagram_client(username, password):
    cl = Client()
    session_file = "insta_session.json"
    
    # 1. 保存されたセッションがあればそれを読み込む
    if os.path.exists(session_file):
        try:
            cl.load_settings(session_file)
            cl.login(username, password)
            return cl
        except Exception:
            # セッションが無効なら削除して再ログイン
            os.remove(session_file)

    # 2. セッションがない場合のみ、新規ログイン
    cl.login(username, password)
    cl.dump_settings(session_file) # ログイン成功後に情報を保存
    return cl

@st.cache_data(ttl=3600)
def fetch_user_data(_cl, target_username, count):
    """特定のユーザーの投稿データを取得"""
    user_info = _cl.user_info_by_username_v1(target_username)
    user_id = user_info.pk
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

# --- 2. 認証・回数制限ロジック ---

def check_access():
    """URLパラメータによるスキップと通常パスワード認証"""
    if "password_correct" not in st.session_state:
        st.session_state["password_correct"] = False

    # URLパラメータ ?access=free がある場合は強制的にTrue
    is_free = (st.query_params.get("access") == "free")
    if is_free:
        st.session_state["password_correct"] = True
        if "welcome_toast" not in st.session_state:
            st.toast("🎉 無料体験モードで起動しました！", icon="🚀")
            st.session_state["welcome_toast"] = True
        return True, True

    # 通常のパスワードチェック
    if st.session_state["password_correct"]:
        return True, False

    st.title("🔐 Client Access Only")
    password = st.text_input("アクセスパスワードを入力してください", type="password")
    if st.button("ログイン"):
        if password == MASTER_PASSWORD:
            st.session_state["password_correct"] = True
            st.rerun()
        else:
            st.error("パスワードが違います")
    return False, False

def check_usage_limit(is_free_mode):
    """無料ユーザーの1日の回数制限 (1日3回)"""
    if not is_free_mode:
        return True, 0
    today = str(datetime.date.today())
    if "usage_date" not in st.session_state or st.session_state["usage_date"] != today:
        st.session_state["usage_date"] = today
        st.session_state["usage_count"] = 0
    remaining = 3 - st.session_state["usage_count"]
    return (remaining > 0), remaining

# アクセス権の確認
access_granted, is_free_mode = check_access()
if not access_granted:
    st.stop()

# 回数制限の確認
can_use, remaining_count = check_usage_limit(is_free_mode)
if is_free_mode and not can_use:
    st.error("🚫 本日の無料体験回数（3回）を超えました。また明日お試しください！")
    st.info("LINE登録で無制限パスワードを配布中です。")
    st.markdown('<a href="YOUR_LINE_URL" target="_blank">👉 LINEでパスワードを受け取る</a>', unsafe_allow_html=True)
    st.stop()

# --- 3. メインアプリ画面 ---

st.title("📸 インスタリサーチ＆ダッシュボード")
if is_free_mode:
    st.warning(f"🔒 無料体験モード：本日あと {remaining_count} 回分析可能です。")

if "all_results" not in st.session_state:
    st.session_state["all_results"] = None

col1, col2 = st.columns([1, 2])

with col1:
    st.header("設定")
    with st.form("search_form"):
        placeholder = "例: nintendo_jp" if is_free_mode else "nintendo_jp, sony"
        target_id = st.text_input("競合IDを入力", placeholder=placeholder)
        
        if is_free_mode:
            st.caption("※無料版は最新5件固定です")
            count = st.slider("取得件数", 5, 30, 5, disabled=True)
        else:
            count = st.slider("取得件数", 5, 50, 10)
        
        start_btn = st.form_submit_button("リサーチ開始")

if start_btn:
    if not target_id:
        st.error("IDを入力してください")
    else:
        # 回数カウントアップ
        if is_free_mode:
            st.session_state["usage_count"] += 1
        
        try:
            cl = get_instagram_client(USERNAME, PASSWORD)
            target_list = [i.strip() for i in target_id.split(",")]
            if is_free_mode:
                target_list = target_list[:1] # 無料版は1つのみ
            
            all_posts = []
            progress_bar = st.progress(0, text="データ取得中...")
            for i, target in enumerate(target_list):
                progress_bar.progress((i + 1) / len(target_list), text=f"{target} を解析中...")
                posts = fetch_user_data(cl, target, count)
                all_posts.extend(posts)
                time.sleep(1)
            progress_bar.empty()

            df = pd.DataFrame(all_posts)
            if not df.empty:
                df = df.sort_values(by="いいね数", ascending=False)
                avg_likes = df["いいね数"].mean()
                df["判定"] = df["いいね数"].apply(lambda x: "🔥バズり" if x > avg_likes * 1.5 else "")
                st.session_state["all_results"] = df
        except Exception as e:
            st.error(f"エラー: {e}")

# --- 4. レポート表示 ---

if st.session_state["all_results"] is not None:
    df = st.session_state["all_results"]
    with col2:
        st.header("分析レポート")
        tab1, tab2, tab3 = st.tabs(["📊 比較分析", "📜 投稿一覧", "🔥 画像一覧"])
        
        with tab1:
            st.bar_chart(df.groupby("アカウント")["いいね数"].mean())
            st.line_chart(df["いいね数"])
        with tab2:
            st.dataframe(df, use_container_width=True)
            if is_free_mode:
                st.error("🔒 CSV保存は完全版限定です")
            else:
                csv = df.to_csv(index=False, encoding="utf-8-sig").encode('utf-8-sig')
                st.download_button("CSVを保存", data=csv, file_name="res.csv")
        with tab3:
            cols = st.columns(3)
            for idx, row in enumerate(df.head(9).itertuples()):
                with cols[idx % 3]:
                    if row.画像URL: st.image(row.画像URL, caption=f"いいね:{row.いいね数}")

st.divider()
st.markdown(f'<div style="text-align:center"><p>気に入ったらLINEで完全版へ！</p><a href="YOUR_LINE_URL">LINE登録はこちら</a></div>', unsafe_allow_html=True)