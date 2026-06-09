import os
import json
import time
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from google import genai
from google.genai import types

JST = timezone(timedelta(hours=9))

def fetch_crypto_news():
    """世界最大級の暗号資産メディアのRSSから最新ニュースを取得"""
    rss_url = "https://www.coindesk.com/arc/outboundfeeds/rss/"
    try:
        req = urllib.request.Request(rss_url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=10) as response:
            root = ET.fromstring(response.read())
            item = root.find('.//item')
            if item is not None:
                title = item.find('title').text
                desc = item.find('description').text
                return f"【最新ニュース】{title} - {desc}"
    except Exception as e:
        print(f"ニュース取得エラー: {e}")
    return "本日は大きなニュースの更新はありませんが、暗号資産市場は常に変動しています。"

def generate_ai_content(news_text):
    """Geminiを使って日英のブログ記事と分析を同時生成する（リトライ機能付き）"""
    api_key = os.environ.get("GEMINI_API_KEY_MEDIA")
    if not api_key:
        print("APIキーが設定されていません。")
        return None

    client = genai.Client(api_key=api_key)
    
    prompt = f"""
    あなたはプロの暗号資産アナリストであり、SEOライターです。
    以下の最新ニュースをもとに、読者がクリックしたくなる「相場分析」と「ブログ記事」を、
    【日本語】と【英語】の両方で作成してください。

    【最新ニュース】
    {news_text}

    【ルール】
    ・出力は必ず以下のJSON形式のみとすること（マークダウンや```json等の記号は絶対に入れないこと）。
    ・HTMLタグ（<p>, <strong>, <br>など）を使って、読みやすく美しいレイアウトにすること。
    ・アフィリエイトへの誘導文を必ずブログ記事の末尾に自然に入れること。

    {{
        "ja_analysis": "<p>今週の市場は...</p>",
        "en_analysis": "<p>This week's market...</p>",
        "ja_blog_title": "【高CTRタイトル】ビットコイン急騰？...",
        "en_blog_title": "Bitcoin Surges?...",
        "ja_blog_html": "<p>読者の皆さん、こんにちは。...</p>",
        "en_blog_html": "<p>Hello readers,...</p>"
    }}
    """

    MAX_RETRIES = 3
    for attempt in range(MAX_RETRIES):
        try:
            print(f"🤖 Geminiにリクエスト送信中... (試行 {attempt + 1}/{MAX_RETRIES})")
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.7
                )
            )
            return json.loads(response.text.strip())
        except Exception as e:
            print(f"⚠️ AI生成エラー (試行 {attempt + 1}): {e}")
            if attempt < MAX_RETRIES - 1:
                wait_time = 2 ** attempt * 5  # 5秒, 10秒と待機時間を増やす
                print(f"⏳ Googleサーバー混雑のため、{wait_time}秒後にリトライします...")
                time.sleep(wait_time)
            else:
                print("❌ 最大リトライ回数に達しました。")
                return None

def main():
    print("🚀 メディアOS: ポータル生成を開始します...")
    
    news_text = fetch_crypto_news()
    print(f"📰 取得したニュース: {news_text[:50]}...")

    ai_data = generate_ai_content(news_text)
    
    # 🛡️ クラッシュ完全防止機能（AIがダウンしていても仮画面を作ってデプロイを止めない）
    if not ai_data:
        print("⚠️ AIデータの生成に失敗しました。安全なデフォルトデータで代用し、システムを止めずに進行します。")
        ai_data = {
            "ja_analysis": "<p>現在、AIが詳細な相場分析を準備中です。次回の更新をお待ちください。</p>",
            "en_analysis": "<p>AI is currently preparing a detailed market analysis. Please wait for the next update.</p>",
            "ja_blog_title": "【お知らせ】次回のマーケットレポート準備中",
            "en_blog_title": "[Notice] Preparing Next Market Report",
            "ja_blog_html": "<p>Google AIサーバーの一時的な混雑により、最新のブログ記事を準備中です。数時間以内に自動復旧しますので、少々お待ちください。</p>",
            "en_blog_html": "<p>Due to temporary high demand on Google AI servers, the latest blog post is being prepared. It will automatically recover within a few hours.</p>"
        }

    # template.html の読み込み
    try:
        with open("template.html", "r", encoding="utf-8") as f:
            html_content = f.read()
    except Exception as e:
        print(f"❌ template.html が見つかりません: {e}")
        return

    # プレースホルダーの置換
    update_time = datetime.now(JST).strftime("%Y-%m-%d %H:%M:%S (JST)")
    
    html_content = html_content.replace("{{UPDATE_TIME}}", update_time)
    html_content = html_content.replace("{{JA_ANALYSIS}}", ai_data.get("ja_analysis", ""))
    html_content = html_content.replace("{{EN_ANALYSIS}}", ai_data.get("en_analysis", ""))
    html_content = html_content.replace("{{JA_BLOG_TITLE}}", ai_data.get("ja_blog_title", ""))
    html_content = html_content.replace("{{EN_BLOG_TITLE}}", ai_data.get("en_blog_title", ""))
    html_content = html_content.replace("{{JA_BLOG_HTML}}", ai_data.get("ja_blog_html", ""))
    html_content = html_content.replace("{{EN_BLOG_HTML}}", ai_data.get("en_blog_html", ""))

    # index.html として書き出し
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html_content)
    
    print("✅ index.html の生成が完了しました！")

if __name__ == "__main__":
    main()
