import os
import json
import time
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from google import genai
from google.genai import types

JST = timezone(timedelta(hours=9))
DATA_DIR = "data"
ARTICLES_DIR = "dist/asset-os-connection/articles"
MAX_HISTORY_LIMIT = 10  # 蓄積する最大記事数。これを超えたら古い順に自動削除（1GBの容量パンクを完全防止）

def fetch_os_data():
    """資産OSのtrade_log.jsonをサーバーサイドから安全にFetch（CORS制限なし）"""
    url = "https://asset.cocoro.workers.dev/trade_log.json"
    try:
        print("📡 資産OSのデータベースを安全にスキャン中...")
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read())
            regime = data.get("system_health", {}).get("current_regime", "Sideways")
            pf = str(data.get("system_stats", {}).get("recent_pf", "1.00"))
            
            # 直近のアクション取得
            action = "Standby"
            if data.get("trade_logs"):
                last_log = data["trade_logs"][-1]
                action = last_log.get("reason", "Standby")
                if len(action) > 15:
                    action = action[:15] + "..."
                    
            print(f"📊 OSデータ取得成功 ➔ レジーム: {regime} / PF: {pf} / 状態: {os_regime_to_ja(regime)}")
            return regime, pf, action
    except Exception as e:
        print(f"⚠️ 資産OSデータの取得をフォールバック回避しました: {e}")
    return "Active", "1.00", "Running"

def os_regime_to_ja(regime):
    mapping = {
        "Strong Bull": "強い上昇トレンド",
        "Weak Bull": "緩やかな上昇トレンド",
        "Strong Bear": "強い下落トレンド（安全回避ロック中）",
        "Weak Bear": "緩やかな下落トレンド",
        "Sideways": "横ばい（レンジ）相場"
    }
    return mapping.get(regime, "シグナル待機中")

def fetch_crypto_news():
    """暗号資産メディアのRSSから最新ニュースを取得"""
    rss_url = "https://www.coindesk.com/arc/outboundfeeds/rss/"
    try:
        req = urllib.request.Request(rss_url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=10) as response:
            root = ET.fromstring(response.read())
            item = root.find('.//item')
            if item is not None:
                title = item.find('title').text
                desc = item.find('description').text
                return f"【ニュース詳細】{title} - {desc}"
    except Exception as e:
        print(f"ニュース取得エラー: {e}")
    return "本日は大きなニュースの更新はありませんが、暗号資産市場は常に変動しています。"

