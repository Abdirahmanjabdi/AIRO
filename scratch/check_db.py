import sqlite3
import json

conn = sqlite3.connect('redis_fallback.db')
tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
print("Tables:", [t[0] for t in tables])

if any(t[0] == 'queue' for t in tables):
    rows = conn.execute("SELECT id, key, substr(value, 1, 100) FROM queue").fetchall()
    print(f"QUEUE ({len(rows)} rows):", rows)
else:
    print("No queue table")

if any(t[0] == 'kv' for t in tables):
    rows = conn.execute("SELECT key, substr(value, 1, 60) FROM kv").fetchall()
    print(f"KV ({len(rows)} rows):", rows)
else:
    print("No kv table")

if any(t[0] == 'vault_kv' for t in tables):
    rows = conn.execute("SELECT key, substr(value, 1, 80) FROM vault_kv").fetchall()
    print(f"VAULT_KV ({len(rows)} rows):", rows)
else:
    print("No vault_kv table")

conn.close()
