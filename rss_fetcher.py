"""
rss_fetcher.py
RSS取得・パース・DB保存を担うクラス群

前提:
  - PostgreSQL コンテナが localhost:5432 で稼働
  - 環境変数で接続情報を管理（.env ファイル参照）
  - pip install flask feedparser psycopg2-binary python-dotenv requests
"""

import os
import logging
import hashlib
from datetime import datetime, timezone
from dataclasses import dataclass, field
from typing import Optional

import feedparser
import psycopg2
import psycopg2.extras
import requests
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# データクラス：1件の記事を表す
# ---------------------------------------------------------------------------

@dataclass
class Article:
    """RSSフィードから取得した1記事分のデータを保持する。"""

    feed_id: int                        # どのフィードから来たか
    guid: str                           # 記事の一意識別子（URL or id）
    title_original: str                 # 原文タイトル（ペルシャ語）
    summary_original: str               # 原文概要（ペルシャ語）
    link: str                           # 元記事URL
    published_at: Optional[datetime]    # 配信日時（UTC）
    fetched_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    title_translated: Optional[str] = None      # 翻訳後タイトル（英語）
    summary_translated: Optional[str] = None    # 翻訳後概要（英語）
    is_translated: bool = False

    @staticmethod
    def make_guid(link: str) -> str:
        """リンクURLからGUID（SHA-256ハッシュ）を生成する。"""
        return hashlib.sha256(link.encode()).hexdigest()


# ---------------------------------------------------------------------------
# DB接続管理
# ---------------------------------------------------------------------------

class DatabaseManager:
    """
    PostgreSQL への接続とスキーマ初期化を管理する。

    環境変数（.env）:
        DB_HOST     : コンテナホスト（デフォルト: localhost）
        DB_PORT     : ポート番号（デフォルト: 5432）
        DB_NAME     : データベース名
        DB_USER     : ユーザー名
        DB_PASSWORD : パスワード
    """

    def __init__(self) -> None:
        self.dsn = {
            "host":     os.getenv("DB_HOST", "localhost"),
            "port":     int(os.getenv("DB_PORT", 5432)),
            "dbname":   os.getenv("DB_NAME", "rss_db"),
            "user":     os.getenv("DB_USER", "rss_user"),
            "password": os.getenv("DB_PASSWORD", ""),
            "sslmode":  os.getenv("DB_SSLMODE", "require"),
        }
        self._conn: Optional[psycopg2.extensions.connection] = None

    # ---- 接続 ---------------------------------------------------------------

    def connect(self) -> None:
        """DBに接続する。既に接続済みの場合はスキップ。"""
        if self._conn is None or self._conn.closed:
            self._conn = psycopg2.connect(**self.dsn)
            self._conn.autocommit = False
            logger.info("DB接続成功: %(host)s:%(port)s/%(dbname)s", self.dsn)

    def disconnect(self) -> None:
        """DB接続を閉じる。"""
        if self._conn and not self._conn.closed:
            self._conn.close()
            logger.info("DB接続をクローズしました。")

    def get_cursor(self) -> psycopg2.extensions.cursor:
        self.connect()
        return self._conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    def commit(self) -> None:
        if self._conn:
            self._conn.commit()

    def rollback(self) -> None:
        if self._conn:
            self._conn.rollback()

    # ---- スキーマ初期化 ------------------------------------------------------

    def initialize_schema(self) -> None:
        """
        必要なテーブルが存在しない場合に作成する。
        アプリ起動時に1回呼び出す。
        """
        ddl = """
        -- フィードマスタ
        CREATE TABLE IF NOT EXISTS feeds (
            id          SERIAL PRIMARY KEY,
            name        VARCHAR(255) NOT NULL,
            url         TEXT NOT NULL UNIQUE,
            language    VARCHAR(10)  NOT NULL DEFAULT 'fa',
            is_active   BOOLEAN      NOT NULL DEFAULT TRUE,
            created_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
            last_fetched_at TIMESTAMPTZ
        );

        -- 記事テーブル
        CREATE TABLE IF NOT EXISTS articles (
            id                  SERIAL PRIMARY KEY,
            feed_id             INTEGER     NOT NULL REFERENCES feeds(id),
            guid                TEXT        NOT NULL UNIQUE,            title_original      TEXT        NOT NULL,
            summary_original    TEXT,
            title_translated    TEXT,
            summary_translated  TEXT,
            link                TEXT        NOT NULL,
            is_translated       BOOLEAN     NOT NULL DEFAULT FALSE,
            published_at        TIMESTAMPTZ,
            fetched_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );

        CREATE INDEX IF NOT EXISTS idx_articles_feed_id
            ON articles(feed_id);
        CREATE INDEX IF NOT EXISTS idx_articles_published_at
            ON articles(published_at DESC);
        """
        with self.get_cursor() as cur:
            cur.execute(ddl)
        self.commit()
        logger.info("スキーマの初期化が完了しました。")


