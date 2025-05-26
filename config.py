import sqlite3
import os
from datetime import datetime
from utils.db_manager import DBManager # Import the new DBManager

DATABASE_NAME = 'jewellery_app.db'
BILLS_FOLDER = 'bills' # Base folder for all bills

def create_bills_directory():
    """Ensures the base bills directory and a daily sub-directory exist."""
    today_folder = datetime.now().strftime('%Y-%m-%d')
    daily_bills_path = os.path.join(BILLS_FOLDER, today_folder)

    if not os.path.exists(daily_bills_path):
        os.makedirs(daily_bills_path)
    return daily_bills_path

def create_tables():
    """Creates database tables if they don't exist."""
    db = DBManager(DATABASE_NAME) # Use DBManager

    # Enable foreign key constraints for data integrity (important!)
    db.execute_query("PRAGMA foreign_keys = ON;")

    # --- New: invoice_numbers table for sequential IDs ---
    db.execute_query('''
        CREATE TABLE IF NOT EXISTS invoice_numbers (
            prefix TEXT PRIMARY KEY,
            invoice_number INTEGER NOT NULL DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # --- 1. Customers Table ---
    db.execute_query('''
        CREATE TABLE IF NOT EXISTS customers (
            customer_id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            phone TEXT UNIQUE,
            address TEXT,
            pan TEXT,
            aadhaar TEXT,
            firstname TEXT,
            lastname TEXT,
            gender TEXT,
            email TEXT,
            alternate_phone TEXT,
            alternate_phone2 TEXT,
            landline_phone TEXT,
            city TEXT,
            state TEXT,
            country TEXT,
            pincode TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # --- 2. Categories Table ---
    db.execute_query('''
        CREATE TABLE IF NOT EXISTS categories (
            category_id INTEGER PRIMARY KEY AUTOINCREMENT,
            category_name TEXT UNIQUE NOT NULL,
            description TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # --- 3. Subcategories Table ---
    db.execute_query('''
        CREATE TABLE IF NOT EXISTS subcategories (
            subcategory_id INTEGER PRIMARY KEY AUTOINCREMENT,
            category_id INTEGER NOT NULL,
            subcategory_name TEXT UNIQUE NOT NULL,
            description TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (category_id) REFERENCES categories (category_id) ON DELETE CASCADE
        )
    ''')

    # --- 4. Metals Table ---
    db.execute_query('''
        CREATE TABLE IF NOT EXISTS metals (
            metal_id INTEGER PRIMARY KEY AUTOINCREMENT,
            metal_name TEXT UNIQUE NOT NULL, -- e.g., Gold, Silver, Platinum
            description TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # --- 5. Purities Table ---
    db.execute_query('''
        CREATE TABLE IF NOT EXISTS purities (
            purity_id INTEGER PRIMARY KEY AUTOINCREMENT,
            purity_value TEXT UNIQUE NOT NULL, -- e.g., 24K, 22K, 92.5%
            description TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # --- 6. Products Table ---
    db.execute_query('''
        CREATE TABLE IF NOT EXISTS products (
            product_id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_name TEXT NOT NULL,
            description TEXT,
            category_id INTEGER,
            subcategory_id INTEGER,
            metal_id INTEGER,
            purity_id INTEGER,
            hsn_code TEXT,
            default_cgst_rate REAL DEFAULT 1.5,
            default_sgst_rate REAL DEFAULT 1.5,
            making_charge_type TEXT, -- 'per_gram', 'fixed', 'percentage'
            default_making_charge REAL,
            current_stock REAL DEFAULT 0.0, -- Initial stock, updated by inventory_transactions
            is_active INTEGER DEFAULT 1, -- 0 for inactive, 1 for active
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (category_id) REFERENCES categories (category_id) ON DELETE SET NULL,
            FOREIGN KEY (subcategory_id) REFERENCES subcategories (subcategory_id) ON DELETE SET NULL,
            FOREIGN KEY (metal_id) REFERENCES metals (metal_id) ON DELETE SET NULL,
            FOREIGN KEY (purity_id) REFERENCES purities (purity_id) ON DELETE SET NULL
        )
    ''')

    # --- 7. Inventory Transactions Table ---
    db.execute_query('''
        CREATE TABLE IF NOT EXISTS inventory_transactions (
            transaction_id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER NOT NULL,
            transaction_type TEXT NOT NULL, -- 'purchase_in', 'sale_out', 'adjustment_in', 'adjustment_out'
            quantity_change REAL NOT NULL, -- Positive for stock in, negative for stock out
            current_stock_after REAL NOT NULL, -- Stock level after this transaction
            reference_id TEXT, -- e.g., invoice_id from sales/purchases
            transaction_date DATETIME DEFAULT CURRENT_TIMESTAMP,
            notes TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (product_id) REFERENCES products (product_id) ON DELETE CASCADE
        )
    ''')

    # --- 8. Sales Table ---
    db.execute_query('''
        CREATE TABLE IF NOT EXISTS sales (
            invoice_id TEXT PRIMARY KEY,
            sale_date DATETIME NOT NULL,
            customer_id INTEGER NOT NULL,
            total_amount REAL NOT NULL,
            cheque_amount REAL DEFAULT 0.0,
            online_amount REAL DEFAULT 0.0,
            upi_amount REAL DEFAULT 0.0,
            cash_amount REAL DEFAULT 0.0,
            old_gold_amount REAL DEFAULT 0.0,
            amount_balance REAL NOT NULL,
            payment_mode TEXT,
            payment_other_info TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (customer_id) REFERENCES customers (customer_id) ON DELETE RESTRICT
        )
    ''')

    # --- 9. Sale Items Table ---
    db.execute_query('''
        CREATE TABLE IF NOT EXISTS sale_items (
            item_id INTEGER PRIMARY KEY AUTOINCREMENT,
            invoice_id TEXT NOT NULL,
            product_id INTEGER, -- Link to products table, NULLable for custom/one-off items
            metal TEXT NOT NULL,
            metal_rate REAL NOT NULL,
            description TEXT NOT NULL,
            qty INTEGER NOT NULL,
            net_wt REAL NOT NULL,
            purity TEXT,
            gross_wt REAL,
            loss_wt REAL,
            making_charge REAL DEFAULT 0.0,
            making_charge_type TEXT, -- 'per_gram', 'fixed', 'percentage' for this specific item
            stone_weight REAL DEFAULT 0.0,
            stone_charge REAL DEFAULT 0.0,
            wastage_percentage REAL DEFAULT 0.0,
            amount REAL NOT NULL,
            cgst_rate REAL DEFAULT 1.5,
            sgst_rate REAL DEFAULT 1.5,
            hsn TEXT DEFAULT '7113',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (invoice_id) REFERENCES sales (invoice_id) ON DELETE CASCADE,
            FOREIGN KEY (product_id) REFERENCES products (product_id) ON DELETE SET NULL
        )
    ''')

    # --- 10. Purchases Table ---
    db.execute_query('''
        CREATE TABLE IF NOT EXISTS purchases (
            invoice_id TEXT PRIMARY KEY,
            purchase_date DATETIME NOT NULL,
            supplier_id INTEGER NOT NULL, -- Customer acting as supplier
            total_amount REAL NOT NULL,
            payment_mode TEXT,
            payment_other_info TEXT,
            cheque_amount REAL DEFAULT 0.0,
            online_amount REAL DEFAULT 0.0,
            upi_amount REAL DEFAULT 0.0,
            cash_amount REAL DEFAULT 0.0,
            amount_balance REAL NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (supplier_id) REFERENCES customers (customer_id) ON DELETE RESTRICT
        )
    ''')

    # --- 11. Purchase Items Table ---
    db.execute_query('''
        CREATE TABLE IF NOT EXISTS purchase_items (
            item_id INTEGER PRIMARY KEY AUTOINCREMENT,
            invoice_id TEXT NOT NULL,
            product_id INTEGER, -- Link to products table, NULLable for custom/one-off items
            metal TEXT NOT NULL,
            qty INTEGER NOT NULL,
            net_wt REAL NOT NULL,
            price REAL NOT NULL, -- Purchase price per unit/gram
            amount REAL NOT NULL,
            gross_wt REAL,
            loss_wt REAL,
            metal_rate REAL,
            description TEXT,
            purity TEXT,
            cgst_rate REAL DEFAULT 1.5,
            sgst_rate REAL DEFAULT 1.5,
            hsn TEXT DEFAULT '7113',
            making_charge REAL DEFAULT 0.0,
            making_charge_type TEXT,
            stone_weight REAL DEFAULT 0.0,
            stone_charge REAL DEFAULT 0.0,
            wastage_percentage REAL DEFAULT 0.0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (invoice_id) REFERENCES purchases (invoice_id) ON DELETE CASCADE,
            FOREIGN KEY (product_id) REFERENCES products (product_id) ON DELETE SET NULL
        )
    ''')

    # --- 12. Udhaar (Pending Amounts for Sales) Table ---
    db.execute_query('''
        CREATE TABLE IF NOT EXISTS udhaar (
            udhaar_id INTEGER PRIMARY KEY AUTOINCREMENT,
            sell_invoice_id TEXT NOT NULL UNIQUE,
            customer_id INTEGER NOT NULL,
            initial_balance REAL NOT NULL,
            current_balance REAL NOT NULL,
            last_payment_date DATETIME,
            status TEXT DEFAULT 'pending', -- 'pending', 'paid', 'partially_paid'
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (customer_id) REFERENCES customers (customer_id) ON DELETE RESTRICT,
            FOREIGN KEY (sell_invoice_id) REFERENCES sales (invoice_id) ON DELETE CASCADE
        )
    ''')

    # --- 13. Udhaar Deposits Table (for advance payments or general deposits) ---
    db.execute_query('''
        CREATE TABLE IF NOT EXISTS udhaar_deposits (
            deposit_id INTEGER PRIMARY KEY AUTOINCREMENT,
            deposit_invoice_id TEXT UNIQUE NOT NULL, -- New: Unique ID for the deposit transaction
            sell_invoice_id TEXT, -- Link to the sales invoice this deposit applies to (nullable if general deposit)
            customer_id INTEGER NOT NULL,
            deposit_amount REAL NOT NULL,
            deposit_date DATETIME DEFAULT CURRENT_TIMESTAMP,
            payment_mode TEXT,
            payment_other_info TEXT,
            notes TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (customer_id) REFERENCES customers (customer_id) ON DELETE RESTRICT,
            FOREIGN KEY (sell_invoice_id) REFERENCES sales (invoice_id) ON DELETE SET NULL
        )
    ''')

    # --- 14. Purchase Udhaar (Pending Amounts for Purchases - what you owe suppliers) Table ---
    db.execute_query('''
        CREATE TABLE IF NOT EXISTS purchase_udhaar (
            udhaar_id INTEGER PRIMARY KEY AUTOINCREMENT,
            purchase_invoice_id TEXT NOT NULL UNIQUE,
            supplier_id INTEGER NOT NULL,
            initial_balance REAL NOT NULL,
            current_balance REAL NOT NULL,
            last_payment_date DATETIME,
            status TEXT DEFAULT 'pending', -- 'pending', 'paid', 'partially_paid'
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (purchase_invoice_id) REFERENCES purchases (invoice_id) ON DELETE CASCADE,
            FOREIGN KEY (supplier_id) REFERENCES customers (customer_id) ON DELETE RESTRICT
        )
    ''')

    # --- 15. Purchase Udhaar Transactions Table ---
    db.execute_query('''
        CREATE TABLE IF NOT EXISTS purchase_udhaar_transactions (
            transaction_id INTEGER PRIMARY KEY AUTOINCREMENT,
            udhaar_id INTEGER NOT NULL,
            payment_date DATETIME NOT NULL,
            amount_paid REAL NOT NULL,
            payment_mode TEXT,
            transaction_info TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (udhaar_id) REFERENCES purchase_udhaar (udhaar_id) ON DELETE CASCADE
        )
    ''')

    # --- 16. Udhaar Transactions Table (Corrected schema for sale udhaar payments) ---
    db.execute_query('''
        CREATE TABLE IF NOT EXISTS udhaar_transactions (
            transaction_id INTEGER PRIMARY KEY AUTOINCREMENT,
            udhaar_id INTEGER NOT NULL, -- Foreign key to the udhaar table
            payment_date DATETIME NOT NULL,
            amount_paid REAL NOT NULL,
            payment_mode TEXT,
            transaction_info TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (udhaar_id) REFERENCES udhaar (udhaar_id) ON DELETE CASCADE
        )
    ''')

    # --- 17. Settings Table (for application-wide configurations) ---
    db.execute_query('''
        CREATE TABLE IF NOT EXISTS settings (
            setting_key TEXT PRIMARY KEY NOT NULL,
            setting_value TEXT,
            description TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    print("Database tables checked/created successfully.")
