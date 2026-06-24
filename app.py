"""
app.py  ─  Flask アプリケーションのエントリポイント

起動方法:
    flask run          # 開発
    gunicorn app:app   # 本番
"""

from flask import Flask, jsonify, render_template
from rss_fetcher import DatabaseManager, FeedRepository, ArticleRepository, RssFetcher

app = Flask(__name__)

# ---------- 依存オブジェクトの初期化 ----------

db           = DatabaseManager()
feed_repo    = FeedRepository(db)
article_repo = ArticleRepository(db)
fetcher      = RssFetcher(db, feed_repo, article_repo)

# アプリ起動時にスキーマを自動作成
with app.app_context():
    db.initialize_schema()
    # サンプルフィードを登録（初回のみ実質的に挿入される）
    feed_repo.add_feed("BBC Persian",        "https://feeds.bbci.co.uk/persian/rss.xml")
    feed_repo.add_feed("Iran International", "https://www.iranintl.com/rss")


# ---------- エンドポイント ----------

@app.get("/")
def index():
    """記事一覧をHTMLで表示する。"""
    articles = article_repo.get_latest(limit=30)
    return render_template("index.html", articles=articles)


@app.get("/api/fetch")
def api_fetch():
    """全フィードを手動で取得するエンドポイント。"""
    result = fetcher.fetch_all()
    return jsonify(result)


@app.get("/api/articles")
def api_articles():
    """最新記事一覧を返す。"""
    articles = article_repo.get_latest(limit=30)
    return jsonify(articles)


if __name__ == "__main__":
    app.run(debug=True, port=50002)