# ---------------------------------------------------------------------------
# RSSフィード設定リポジトリ
# ---------------------------------------------------------------------------

class FeedRepository:
    """
    feeds テーブルの CRUD を担当する。
    """

    def __init__(self, db: DatabaseManager) -> None:
        self.db = db

    def add_feed(self, name: str, url: str, language: str = "fa") -> int:
        """フィードを登録し、IDを返す。既存URLなら既存IDを返す。"""
        sql = """
            INSERT INTO feeds (name, url, language)
            VALUES (%s, %s, %s)
            ON CONFLICT (url) DO UPDATE SET name = EXCLUDED.name
            RETURNING id;
        """
        with self.db.get_cursor() as cur:
            cur.execute(sql, (name, url, language))
            feed_id = cur.fetchone()[0]
        self.db.commit()
        logger.info("フィード登録: id=%s, name=%s", feed_id, name)
        return feed_id

    def get_active_feeds(self) -> list[dict]:
        """is_active=True のフィード一覧を取得する。"""
        sql = "SELECT id, name, url, language FROM feeds WHERE is_active = TRUE;"
        with self.db.get_cursor() as cur:
            cur.execute(sql)
            return [dict(row) for row in cur.fetchall()]

    def update_last_fetched(self, feed_id: int) -> None:
        """最終取得日時を現在時刻に更新する。"""
        sql = "UPDATE feeds SET last_fetched_at = NOW() WHERE id = %s;"
        with self.db.get_cursor() as cur:
            cur.execute(sql, (feed_id,))
        self.db.commit()


# ---------------------------------------------------------------------------
# 記事リポジトリ
# ---------------------------------------------------------------------------

class ArticleRepository:
    """
    articles テーブルへの挿入・参照を担当する。
    """

    def __init__(self, db: DatabaseManager) -> None:
        self.db = db

    def save(self, article: Article) -> bool:
        """
        記事を保存する。GUIDが重複する場合はスキップ（冪等）。
        戻り値: 新規保存なら True、スキップなら False。
        """
        sql = """
            INSERT INTO articles (
                feed_id, guid, title_original, summary_original,
                link, published_at, fetched_at,
                title_translated, summary_translated, is_translated
            ) VALUES (
                %(feed_id)s, %(guid)s, %(title_original)s, %(summary_original)s,
                %(link)s, %(published_at)s, %(fetched_at)s,
                %(title_translated)s, %(summary_translated)s, %(is_translated)s
            )
            ON CONFLICT (guid) DO NOTHING
            RETURNING id;
        """
        params = {
            "feed_id":            article.feed_id,
            "guid":               article.guid,
            "title_original":     article.title_original,
            "summary_original":   article.summary_original,
            "link":               article.link,
            "published_at":       article.published_at,
            "fetched_at":         article.fetched_at,
            "title_translated":   article.title_translated,
            "summary_translated": article.summary_translated,
            "is_translated":      article.is_translated,
        }
        with self.db.get_cursor() as cur:
            cur.execute(sql, params)
            result = cur.fetchone()
        self.db.commit()
        inserted = result is not None
        if inserted:
            logger.debug("記事保存: guid=%s", article.guid)
        return inserted

    def get_latest(self, limit: int = 20, translated_only: bool = False) -> list[dict]:
        """最新記事を取得する。"""
        condition = "WHERE a.is_translated = TRUE" if translated_only else ""
        sql = f"""
            SELECT a.id, a.title_original, a.title_translated,
                   a.summary_original, a.summary_translated,
                   a.link, a.published_at, f.name AS feed_name
            FROM articles a
            JOIN feeds f ON a.feed_id = f.id
            {condition}
            ORDER BY a.published_at DESC NULLS LAST
            LIMIT %s;
        """
        with self.db.get_cursor() as cur:
            cur.execute(sql, (limit,))
            return [dict(row) for row in cur.fetchall()]


