import os
import json
import urllib.request
from datetime import datetime, timezone, timedelta

JST = timezone(timedelta(hours=9))
DATA_DIR = "data"
ARTICLES_DIR = "dist/asset-os-connection/articles"
MAX_HISTORY_LIMIT = 10

def strip_html(text):
    import re
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

            action = "Standby"
            trade_logs = data.get("trade_logs", [])
            if trade_logs:
                last_log = trade_logs[-1]
                action = last_log.get("reason", "Standby")
                if len(action) > 15:
                    action = action[:15] + "..."

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

            print(f"📊 OS実績集計完了 ➔ Regime: {regime} / PF: {pf}")
            return regime, pf, action, total_profit_str, win_rate_str, total_trades_str, max_dd_str

    except Exception as e:
        print(f"⚠️ 資産OSデータの取得をフォールバック回避しました: {e}")
    return "Active", "1.00", "Running", "0", "0.0", "0", "0.0"

def fetch_exchange_prices():
    """複数取引所からBTC/JPY価格を無料APIで取得し、価格差を計算する"""
    exchanges = {
        "bitFlyer": "https://api.bitflyer.com/v1/ticker?product_code=BTC_JPY",
        "Coincheck": "https://coincheck.com/api/ticker",
        "GMOコイン": "https://api.coin.z.com/public/v1/ticker?symbol=BTC",
        "bitbank": "https://public.bitbank.cc/btc_jpy/ticker",
    }
    
    results = {}
    
    for name, url in exchanges.items():
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=10) as response:
                data = json.loads(response.read())
                
                # 各取引所のレスポンス形式の違いを吸収
                if name == "bitFlyer":
                    price = float(data["ltp"])
                elif name == "Coincheck":
                    price = float(data["last"])
                elif name == "GMOコイン":
                    price = float(data["data"][0]["last"])
                elif name == "bitbank":
                    price = float(data["data"]["last"])
                
                results[name] = price
                print(f"✅ {name}: {price:,.0f}円")
        except Exception as e:
            print(f"⚠️ {name} の価格取得失敗: {e}")
    
    if len(results) < 2:
        return None
    
    sorted_results = sorted(results.items(), key=lambda x: x[1])
    cheapest_name, cheapest_price = sorted_results[0]
    expensive_name, expensive_price = sorted_results[-1]
    price_diff = expensive_price - cheapest_price
    
    return {
        "rankings": sorted_results,
        "cheapest": cheapest_name,
        "cheapest_price": cheapest_price,
        "expensive": expensive_name,
        "expensive_price": expensive_price,
        "diff": price_diff,
        "diff_str": f"{price_diff:,.0f}",
        "all": results
    }

def build_sitemap(active_json_files):
    base_url = "https://ai-market.pray-power-is-god-and-cocoro.com/asset-os-connection"
    today = datetime.now(JST).strftime("%Y-%m-%d")
    
    sitemap_xml = '<?xml version="1.0" encoding="UTF-8"?>\n'
    sitemap_xml += '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    sitemap_xml += f"  <url><loc>{base_url}/</loc><lastmod>{today}</lastmod><changefreq>hourly</changefreq><priority>1.0</priority></url>\n"
    
    for j_file in active_json_files:
        slug = j_file.replace(".json", "")
        date_part = slug.replace("article-", "")[:8]
        try:
            lastmod = f"{date_part[:4]}-{date_part[4:6]}-{date_part[6:8]}"
        except Exception:
            lastmod = today
        sitemap_xml += f"  <url><loc>{base_url}/articles/{slug}.html</loc><lastmod>{lastmod}</lastmod><changefreq>monthly</changefreq><priority>0.8</priority></url>\n"
    
    sitemap_xml += "</urlset>"
    
    os.makedirs("dist/asset-os-connection", exist_ok=True)
    with open("dist/asset-os-connection/sitemap.xml", "w", encoding="utf-8") as f:
        f.write(sitemap_xml)
    print("🗺️ sitemap.xml の生成が完了しました！")