def generate_ai_content(news_text, os_regime, os_pf, os_action):
    """まごころ資産OSのデータを踏まえて、世界に1つの超ハイクオリティ記事を生成する"""
    api_key = os.environ.get("GEMINI_API_KEY_MEDIA")
    if not api_key:
        print("APIキーが設定されていません。")
        return None

    client = genai.Client(api_key=api_key)
    
    os_regime_ja = os_regime_to_ja(os_regime)
    
    prompt = f"""
    あなたは、難解な経済やクオンツ運用を「中学生でも情景が浮かぶ言葉」で日本一わかりやすく解説する、プロの投資コラムニスト（編集長cocoro）です。
    以下の【最新ニュース】と、当社の完全自律AI自動売買システム【まごころ資産OSの本日のデータ】を厳密にマージし、
    他のサイトでは絶対に読めない「独自性・客観的データ・初心者への深い比喩」を交えた最高品質のコラムと分析を、
    【日本語】と【英語】の両方で作成してください。

    【最新ニュース】
    {news_text}

    【まごころ資産OSの本日のデータ】
    ・現在の市場レジーム判定: {os_regime} （日本語訳: {os_regime_ja}）
    ・システムPF（プロフィットファクター）: {os_pf}
    ・現在の行動ステータス: {os_action}

    【執筆の絶対ルール（デグレ・低価値判定の完全防止）】
    1. 【テーマの棲み分け（重複回避）】
       ・「ja_analysis/en_analysis（クオンツ分析）」には、最新ニュース（{news_text}）の内容は絶対に書かないでください。
         ここは「純粋に本日の資産OSデータ（レジーム、PF値、売買判断）から読み取れるテクニカルな市場動向と運用戦略の解説」に特化してください。
       ・「ja_blog_html/en_blog_html（ブログコラム）」にのみ、最新ニュースの具体的な中身（論争や出来事など）を比喩を交えて執筆してください。
         これにより、前半と後半での内容の重複を完全にゼロにし、読者を飽きさせないクリーンな構成にします。

    2. 【固有名詞の正確な保護（信頼性の死守）】
       ・文章中に登場するすべての固有名詞（例：MicroStrategy、Ark Invest、Bitcoin、Ethereum、Sora、xAI、マイケル・セイラーなど）は、
         勝手に省略したりスペルを変えたりせず（例：「MicroStrategy」を「Strategy」、「Ark Invest」を「Arca」とする等の中途半端な省略は厳禁）、
         正確な正式名称または日本で正しく通用する一般的表記で完璧に記述してください。

    3. 【断定表現の抑制（金融YMYL対策の徹底）】
       ・投資や利確に関する絶対的な断定表現や、「確実に利益が積み上げられる優秀なシステム」「勝てる」といった誇大広告に聞こえる不実表示は完全に排除してください。
       ・代わりに、「客観的なデータに基づいて感情を徹底排除した冷静な判断プロセス」「中長期的な資産防衛に主眼を置いた堅実な稼働設計」「リスク許容度を緻密に管理する論理的な判断」など、
         控えめで知的、かつ統計的な事実に基づく信頼性の極めて高いコラムを徹底してください。

    4. 【コラムの構成】
       ・日本語ブログのタイトルには「読者が思わずクリックして深く読みたくなる、具体的で疑問形を含んだ高CTRなタイトル」を付けてください。
       ・説明には必ず「たとえば〜」から始まる誰もが膝を打つような比喩（例え話）を深く掘り下げて記述し、専門用語は完全に噛み砕いてください。
       ・ブログコラムの末尾には、以下の免責事項と自然なアフィリエイト誘導文（検証環境の再現を前提とした自然な文脈）を必ず添えてください：
         「※本分析はAIと当社のクオンツデータに基づいていますが、投資の最終判断は自己責任でお願いいたします。
         👉 <a href="【あなたのアフィリエイトURL】" target="_blank" style="color:#58a6ff; font-weight:bold;">検証に使用している国内最大手 bitFlyer 口座開設（無料）はこちら</a>」

    【出力形式（厳格なJSON形式のみ）】
    ・マークダウンの```jsonや```などは絶対に出力に含めないでください。

    {{
        "ja_analysis": "<p>本日の資産OSのデータからは...</p>",
        "en_analysis": "<p>Based on today's Magokoro OS metrics...</p>",
        "ja_blog_title": "【高CTRタイトル】...",
        "en_blog_title": "...",
        "ja_blog_html": "<p>読者の皆さん、こんにちは。編集長のcocoroです。本日ニュースとなった出来事は...</p>",
        "en_blog_html": "<p>Hello readers, cocoro here. Today's news reveals...</p>"
    }}
    """

    # 🛡️ 503エラー混雑を突破するための、自動切り替え ＆ 指数バックオフ（最大5回リトライ）
    models_to_try = ["gemini-2.5-flash", "gemini-1.5-flash"]
    
    for model_name in models_to_try:
        max_retries = 3 if model_name == "gemini-2.5-flash" else 2
        for attempt in range(max_retries):
            try:
                print(f"🤖 Gemini ({model_name}) にリクエスト送信中... (試行 {attempt + 1}/{max_retries})")
                response = client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        temperature=0.7
                    )
                )
                return json.loads(response.text.strip())
            except Exception as e:
                print(f"⚠️ {model_name} エラー (試行 {attempt + 1}): {e}")
                if attempt < max_retries - 1:
                    wait_time = (2 ** attempt) * 10  # 10秒, 20秒... としっかり待機して混雑をすり抜ける
                    print(f"⏳ Googleサーバー混雑のため、{wait_time}秒後に再トライします...")
                    time.sleep(wait_time)
                else:
                    print(f"❌ {model_name} での生成を断念しました。")
                    
    print("❌ すべてのモデルで生成に失敗しました。")
    return None

