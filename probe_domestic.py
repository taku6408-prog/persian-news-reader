
import logging
from app import db, feed_repo, article_repo, fetcher

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ProbeDomestic")

def probe():
    # 調査対象の国内メディア
    domestic_feeds = [
        {"name": "IRNA (State News)", "url": "https://www.irna.ir/rss"},
        {"name": "ISNA (Students News)", "url": "https://www.isna.ir/rss"},
        {"name": "Fars News", "url": "https://www.farsnews.ir/rss"}
    ]
    
    results = []
    
    for f in domestic_feeds:
        logger.info(f"Probing {f['name']} at {f['url']}...")
        # フィードをDBに登録
        fid = feed_repo.add_feed(f['name'], f['url'])
        
        # 取得試行
        try:
            new_count = fetcher.fetch_by_id(fid)
            results.append({
                "name": f['name'],
                "status": "SUCCESS",
                "new_articles": new_count
            })
            logger.info(f"SUCCESS: {f['name']} returned {new_count} new articles.")
        except Exception as e:
            results.append({
                "name": f['name'],
                "status": "FAILED",
                "error": str(e)
            })
            logger.error(f"FAILED: {f['name']} - {e}")

    print("\n--- PROBE RESULTS ---")
    for r in results:
        status_str = f"[{r['status']}] {r['name']}"
        if r['status'] == "SUCCESS":
            print(f"{status_str}: Reachable. New articles: {r['new_articles']}")
        else:
            print(f"{status_str}: UNREACHABLE. Error: {r['error']}")

if __name__ == "__main__":
    probe()