# ---------------------------------------------------------------------------
# RSSフェッチャー（中心クラス）
# ---------------------------------------------------------------------------

class RssFetcher:
    """
    アクティブなフィードを順番に取得・パースし、
    新着記事を DB に保存する。

    使い方:
        fetcher = RssFetcher(db, feed_repo, article_repo)
        result  = fetcher.fetch_all()
    """

    REQUEST_TIMEOUT = 15        # 秒
    REQUEST_HEADERS = {
        "User-Agent": "PersianNewsReader/1.0 (RSS Aggregator)",
    }

    def __init__(
        self,
        db: DatabaseManager,
        feed_repo: FeedRepository,
        article_repo: ArticleRepository,
    ) -> None:
        self.db = db
        self.feed_repo = feed_repo
        self.article_repo = article_repo

    # ---- 公開メソッド -------------------------------------------------------

    def fetch_all(self) -> dict:
        """
        全アクティブフィードを取得する。
        戻り値: { "total": int, "new": int, "errors": list[str] }
        """
        feeds = self.feed_repo.get_active_feeds()
        total_new = 0
        errors = []

        for feed in feeds:
            try:
                new_count = self._fetch_one(feed)
                total_new += new_count
                self.feed_repo.update_last_fetched(feed["id"])
                logger.info(
                    "フィード取得完了: %s → 新着 %d 件", feed["name"], new_count
                )
            except Exception as exc:
                msg = f"{feed['name']} ({feed['url']}): {exc}"
                logger.error("フィード取得エラー: %s", msg)
                errors.append(msg)

        return {
            "total_feeds": len(feeds),
            "new_articles": total_new,
            "errors": errors,
        }

    def fetch_by_id(self, feed_id: int) -> int:
        """指定IDのフィードのみ取得する。戻り値: 新着件数。"""
        feeds = self.feed_repo.get_active_feeds()
        target = next((f for f in feeds if f["id"] == feed_id), None)
        if target is None:
            raise ValueError(f"feed_id={feed_id} が見つかりません。")
        return self._fetch_one(target)

    # ---- 内部メソッド -------------------------------------------------------

    def _fetch_one(self, feed: dict) -> int:
        """1フィードを取得・パースして記事を保存する。新着件数を返す。"""
        raw_xml = self._download(feed["url"])
        articles = self._parse(raw_xml, feed["id"])
        new_count = sum(self.article_repo.save(a) for a in articles)
        return new_count

    def _download(self, url: str) -> bytes:
        """フィードURLからXMLを取得する。"""
        resp = requests.get(
            url,
            headers=self.REQUEST_HEADERS,
            timeout=self.REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        return resp.content

    def _parse(self, raw_xml: bytes, feed_id: int) -> list[Article]:
        """feedparser でXMLを解析し、Articleリストを返す。"""
        parsed = feedparser.parse(raw_xml)

        if parsed.bozo and not parsed.entries:
            raise ValueError(
                f"feedparser パースエラー: {parsed.bozo_exception}"
            )

        articles = []
        for entry in parsed.entries:
            try:
                article = self._entry_to_article(entry, feed_id)
                articles.append(article)
            except Exception as exc:
                logger.warning("エントリのパースをスキップ: %s", exc)

        return articles

    def _entry_to_article(self, entry, feed_id: int) -> Article:
        """feedparser のエントリを Article データクラスに変換する。"""
        link = getattr(entry, "link", "") or ""
        guid = getattr(entry, "id", link) or Article.make_guid(link)
        title = getattr(entry, "title", "") or ""
        summary = getattr(entry, "summary", "") or ""
        published_at = self._parse_datetime(entry)

        return Article(
            feed_id=feed_id,
            guid=guid,
            title_original=title,
            summary_original=summary,
            link=link,
            published_at=published_at,
        )

    @staticmethod
    def _parse_datetime(entry) -> Optional[datetime]:
        """published_parsed または updated_parsed をUTC datetimeに変換する。"""
        import time
        for attr in ("published_parsed", "updated_parsed"):
            t = getattr(entry, attr, None)
            if t:
                return datetime.fromtimestamp(
                    time.mktime(t), tz=timezone.utc
                )
        return None