def main():
    print("🚀 メディアOS: ポータルおよびアーカイブ自動生成を開始します...")
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(ARTICLES_DIR, exist_ok=True)
    
    # 資産OSデータのFetch
    os_regime, os_pf, os_action = fetch_os_data()

    news_text = fetch_crypto_news()
    print(f"📰 取得したニュース: {news_text[:50]}...")

    ai_data = generate_ai_content(news_text, os_regime, os_pf, os_action)
    
    # クラッシュ完全防止機能（AIがダウンしていても仮画面を作ってデプロブを止めない）
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

    # 最新記事をJSON履歴に保存する
    timestamp_slug = datetime.now(JST).strftime("%Y%m%d-%H%M%S")
    new_article_file = os.path.join(DATA_DIR, f"article-{timestamp_slug}.json")
    
    article_record = {
        "time": datetime.now(JST).strftime("%Y-%m-%d %H:%M:%S"),
        "os_regime": os_regime,
        "os_pf": os_pf,
        "os_action": os_action,
        "ja_analysis": ai_data["ja_analysis"],
        "en_analysis": ai_data["en_analysis"],
        "ja_blog_title": ai_data["ja_blog_title"],
        "en_blog_title": ai_data["en_blog_title"],
        "ja_blog_html": ai_data["ja_blog_html"],
        "en_blog_html": ai_data["en_blog_html"],
        "slug": f"article-{timestamp_slug}"
    }
    
    with open(new_article_file, "w", encoding="utf-8") as f:
        json.dump(article_record, f, ensure_ascii=False, indent=2)

    # ローテーション機能（10記事を超えたら古い順に自動削除：1GBの容量パンクを完全防止）
    all_json_files = sorted([f for f in os.listdir(DATA_DIR) if f.startswith("article-") and f.endswith(".json")], reverse=True)
    if len(all_json_files) > MAX_HISTORY_LIMIT:
        print(f"🗑️ 履歴制限({MAX_HISTORY_LIMIT}件)を超過したため、古い記事を自動パージします。")
        for old_file in all_json_files[MAX_HISTORY_LIMIT:]:
            # データJSONの削除
            json_path = os.path.join(DATA_DIR, old_file)
            if os.path.exists(json_path):
                os.remove(json_path)
            # 個別記事HTMLの削除
            html_slug = old_file.replace(".json", "")
            html_path = os.path.join(ARTICLES_DIR, f"{html_slug}.html")
            if os.path.exists(html_path):
                os.remove(html_path)

    # 過去ログからアーカイブ記事一覧のHTMLをビルドする
    active_json_files = sorted([f for f in os.listdir(DATA_DIR) if f.startswith("article-") and f.endswith(".json")], reverse=True)
    
    ja_archive_html = ""
    en_archive_html = ""
    
    for j_file in active_json_files:
        with open(os.path.join(DATA_DIR, j_file), "r", encoding="utf-8") as f:
            art = json.load(f)
            
        a_slug = art["slug"]
        a_time = art["time"]
        
        # 日本語アーカイブカード
        ja_archive_html += f"""
        <div class="article-card">
            <div class="article-meta">
                <span>📅 {a_time}</span>
                <span style="color:#56d364;">まごころ資産OS連動</span>
            </div>
            <h3>{art['ja_blog_title']}</h3>
            <p>{art['ja_analysis'][:80]}...</p>
            <a href="/asset-os-connection/articles/{a_slug}.html" class="read-more">続きを読む &rarr;</a>
        </div>
        """
        
        # 英語アーカイブカード
        en_archive_html += f"""
        <div class="article-card">
            <div class="article-meta">
                <span>📅 {a_time}</span>
                <span style="color:#56d364;">Magokoro OS Synced</span>
            </div>
            <h3>{art['en_blog_title']}</h3>
            <p>{art['en_analysis'][:80]}...</p>
            <a href="/asset-os-connection/articles/{a_slug}.html" class="read-more">Read More &rarr;</a>
        </div>
        """

    # template.html の読み込み
    try:
        with open("template.html", "r", encoding="utf-8") as f:
            template_content = f.read()
    except Exception as e:
        print(f"❌ template.html が見つかりません: {e}")
        return

    # ① すべての個別記事（過去記事）を template.html 1枚から静的ビルド(SSG)してarticles/に書き出す
    for j_file in active_json_files:
        with open(os.path.join(DATA_DIR, j_file), "r", encoding="utf-8") as f:
            art = json.load(f)
            
        a_slug = art["slug"]
        
        page_html = template_content
        page_html = page_html.replace("{{UPDATE_TIME}}", art["time"])
        page_html = page_html.replace("{{JA_ANALYSIS}}", art["ja_analysis"])
        page_html = page_html.replace("{{EN_ANALYSIS}}", art["en_analysis"])
        page_html = page_html.replace("{{JA_BLOG_TITLE}}", art["ja_blog_title"])
        page_html = page_html.replace("{{EN_BLOG_TITLE}}", art["en_blog_title"])
        page_html = page_html.replace("{{JA_BLOG_HTML}}", art["ja_blog_html"])
        page_html = page_html.replace("{{EN_BLOG_HTML}}", art["en_blog_html"])
        
        # 資産OSデータ
        page_html = page_html.replace("{{OS_REGIME}}", art["os_regime"])
        page_html = page_html.replace("{{OS_PF}}", art["os_pf"])
        page_html = page_html.replace("{{OS_ACTION}}", art["os_action"])
        
        # 個別記事ページにはアーカイブ一覧
        page_html = page_html.replace("{{JA_ARCHIVE_LIST}}", ja_archive_html)
        page_html = page_html.replace("{{EN_ARCHIVE_LIST}}", en_archive_html)
        
        # 個別HTMLの出力
        with open(os.path.join(ARTICLES_DIR, f"{a_slug}.html"), "w", encoding="utf-8") as f:
            f.write(page_html)

    # ② 最新コラムを載せた index.html（トップページ）のビルド
    latest_art = article_record  # 今回生成した最新記事
    
    index_html = template_content
    index_html = index_html.replace("{{UPDATE_TIME}}", latest_art["time"])
    index_html = index_html.replace("{{JA_ANALYSIS}}", latest_art["ja_analysis"])
    index_html = index_html.replace("{{EN_ANALYSIS}}", latest_art["en_analysis"])
    index_html = index_html.replace("{{JA_BLOG_TITLE}}", latest_art["ja_blog_title"])
    index_html = index_html.replace("{{EN_BLOG_TITLE}}", latest_art["en_blog_title"])
    index_html = index_html.replace("{{JA_BLOG_HTML}}", latest_art["ja_blog_html"])
    index_html = index_html.replace("{{EN_BLOG_HTML}}", latest_art["en_blog_html"])
    
    # 資産OSデータ
    index_html = index_html.replace("{{OS_REGIME}}", os_regime)
    index_html = index_html.replace("{{OS_PF}}", os_pf)
    index_html = index_html.replace("{{OS_ACTION}}", os_action)
    
    # アーカイブコラム一覧の動的差し込み
    index_html = index_html.replace("{{JA_ARCHIVE_LIST}}", ja_archive_html)
    index_html = index_html.replace("{{EN_ARCHIVE_LIST}}", en_archive_html)

    # index.html として書き出し
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(index_html)
    
    print("✅ index.html & 個別アーカイブHTMLのビルドが100%正常完了しました！")

if __name__ == "__main__":
    main()
