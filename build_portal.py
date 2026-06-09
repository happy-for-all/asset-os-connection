import os
import re
import json
import time
import traceback
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from google import genai
from google.genai import types

JST = timezone(timedelta(hours=9))
DATA_DIR = "data"
ARTICLES_DIR = "dist/asset-os-connection/articles"
BOOKS_DIR = "dist/asset-os-connection/books"
MAX_HISTORY_LIMIT = 10   # 容量パンク防止用の記事上限
MAX_BOOKS_LIMIT = 3      # 保存する電子書籍 of 最大数

RSS_SOURCES = [
    "https://www.coindesk.com/arc/outboundfeeds/rss/",
    "https://cointelegraph.com/rss",
    "https://decrypt.co/feed"
]

def strip_html(text):
    """プレビュー用要約テキストからHTMLタグを完全に排除して品質を高める"""
    return re.sub(r'<[^>]+>', '', text)

def fetch_os_data():
    """資産OSのtrade_log.jsonをサーバーサイドから安全にFetchし、実績を動的にクオンツ集計"""
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
            trade_logs = data.get("trade_logs", [])
            if trade_logs:
                last_log = trade_logs[-1]
                action = last_log.get("reason", "Standby")
                if len(action) > 15:
                    action = action[:15] + "..."

            # 本番取引実績の完全集計
            system_stats = data.get("system_stats", {})
            try:
                total_profit = float(system_stats.get("total_realized_profit", 0))
                total_profit_str = f"{total_profit:+,.0f}" if total_profit != 0 else "0"
            except (TypeError, ValueError):
                total_profit_str = "0"

            realized_trades = [log.get("diff_price", 0) for log in trade_logs if log.get("diff_price", 0) != 0]
            total_trades = len(realized_trades)
            total_trades_str = str(total_trades)

            wins = [x for x in realized_trades if x > 0]
            win_rate = (len(wins) / total_trades * 100) if total_trades > 0 else 0.0
            win_rate_str = f"{win_rate:.1f}"

            balances = [log.get("balance", 0) for log in trade_logs if log.get("balance", 0) > 0]
            max_dd = 0.0
            if balances:
                peak = balances[0]
                for b in balances:
                    if b > peak:
                        peak = b
                    dd = (peak - b) / peak if peak > 0 else 0.0
                    if dd > max_dd:
                        max_dd = dd
            max_dd_str = f"{max_dd * 100:.1f}"

            # 直近5件の取引履歴を整形
            recent_logs = trade_logs[-5:] if len(trade_logs) >= 5 else trade_logs
            recent_trades_list = []
            for log in recent_logs:
                t = log.get("time", "")
                price = log.get("price", 0)
                reason = log.get("reason", "")
                diff = log.get("diff_price", 0)
            # 直近5件の取引履歴を整形（改行をスペースに変換してJSON汚染を防ぐ）
                recent_trades_list.append(
                    f"{t} / 価格:{price}円 / 判定:{reason.replace(chr(10), ' ')} / 損益:{diff}円"
                )
            recent_trades_str = " | ".join(recent_trades_list) if recent_trades_list else "データなし"

            # シャドーAIレポートの取得
            shadow_logs = data.get("shadow_logs", [])
            shadow_summary_list = []
            for s in shadow_logs:
                s_type = s.get("shadow_type", "")
                s_profit = s.get("profit_percent", 0)
                s_win = "勝" if s.get("win_loss") else "敗"
                s_exit = s.get("exit_type", "")
                shadow_summary_list.append(f"{s_type}: {s_win} / 損益率:{s_profit}% / 決済:{s_exit}")
            shadow_report_str = " | ".join(shadow_summary_list) if shadow_summary_list else "データなし"

            print(f"📊 OS実績集計完了 ➔ Regime: {regime} / PF: {pf} / Profit: {total_profit_str}円 / WinRate: {win_rate_str}% / Trades: {total_trades_str}回 / MaxDD: {max_dd_str}%")
            return regime, pf, action, total_profit_str, win_rate_str, total_trades_str, max_dd_str, recent_trades_str, shadow_report_str

    except Exception as e:
        print(f"⚠️ 資産OSデータの取得をフォールバック回避しました: {e}")
        print(traceback.format_exc())
    return "Active", "1.00", "Running", "0", "0.0", "0", "0.0", "データなし", "データなし"

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
    """複数のRSSソースを順次巡回し、最新の海外ニュースを取得"""
    for rss_url in RSS_SOURCES:
        try:
            req = urllib.request.Request(rss_url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=10) as response:
                root = ET.fromstring(response.read())
                item = root.find('.//item')
                if item is not None:
                    title = item.find('title').text
                    desc_el = item.find('description')
                    desc = desc_el.text if desc_el is not None else ""
                    print(f"📰 RSSソース取得成功: {rss_url}")
                    return f"【ニュース詳細】{title} - {desc}"
        except Exception as e:
            print(f"⚠️ RSSフォールバック警告: {rss_url} → {e}")
    return "本日は大きなニュースの更新はありませんが、暗号資産市場は常に変動しています。"

