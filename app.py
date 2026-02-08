import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import requests
import os 
import time
import datetime
from dotenv import load_dotenv

# --- 0. 環境設定 & 3種の神器 ---
load_dotenv()

# ※これらは .env に書くか、直接書き換えてください
ACCESS_TOKEN = os.getenv("INSTA_ACCESS_TOKEN")
MY_INSTA_ID = os.getenv("MY_INSTA_BUSINESS_ID")
MASTER_PASSWORD = os.getenv("APP_ACCESS_PASSWORD", "default_pass")
CLIENT_ID = "1661375178186382" 
CLIENT_SECRET = os.getenv("INSTA_CLIENT_SECRET")


st.set_page_config(page_title="Insta Analytics - Insco", layout="wide")

# --- 1. Google Analytics 設定 (既存維持) ---
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

# --- トークンの自動更新機能を追加 ---

def refresh_long_lived_token(token):
    """
    今ある長期トークンの期限をさらに60日延長する
    """
    url = "https://graph.facebook.com/v21.0/oauth/access_token"
    params = {
        "grant_type": "fb_exchange_token",
        "client_id": "1661375178186382", # あなたのアプリID (スクリーンショットより)
        "client_secret": "ここにあなたのアプリシークレットを貼る", # ★重要★
        "fb_exchange_token": token
    }
    
    try:
        response = requests.get(url, params=params)
        data = response.json()
        if "access_token" in data:
            # 新しいトークンを返す
            return data["access_token"]
        else:
            return token # 失敗した場合は元のトークンを返す
    except:
        return token

# --- メインロジックの冒頭でトークンを更新 ---

# 起動時に一度だけトークンをリフレッシュ（簡易版）
if "refreshed_token" not in st.session_state:
    new_token = refresh_long_lived_token(ACCESS_TOKEN)
    st.session_state["refreshed_token"] = new_token
    # 以降、APIリクエストには st.session_state["refreshed_token"] を使うように変更



# --- 2. 公式API データ取得エンジン ---

@st.cache_data(ttl=3600)
def fetch_user_data_official(target_username, count):
    """Business Discoveryを使用して特定ユーザーの投稿を取得"""
    url = f"https://graph.facebook.com/v21.0/{MY_INSTA_ID}"
    fields = f"business_discovery.username({target_username}){{media.limit({count}){{id,caption,like_count,comments_count,media_url,permalink,timestamp}}}}"
    params = {"fields": fields, "access_token": ACCESS_TOKEN}

    try:
        response = requests.get(url, params=params)
        data = response.json()
        
        if "error" in data:
            st.error(f"APIエラー ({target_username}): {data['error'].get('message')}")
            return []

        items = data.get("business_discovery", {}).get("media", {}).get("data", [])
        posts = []
        for item in items:
            posts.append({
                "アカウント": target_username,
                "URL": item.get("permalink"),
                "画像URL": item.get("media_url"),
                "いいね数": item.get("like_count", 0),
                "コメント数": item.get("comments_count", 0),
                "本文": (item.get("caption") or "").replace("\n", ' ')[:50],
                "投稿日時": item.get("timestamp")
            })
        return posts
    except Exception as e:
        st.error(f"接続失敗: {e}")
        return []

# --- 3. 認証・制限ロジック (既存維持) ---

def check_access():
    if "password_correct" not in st.session_state:
        st.session_state["password_correct"] = False
    
    # URLパラメータ ?access=free のチェック
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

# --- 4. メインロジック ---

access_granted, is_free_mode = check_access()
if not access_granted:
    st.stop()

can_use, remaining_count = check_usage_limit(is_free_mode)
if is_free_mode and not can_use:
    st.error("🚫 本日の無料体験回数（3回）を超えました。公式LINEからパスワードを取得してください。")
    st.stop()

st.title("📸 インスタリサーチ Insco (Official API)")

if "all_results" not in st.session_state:
    st.session_state["all_results"] = None

col1, col2 = st.columns([1, 2])

with col1:
    with st.form("search_form"):
        target_id = st.text_input("分析したいID (カンマ区切り)", placeholder="nintendo_jp")
        # 無料枠なら5件固定、パスありならスライダー有効
        count = st.slider("取得件数", 5, 50, 15) if not is_free_mode else 5
        start_btn = st.form_submit_button("リサーチ開始")

if start_btn:
    if not target_id:
        st.error("IDを入力してください")
    else:
        if is_free_mode:
            st.session_state["usage_count"] += 1
        
        raw_list = [i.strip() for i in target_id.split(",")]
        # 無料なら1件、パスありなら3件まで
        target_list = raw_list[:1] if is_free_mode else raw_list[:3]
        
        all_posts = []
        progress_bar = st.progress(0, text="公式APIで高速解析中...")
        
        for i, target in enumerate(target_list):
            progress_bar.progress((i + 1) / len(target_list))
            posts = fetch_user_data_official(target, count)
            all_posts.extend(posts)
            time.sleep(0.5) # 公式APIなので待機は短くてOK
            
        progress_bar.empty()

        if all_posts:
            df = pd.DataFrame(all_posts)
            df = df.sort_values(by="いいね数", ascending=False)
            avg_likes = df["いいね数"].mean()
            # 解析系：バズり判定ロジック
            df["判定"] = df["いいね数"].apply(lambda x: "🔥バズり" if x > avg_likes * 1.5 else "")
            st.session_state["all_results"] = df
            st.success(f"分析完了！ {'(無料枠: 残り' + str(remaining_count-1) + '回)' if is_free_mode else ''}")

# --- 5. レポート表示エリア (既存維持) ---

if st.session_state["all_results"] is not None:
    df = st.session_state["all_results"]
    with col2:
        tab1, tab2, tab3 = st.tabs(["📊 分析", "📜 一覧", "🔥 ギャラリー"])
        
        with tab1:
            st.subheader("平均いいね数 (アカウント別)")
            st.bar_chart(df.groupby("アカウント")["いいね数"].mean())
            
        with tab2:
            st.dataframe(df)
            if not is_free_mode:
                csv = df.to_csv(index=False).encode('utf-8-sig')
                st.download_button("📥 CSV保存 (パスワード特典)", data=csv, file_name="insco_research.csv")
        
        with tab3:
            st.subheader("人気投稿トップ9")
            cols = st.columns(3)
            # いいね数上位9件を表示
            for idx, row in enumerate(df.head(9).itertuples()):
                with cols[idx % 3]:
                    st.image(row.画像URL, use_container_width=True)
                    st.caption(f"❤️ {row.いいね数} | {row.判定}")
                    st.markdown(f"[投稿を見る]({row.URL})")

# フッター
st.divider()
st.info("💎 完全版パスワードは公式LINEで配布中！")