def main():
    print("🚀 アビトラ（価格差）チェッカー自動生成を開始します...")
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(ARTICLES_DIR, exist_ok=True)
    
    os_regime, os_pf, os_action, os_total_profit, os_win_rate, os_total_trades, os_max_dd = fetch_os_data()
    
    exchange_data = fetch_exchange_prices()

    if exchange_data:
        rankings_html_ja = ""
        rankings_html_en = ""
        medals = ["🥇", "🥈", "🥉", "4️⃣"]
        
        # 👑 審査が通ったら、ここを実際のアフィリエイトURLに差し替えるだけです
        affiliate_links = {
            "bitFlyer": "https://bitflyer.com/ja-jp/",
            "Coincheck": "https://coincheck.com/ja/",
            "GMOコイン": "https://coin.z.com/jp/",
            "bitbank": "https://bitbank.cc/",
        }
        
        for i, (name, price) in enumerate(exchange_data["rankings"]):
            medal = medals[i] if i < len(medals) else ""
            aff_url = affiliate_links.get(name, "#")
            label_ja = "← 今一番安い！" if i == 0 else ""
            label_en = "← Cheapest Now!" if i == 0 else ""
            
            rankings_html_ja += f"""
            <div class="rank-card {'rank-best' if i == 0 else ''}">
                <div class="rank-medal">{medal}</div>
                <div class="rank-name">{name}</div>
                <div class="rank-price">{price:,.0f} 円 <span class="rank-label">{label_ja}</span></div>
                <a href="{aff_url}" target="_blank" class="rank-btn">無料口座開設 &rarr;</a>
            </div>
            """
            rankings_html_en += f"""
            <div class="rank-card {'rank-best' if i == 0 else ''}">
                <div class="rank-medal">{medal}</div>
                <div class="rank-name">{name}</div>
                <div class="rank-price">{price:,.0f} JPY <span class="rank-label">{label_en}</span></div>
                <a href="{aff_url}" target="_blank" class="rank-btn">Open Account &rarr;</a>
            </div>
            """
        
        ai_data = {
            "ja_analysis": f"""
            <p>現在のBTC/JPY価格差レポートです。最安値は <strong>{exchange_data['cheapest']}</strong>（{exchange_data['cheapest_price']:,.0f}円）、最高値は <strong>{exchange_data['expensive']}</strong>（{exchange_data['expensive_price']:,.0f}円）で、現在 <strong style="color:#56d364;">{exchange_data['diff_str']}円</strong> の価格差があります。</p>
            <div class="rankings-container">{rankings_html_ja}</div>
            """,
            "en_analysis": f"""
            <p>Current BTC/JPY price spread report. Cheapest: <strong>{exchange_data['cheapest']}</strong> ({exchange_data['cheapest_price']:,.0f} JPY), Most Expensive: <strong>{exchange_data['expensive']}</strong> ({exchange_data['expensive_price']:,.0f} JPY). Current spread: <strong style="color:#56d364;">{exchange_data['diff_str']} JPY</strong>.</p>
            <div class="rankings-container">{rankings_html_en}</div>
            """,
            "ja_blog_title": f"【速報】BTC価格差 {exchange_data['diff_str']}円！今一番安い取引所はどこ？",
            "en_blog_title": f"[Live] BTC Spread: {exchange_data['diff_str']} JPY! Which Exchange is Cheapest?",
            "ja_blog_html": f"<p>国内主要取引所のBTC/JPY価格を自動集計しています。口座開設は無料です。複数の取引所に登録することで、常に一番安い有利な価格で取引できます。</p><p>※本情報は投資助言ではありません。投資の最終判断はご自身でお願いします。</p>",
            "en_blog_html": f"<p>We automatically aggregate BTC/JPY prices from major domestic exchanges. Registering with multiple exchanges allows you to always trade at favorable prices.</p>"
        }
        ai_data_success = True
    else:
        ai_data_success = False
        ai_data = None

    all_json_files = sorted([f for f in os.listdir(DATA_DIR) if f.startswith("article-") and f.endswith(".json")], reverse=True)
    
    if not ai_data:
        ai_data_success = False
        print("⚠️ データ生成に失敗。最新の過去キャッシュを探して表示維持を試みます。")
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
            except Exception as e:
                print(f"キャッシュの読込エラー: {e}")
                
        if not ai_data:
            ai_data = {
                "ja_analysis": "<p>現在、APIから価格データを取得中です...</p>",
                "en_analysis": "<p>Currently fetching price data...</p>",
                "ja_blog_title": "【準備中】リアルタイム価格差チェッカー",
                "en_blog_title": "[Preparing] Real-time Price Checker",
                "ja_blog_html": "<p>少々お待ちください。</p>",
                "en_blog_html": "<p>Please wait.</p>"
            }

    latest_art = None
    if ai_data_success:
        timestamp_slug = datetime.now(JST).strftime("%Y%m%d-%H%M%S")
        new_article_file = os.path.join(DATA_DIR, f"article-{timestamp_slug}.json")
        
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
        if all_json_files:
            latest_cache_file = os.path.join(DATA_DIR, all_json_files[0])
            with open(latest_cache_file, "r", encoding="utf-8") as f:
                latest_art = json.load(f)
            latest_art.setdefault("os_total_profit", os_total_profit)
            latest_art.setdefault("os_win_rate", os_win_rate)
            latest_art.setdefault("os_total_trades", os_total_trades)
            latest_art.setdefault("os_max_dd", os_max_dd)
        else:
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

    active_json_files = sorted([f for f in os.listdir(DATA_DIR) if f.startswith("article-") and f.endswith(".json")], reverse=True)
    
    ja_archive_html = ""
    en_archive_html = ""
    
    for j_file in active_json_files:
        with open(os.path.join(DATA_DIR, j_file), "r", encoding="utf-8") as f:
            art = json.load(f)
            
        a_slug = art["slug"]
        a_time = art["time"]
        ja_preview = strip_html(art['ja_analysis'])[:80]
        en_preview = strip_html(art['en_analysis'])[:80]
        
        ja_archive_html += f"""
        <div class="article-card">
            <div class="article-meta">
                <span>📅 {a_time}</span>
                <span style="color:#56d364;">価格チェッカー履歴</span>
            </div>
            <h3>{art['ja_blog_title']}</h3>
            <p>{ja_preview}...</p>
            <a href="/asset-os-connection/articles/{a_slug}.html" class="read-more">詳細を見る &rarr;</a>
        </div>
        """
        
        en_archive_html += f"""
        <div class="article-card">
            <div class="article-meta">
                <span>📅 {a_time}</span>
                <span style="color:#56d364;">Price History</span>
            </div>
            <h3>{art['en_blog_title']}</h3>
            <p>{en_preview}...</p>
            <a href="/asset-os-connection/articles/{a_slug}.html" class="read-more">View Details &rarr;</a>
        </div>
        """

    try:
        with open("template.html", "r", encoding="utf-8") as f:
            template_content = f.read()
    except Exception as e:
        print(f"❌ template.html が見つかりません: {e}")
        return

    for j_file in active_json_files:
        with open(os.path.join(DATA_DIR, j_file), "r", encoding="utf-8") as f:
            art = json.load(f)
            
        a_slug = art["slug"]
        
        page_html = template_content
        page_html = page_html.replace("{{PAGE_TITLE}}", art["ja_blog_title"] + " | 仮想通貨価格チェッカー")
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
        page_html = page_html.replace("{{WEEKLY_BOOK_BANNER}}", "") # 電子書籍機能を消したため空文字で安全に削除
        
        page_html = page_html.replace("{{OS_TOTAL_PROFIT}}", str(art.get("os_total_profit", os_total_profit)))
        page_html = page_html.replace("{{OS_WIN_RATE}}", str(art.get("os_win_rate", os_win_rate)))
        page_html = page_html.replace("{{OS_TOTAL_TRADES}}", str(art.get("os_total_trades", os_total_trades)))
        page_html = page_html.replace("{{OS_MAX_DD}}", str(art.get("os_max_dd", os_max_dd)))
        
        with open(os.path.join(ARTICLES_DIR, f"{a_slug}.html"), "w", encoding="utf-8") as f:
            f.write(page_html)

    index_html = template_content
    index_html = index_html.replace("{{PAGE_TITLE}}", "仮想通貨価格チェッカー | どこで買うのが一番お得？")
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
    index_html = index_html.replace("{{WEEKLY_BOOK_BANNER}}", "") # 電子書籍機能を消したため空文字で安全に削除
    
    index_html = index_html.replace("{{OS_TOTAL_PROFIT}}", os_total_profit)
    index_html = index_html.replace("{{OS_WIN_RATE}}", os_win_rate)
    index_html = index_html.replace("{{OS_TOTAL_TRADES}}", os_total_trades)
    index_html = index_html.replace("{{OS_MAX_DD}}", os_max_dd)

    with open("index.html", "w", encoding="utf-8") as f:
        f.write(index_html)
    
    build_sitemap(active_json_files)
    print("✅ index.html & 個別アーカイブHTMLのビルドが100%正常完了しました！")

if __name__ == "__main__":
    main()