def generate_ai_content(news_text, os_regime, os_pf, os_action,
                        os_total_profit, os_win_rate, os_total_trades,
                        os_max_dd, recent_trades, shadow_report):
    """まごころ資産OSのすべてのデータを完璧にマージし、世界に1つの超ハイクオリティ記事を生成する"""
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
    ・レジーム: {os_regime} （日本語訳: {os_regime_ja}）
    ・PF: {os_pf}
    ・アクション: {os_action}
    ・通算損益: {os_total_profit}円
    ・勝率: {os_win_rate}%
    ・取引回数: {os_total_trades}回
    ・最大DD: {os_max_dd}%
    ・シャドーAIレポート: {shadow_report}
    ・直近5件の取引履歴: {recent_trades}

    【執筆の絶対ルール】
    1. 【テーマの棲み分け（重複回避）】
       ・「ja_analysis/en_analysis（クオンツ分析）」には、最新ニュース（{news_text}）の内容は絶対に書かないでください。
         ここは「純粋に本日の資産OSデータ（レジーム、PF値、売買判断）から読み取れるテクニカルな市場動向と運用戦略の解説」に特化してください。
       ・「ja_blog_html/en_blog_html（ブログコラム）」にのみ、最新ニュースの具体的な中身（論争や出来事など）を比喩を交えて執筆してください。
         これにより、前半と後半での内容の重複を完全にゼロにし、読者を飽きさせないクリーンな構成にします。

    2. 【固有名詞の正確な保護】
       ・文章中に登場するすべての固有名詞（例：MicroStrategy、Ark Invest、Bitcoin、Ethereum、Sora、xAI、マイケル・セイラーなど）は、
         勝手に省略したりスペルを変えたりせず、正確な正式名称または日本で正しく通用する一般的表記で完璧に記述してください。

    3. 【断定表現の抑制（金融YMYL対策の徹底）】
       ・投資や利確に関する絶対的な断定表現や、「確実に利益が積み上げられる優秀なシステム」「勝てる」といった誇大広告に聞こえる不実表示は完全に排除してください。
       ・代わりに、「客観的なデータに基づいて感情を徹底排除した冷静な判断プロセス」「中長期的な資産防衛に主眼を置いた堅実な稼働設計」など、
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
                
                raw_text = response.text.strip()
                match = re.search(r"(\{.*\})", raw_text, re.DOTALL)
                clean_text = match.group(1) if match else raw_text.replace("```json", "").replace("```", "")
                
                return json.loads(clean_text.strip())
            except Exception as e:
                print(f"⚠️ {model_name} エラー (試行 {attempt + 1}): {e}")
                print(traceback.format_exc())
                if attempt < max_retries - 1:
                    wait_time = (2 ** attempt) * 10
                    print(f"⏳ Googleサーバー混雑のため、{wait_time}秒後に再トライします...")
                    time.sleep(wait_time)
                else:
                    print(f"❌ {model_name} での生成を断念しました。")
                    
    print("❌ すべてのモデルで生成に失敗しました。")
    return None

