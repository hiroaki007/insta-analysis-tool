import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
from instagrapi import Client
import os 
import time
import datetime
import json
from dotenv import load_dotenv

# .envの読み込み
load_dotenv()
USERNAME = os.getenv("INSTA_USERNAME")
PASSWORD = os.getenv("INSTA_PASSWORD")
MASTER_PASSWORD = os.getenv("APP_ACCESS_PASSWORD", "default_pass")

st.set_page_config(page_title="Insta Analytics - Insco", layout="wide")

# Google Analytics 設定
GA_ID = "G-REMVLCYMSN"
ga_code = f"""
    <script async src="https://www.googletagmanager.com/gtag/js?id={GA_ID}"></script>
    <script>
        window.dataLayer = window.dataLayer || [];
        function gtag(){{dataLayer.push(arguments);}}
        gtag('js', new Date());
        gtag('config', '{GA_ID}');
    </script>
"""
components.html(ga_code, height=0)

# --- 1. Instagramログイン管理 (セッション保存対応) ---

def get_instagram_client(username, password):
    """パスワードを使わず Session ID で直接ログインする"""
    cl = Client()
    
    # 自宅Macへのトンネル設定
    cl.set_proxy("socks5://127.0.0.1:1080")

    # ブラウザから取得した最新の sessionid をここに入れてください
    # ※コード内に直接書くのが一番確実です
    MY_SESSION_ID = "80518945892%3A8JmMwEFs2KYO3o%3A6%3AAYiVqQir3aBZ-XPAVNH1bwFPx2jkg9CtgMXSe46YBQ"

    cl.delay_range = [2, 5]
    
    try:
        # パスワードログインを一切行わず、Session IDだけで入る
        st.info("Session IDを使用して認証中...")
        cl.login_by_sessionid(MY_SESSION_ID)
        
        # 内部エラー防止のため、ユーザー名だけセットしておく
        cl.username = username
        
        # ログインできているか念のためテスト（ユーザー自身の情報を取得）
        cl.account_info()
        st.success("セッション認証に成功しました！")
        
    except Exception as e:
        st.error(f"セッションログイン失敗: {e}")
        st.warning("Session IDが期限切れの可能性があります。ブラウザで再取得してください。")
        return None
        
    return cl

@st.cache_data(ttl=3600)
def fetch_user_data(_cl, target_username, count):
    """特定のユーザーの投稿データを取得"""
    try:
        user_info = _cl.user_info_by_username_v1(target_username)
        user_id = user_info.pk
        result = _cl.private_request(f"feed/user/{user_id}/", params={"count": count})
        items = result.get("items", [])
        
        posts = []
        for item in items:
            caption = item.get("caption") or {}
            image_versions = item.get("image_versions2") or {}
            candidates = image_versions.get("candidates", [{}])
            image_url = item.get("thumbnail_url") or candidates[0].get("url")
            
            posts.append({
                "アカウント": target_username,
                "URL": f"https://www.instagram.com/p/{item.get('code')}/",
                "画像URL": image_url,
                "いいね数": item.get("like_count", 0),
                "コメント数": item.get("comment_count", 0),
                "本文": caption.get("text", "").replace("\n", ' ')[:50]
            })
        return posts
    except Exception as e:
        st.error(f"{target_username} のデータ取得に失敗しました: {e}")
        return []

# --- 2. 認証・回数制限ロジック ---

def check_access():
    if "password_correct" not in st.session_state:
        st.session_state["password_correct"] = False

    is_free = (st.query_params.get("access") == "free")
    
    if is_free:
        st.session_state["password_correct"] = True
        return True, True

    if st.session_state["password_correct"]:
        return True, False

    st.title("🔐 Insco Client Access")
    password = st.text_input("アクセスパスワード", type="password")
    if st.button("ログイン"):
        if password == MASTER_PASSWORD:
            st.session_state["password_correct"] = True
            st.rerun()
        else:
            st.error("パスワードが違います")
    return False, False

def check_usage_limit(is_free_mode):
    if not is_free_mode:
        return True, 0
    today = str(datetime.date.today())
    if "usage_date" not in st.session_state or st.session_state["usage_date"] != today:
        st.session_state["usage_date"] = today
        st.session_state["usage_count"] = 0
    remaining = 3 - st.session_state["usage_count"]
    return (remaining > 0), remaining

# --- メインロジック ---

access_granted, is_free_mode = check_access()
if not access_granted:
    st.stop()

can_use, remaining_count = check_usage_limit(is_free_mode)
if is_free_mode and not can_use:
    st.error("🚫 本日の無料体験回数（3回）を超えました。")
    st.stop()

st.title("📸 インスタリサーチ Insco")

if "all_results" not in st.session_state:
    st.session_state["all_results"] = None

col1, col2 = st.columns([1, 2])

with col1:
    with st.form("search_form"):
        target_id = st.text_input("分析したいID (カンマ区切り)", placeholder="nintendo_jp")
        count = st.slider("取得件数", 5, 30, 15) if not is_free_mode else 5
        start_btn = st.form_submit_button("リサーチ開始")

if start_btn:
    if not target_id:
        st.error("IDを入力してください")
    else:
        if is_free_mode:
            st.session_state["usage_count"] += 1
        
        try:
            # ログイン処理
            cl = get_instagram_client(USERNAME, PASSWORD)
            
            raw_list = [i.strip() for i in target_id.split(",")]
            target_list = raw_list[:1] if is_free_mode else raw_list[:3]
            
            all_posts = []
            progress_bar = st.progress(0, text="解析中...")
            
            for i, target in enumerate(target_list):
                progress_bar.progress((i + 1) / len(target_list))
                posts = fetch_user_data(cl, target, count)
                all_posts.extend(posts)
                time.sleep(2) # ブロック回避の待機
                
            progress_bar.empty()

            if all_posts:
                df = pd.DataFrame(all_posts)
                df = df.sort_values(by="いいね数", ascending=False)
                avg_likes = df["いいね数"].mean()
                df["判定"] = df["いいね数"].apply(lambda x: "🔥バズり" if x > avg_likes * 1.5 else "")
                st.session_state["all_results"] = df
                st.success("分析完了！")
        except Exception as e:
            st.error(f"致命的なエラー: {e}")

# レポート表示エリア
if st.session_state["all_results"] is not None:
    df = st.session_state["all_results"]
    with col2:
        tab1, tab2, tab3 = st.tabs(["📊 分析", "📜 一覧", "🔥 ギャラリー"])
        with tab1:
            st.bar_chart(df.groupby("アカウント")["いいね数"].mean())
        with tab2:
            st.dataframe(df)
            if not is_free_mode:
                csv = df.to_csv(index=False).encode('utf-8-sig')
                st.download_button("CSV保存", data=csv, file_name="insco.csv")
        with tab3:
            cols = st.columns(3)
            for idx, row in enumerate(df.head(9).itertuples()):
                with cols[idx % 3]:
                    st.image(row.画像URL, caption=f"{row.いいね数}")

# フッター誘導
st.divider()
st.info("💎 完全版パスワードは公式LINEで配布中！")