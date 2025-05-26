import sqlite3
from datetime import datetime
from utils.config import DATABASE_NAME
from utils.db_manager import DBManager

def update_udhaar_deposit(
    deposit_invoice_id,
    new_sell_invoice_id,
    new_customer_id,
    new_deposit_amount,
    new_payment_mode,
    new_payment_info
):
    """
    Updates an existing udhaar deposit record in the database.

    Args:
        deposit_invoice_id (str): The ID of the deposit invoice to update.
        new_sell_invoice_id (str): The updated linked sales invoice ID (can be None).
        new_customer_id (int): The updated customer ID.
        new_deposit_amount (float): The updated deposit amount.
        new_payment_mode (str): The updated payment mode.
        new_payment_info (str): The updated payment other info.

    Returns:
        bool: True if the update was successful, False otherwise.
    """
    db = DBManager(DATABASE_NAME)
    current_timestamp = datetime.now().isoformat()

    try:
        # Fetch original deposit details and associated udhaar balance
        original_deposit_details = db.fetch_one(
            "SELECT deposit_amount, sell_invoice_id, customer_id FROM udhaar_deposits WHERE deposit_invoice_id = ?",
            (deposit_invoice_id,)
        )

        if not original_deposit_details:
            print(f"Debug (update_udhaar_deposit): No deposit found for ID: {deposit_invoice_id}")
            return False

        original_deposit_amount = original_deposit_details[0]
        original_sell_invoice_id = original_deposit_details[1]
        original_customer_id = original_deposit_details[2]

        print(f"Debug (update_udhaar_deposit): Original Deposit Amount: {original_deposit_amount}")
        print(f"Debug (update_udhaar_deposit): New Deposit Amount: {new_deposit_amount}")
        print(f"Debug (update_udhaar_deposit): Original Sell Invoice ID: {original_sell_invoice_id}")
        print(f"Debug (update_udhaar_deposit): New Sell Invoice ID: {new_sell_invoice_id}")

        # Step 1: Reverse the effect of the original deposit on the original linked sale invoice (if any)
        if original_sell_invoice_id:
            udhaar_record = db.fetch_one(
                "SELECT udhaar_id, current_balance FROM udhaar WHERE sell_invoice_id = ? AND customer_id = ?",
                (original_sell_invoice_id, original_customer_id)
            )
            if udhaar_record:
                udhaar_id = udhaar_record[0]
                current_balance = udhaar_record[1]
                # Add back the original deposit amount to the current balance
                adjusted_balance = current_balance + original_deposit_amount
                db.execute_query(
                    "UPDATE udhaar SET current_balance = ?, status = ?, updated_at = ? WHERE udhaar_id = ?",
                    (adjusted_balance, 'pending', current_timestamp, udhaar_id)
                )
                print(f"Debug: Reversed original deposit for udhaar_id {udhaar_id}. New balance: {adjusted_balance}")
            else:
                print(f"Debug: No udhaar record found for original sell_invoice_id {original_sell_invoice_id} to reverse.")

        # Step 2: Update the udhaar_deposits record
        db.execute_query(
            """
            UPDATE udhaar_deposits
            SET sell_invoice_id = ?, customer_id = ?, deposit_amount = ?,
                payment_mode = ?, payment_other_info = ?, updated_at = ?
            WHERE deposit_invoice_id = ?
            """,
            (
                new_sell_invoice_id, new_customer_id, new_deposit_amount,
                new_payment_mode, new_payment_info, current_timestamp, deposit_invoice_id
            )
        )
        print(f"Debug: Updated udhaar_deposits record for ID: {deposit_invoice_id}")

        # Step 3: Apply the effect of the new deposit amount to the new linked sale invoice (if any)
        if new_sell_invoice_id:
            udhaar_record = db.fetch_one(
                "SELECT udhaar_id, current_balance FROM udhaar WHERE sell_invoice_id = ? AND customer_id = ?",
                (new_sell_invoice_id, new_customer_id)
            )
            if udhaar_record:
                udhaar_id = udhaar_record[0]
                current_balance = udhaar_record[1]
                # Subtract the new deposit amount from the current balance
                adjusted_balance = current_balance - new_deposit_amount
                status = 'pending' if adjusted_balance > 0 else 'paid'
                db.execute_query(
                    "UPDATE udhaar SET current_balance = ?, status = ?, last_payment_date = ?, updated_at = ? WHERE udhaar_id = ?",
                    (adjusted_balance, status, current_timestamp, udhaar_id)
                )
                print(f"Debug: Applied new deposit for udhaar_id {udhaar_id}. New balance: {adjusted_balance}")
            else:
                print(f"Debug: No udhaar record found for new sell_invoice_id {new_sell_invoice_id} to apply deposit.")
                # If no udhaar record exists for the new linked invoice, it means this deposit is effectively an advance
                # for a future sale or a general deposit, which is fine.

        return True

    except Exception as e:
        print(f"Error updating udhaar deposit {deposit_invoice_id}: {e}")
        return False

