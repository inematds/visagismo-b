import contextlib
import sqlite3
from .config import DATA

@contextlib.contextmanager
def db():
    con = sqlite3.connect(DATA / 'visagismo.sqlite3', timeout=30)
    con.row_factory = sqlite3.Row
    con.execute('PRAGMA foreign_keys=ON')
    try:
        yield con
        con.commit()
    except BaseException:
        con.rollback()
        raise
    finally:
        con.close()

def init():
    with db() as con:
        con.execute('PRAGMA journal_mode=WAL')
        con.executescript('''
        CREATE TABLE IF NOT EXISTS tenants (
          id TEXT PRIMARY KEY, name TEXT NOT NULL, city TEXT DEFAULT '',
          professional TEXT NOT NULL, price_cents INTEGER DEFAULT 0,
          contact TEXT DEFAULT '', color TEXT DEFAULT '#b82835');
        CREATE TABLE IF NOT EXISTS users (
          id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL REFERENCES tenants(id),
          email TEXT UNIQUE NOT NULL, password TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS sessions (
          token TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id),
          csrf TEXT NOT NULL, expires REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS consultations (
          id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL REFERENCES tenants(id),
          client TEXT NOT NULL, answers TEXT NOT NULL, status TEXT NOT NULL,
          result TEXT, notes TEXT DEFAULT '', reviewer TEXT, reviewed_at REAL,
          created REAL NOT NULL, updated REAL NOT NULL, next_visit TEXT DEFAULT '',
          paid INTEGER DEFAULT 0, payment_method TEXT, payment_id TEXT UNIQUE,
          price_cents INTEGER NOT NULL DEFAULT 0, error TEXT, attempts INTEGER DEFAULT 0,
          share_hash TEXT, share_expires REAL, simulation_note TEXT DEFAULT '');
        CREATE TABLE IF NOT EXISTS login_attempts (
          key TEXT PRIMARY KEY, count INTEGER NOT NULL, expires REAL NOT NULL);
        CREATE INDEX IF NOT EXISTS consultations_tenant ON consultations(tenant_id,created);
        CREATE INDEX IF NOT EXISTS consultations_status ON consultations(status);
        ''')
