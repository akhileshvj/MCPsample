import sqlite3

conn = sqlite3.connect("sample.db")
cur = conn.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS customers (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    city TEXT
);
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY,
    customer_id INTEGER NOT NULL,
    amount REAL NOT NULL,
    order_date TEXT NOT NULL,
    FOREIGN KEY (customer_id) REFERENCES customers(id)
);
""")

cur.executemany(
    "INSERT INTO customers (id, name, city) VALUES (?, ?, ?)",
    [
        (1, "Alice", "London"),
        (2, "Bob", "Paris"),
        (3, "Charlie", "Berlin"),
    ],
)

cur.executemany(
    "INSERT INTO orders (id, customer_id, amount, order_date) VALUES (?, ?, ?, ?)",
    [
        (1, 1, 120.50, "2024-10-01"),
        (2, 1, 80.00, "2024-10-05"),
        (3, 2, 200.00, "2024-10-02"),
        (4, 3, 50.00, "2024-09-20"),
    ],
)

conn.commit()
conn.close()
print("sample.db created")