def generate_weekly_book(materials_text, os_regime, os_pf):
    """【2号店機能移植】蓄積されたニュースと資産OSデータから、1万字規模の日英電子書籍を自動執筆"""
    api_key = os.environ.get("GEMINI_API_KEY_MEDIA")
    if not api_key:
        return None

    client = genai.Client(api_key=api_key)
    
    prompt = f"""
    あなたは、世界経済・株式投資・クオンツ運用のプロフェッショナルであり、読者をワクワクさせる優れたジャーナリストです。
    提供された【直近のニュースと資産データ】を美しく紡ぎ合わせ、日本語と英語の両方で読める、
    1万文字規模の圧倒的に分かりやすくて深い, 投資家のバイブルとなる「世界経済トレンド完全解剖書（日英併記プチ書籍）」を執筆してください。

    【直近のニュースと資産データ】
    ・まごころ資産OSレジーム判定: {os_regime}
    ・システムPF: {os_pf}
    ・直近のマーケットデータ履歴:
    {materials_text}

    【執筆上の厳格ルール】
    - 専門用語を絶対にそのまま放置せず、必ず誰もが膝を打つような「具体的な例え話」で完璧に噛み砕いてください。
    - 出力は必ず以下のJSON形式のみとすること（マークダウン記号は絶対に入れないこと）。
    - HTMLタグ（<h3>, <p>, <strong>, <blockquote>など）を適切に使用してレイアウトしてください。

    {{
        "ja_book_title": "2026年 最新号：世界経済トレンド完全解剖書",
        "en_book_title": "2026 Edition: Weekly Global Trend Analysis",
        "ja_book_html": "<h3>第1章：世界市場の潮流</h3><p>...</p><h3>第2章：クオンツ防衛と当社の判定</h3><p>...</p>",
        "en_book_html": "<h3>Chapter 1: Global Market Dynamics</h3><p>...</p><h3>Chapter 2: Quant Defense Strategy</h3><p>...</p>"
    }}
    """
    
    try:
        print("📚 AIに日英プチ書籍を執筆させています（1万字規模のビッグデータ錬成中）...")
        response = client.models.generate_content(
            model="gemini-1.5-flash",  # 長文執筆が得意な1.5を特別採用
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.7
            )
        )
        raw_text = response.text.strip()
        match = re.search(r"(\{.*\})", raw_text, re.DOTALL)
        clean_text = match.group(1) if match else raw_text.replace("```json", "").replace("```", "")
        return json.loads(clean_text.strip())
    except Exception as e:
        print(f"⚠️ 電子書籍の執筆失敗: {e}")
        print(traceback.format_exc())
    return None

def build_sitemap(active_json_files):
    """👑 改善：lastmod / priority / changefreq を完備し、さらにbooks（電子書籍）も動的スキャンして自動登録する最強のsitemap.xml生成エンジン"""
    base_url = "https://ai-market.pray-power-is-god-and-cocoro.com/asset-os-connection"
    today = datetime.now(JST).strftime("%Y-%m-%d")
    
    sitemap_xml = '<?xml version="1.0" encoding="UTF-8"?>\n'
    sitemap_xml += '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    
    # トップページ（インデックス）は最高優先度
    sitemap_xml += f"  <url><loc>{base_url}/</loc><lastmod>{today}</lastmod><changefreq>daily</changefreq><priority>1.0</priority></url>\n"
    
    # 過去記事の登録
    for j_file in active_json_files:
        slug = j_file.replace(".json", "")
        date_part = slug.replace("article-", "")[:8]
        try:
            lastmod = f"{date_part[:4]}-{date_part[4:6]}-{date_part[6:8]}"
        except Exception:
            lastmod = today
            
        sitemap_xml += f"  <url><loc>{base_url}/articles/{slug}.html</loc><lastmod>{lastmod}</lastmod><changefreq>monthly</changefreq><priority>0.8</priority></url>\n"
    
    # 👑 改善：生成された電子書籍（books/*.html）も自動巡回して、インデックスへ優先度0.9で動的自動登録
    if os.path.exists(BOOKS_DIR):
        for book_file in os.listdir(BOOKS_DIR):
            if book_file.endswith(".html"):
                sitemap_xml += f"  <url><loc>{base_url}/books/{book_file}</loc><lastmod>{today}</lastmod><changefreq>weekly</changefreq><priority>0.9</priority></url>\n"
                
    sitemap_xml += "</urlset>"
    
    os.makedirs("dist/asset-os-connection", exist_ok=True)
    with open("dist/asset-os-connection/sitemap.xml", "w", encoding="utf-8") as f:
        f.write(sitemap_xml)
    print("🗺️ sitemap.xml の生成が完了しました！")

