import os
import json
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from google import genai
from google.genai import types

JST = timezone(timedelta(hours=9))

def fetch_crypto_news():
    """世界最大級の暗号資産メディア（CoinDesk等）のRSSから最新ニュースを1件取得"""
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
    """Geminiを使って日英のブログ記事と分析を同時生成する"""
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

    try:
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
        print(f"AI生成エラー: {e}")
        return None

def main():
    print("🚀 メディアOS: ポータル生成を開始します...")
    
    news_text = fetch_crypto_news()
    print(f"📰 取得したニュース: {news_text[:50]}...")

    ai_data = generate_ai_content(news_text)
    if not ai_data:
        print("❌ AIデータの生成に失敗したため、処理を中断します。")
        return

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

    # index.html として書き出し（これがCloudflareへデプロイされる本番ファイルになります）
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html_content)
    
    print("✅ index.html の生成が完了しました！")

if __name__ == "__main__":
    main()
