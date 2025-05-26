import sqlite3
from datetime import datetime
from utils.config import DATABASE_NAME
from utils.db_manager import DBManager

def get_next_invoice_number(prefix):
    """
    Retrieves the next sequential invoice number for a given prefix (e.g., 'SALES', 'PURCHASE').
    Updates the last used number in the database.
    """
    db = DBManager(DATABASE_NAME) # Instantiate DBManager
    try:
        # Use db.fetch_one instead of cursor.execute and cursor.fetchone
        last_number_result = db.fetch_one("SELECT MAX(invoice_number) FROM invoice_numbers WHERE prefix = ?", (prefix,))
        last_number = last_number_result[0] if last_number_result else None # Extract value from tuple

        next_number = (last_number if last_number is not None else 0) + 1

        # Use db.execute_query instead of cursor.execute and conn.commit
        db.execute_query("REPLACE INTO invoice_numbers (prefix, invoice_number) VALUES (?, ?)", (prefix, next_number))
        
        return next_number
    except Exception as e:
        print(f"Error getting next invoice number for prefix {prefix}: {e}")
        # DBManager's execute_query handles rollback internally, no need for conn.rollback()
        return None
    finally:
        # DBManager handles connection closing, no need for conn.close()
        pass

def generate_sales_invoice_id():
    """
    Generates a unique sales invoice ID in the format SAL-YYYY-NNNNN.
    """
    year = datetime.now().strftime("%Y")
    next_num = get_next_invoice_number("SALES")
    if next_num is None:
        return None # Handle error case
    return f"SAL-{year}-{next_num:05d}" # Example: SAL-2023-00001

def generate_purchase_invoice_id():
    """
    Generates a unique purchase invoice ID in the format PUR-YYYY-NNNNN.
    """
    year = datetime.now().strftime("%Y")
    next_num = get_next_invoice_number("PURCHASE")
    if next_num is None:
        return None # Handle error case
    return f"PUR-{year}-{next_num:05d}"

def generate_udhaar_invoice_id(customer_id):
    """
    Generates a unique udhaar (credit) invoice ID in the format UDH-YYYY-CUSTOMERID-NNN.
    """
    year = datetime.now().strftime("%Y")
    # Using customer_id as part of the prefix for udhaar to ensure uniqueness per customer
    next_num = get_next_invoice_number(f"UDHAAR-{customer_id}")
    if next_num is None:
        return None # Handle error case
    return f"UDH-{year}-{customer_id}-{next_num:03d}"
