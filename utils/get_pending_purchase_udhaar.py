import sqlite3
from utils.config import DATABASE_NAME
from datetime import datetime # Import datetime for current_timestamp in update_purchase_udhaar
from utils.db_manager import DBManager # Import the new DBManager

def get_pending_purchase_udhaar(supplier_id):
    """
    Fetches the total pending purchase amount for a given supplier.

    Args:
        supplier_id (int): The ID of the supplier (customer_id).

    Returns:
        float: The total pending amount for the supplier. Returns 0.0 if no pending amount.
    """
    db = DBManager(DATABASE_NAME) # Use DBManager
    try:
        # Corrected: Sum current_balance instead of pending_amount
        total_pending = db.fetch_one(
            "SELECT SUM(current_balance) FROM purchase_udhaar WHERE supplier_id = ?",
            (supplier_id,)
        )
        return total_pending[0] if total_pending and total_pending[0] is not None else 0.0
    except Exception as e:
        print(f"Error fetching pending purchase udhaar for supplier {supplier_id}: {e}")
        return 0.0
    finally:
        # DBManager handles connection closing, so no need for explicit conn.close() here
        pass

def get_all_pending_purchase_udhaar():
    """
    Fetches all pending purchase amounts from the purchase_udhaar table.

    Returns:
        list of dict: A list of dictionaries, each representing a pending purchase udhaar record.
                      Returns an empty list if no pending amounts.
    """
    db = DBManager(DATABASE_NAME) # Use DBManager for fetching rows
    try:
        rows = db.fetch_all("SELECT * FROM purchase_udhaar WHERE current_balance > 0")
        
        if rows:
            # Get column names from schema for dict conversion
            # This part needs a direct sqlite3 connection for PRAGMA,
            # as DBManager's methods don't expose cursor.description directly.
            temp_conn = sqlite3.connect(DATABASE_NAME)
            temp_conn.row_factory = sqlite3.Row # Set row_factory for column names
            temp_cursor = temp_conn.cursor()
            temp_cursor.execute("PRAGMA table_info(purchase_udhaar)")
            columns = [col[1] for col in temp_cursor.fetchall()]
            temp_conn.close() # Close the temporary connection

            return [dict(zip(columns, row)) for row in rows]
        return []
    except Exception as e:
        print(f"Error fetching all pending purchase udhaar: {e}")
        return []
    finally:
        # DBManager handles connection closing for its operations
        pass


def update_purchase_udhaar(purchase_invoice_id, amount_paid):
    """
    Updates the pending amount for a specific purchase invoice in the purchase_udhaar table.
    If the pending amount becomes zero or less, the record is removed.

    Args:
        purchase_invoice_id (str): The invoice ID of the purchase.
        amount_paid (float): The amount being paid against this pending purchase.

    Returns:
        bool: True if update was successful, False otherwise.
    """
    db = DBManager(DATABASE_NAME) # Use DBManager
    try:
        print(f"Debug (update_purchase_udhaar): Attempting to update purchase invoice {purchase_invoice_id} with amount paid {amount_paid}")
        result = db.fetch_one(
            "SELECT current_balance FROM purchase_udhaar WHERE purchase_invoice_id = ?",
            (purchase_invoice_id,)
        )

        if result:
            current_pending = result[0]
            new_pending = current_pending - amount_paid
            current_timestamp = datetime.now().isoformat()
            print(f"Debug (update_purchase_udhaar): Current pending: {current_pending}, New pending: {new_pending}")

            if new_pending <= 0:
                db.execute_query(
                    "UPDATE purchase_udhaar SET current_balance = ?, status = 'paid', last_payment_date = ?, updated_at = ? WHERE purchase_invoice_id = ?",
                    (0.0, current_timestamp, current_timestamp, purchase_invoice_id)
                )
                print(f"Debug (update_purchase_udhaar): Set purchase invoice {purchase_invoice_id} to paid.")
            else:
                db.execute_query(
                    "UPDATE purchase_udhaar SET current_balance = ?, status = 'partially_paid', last_payment_date = ?, updated_at = ? WHERE purchase_invoice_id = ?",
                    (new_pending, current_timestamp, current_timestamp, purchase_invoice_id)
                )
                print(f"Debug (update_purchase_udhaar): Updated purchase invoice {purchase_invoice_id} to {new_pending}.")
            
            # Log the transaction in purchase_udhaar_transactions
            udhaar_id_result = db.fetch_one("SELECT udhaar_id FROM purchase_udhaar WHERE purchase_invoice_id = ?", (purchase_invoice_id,))
            if udhaar_id_result:
                udhaar_id = udhaar_id_result[0]
                db.execute_query('''
                    INSERT INTO purchase_udhaar_transactions (udhaar_id, payment_date, amount_paid, payment_mode, transaction_info)
                    VALUES (?, ?, ?, ?, ?)
                ''', (udhaar_id, current_timestamp, amount_paid, 'Adjustment (Sale)', f"Adjusted against sale invoice"))
                print(f"Debug (update_purchase_udhaar): Logged transaction for udhaar_id {udhaar_id}.")
            else:
                print(f"Debug (update_purchase_udhaar): Could not find udhaar_id for logging transaction for {purchase_invoice_id}.")


            print(f"Debug (update_purchase_udhaar): Transaction for purchase invoice {purchase_invoice_id} processed via DBManager.")
            return True
        else:
            print(f"Debug (update_purchase_udhaar): No pending purchase found for invoice ID: {purchase_invoice_id}")
            return False
    except Exception as e:
        print(f"Error updating purchase udhaar for invoice {purchase_invoice_id}: {e}")
        return False
    finally:
        # DBManager handles connection closing
        pass
