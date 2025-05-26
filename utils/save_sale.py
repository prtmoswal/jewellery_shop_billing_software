import streamlit as st
import sqlite3
from datetime import datetime
from utils.config import DATABASE_NAME, BILLS_FOLDER
from utils.get_pending_purchase_udhaar import update_purchase_udhaar
from utils.db_manager import DBManager # Import the new DBManager

def save_sale(invoice_id, customer_id, total_amount, cheque_amount, online_amount, upi_amount, cash_amount, old_gold_amount, amount_balance, payment_mode, payment_other_info, sale_date, sale_items_data, applied_purchase_udhaar=0.0):
    """
    Saves a new sale record and its associated items to the database.
    Also handles inventory updates, creates udhaar records if there's a balance,
    and updates pending purchase amounts if applied.

    Args:
        invoice_id (str): Unique identifier for the sale invoice.
        customer_id (int): ID of the customer.
        total_amount (float): Total amount of the sale.
        cheque_amount (float): Amount paid by cheque.
        online_amount (float): Amount paid online.
        upi_amount (float): Amount paid via UPI.
        cash_amount (float): Amount paid by cash.
        old_gold_amount (float): Value of old gold exchanged.
        amount_balance (float): Remaining balance to be paid.
        payment_mode (str): Primary mode of payment.
        payment_other_info (str): Additional payment details.
        sale_date (str): Date of the sale (e.g., 'YYYY-MM-DD HH:MM:SS').
        sale_items_data (list): A list of dictionaries, each representing a sale item.
                                 Expected keys in each item: 'metal', 'metal_rate',
                                 'description', 'qty', 'net_wt', 'amount', 'purity',
                                 'gross_wt', 'loss_wt', 'making_charge', 'making_charge_type',
                                 'stone_weight', 'stone_charge', 'wastage_percentage',
                                 'product_id', 'cgst_rate', 'sgst_rate', 'hsn'.
                                 Some keys can be optional and will default to 0.0 or None.
        applied_purchase_udhaar (float, optional): Amount of pending purchase udhaar applied to this sale. Defaults to 0.0.

    Returns:
        str: The invoice_id if the sale is saved successfully, None otherwise.
    """
    # Validation
    if not customer_id:
        st.error("Customer is required for sale!")
        return None

    if not sale_items_data:
        st.error("At least one sale item is required!")
        return None

    if total_amount <= 0:
        st.error("Total amount must be greater than zero!")
        return None

    # Validate each item has required fields
    for item in sale_items_data:
        if not all(key in item for key in ['metal', 'metal_rate', 'description', 'qty', 'net_wt', 'amount']):
            st.error("All item details are required (metal, rate, description, quantity, weight, amount)")
            return None

        if item['qty'] <= 0 or item['net_wt'] <= 0 or item['amount'] <= 0:
            st.error("Quantity, weight, and amount must be greater than zero!")
            return None

    db = DBManager(DATABASE_NAME) # Use DBManager

    try:
        current_timestamp = datetime.now().isoformat() # For created_at and updated_at

        # Insert into sales table
        db.execute_query(
            """
            INSERT INTO sales (
                invoice_id, sale_date, customer_id, total_amount,
                cheque_amount, online_amount, upi_amount, cash_amount,
                old_gold_amount, amount_balance, payment_mode, payment_other_info,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                invoice_id, sale_date, customer_id, total_amount,
                cheque_amount, online_amount, upi_amount, cash_amount,
                old_gold_amount, amount_balance, payment_mode, payment_other_info,
                current_timestamp, current_timestamp
            )
        )

        for item in sale_items_data:
            # Extract item details, providing defaults for new fields
            product_id = item.get('product_id') # Can be None if not linked to a product
            gross_wt = item.get('gross_wt', 0.0)
            loss_wt = item.get('loss_wt', 0.0)
            making_charge = item.get('making_charge', 0.0)
            making_charge_type = item.get('making_charge_type', 'fixed') # Default type
            stone_weight = item.get('stone_weight', 0.0)
            stone_charge = item.get('stone_charge', 0.0)
            wastage_percentage = item.get('wastage_percentage', 0.0)
            # Use defaults from table schema if not provided in item data
            cgst_rate = item.get('cgst_rate', 1.5)
            sgst_rate = item.get('sgst_rate', 1.5)
            hsn = item.get('hsn', '7113')
            purity = item.get('purity') # Purity can be None if not applicable or chosen

            # Insert into sale_items table with all new columns
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
                    invoice_id, product_id, item['metal'], item['metal_rate'], item['description'],
                    item['qty'], item['net_wt'], purity, gross_wt, loss_wt,
                    making_charge, making_charge_type, stone_weight, stone_charge,
                    wastage_percentage, item['amount'], cgst_rate, sgst_rate, hsn,
                    current_timestamp, current_timestamp
                )
            )

            # --- Inventory Management: Update product stock and log transaction ---
            if product_id:
                # Update current_stock in products table
                db.execute_query(
                    "UPDATE products SET current_stock = current_stock - ?, updated_at = ? WHERE product_id = ?",
                    (item['qty'], current_timestamp, product_id)
                )

                # Fetch the updated current_stock to log accurately
                new_stock = db.fetch_one("SELECT current_stock FROM products WHERE product_id = ?", (product_id,))[0]

                # Log inventory transaction
                db.execute_query(
                    """
                    INSERT INTO inventory_transactions (
                        product_id, transaction_type, quantity_change,
                        current_stock_after, reference_id, transaction_date, notes, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        product_id, 'sale_out', -item['qty'], new_stock,
                        invoice_id, current_timestamp, f"Sale of {item['qty']} units for invoice {invoice_id}",
                        current_timestamp
                    )
                )

        # Insert into udhaar table if there's a balance
        if amount_balance != 0:
            # Corrected: Use initial_balance and current_balance
            db.execute_query(
                "INSERT INTO udhaar (sell_invoice_id, customer_id, initial_balance, current_balance, status, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (invoice_id, customer_id, amount_balance, amount_balance, 'pending', current_timestamp, current_timestamp)
            )

        # --- Update pending purchase udhaar if applied ---
        if applied_purchase_udhaar > 0:
            print(f"Debug (save_sale): Attempting to apply {applied_purchase_udhaar} from purchase udhaar for customer {customer_id}")
            # Fetch all pending purchase invoices for this supplier/customer
            pending_purchases = db.fetch_all(
                "SELECT udhaar_id, purchase_invoice_id, current_balance FROM purchase_udhaar WHERE supplier_id = ? AND current_balance > 0 ORDER BY created_at ASC",
                (customer_id,)
            )
            print(f"Debug (save_sale): Found pending purchases: {pending_purchases}")

            remaining_to_apply = applied_purchase_udhaar
            for udhaar_id, pur_inv_id, pur_pending_amt in pending_purchases:
                if remaining_to_apply <= 0:
                    break

                amount_to_clear_this_invoice = min(remaining_to_apply, pur_pending_amt)
                print(f"Debug (save_sale): Clearing {amount_to_clear_this_invoice} from purchase invoice {pur_inv_id}")

                # Update the specific purchase udhaar record
                # This will either reduce the current_balance or set to 0 and update status
                update_purchase_udhaar(pur_inv_id, amount_to_clear_this_invoice)

                remaining_to_apply -= amount_to_clear_this_invoice

            if remaining_to_apply > 0:
                st.warning(f"Note: Could not fully apply pending purchase amount. Remaining to apply: {remaining_to_apply:.2f}")


        print(f"Debug (save_sale): All transactions for invoice {invoice_id} processed via DBManager.")
        return invoice_id
    except Exception as e:
        st.error(f"Error saving sale: {str(e)}")
        print(f"Debug (save_sale): Error during save_sale: {e}")
        return None