def main():
    print("🚀 メディアOS: ポータルおよびアーカイブ自動生成を開始します...")
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(ARTICLES_DIR, exist_ok=True)
    os.makedirs(BOOKS_DIR, exist_ok=True)
    
    # 👑 改善：fetch_os_dataから新設した直近履歴、シャドーレポート等すべての集計データを正確に受け取る
    os_regime, os_pf, os_action, os_total_profit, os_win_rate, os_total_trades, os_max_dd, recent_trades, shadow_report = fetch_os_data()
    news_text = fetch_crypto_news()
    print(f"📰 取得したニュース: {news_text[:50]}...")

    ai_data_success = True
    # 👑 改善：generate_ai_contentへ集計した本番・シャドーデータをすべて引数として漏れなく引き渡す（デグレ完全排除）
    ai_data = generate_ai_content(news_text, os_regime, os_pf, os_action,
                                  os_total_profit, os_win_rate, os_total_trades,
                                  os_max_dd, recent_trades, shadow_report)
    
    # 過去キャッシュの取得
    all_json_files = sorted([f for f in os.listdir(DATA_DIR) if f.startswith("article-") and f.endswith(".json")], reverse=True)
    
    # 究極のクラッシュ完全防止＆画面表示維持
    if not ai_data:
        ai_data_success = False
        print("⚠️ AIデータの生成に失敗しました。最新の過去キャッシュを探して表示維持を試みます。")
        
        if all_json_files:
            latest_cache_file = os.path.join(DATA_DIR, all_json_files[0])
            try:
                with open(latest_cache_file, "r", encoding="utf-8") as f:
                    cached_art = json.load(f)
                ai_data = {
                    "ja_analysis": cached_art["ja_analysis"],
                    "en_analysis": cached_art["en_analysis"],
                    "ja_blog_title": cached_art["ja_blog_title"],
                    "en_blog_title": cached_art["en_blog_title"],
                    "ja_blog_html": cached_art["ja_blog_html"],
                    "en_blog_html": cached_art["en_blog_html"]
                }
                print("♻️ キャッシュデータの読込に成功しました。表示維持。")
            except Exception as e:
                print(f"キャッシュの読込エラー: {e}")
                
        # 究極のバックアップ（※クラッシュ完全ガード）
        if not ai_data:
            ai_data = {
                "ja_analysis": "<p>現在、AIが詳細な相場分析を準備中です。次回の更新をお待ちください。</p>",
                "en_analysis": "<p>AI is currently preparing a detailed market analysis. Please wait for the next update.</p>",
                "ja_blog_title": "【お知らせ】次回のマーケットレポート準備中",
                "en_blog_title": "[Notice] Preparing Next Market Report",
                "ja_blog_html": "<p>Google AIサーバーの一時的な混雑により、最新のブログ記事を準備中です。数時間以内に自動復旧しますので、少々お待ちください。</p>",
                "en_blog_html": "<p>Due to temporary high demand on Google AI servers, the latest blog post is being prepared. It will automatically recover within a few hours.</p>"
            }

    # 成功時のみ新規JSONに書き込む
    latest_art = None
    if ai_data_success:
        timestamp_slug = datetime.now(JST).strftime("%Y%m%d-%H%M%S")
        new_article_file = os.path.join(DATA_DIR, f"article-{timestamp_slug}.json")
        
        # 最新時点の実績を永続固定保存
        latest_art = {
            "time": datetime.now(JST).strftime("%Y-%m-%d %H:%M:%S"),
            "os_regime": os_regime,
            "os_pf": os_pf,
            "os_action": os_action,
            "os_total_profit": os_total_profit,
            "os_win_rate": os_win_rate,
            "os_total_trades": os_total_trades,
            "os_max_dd": os_max_dd,
            "ja_analysis": ai_data["ja_analysis"],
            "en_analysis": ai_data["en_analysis"],
            "ja_blog_title": ai_data["ja_blog_title"],
            "en_blog_title": ai_data["en_blog_title"],
            "ja_blog_html": ai_data["ja_blog_html"],
            "en_blog_html": ai_data["en_blog_html"],
            "slug": f"article-{timestamp_slug}"
        }
        
        with open(new_article_file, "w", encoding="utf-8") as f:
            json.dump(latest_art, f, ensure_ascii=False, indent=2)
    else:
        # 失敗時は、キャッシュの一番新しいものを今回の最新画面としてバインド
        if all_json_files:
            latest_cache_file = os.path.join(DATA_DIR, all_json_files[0])
            with open(latest_cache_file, "r", encoding="utf-8") as f:
                latest_art = json.load(f)
                
            # 👑 改善：実績データが欠落している古いキャッシュJSONを読み込んだ場合でも、KeyErrorを出さずに後方互換性を100%保証する注入(setdefault)ガード
            latest_art.setdefault("os_total_profit", os_total_profit)
            latest_art.setdefault("os_win_rate", os_win_rate)
            latest_art.setdefault("os_total_trades", os_total_trades)
            latest_art.setdefault("os_max_dd", os_max_dd)
        else:
            # キャッシュも何も存在しない場合の安全フォールバック時に slug を持たせてクラッシュを防ぎつつ互換値をセット
            latest_art = {
                "time": datetime.now(JST).strftime("%Y-%m-%d %H:%M:%S"),
                "os_regime": os_regime,
                "os_pf": os_pf,
                "os_action": os_action,
                "os_total_profit": os_total_profit,
                "os_win_rate": os_win_rate,
                "os_total_trades": os_total_trades,
                "os_max_dd": os_max_dd,
                "slug": "fallback",
                **ai_data
            }

    # ローテーション機能（最大10件）
    all_json_files = sorted([f for f in os.listdir(DATA_DIR) if f.startswith("article-") and f.endswith(".json")], reverse=True)
    if len(all_json_files) > MAX_HISTORY_LIMIT:
        print(f"🗑️ 履歴制限({MAX_HISTORY_LIMIT}件)を超過したため、古い記事を自動パージします。")
        for old_file in all_json_files[MAX_HISTORY_LIMIT:]:
            json_path = os.path.join(DATA_DIR, old_file)
            if os.path.exists(json_path):
                os.remove(json_path)
            html_slug = old_file.replace(".json", "")
            html_path = os.path.join(ARTICLES_DIR, f"{html_slug}.html")
            if os.path.exists(html_path):
                os.remove(html_path)

    # 過去ログからアーカイブ記事一覧のHTMLをビルド
    active_json_files = sorted([f for f in os.listdir(DATA_DIR) if f.startswith("article-") and f.endswith(".json")], reverse=True)
    
    ja_archive_html = ""
    en_archive_html = ""
    combined_materials = []
    
    for j_file in active_json_files:
        with open(os.path.join(DATA_DIR, j_file), "r", encoding="utf-8") as f:
            art = json.load(f)
            
        a_slug = art["slug"]
        a_time = art["time"]
        
        combined_materials.append(f"【タイトル】: {art['ja_blog_title']}\n【分析要約】: {art['ja_analysis']}")
        
        ja_preview = strip_html(art['ja_analysis'])[:80]
        en_preview = strip_html(art['en_analysis'])[:80]
        
        # 日本語アーカイブカード
        ja_archive_html += f"""
        <div class="article-card">
            <div class="article-meta">
                <span>📅 {a_time}</span>
                <span style="color:#56d364;">まごころ資産OS連動</span>
            </div>
            <h3>{art['ja_blog_title']}</h3>
            <p>{ja_preview}...</p>
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
            <p>{en_preview}...</p>
            <a href="/asset-os-connection/articles/{a_slug}.html" class="read-more">Read More &rarr;</a>
        </div>
        """

    # 【電子書籍ビルド機能（週次重複生成防止 ＆ 最新自動バナー）】
    current_week_slug = f"weekly-market-book-{datetime.now(JST).strftime('%Y-%m-w%W')}"
    book_path = os.path.join(BOOKS_DIR, f"{current_week_slug}.html")
    
    if len(active_json_files) >= 5 and not os.path.exists(book_path):
        materials_text = "\n\n---\n\n".join(combined_materials[:5])
        book_data = generate_weekly_book(materials_text, os_regime, os_pf)
        
        if book_data:
            with open("template.html", "r", encoding="utf-8") as f:
                template_content = f.read()
            
            # 書籍HTMLのコンパイル
            book_html = template_content
            book_html = book_html.replace("{{PAGE_TITLE}}", book_data["ja_book_title"] + " | AI Frontier Market")
            book_html = book_html.replace("{{PAGE_DESCRIPTION}}", "今週配信された資産データと相場分析をAIが統合したクオンツ投資解剖書です。")
            book_html = book_html.replace("{{UPDATE_TIME}}", datetime.now(JST).strftime("%Y-%m-%d"))
            book_html = book_html.replace("{{JA_ANALYSIS}}", book_data["ja_book_html"])
            book_html = book_html.replace("{{EN_ANALYSIS}}", book_data["en_book_html"])
            book_html = book_html.replace("{{JA_BLOG_TITLE}}", book_data["ja_book_title"])
            book_html = book_html.replace("{{EN_BLOG_TITLE}}", book_data["en_book_title"])
            book_html = book_html.replace("{{JA_BLOG_HTML}}", "<p>※第1章および第2章より体系的な電子書籍コンテンツをお楽しみください。</p>")
            book_html = book_html.replace("{{EN_BLOG_HTML}}", "<p>※Please enjoy the structured weekly book content in Chapter 1 & 2 above.</p>")
            book_html = book_html.replace("{{OS_REGIME}}", os_regime)
            book_html = book_html.replace("{{OS_PF}}", os_pf)
            book_html = book_html.replace("{{OS_ACTION}}", "Published")
            book_html = book_html.replace("{{JA_ARCHIVE_LIST}}", ja_archive_html)
            book_html = book_html.replace("{{EN_ARCHIVE_LIST}}", en_archive_html)
            book_html = book_html.replace("{{WEEKLY_BOOK_BANNER}}", "") # 書籍画面自身にはバナーを出さない
            
            # 実績データの置換
            book_html = book_html.replace("{{OS_TOTAL_PROFIT}}", os_total_profit)
            book_html = book_html.replace("{{OS_WIN_RATE}}", os_win_rate)
            book_html = book_html.replace("{{OS_TOTAL_TRADES}}", os_total_trades)
            book_html = book_html.replace("{{OS_MAX_DD}}", os_max_dd)
            
            # 書籍データの書き込み
            with open(book_path, "w", encoding="utf-8") as f:
                f.write(book_html)

            # 書籍ローテーションの実行（書き込み完了直後）
            all_book_files = sorted([f for f in os.listdir(BOOKS_DIR) if f.startswith("weekly-market-book-") and f.endswith(".html")], reverse=True)
            if len(all_book_files) > MAX_BOOKS_LIMIT:
                print(f"🗑️ 電子書籍の履歴制限({MAX_BOOKS_LIMIT}冊)を超過したため、古い書籍をパージします。")
                for old_book in all_book_files[MAX_BOOKS_LIMIT:]:
                    ob_path = os.path.join(BOOKS_DIR, old_book)
                    if os.path.exists(ob_path):
                        os.remove(ob_path)
    else:
        if len(active_json_files) < 5:
            print("📚 書籍生成スキップ: 記事数が5件未満です。")
        else:
            print("📚 書籍生成スキップ: 今週の電子書籍はすでに生成済みです。")

    # 動的バナー生成（誤字 "一冊 of ストーリー" ➔ "一冊のストーリー" へ完璧に修復）
    weekly_book_banner_html = ""
    if os.path.exists(BOOKS_DIR):
        existing_books = sorted([f for f in os.listdir(BOOKS_DIR) if f.startswith("weekly-market-book-") and f.endswith(".html")], reverse=True)
        if existing_books:
            latest_book_filename = existing_books[0]
            weekly_book_banner_html = f"""
            <section style="margin-bottom: 40px; background: linear-gradient(135deg, #0070f3, #3291ff); border: none; border-radius: 16px; padding: 30px; text-align: center; box-shadow: 0 8px 24px rgba(0, 112, 243, 0.25);">
                <div class="lang-content ja active">
                    <span style="background: rgba(255,255,255,0.2); padding: 4px 12px; border-radius: 999px; font-size: 0.8rem; font-weight: 800; color: #fff;">🆕 AI WEEKLY BOOK 配信中</span>
                    <h2 style="font-size: 1.6rem; font-weight: 900; margin: 15px 0 10px; color: #fff; border:none; padding:0;">世界経済トレンド完全解剖書</h2>
                    <p style="font-size: 0.95rem; color: rgba(255,255,255,0.9); max-width: 500px; margin: 0 auto 20px;">今週配信された資産データと相場分析をAIが統合し、一冊のストーリーにまとめあげたクオンツ投資解剖書です。</p>
                    <a href="/asset-os-connection/books/{latest_book_filename}" style="background: #fff; color: #0070f3; padding: 12px 24px; border-radius: 999px; font-weight: 800; text-decoration: none; display: inline-block;">電子書籍を読む（無料） &rarr;</a>
                </div>
                <div class="lang-content en">
                    <span style="background: rgba(255,255,255,0.2); padding: 4px 12px; border-radius: 999px; font-size: 0.8rem; font-weight: 800; color: #fff;">🆕 AI WEEKLY BOOK NOW ON SALE</span>
                    <h2 style="font-size: 1.6rem; font-weight: 900; margin: 15px 0 10px; color: #fff; border:none; padding:0;">Weekly Global Trend Analysis</h2>
                    <p style="font-size: 0.95rem; color: rgba(255,255,255,0.9); max-width: 500px; margin: 0 auto 20px;">An AI-synthesized weekly book integrating Magokoro OS metrics and global market trends into a single structured report.</p>
                    <a href="/asset-os-connection/books/{latest_book_filename}" style="background: #fff; color: #0070f3; padding: 12px 24px; border-radius: 999px; font-weight: 800; text-decoration: none; display: inline-block;">Read Free Book &rarr;</a>
                </div>
            </section>
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
        page_html = page_html.replace("{{PAGE_TITLE}}", art["ja_blog_title"] + " | AI Frontier Market")
        page_html = page_html.replace("{{PAGE_DESCRIPTION}}", strip_html(art["ja_analysis"])[:120].replace('"', '&quot;'))
        page_html = page_html.replace("{{UPDATE_TIME}}", art["time"])
        page_html = page_html.replace("{{JA_ANALYSIS}}", art["ja_analysis"])
        page_html = page_html.replace("{{EN_ANALYSIS}}", art["en_analysis"])
        page_html = page_html.replace("{{JA_BLOG_TITLE}}", art["ja_blog_title"])
        page_html = page_html.replace("{{EN_BLOG_TITLE}}", art["en_blog_title"])
        page_html = page_html.replace("{{JA_BLOG_HTML}}", art["ja_blog_html"])
        page_html = page_html.replace("{{EN_BLOG_HTML}}", art["en_blog_html"])
        page_html = page_html.replace("{{OS_REGIME}}", art["os_regime"])
        page_html = page_html.replace("{{OS_PF}}", art["os_pf"])
        page_html = page_html.replace("{{OS_ACTION}}", art["os_action"])
        page_html = page_html.replace("{{JA_ARCHIVE_LIST}}", ja_archive_html)
        page_html = page_html.replace("{{EN_ARCHIVE_LIST}}", en_archive_html)
        page_html = page_html.replace("{{WEEKLY_BOOK_BANNER}}", weekly_book_banner_html)
        
        # 個別記事のコンパイル時は「今日現在」の最新データではなく「コラムが執筆された当時」の数値を完全に固定保存・表示して履歴の整合性を死守（後方互換性ガード付き）
        page_html = page_html.replace("{{OS_TOTAL_PROFIT}}", str(art.get("os_total_profit", os_total_profit)))
        page_html = page_html.replace("{{OS_WIN_RATE}}", str(art.get("os_win_rate", os_win_rate)))
        page_html = page_html.replace("{{OS_TOTAL_TRADES}}", str(art.get("os_total_trades", os_total_trades)))
        page_html = page_html.replace("{{OS_MAX_DD}}", str(art.get("os_max_dd", os_max_dd)))
        
        with open(os.path.join(ARTICLES_DIR, f"{a_slug}.html"), "w", encoding="utf-8") as f:
            f.write(page_html)

    # ② 最新コラムを載せた index.html（トップページ）のビルド（最新コラムなので、今日現在の最新データを反映）
    index_html = template_content
    index_html = index_html.replace("{{PAGE_TITLE}}", "AI Frontier Market | Global Asset Research")
    index_html = index_html.replace("{{PAGE_DESCRIPTION}}", strip_html(latest_art["ja_analysis"])[:120].replace('"', '&quot;'))
    index_html = index_html.replace("{{UPDATE_TIME}}", latest_art["time"])
    index_html = index_html.replace("{{JA_ANALYSIS}}", latest_art["ja_analysis"])
    index_html = index_html.replace("{{EN_ANALYSIS}}", latest_art["en_analysis"])
    index_html = index_html.replace("{{JA_BLOG_TITLE}}", latest_art["ja_blog_title"])
    index_html = index_html.replace("{{EN_BLOG_TITLE}}", latest_art["en_blog_title"])
    index_html = index_html.replace("{{JA_BLOG_HTML}}", latest_art["ja_blog_html"])
    index_html = index_html.replace("{{EN_BLOG_HTML}}", latest_art["en_blog_html"])
    index_html = index_html.replace("{{OS_REGIME}}", os_regime)
    index_html = index_html.replace("{{OS_PF}}", os_pf)
    index_html = index_html.replace("{{OS_ACTION}}", os_action)
    index_html = index_html.replace("{{JA_ARCHIVE_LIST}}", ja_archive_html)
    index_html = index_html.replace("{{EN_ARCHIVE_LIST}}", en_archive_html)
    index_html = index_html.replace("{{WEEKLY_BOOK_BANNER}}", weekly_book_banner_html)
    
    # 集計実績データの置換（index.html）
    index_html = index_html.replace("{{OS_TOTAL_PROFIT}}", os_total_profit)
    index_html = index_html.replace("{{OS_WIN_RATE}}", os_win_rate)
    index_html = index_html.replace("{{OS_TOTAL_TRADES}}", os_total_trades)
    index_html = index_html.replace("{{OS_MAX_DD}}", os_max_dd)

    # index.html として書き出し
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(index_html)
    
    # サイトマップsitemap.xmlの全自動更新コンパイラをキック（booksスキャン対応）
    build_sitemap(active_json_files)
    
    print("✅ index.html & 個別アーカイブHTMLのビルドが100%正常完了しました！")

if __name__ == "__main__":
    main()
