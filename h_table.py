import sqlite3

conn = sqlite3.connect("shippers.db")
cur = conn.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS stock_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    shipper_id INTEGER,
    name TEXT,
    old_stock INTEGER,
    new_stock INTEGER,
    diff INTEGER,
    timestamp TEXT
)
""")

conn.commit()
conn.close()

print("History table created!")