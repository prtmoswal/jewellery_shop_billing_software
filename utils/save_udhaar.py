import sqlite3
import os
from datetime import datetime
from utils.db_manager import DBManager
from utils.get_pending_purchase_udhaar import update_purchase_udhaar # Import the function to update purchase udhaar

DATABASE_NAME = 'jewellery_app.db'
BILLS_FOLDER = 'bills' # Base folder for all bills

def save_udhaar_deposit(deposit_invoice_id, sell_invoice_id, customer_id, deposit_amount, payment_mode, payment_other_info, linked_purchase_invoice_id=None):
    # Validation
    if not deposit_invoice_id or not customer_id:
        print("Error: Deposit Invoice ID and customer are required for save_udhaar_deposit.")
        return None
    
    if deposit_amount <= 0:
        print("Error: Deposit amount must be greater than zero for save_udhaar_deposit.")
        return None
    
    db = DBManager(DATABASE_NAME) # Instantiate DBManager

    try:
        current_timestamp = datetime.now().isoformat()

        # Get current pending amount for the associated sales invoice (if any)
        udhaar_record_data = db.fetch_one(
            "SELECT udhaar_id, current_balance FROM udhaar WHERE sell_invoice_id = ? AND customer_id = ?",
            (sell_invoice_id, customer_id)
        )

        udhaar_id_for_update = None
        current_pending = 0.0
        if udhaar_record_data:
            udhaar_id_for_update = udhaar_record_data[0]
            current_pending = udhaar_record_data[1]

        # If a sell_invoice_id is provided, validate deposit against it
        if sell_invoice_id:
            if udhaar_record_data is None:
                print(f"Error: No pending balance found for Sell Invoice ID '{sell_invoice_id}' for customer {customer_id}.")
                return None
            # Allow deposit to exceed pending if it's also linked to a purchase invoice,
            # otherwise, validate against sale udhaar pending.
            if not linked_purchase_invoice_id and deposit_amount > current_pending:
                 print(f"Error: Deposit amount ({deposit_amount:.2f}) exceeds pending amount ({current_pending:.2f}) for Invoice ID '{sell_invoice_id}'.")
                 return None
        
        # Insert into udhaar_deposits table
        db.execute_query(
            "INSERT INTO udhaar_deposits (deposit_invoice_id, sell_invoice_id, customer_id, deposit_amount, deposit_date, payment_mode, payment_other_info) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (deposit_invoice_id, sell_invoice_id, customer_id, deposit_amount, current_timestamp, payment_mode, payment_other_info)
        )
        
        # Update pending amount in udhaar table (if a sell_invoice_id was provided and a record existed)
        if sell_invoice_id and udhaar_record_data:
            remaining_amount = current_pending - deposit_amount
            if remaining_amount <= 0:
                db.execute_query(
                    "UPDATE udhaar SET current_balance = ?, status = 'paid', last_payment_date = ?, updated_at = ? WHERE udhaar_id = ?",
                    (0.0, current_timestamp, current_timestamp, udhaar_id_for_update)
                )
            else:
                db.execute_query(
                    "UPDATE udhaar SET current_balance = ?, status = 'partially_paid', last_payment_date = ?, updated_at = ? WHERE udhaar_id = ?",
                    (remaining_amount, current_timestamp, current_timestamp, udhaar_id_for_update)
                )
            
            # Log the transaction in udhaar_transactions
            db.execute_query(
                """
                INSERT INTO udhaar_transactions (udhaar_id, payment_date, amount_paid, payment_mode, transaction_info)
                VALUES (?, ?, ?, ?, ?)
                """,
                (udhaar_id_for_update, current_timestamp, deposit_amount, payment_mode, f"Deposit against {sell_invoice_id or 'general'}")
            )

        # --- NEW: Apply deposit to linked purchase udhaar if specified ---
        if linked_purchase_invoice_id:
            print(f"Debug (save_udhaar_deposit): Attempting to apply deposit to purchase udhaar: {linked_purchase_invoice_id}")
            # Call update_purchase_udhaar to reduce the pending balance for the purchase invoice
            # This function handles its own logging and status updates
            if not update_purchase_udhaar(linked_purchase_invoice_id, deposit_amount):
                print(f"Warning: Failed to fully apply deposit amount to purchase invoice {linked_purchase_invoice_id}.")
        # --- END NEW ---

        return deposit_invoice_id
    except Exception as e:
        print(f"Debug: Error saving udhaar deposit: {e}")
        return None
