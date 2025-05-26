import sqlite3
from datetime import datetime
from utils.db_manager import DBManager
from utils.config import DATABASE_NAME

def delete_udhaar_deposit_and_reverse(deposit_invoice_id):
    """
    Deletes an udhaar deposit record and reverses its impact on associated
    udhaar (sale pending) and purchase_udhaar (your pending) balances.
    This function does NOT contain Streamlit UI elements; it returns True/False for success.
    """
    db = DBManager(DATABASE_NAME)
    try:
        # 1. Retrieve the deposit info, including linked_purchase_invoice_id
        deposit_info = db.fetch_one(
            "SELECT sell_invoice_id, deposit_amount, customer_id, linked_purchase_invoice_id FROM udhaar_deposits WHERE deposit_invoice_id = ?",
            (deposit_invoice_id,),
        )

        if not deposit_info:
            print(f"Error: Udhaar Deposit with Invoice ID '{deposit_invoice_id}' not found for reversal.")
            return False

        sell_invoice_id, deposit_amount, customer_id, linked_purchase_invoice_id = deposit_info

        # 2. Delete the udhaar_deposit record
        db.execute_query(
            "DELETE FROM udhaar_deposits WHERE deposit_invoice_id = ?",
            (deposit_invoice_id,),
        )
        print(f"Debug: Deleted udhaar_deposit record for ID: {deposit_invoice_id}")

        # 3. Reverse effects on udhaar (sale pending) balance if linked
        if sell_invoice_id:
            udhaar_record = db.fetch_one(
                "SELECT udhaar_id, current_balance FROM udhaar WHERE sell_invoice_id = ?",
                (sell_invoice_id,),
            )
            if udhaar_record:
                udhaar_id, current_pending = udhaar_record
                new_pending_amount = current_pending + deposit_amount
                # Determine status based on new balance
                status = 'pending' if new_pending_amount > 0 else 'paid'
                db.execute_query(
                    "UPDATE udhaar SET current_balance = ?, status = ?, updated_at = ? WHERE udhaar_id = ?",
                    (new_pending_amount, status, datetime.now().isoformat(), udhaar_id),
                )
                print(f"Debug: Reversed deposit: Udhaar for sale invoice {sell_invoice_id} increased by {deposit_amount}. New balance: {new_pending_amount}")
            else:
                # If no corresponding udhaar entry exists (implies it was fully paid off by this deposit), create one
                db.execute_query(
                    "INSERT INTO udhaar (sell_invoice_id, customer_id, initial_balance, current_balance, status, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (sell_invoice_id, customer_id, deposit_amount, deposit_amount, 'pending', datetime.now().isoformat(), datetime.now().isoformat()),
                )
                print(f"Debug: Reversed deposit: New udhaar record created for sale invoice {sell_invoice_id} with amount {deposit_amount}.")

        # 4. Reverse effects on purchase_udhaar (your pending) balance if linked
        if linked_purchase_invoice_id:
            purchase_udhaar_record = db.fetch_one(
                "SELECT udhaar_id, current_balance FROM purchase_udhaar WHERE purchase_invoice_id = ?",
                (linked_purchase_invoice_id,)
            )
            if purchase_udhaar_record:
                pur_udhaar_id, pur_current_balance = purchase_udhaar_record
                pur_new_balance = pur_current_balance + deposit_amount
                # Determine status based on new balance
                pur_status = 'pending' if pur_new_balance > 0 else 'paid'
                db.execute_query(
                    "UPDATE purchase_udhaar SET current_balance = ?, status = ?, updated_at = ? WHERE udhaar_id = ?",
                    (pur_new_balance, pur_status, datetime.now().isoformat(), pur_udhaar_id)
                )
                print(f"Debug: Reversed deposit: Purchase udhaar for invoice {linked_purchase_invoice_id} increased by {deposit_amount}. New balance: {pur_new_balance}")
            else:
                print(f"Warning: Linked purchase udhaar record {linked_purchase_invoice_id} not found during deposit reversal.")

        return True
    except Exception as e:
        print(f"Error in delete_udhaar_deposit_and_reverse: {e}")
        return False
