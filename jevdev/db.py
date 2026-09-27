"""SQLite 存储。数据库文件在 data/jevdev.db（不入库）。"""
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "jevdev.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS notes (
    id           TEXT PRIMARY KEY,
    platform     TEXT NOT NULL DEFAULT 'xhs',
    xsec_token   TEXT,
    title        TEXT,
    note_type    TEXT,            -- normal=图文, video=视频
    author_id    TEXT,
    author_name  TEXT,
    cover_w      INTEGER,
    cover_h      INTEGER,
    cover_url    TEXT,
    first_seen   TEXT,
    -- 以下来自详情页，可能为空
    desc         TEXT,
    publish_ts   INTEGER,         -- 毫秒
    image_count  INTEGER,
    detail_at    TEXT,
    is_ours      INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS snapshots (   -- 互动数据的时间序列（同一篇可多次记录）
    note_id     TEXT NOT NULL,
    fetched_at  TEXT NOT NULL,
    liked       INTEGER,
    collected   INTEGER,
    comments    INTEGER,
    shared      INTEGER,
    source      TEXT                  -- search / detail
);
CREATE TABLE IF NOT EXISTS search_hits (
    keyword     TEXT NOT NULL,
    sort_by     TEXT NOT NULL,
    note_id     TEXT NOT NULL,
    rank        INTEGER,
    fetched_at  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_snap_note ON snapshots(note_id);
"""


def connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH, timeout=30)  # 采集和打分脚本可能同时写库
    con.row_factory = sqlite3.Row
    con.executescript(SCHEMA)
    return con
