import sqlite3
from datetime import datetime
from utils.db_manager import DBManager
from utils.config import DATABASE_NAME

def update_sale_bill(
    invoice_id,
    new_customer_id,
    new_sale_date, # This will be a date object from st.date_input
    new_items, # List of dictionaries: [{"item_name": "...", "quantity": ..., "weight": ..., "rate": ..., "amount": ...}]
    new_payment_mode,
    new_payment_info,
    new_amount_paid,
    new_total_bill_amount # Calculated from UI
):
    """
    Updates an existing sale bill and its associated records in the database.
    Handles recalculation of udhaar balances if the total bill amount or amount paid changes.
    """
    db = DBManager(DATABASE_NAME)

    try:
        current_timestamp = datetime.now().isoformat()
        sale_date_str = new_sale_date.strftime('%Y-%m-%d %H:%M:%S') # Format date object for DB

        # 1. Fetch current sale details to determine old udhaar implications
        # We need the original total_amount and amount_paid to adjust udhaar correctly
        old_sale_details = db.fetch_one(
            "SELECT total_amount, cheque_amount, online_amount, upi_amount, cash_amount, old_gold_amount, amount_balance FROM sales WHERE invoice_id = ?",
            (invoice_id,)
        )

        if not old_sale_details:
            print(f"Error: Sale Invoice '{invoice_id}' not found for update.")
            return False

        # Unpack old payment details to calculate old_total_paid
        old_total_amount, old_cheque, old_online, old_upi, old_cash, old_old_gold, old_amount_balance = old_sale_details
        old_total_paid = old_cheque + old_online + old_upi + old_cash + old_old_gold

        # 2. Update the main 'sales' table
        new_cheque_amount = 0.0
        new_online_amount = 0.0
        new_upi_amount = 0.0
        new_cash_amount = 0.0
        
        # --- CHANGE MADE HERE ---
        # Ensure original_old_gold_amount is always a float, defaulting to 0.0 if None
        original_old_gold_amount_raw = db.fetch_one("SELECT old_gold_amount FROM sales WHERE invoice_id = ?", (invoice_id,))[0]
        original_old_gold_amount = float(original_old_gold_amount_raw) if original_old_gold_amount_raw is not None else 0.0
        # --- END CHANGE ---

        if new_payment_mode == "Cash":
            new_cash_amount = new_amount_paid
        elif new_payment_mode == "Online":
            new_online_amount = new_amount_paid
        elif new_payment_mode == "Cheque":
            new_cheque_amount = new_amount_paid
        elif new_payment_mode == "UPI":
            new_upi_amount = new_amount_paid
        # 'Other' payment mode will default to cash for simplicity if no specific breakdown is provided in UI
        else:
            new_cash_amount = new_amount_paid

        # Recalculate amount_balance based on new total and new payments
        new_balance_amount = new_total_bill_amount - (new_cheque_amount + new_online_amount + new_upi_amount + new_cash_amount + original_old_gold_amount)

        # --- DEBUG PRINT ---
        print(f"Debug (update_sale_bill): Invoice ID: {invoice_id}")
        print(f"Debug (update_sale_bill): new_total_bill_amount: {new_total_bill_amount}")
        print(f"Debug (update_sale_bill): new_amount_paid: {new_amount_paid}")
        print(f"Debug (update_sale_bill): original_old_gold_amount: {original_old_gold_amount}")
        print(f"Debug (update_sale_bill): new_balance_amount: {new_balance_amount}")
        # --- END DEBUG PRINT ---

        db.execute_query(
            """
            UPDATE sales SET
                customer_id = ?,
                total_amount = ?,
                cheque_amount = ?,
                online_amount = ?,
                upi_amount = ?,
                cash_amount = ?,
                old_gold_amount = ?,
                amount_balance = ?,
                payment_mode = ?,
                payment_other_info = ?,
                sale_date = ?,
                updated_at = ?
            WHERE invoice_id = ?
            """,
            (
                new_customer_id,
                new_total_bill_amount,
                new_cheque_amount,
                new_online_amount,
                new_upi_amount,
                new_cash_amount,
                original_old_gold_amount, # Use the original old_gold_amount for now
                new_balance_amount,
                new_payment_mode,
                new_payment_info,
                sale_date_str,
                current_timestamp,
                invoice_id
            )
        )
        print(f"Debug: Updated sales record for invoice {invoice_id}")

        # 3. Delete old sale items and insert new ones
        db.execute_query("DELETE FROM sale_items WHERE invoice_id = ?", (invoice_id,))
        print(f"Debug: Deleted old sale_items for invoice {invoice_id}")

        for item in new_items:
            # Extract item details, providing defaults for new fields
            product_id = item.get('product_id') # Can be None if not linked to a product
            gross_wt = item.get('gross_wt', 0.0)
            loss_wt = item.get('loss_wt', 0.0)
            making_charge = item.get('making_charge', 0.0)
            making_charge_type = item.get('making_charge_type', 'fixed') # Default type
            stone_weight = item.get('stone_weight', 0.0)
            stone_charge = item.get('stone_charge', 0.0)
            wastage_percentage = item.get('wastage_percentage', 0.0)
            cgst_rate = item.get('cgst_rate', 1.5)
            sgst_rate = item.get('sgst_rate', 1.5)
            hsn = item.get('hsn', '7113')
            purity = item.get('purity') # Purity can be None if not applicable or chosen

            db.execute_query(
                """
                INSERT INTO sale_items (
                    invoice_id, product_id, metal, metal_rate, description, qty, net_wt,
                    purity, gross_wt, loss_wt, making_charge, making_charge_type,
                    stone_weight, stone_charge, wastage_percentage, amount,
                    cgst_rate, sgst_rate, hsn, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    invoice_id, product_id, item['metal'], item['metal_rate'], item['item_name'], # item_name from UI maps to description
                    item['qty'], item['net_wt'], purity, gross_wt, loss_wt,
                    making_charge, making_charge_type, stone_weight, stone_charge,
                    wastage_percentage, item['amount'], cgst_rate, sgst_rate, hsn,
                    current_timestamp, current_timestamp
                )
            )
        print(f"Debug: Inserted new sale_items for invoice {invoice_id}")

        # 4. Adjust the 'udhaar' balance (if applicable)
        # The new pending amount is derived from the updated bill's total and new payments
        # We need to consider all payments (cash, online, cheque, upi, old_gold)
        new_total_paid_for_udhaar_calc = new_cheque_amount + new_online_amount + new_upi_amount + new_cash_amount + original_old_gold_amount
        calculated_new_pending_for_udhaar = new_total_bill_amount - new_total_paid_for_udhaar_calc

        udhaar_record = db.fetch_one(
            "SELECT udhaar_id FROM udhaar WHERE sell_invoice_id = ?",
            (invoice_id,)
        )

        if udhaar_record:
            udhaar_id = udhaar_record[0]
            
            new_status = 'pending'
            if calculated_new_pending_for_udhaar <= 0:
                new_status = 'paid'
            elif calculated_new_pending_for_udhaar < new_total_bill_amount - new_total_paid_for_udhaar_calc: # Partial payment
                new_status = 'partially_paid'

            db.execute_query(
                """
                UPDATE udhaar SET
                    customer_id = ?,
                    initial_balance = ?, -- This is the original full pending amount
                    current_balance = ?,
                    status = ?,
                    updated_at = ?
                WHERE udhaar_id = ?
                """,
                (
                    new_customer_id, # Update customer ID in udhaar if changed
                    calculated_new_pending_for_udhaar, # Initial udhaar amount for this bill
                    calculated_new_pending_for_udhaar,
                    new_status,
                    current_timestamp,
                    udhaar_id
                )
            )
            print(f"Debug: Updated udhaar record {udhaar_id} for invoice {invoice_id}. New pending: {calculated_new_pending_for_udhaar}")

        elif calculated_new_pending_for_udhaar > 0:
            # If no udhaar record existed but there's a new pending amount, create one
            db.execute_query(
                """
                INSERT INTO udhaar (sell_invoice_id, customer_id, initial_balance, current_balance, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    invoice_id,
                    new_customer_id,
                    calculated_new_pending_for_udhaar, # Initial balance from the modified bill
                    calculated_new_pending_for_udhaar,
                    'pending',
                    current_timestamp, # Or original created_at if available
                    current_timestamp
                )
            )
            print(f"Debug: Created new udhaar record for invoice {invoice_id}. Pending: {calculated_new_pending_for_udhaar}")
        else:
            print(f"Debug: No udhaar record to update/create for invoice {invoice_id} as new pending is {calculated_new_pending_for_udhaar}")


        return True

    except Exception as e:
        print(f"Error updating sale bill {invoice_id}: {e}")
        return False
