import sqlite3
from datetime import datetime
from utils.config import DATABASE_NAME
from utils.db_manager import DBManager
from utils.get_pending_purchase_udhaar import update_purchase_udhaar as update_purchase_udhaar_balance # Avoid name conflict

def update_purchase_bill(
    invoice_id,
    new_supplier_id,
    new_purchase_date,
    new_purchase_items,
    new_payment_mode,
    new_payment_info,
    new_amount_paid,
    new_total_bill_amount
):
    """
    Updates an existing purchase bill in the database.

    Args:
        invoice_id (str): The ID of the purchase invoice to update.
        new_supplier_id (int): The updated supplier ID.
        new_purchase_date (datetime.date): The updated purchase date.
        new_purchase_items (list): List of dictionaries for updated purchase items.
        new_payment_mode (str): The updated payment mode.
        new_payment_info (str): The updated payment other info.
        new_amount_paid (float): The updated amount paid.
        new_total_bill_amount (float): The recalculated total bill amount.

    Returns:
        bool: True if the update was successful, False otherwise.
    """
    db = DBManager(DATABASE_NAME)
    current_timestamp = datetime.now().isoformat()
    purchase_date_iso = new_purchase_date.isoformat()

    try:
        # Fetch original old_gold_amount and amount_balance for adjustment if needed
        # Note: 'purchases' table does not have 'old_gold_amount'. It has amount_balance.
        original_purchase_details = db.fetch_one(
            "SELECT amount_balance FROM purchases WHERE invoice_id = ?",
            (invoice_id,)
        )
        original_balance_amount = original_purchase_details[0] if original_purchase_details else 0.0

        # Calculate new balance amount
        new_balance_amount = new_total_bill_amount - new_amount_paid

        print(f"Debug (update_purchase_bill): Invoice ID: {invoice_id}")
        print(f"Debug (update_purchase_bill): new_total_bill_amount: {new_total_bill_amount}")
        print(f"Debug (update_purchase_bill): new_amount_paid: {new_amount_paid}")
        print(f"Debug (update_purchase_bill): original_balance_amount: {original_balance_amount}")
        print(f"Debug (update_purchase_bill): new_balance_amount: {new_balance_amount}")

        # Update the main purchases record
        db.execute_query(
            """
            UPDATE purchases
            SET supplier_id = ?, purchase_date = ?, total_amount = ?,
                payment_mode = ?, payment_other_info = ?,
                cheque_amount = ?, online_amount = ?, upi_amount = ?, cash_amount = ?,
                amount_balance = ?, updated_at = ?
            WHERE invoice_id = ?
            """,
            (
                new_supplier_id, purchase_date_iso, new_total_bill_amount,
                new_payment_mode, new_payment_info,
                # Assuming new_amount_paid is distributed among these based on new_payment_mode
                # For simplicity, we'll put the whole new_amount_paid into the selected mode.
                # In a real app, you might have separate inputs for each payment type.
                new_amount_paid if new_payment_mode == 'Cheque' else 0.0,
                new_amount_paid if new_payment_mode == 'Online' else 0.0,
                new_amount_paid if new_payment_mode == 'UPI' else 0.0,
                new_amount_paid if new_payment_mode == 'Cash' else 0.0,
                new_balance_amount, current_timestamp, invoice_id
            )
        )
        print(f"Debug: Updated purchases record for invoice {invoice_id}")

        # Delete existing items for this invoice
        db.execute_query("DELETE FROM purchase_items WHERE invoice_id = ?", (invoice_id,))
        print(f"Debug: Deleted old purchase_items for invoice {invoice_id}")

        # Insert new items
        for item in new_purchase_items:
            product_id = item.get('product_id')
            gross_wt = item.get('gross_wt', 0.0)
            loss_wt = item.get('loss_wt', 0.0)
            making_charge = item.get('making_charge', 0.0)
            making_charge_type = item.get('making_charge_type', 'fixed')
            stone_weight = item.get('stone_weight', 0.0)
            stone_charge = item.get('stone_charge', 0.0)
            wastage_percentage = item.get('wastage_percentage', 0.0)
            cgst_rate = item.get('cgst_rate', 1.5)
            sgst_rate = item.get('sgst_rate', 1.5)
            hsn = item.get('hsn', '7113')
            purity = item.get('purity')
            price = item.get('price', 0.0) # Ensure price is handled

            db.execute_query(
                """
                INSERT INTO purchase_items (
                    invoice_id, product_id, metal, qty, net_wt, price, amount,
                    gross_wt, loss_wt, metal_rate, description, purity,
                    cgst_rate, sgst_rate, hsn, making_charge, making_charge_type,
                    stone_weight, stone_charge, wastage_percentage, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    invoice_id, product_id, item['metal'], item['qty'], item['net_wt'], item['price'], item['amount'],
                    gross_wt, loss_wt, item['metal_rate'], item['description'], purity,
                    cgst_rate, sgst_rate, hsn, making_charge, making_charge_type,
                    stone_weight, stone_charge, wastage_percentage, current_timestamp, current_timestamp
                )
            )
        print(f"Debug: Inserted new purchase_items for invoice {invoice_id}")

        # Update or insert into purchase_udhaar table
        if new_balance_amount != 0:
            udhaar_record = db.fetch_one(
                "SELECT udhaar_id, current_balance FROM purchase_udhaar WHERE purchase_invoice_id = ?",
                (invoice_id,)
            )
            if udhaar_record:
                udhaar_id = udhaar_record[0]
                # Update existing udhaar record
                db.execute_query(
                    """
                    UPDATE purchase_udhaar
                    SET current_balance = ?, status = ?, updated_at = ?
                    WHERE udhaar_id = ?
                    """,
                    (
                        new_balance_amount,
                        'pending' if new_balance_amount > 0 else 'paid',
                        current_timestamp,
                        udhaar_id
                    )
                )
                print(f"Debug: Updated purchase_udhaar record {udhaar_id} for invoice {invoice_id}. New pending: {new_balance_amount}")
            else:
                # Insert new udhaar record
                db.execute_query(
                    """
                    INSERT INTO purchase_udhaar (
                        purchase_invoice_id, supplier_id, initial_balance, current_balance, status, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        invoice_id, new_supplier_id, new_balance_amount, new_balance_amount,
                        'pending' if new_balance_amount > 0 else 'paid',
                        current_timestamp, current_timestamp
                    )
                )
                print(f"Debug: Inserted new purchase_udhaar record for invoice {invoice_id}. Balance: {new_balance_amount}")
        else: # If new_balance_amount is 0, ensure udhaar record is removed or set to paid
            db.execute_query(
                "DELETE FROM purchase_udhaar WHERE purchase_invoice_id = ? AND current_balance <= 0",
                (invoice_id,)
            )
            print(f"Debug: Cleared purchase_udhaar record for invoice {invoice_id} as balance is zero.")

        return True

    except Exception as e:
        print(f"Error updating purchase bill {invoice_id}: {e}")
        return False

