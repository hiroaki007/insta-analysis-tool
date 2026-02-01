import os
import time
import random
import pandas as pd
from dotenv import load_dotenv
from instagrapi import Client

load_dotenv()
USERNAME = os.getenv("INSTA_USERNAME")
PASSWORD = os.getenv("INSTA_PASSWORD")

# 分析ターゲット
TARGET_USERS = ["nintendo_jp", "sony", "xbox"] 

cl = Client()

def login():
    session_file = "session.json"
    if os.path.exists(session_file):
        cl.load_settings(session_file)
    cl.login(USERNAME, PASSWORD)
    cl.dump_settings(session_file)
    print("✅ ログイン成功")

def get_user_posts_ultimate(target_username):
    """
    ID取得から投稿取得まで、バグを回避して直接通信する究極の安定関数
    """
    try:
        print(f"🔍 {target_username} を分析中...")
        
        # 1. ユーザーの基本情報を直接取得（ライブラリのバグ回避）
        user_info = cl.user_info_by_username_v1(target_username)
        user_id = user_info.pk
        
        # 2. 投稿を直接リクエスト
        result = cl.private_request(f"feed/user/{user_id}/", params={"count": 10})
        items = result.get("items", [])
        
        posts = []
        for item in items:
            code = item.get("code")
            caption = item.get("caption") or {}
            # ↓ ここを replace に修正！
            text = caption.get("text", "").replace('\n', ' ')
            
            posts.append({
                "ユーザー名": target_username,
                "URL": f"https://www.instagram.com/p/{code}/",
                "いいね数": item.get("like_count", 0),
                "コメント数": item.get("comment_count", 0),
                "本文": text[:30]
            })
        return posts
    except Exception as e:
        print(f"⚠️ {target_username} の取得中にエラー: {e}")
        return []

if __name__ == "__main__":
    login()
    
    all_results = []
    for user in TARGET_USERS:
        data = get_user_posts_ultimate(user)
        all_results.extend(data)
        
        # 次のユーザーへ行く前にランダム待機（ボット検知回避）
        wait = random.uniform(5, 10)
        print(f"⏳ {wait:.1f}秒 待機中...")
        time.sleep(wait)

    if all_results:
        df = pd.DataFrame(all_results)
        
        # 各ユーザーごとのバズり分析
        df["ユーザー平均いいね"] = df.groupby("ユーザー名")["いいね数"].transform("mean")
        df["バズり判定"] = df.apply(lambda row: "★バズり" if row["いいね数"] > row["ユーザー平均いいね"] * 1.5 else "", axis=1)

        timestamp = time.strftime("%Y%m%d_%H%M")
        output_path = f"data/bulk_analysis_{timestamp}.csv"
        df.to_csv(output_path, index=False, encoding="utf-8-sig")
        
        print("-" * 30)
        print(f"✨ 完了！ 保存先: {output_path}")
        print(df[["ユーザー名", "いいね数", "バズり判定"]])