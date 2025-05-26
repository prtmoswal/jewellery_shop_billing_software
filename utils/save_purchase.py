import sqlite3
from datetime import datetime
import json # Import the json library for deserialization
from utils.config import DATABASE_NAME
from utils.db_manager import DBManager

def save_purchase(invoice_id, supplier_id, total_amount, cheque_amount, online_amount, upi_amount, cash_amount, payment_mode, payment_other_info, purchase_date, purchase_items_json, amount_balance):
    """
    Saves purchase details and associated items to the database.

    Args:
        invoice_id (str): Unique identifier for the purchase invoice.
        supplier_id (int): ID of the supplier (customer_id from customers table).
        total_amount (float): The total taxable amount of the purchase.
        cheque_amount (float): Amount paid by cheque.
        online_amount (float): Amount paid online.
        upi_amount (float): Amount paid via UPI.
        cash_amount (float): Amount paid by cash.
        payment_mode (str): Overall payment mode (e.g., "Cash", "Mixed").
        payment_other_info (str): Additional payment details (e.g., transaction IDs).
        purchase_date (str): The date of the purchase in ISO format.
        purchase_items_json (str): JSON string representation of the list of purchase items.
        amount_balance (float): The balance amount remaining for this purchase.

    Returns:
        str: The invoice_id if the save is successful, None otherwise.
    """
    db = DBManager(DATABASE_NAME)

    try:
        current_timestamp = datetime.now().isoformat()

        # Deserialize the purchase_items_json back to a list of dictionaries
        purchase_items = json.loads(purchase_items_json)

        # Save purchase details to the 'purchases' table
        db.execute_query(
            '''
            INSERT INTO purchases (invoice_id, purchase_date, supplier_id, total_amount,
                                   payment_mode, payment_other_info, cheque_amount, online_amount,
                                   upi_amount, cash_amount, amount_balance, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''',
            (invoice_id, purchase_date, supplier_id, total_amount,
             payment_mode, payment_other_info, cheque_amount, online_amount,
             upi_amount, cash_amount, amount_balance, current_timestamp, current_timestamp)
        )

        # Save each purchase item to the 'purchase_items' table
        for item in purchase_items:
            db.execute_query(
                '''
                INSERT INTO purchase_items (invoice_id, metal, qty, net_wt, price, amount,
                                            gross_wt, loss_wt, metal_rate, description, purity,
                                            cgst_rate, sgst_rate, hsn, making_charge,
                                            making_charge_type, stone_weight, stone_charge,
                                            wastage_percentage, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''',
                (invoice_id, item['metal'], item['qty'], item['net_wt'], item['price'], item['amount'],
                 item['gross_wt'], item['loss_wt'], item['metal_rate'], item['description'], item['purity'],
                 item['cgst_rate'], item['sgst_rate'], item['hsn'], item['making_charge'],
                 item['making_charge_type'], item['stone_weight'], item['stone_charge'],
                 item['wastage_percentage'], current_timestamp, current_timestamp)
            )

        # If there's a balance remaining, save it to the purchase_udhaar table
        if amount_balance > 0:
            # Check if an entry for this purchase invoice already exists in purchase_udhaar
            existing_udhaar_entry = db.fetch_one('SELECT udhaar_id, current_balance FROM purchase_udhaar WHERE purchase_invoice_id = ?', (invoice_id,))

            udhaar_id_for_transaction = None
            if existing_udhaar_entry:
                # If an entry exists, update its current_balance
                udhaar_id = existing_udhaar_entry[0]
                # Add the new amount_balance to the existing current_balance
                updated_balance = existing_udhaar_entry[1] + amount_balance
                db.execute_query(
                    '''
                    UPDATE purchase_udhaar
                    SET current_balance = ?, updated_at = ?
                    WHERE udhaar_id = ?
                    ''',
                    (updated_balance, current_timestamp, udhaar_id)
                )
                udhaar_id_for_transaction = udhaar_id
            else:
                # If no entry exists, create a new one
                db.execute_query(
                    '''
                    INSERT INTO purchase_udhaar (purchase_invoice_id, supplier_id, initial_balance, current_balance, status, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    ''',
                    (invoice_id, supplier_id, amount_balance, amount_balance, 'pending', current_timestamp, current_timestamp)
                )
                # Fetch the udhaar_id of the newly inserted record for the transaction log
                new_udhaar_id_result = db.fetch_one('SELECT udhaar_id FROM purchase_udhaar WHERE purchase_invoice_id = ?', (invoice_id,))
                if new_udhaar_id_result:
                    udhaar_id_for_transaction = new_udhaar_id_result[0]
                else:
                    print(f"Warning: Could not retrieve udhaar_id for new purchase udhaar {invoice_id}")


            # Record the transaction in purchase_udhaar_transactions
            if udhaar_id_for_transaction:
                db.execute_query(
                    '''
                    INSERT INTO purchase_udhaar_transactions (udhaar_id, payment_date, amount_paid, payment_mode, transaction_info)
                    VALUES (?, ?, ?, ?, ?)
                    ''',
                    (udhaar_id_for_transaction, current_timestamp, 0, 'N/A', 'Initial Balance/Balance Added')
                )
            else:
                print(f"Error: Could not log purchase udhaar transaction for {invoice_id} as udhaar_id was not found.")

        return invoice_id
    except Exception as e:
        # Print error to console for debugging, don't use st.error here
        print(f"Error saving purchase: {e}")
        return None
    finally:
        pass # DBManager handles connection closing
