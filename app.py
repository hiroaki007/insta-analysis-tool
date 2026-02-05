import streamlit as st
import streamlit.components.v1 as components
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

# Google Analyticsの測定ID（G-XXXXXXXXXX）
GA_ID = "G-REMVLCYMSN"

# GA4のトラッキングコード
ga_code = f"""
    <script async src="https://www.googletagmanager.com/gtag/js?id={GA_ID}"></script>
    <script>
        window.dataLayer = window.dataLayer || [];
        function gtag(){{dataLayer.push(arguments);}}
        gtag('js', new Date());
        gtag('config', '{GA_ID}');
    </script>
"""


# --- 1. キャッシュ・リソース管理 ---

@st.cache_resource
def get_instagram_client(username, password):
    """Instagramへのログインを管理"""
    cl = Client()
    # IPブロック回避のための遅延設定
    cl.delay_range = [1, 3] 
    cl.login(username, password)
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

# --- 2. 認証・回数制限ロジック ---

def check_access():
    """URLパラメータによるスキップ判定と通常認証"""
    if "password_correct" not in st.session_state:
        st.session_state["password_correct"] = False

    # URLパラメータ ?access=free がある場合は無料体験モード
    is_free = (st.query_params.get("access") == "free")
    
    if is_free:
        st.session_state["password_correct"] = True
        if "welcome_toast" not in st.session_state:
            st.toast("🎉 無料体験モードで起動しました！", icon="🚀")
            st.session_state["welcome_toast"] = True
        return True, True

    if st.session_state["password_correct"]:
        return True, False

    st.title("🔐 Insco Client Access")
    st.write("このアプリをご利用いただくにはパスワードが必要です。")
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

# 権限チェック
access_granted, is_free_mode = check_access()
if not access_granted:
    st.stop()

# 回数制限チェック
can_use, remaining_count = check_usage_limit(is_free_mode)
if is_free_mode and not can_use:
    st.error("🚫 本日の無料体験回数（3回）を超えました。また明日お試しください！")
    st.info("LINE登録で無制限パスワードを配布中です。")
    st.markdown('<a href="https://lin.ee/GKsM8P9" target="_blank">👉 LINEで完全版パスワードを受け取る</a>', unsafe_allow_html=True)
    st.stop()

# --- 3. メイン画面 ---

st.title("📸 インスタリサーチ＆ダッシュボード")

if is_free_mode:
    st.warning(f"🔒 現在【無料体験モード】です。本日あと {remaining_count} 回分析可能です。")
else:
    st.success("💎 【完全版】ログイン済み：30件・3アカウント同時分析が可能です。")

if "all_results" not in st.session_state:
    st.session_state["all_results"] = None

col1, col2 = st.columns([1, 2])

with col1:
    st.header("設定")
    with st.form("search_form"):
        if is_free_mode:
            target_id = st.text_input("分析したいID (1件)", placeholder="nintendo_jp")
            st.caption("※無料版は最新5件固定です")
            count = st.slider("取得件数", 5, 30, 5, disabled=True)
        else:
            target_id = st.text_input("競合IDを入力 (カンマ区切りで3件まで)", placeholder="nintendo_jp, sony, starbucks_j")
            st.caption("※完全版：最大30件まで分析可能")
            count = st.slider("取得件数", 5, 30, 15)
        
        start_btn = st.form_submit_button("リサーチ開始")

if start_btn:
    if not target_id:
        st.error("分析対象のIDを入力してください")
    else:
        if is_free_mode:
            st.session_state["usage_count"] += 1
        
        try:
            cl = get_instagram_client(USERNAME, PASSWORD)
            
            # 入力IDをリスト化
            raw_list = [i.strip() for i in target_id.split(",")]
            # モード別の件数制限
            target_list = raw_list[:1] if is_free_mode else raw_list[:3]
            
            all_posts = []
            progress_bar = st.progress(0, text="Instagramへアクセス中...")
            
            for i, target in enumerate(target_list):
                progress_bar.progress((i + 1) / len(target_list), text=f"{target} のデータを解析中...")
                posts = fetch_user_data(cl, target, count)
                all_posts.extend(posts)
                time.sleep(1) # IPブロック対策の待機
                
            progress_bar.empty()

            df = pd.DataFrame(all_posts)
            if not df.empty:
                df = df.sort_values(by="いいね数", ascending=False)
                avg_likes = df["いいね数"].mean()
                df["判定"] = df["いいね数"].apply(lambda x: "🔥バズり" if x > avg_likes * 1.5 else "")
                st.session_state["all_results"] = df
                st.success("分析が完了しました！")
            else:
                st.warning("投稿データが見つかりませんでした。")
                
        except Exception as e:
            st.error(f"エラーが発生しました: {e}")

# --- 4. レポート表示エリア ---

if st.session_state["all_results"] is not None:
    df = st.session_state["all_results"]
    
    with col2:
        st.header("分析レポート")
        tab1, tab2, tab3 = st.tabs(["📊 比較分析", "📜 投稿一覧", "🔥 バズビジュアル"])
        
        with tab1:
            st.subheader("平均いいね比較")
            st.bar_chart(df.groupby("アカウント")["いいね数"].mean())
            st.subheader("いいね数推移")
            st.line_chart(df["いいね数"])
            
        with tab2:
            st.subheader("全投稿データ一覧")
            st.dataframe(df, use_container_width=True)
            if is_free_mode:
                st.error("🔒 CSVダウンロードは完全版限定の機能です。")
            else:
                csv = df.to_csv(index=False, encoding="utf-8-sig").encode('utf-8-sig')
                st.download_button("CSVを保存する", data=csv, file_name="insco_analysis.csv")
                
        with tab3:
            st.subheader("上位投稿ギャラリー")
            top_posts = df.head(9)
            cols = st.columns(3)
            for idx, row in enumerate(top_posts.itertuples()):
                with cols[idx % 3]:
                    if row.画像URL:
                        st.image(row.画像URL, caption=f"【{row.アカウント}】 ❤️ {row.いいね数}")

# --- 5. フッター：LINE誘導セクション ---
st.divider()
line_html = f"""
<div style="background-color: #f8f9fa; border: 2px solid #06C755; border-radius: 15px; padding: 25px; text-align: center; margin-top: 20px; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
    <h3 style="color: #333; margin-bottom: 10px;">🎁 ベータ版につき【完全開放中】</h3>
    <p style="color: #666; font-size: 15px; margin-bottom: 20px;">
        公式LINEに登録するだけで、<b>完全版アクセスパスワード</b>を即発行します。<br>
        取得件数の上限アップ・CSV保存・複数同時比較がすべて使い放題！
    </p>
    <a href="https://lin.ee/GKsM8P9" target="_blank" style="text-decoration: none;">
        <div style="background-color: #06C755; color: white; padding: 15px 35px; border-radius: 50px; font-weight: bold; font-size: 18px; display: inline-block; transition: 0.3s;">
            ✨ 完全版パスワードを無料で受け取る
        </div>
    </a>
    <p style="color: #999; font-size: 12px; margin-top: 15px;">※登録後、あいさつメッセージでパスワードが自動送信されます。</p>
</div>
"""
st.markdown(line_html, unsafe_allow_html=True)