import sqlite3
import hashlib
import json
import os
from contextlib import contextmanager

CACHE_DB_PATH = os.path.join(os.getcwd(), ".pytest_semantic_cache.db")

@contextmanager
def get_db_connection():
    conn = sqlite3.connect(CACHE_DB_PATH)
    try:
        yield conn
    finally:
        conn.close()

def init_db():
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS semantic_evaluations (
                eval_hash TEXT PRIMARY KEY,
                passed BOOLEAN,
                reason TEXT
            )
        ''')
        conn.commit()

def generate_hash(intent: str, trace_log: str) -> str:
    hash_input = f"{intent}|{trace_log}".encode('utf-8')
    return hashlib.sha256(hash_input).hexdigest()

def get_cached_evaluation(eval_hash: str):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT passed, reason FROM semantic_evaluations WHERE eval_hash = ?', (eval_hash,))
        result = cursor.fetchone()
        if result:
            return {"passed": bool(result[0]), "reason": result[1]}
    return None

def cache_evaluation(eval_hash: str, passed: bool, reason: str):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO semantic_evaluations (eval_hash, passed, reason)
            VALUES (?, ?, ?)
        ''', (eval_hash, passed, reason))
        conn.commit()

# Initialize DB on import
init_db()
