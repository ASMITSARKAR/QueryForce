import sqlite3
import argparse
import sys
import random
from datetime import datetime, timedelta
from pathlib import Path

# Add project root to sys.path to import src.config
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import settings

def generate_random_date(start_days_ago=365):
    start = datetime.now() - timedelta(days=start_days_ago)
    return start + timedelta(seconds=random.randint(0, start_days_ago * 24 * 60 * 60))

def seed_database(reset: bool = False):
    db_path = Path(settings.ANALYTICS_DB_PATH)
    
    # Ensure data directory exists
    db_path.parent.mkdir(parents=True, exist_ok=True)
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute("PRAGMA foreign_keys = ON;")
    
    if reset:
        print("Resetting database...")
        tables = ["reviews", "order_items", "orders", "products", "customers"]
        for table in tables:
            cursor.execute(f"DROP TABLE IF EXISTS {table};")
            
    # DDL
    print("Creating tables...")
    cursor.executescript("""
    CREATE TABLE IF NOT EXISTS customers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL COLLATE NOCASE,
        country TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        category TEXT NOT NULL,
        price REAL NOT NULL,
        stock_quantity INTEGER NOT NULL
    );

    CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        customer_id INTEGER NOT NULL,
        status TEXT NOT NULL,
        total_amount REAL NOT NULL,
        order_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (customer_id) REFERENCES customers(id)
    );

    CREATE TABLE IF NOT EXISTS order_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_id INTEGER NOT NULL,
        product_id INTEGER NOT NULL,
        quantity INTEGER NOT NULL,
        unit_price REAL NOT NULL,
        FOREIGN KEY (order_id) REFERENCES orders(id),
        FOREIGN KEY (product_id) REFERENCES products(id)
    );

    CREATE TABLE IF NOT EXISTS reviews (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        product_id INTEGER NOT NULL,
        customer_id INTEGER NOT NULL,
        rating INTEGER,
        comment TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (product_id) REFERENCES products(id),
        FOREIGN KEY (customer_id) REFERENCES customers(id)
    );
    """)
    
    # Check if already seeded
    cursor.execute("SELECT COUNT(*) FROM customers")
    if cursor.fetchone()[0] > 0:
        print("Database already contains data. Use --reset to re-seed.")
        return
        
    print("Inserting customers...")
    countries = ["USA", "UK", "Canada", "Australia", "Germany"]
    customers_data = []
    for i in range(1, 101):
        created = generate_random_date()
        customers_data.append((
            f"Customer {i}",
            f"customer{i}@example.com",
            random.choice(countries),
            created.strftime("%Y-%m-%d %H:%M:%S")
        ))
    cursor.executemany("INSERT INTO customers (name, email, country, created_at) VALUES (?, ?, ?, ?)", customers_data)
    
    print("Inserting products...")
    categories = ["Electronics", "Clothing", "Home", "Sports"]
    products_data = []
    for i in range(1, 51):
        products_data.append((
            f"Product {i}",
            random.choice(categories),
            round(random.uniform(10.0, 500.0), 2),
            random.randint(10, 1000)
        ))
    cursor.executemany("INSERT INTO products (name, category, price, stock_quantity) VALUES (?, ?, ?, ?)", products_data)
    
    print("Inserting orders...")
    statuses = ["Delivered", "Shipped", "Processing", "Cancelled"]
    orders_data = []
    for i in range(1, 301):
        customer_id = random.randint(1, 100)
        orders_data.append((
            customer_id,
            random.choices(statuses, weights=[0.7, 0.15, 0.1, 0.05])[0],
            0.0, # Will update later
            generate_random_date(180).strftime("%Y-%m-%d %H:%M:%S")
        ))
    cursor.executemany("INSERT INTO orders (customer_id, status, total_amount, order_date) VALUES (?, ?, ?, ?)", orders_data)
    
    print("Inserting order_items...")
    order_items_data = []
    # 600 items across 300 orders -> avg 2 items per order
    for i in range(1, 601):
        order_id = random.randint(1, 300)
        product_id = random.randint(1, 50)
        quantity = random.randint(1, 5)
        # Fetch price
        cursor.execute("SELECT price FROM products WHERE id = ?", (product_id,))
        unit_price = cursor.fetchone()[0]
        order_items_data.append((
            order_id,
            product_id,
            quantity,
            unit_price
        ))
    cursor.executemany("INSERT INTO order_items (order_id, product_id, quantity, unit_price) VALUES (?, ?, ?, ?)", order_items_data)
    
    # Update order totals
    cursor.execute("""
        UPDATE orders 
        SET total_amount = (
            SELECT COALESCE(SUM(quantity * unit_price), 0) 
            FROM order_items 
            WHERE order_items.order_id = orders.id
        )
    """)
    
    print("Inserting reviews...")
    reviews_data = []
    for i in range(1, 151):
        product_id = random.randint(1, 50)
        customer_id = random.randint(1, 100)
        
        # 10% NULL rating
        if random.random() < 0.1:
            rating = None
            comment = None
        else:
            rating = random.randint(1, 5)
            comment = f"Review for product {product_id} by customer {customer_id}"
            
        reviews_data.append((
            product_id,
            customer_id,
            rating,
            comment,
            generate_random_date(90).strftime("%Y-%m-%d %H:%M:%S")
        ))
    cursor.executemany("INSERT INTO reviews (product_id, customer_id, rating, comment, created_at) VALUES (?, ?, ?, ?, ?)", reviews_data)
    
    conn.commit()
    conn.close()
    print("Database seeding complete!")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed the QueryForce database.")
    parser.add_argument("--reset", action="store_true", help="Drop existing tables and re-seed.")
    args = parser.parse_args()
    seed_database(reset=args.reset)
