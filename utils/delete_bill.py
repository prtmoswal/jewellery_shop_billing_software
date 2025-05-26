import sqlite3
import streamlit as st
import os
from utils.config import DATABASE_NAME, BILLS_FOLDER
from utils.db_manager import DBManager
from datetime import datetime # Import datetime for timestamp comparison
from utils.delete_udhaar_deposit import delete_udhaar_deposit_and_reverse # NEW: Import the specific deposit deletion/reversal function

def delete_bill(invoice_id):
    """
    Deletes a bill (sale, purchase, or deposit) from the database and its associated records.
    Deletion is restricted to only the latest bill recorded across sales, purchases, and deposits.
    If the latest bill is deleted, its invoice ID is made available for reuse.
    """
    if not invoice_id:
        st.error("Invoice ID is required for deletion!")
        return

    db = DBManager(DATABASE_NAME) # Instantiate DBManager

    try:
        # --- Check if the provided invoice_id is the latest bill ---
        # Get the latest sale invoice ID based on created_at
        latest_sale_invoice_data = db.fetch_one("SELECT invoice_id FROM sales ORDER BY created_at DESC LIMIT 1")
        latest_sale_invoice_id = latest_sale_invoice_data[0] if latest_sale_invoice_data else None

        # Get the latest purchase invoice ID based on created_at
        latest_purchase_invoice_data = db.fetch_one("SELECT invoice_id FROM purchases ORDER BY created_at DESC LIMIT 1")
        latest_purchase_invoice_id = latest_purchase_invoice_data[0] if latest_purchase_invoice_data else None

        # Get the latest deposit invoice ID based on created_at
        latest_deposit_invoice_data = db.fetch_one("SELECT deposit_invoice_id, customer_id FROM udhaar_deposits ORDER BY created_at DESC LIMIT 1")
        latest_deposit_invoice_id = latest_deposit_invoice_data[0] if latest_deposit_invoice_data else None
        latest_deposit_customer_id = latest_deposit_invoice_data[1] if latest_deposit_invoice_data else None


        is_latest_bill = False
        bill_type = None # To identify which type of bill was deleted
        
        if invoice_id == latest_sale_invoice_id:
            is_latest_bill = True
            bill_type = 'sale'
        elif invoice_id == latest_purchase_invoice_id:
            is_latest_bill = True
            bill_type = 'purchase'
        elif invoice_id == latest_deposit_invoice_id:
            is_latest_bill = True
            bill_type = 'deposit'

        if not is_latest_bill:
            st.error(f"Deletion restricted: Only the latest bill (sale, purchase, or deposit) can be deleted at this time. The latest invoice IDs are: Sale: {latest_sale_invoice_id or 'N/A'}, Purchase: {latest_purchase_invoice_id or 'N/A'}, Deposit: {latest_deposit_invoice_id or 'N/A'}")
            return
        # --- END Check for latest bill ---

        # First, check if the bill exists in any of the primary tables
        sale_exists = db.fetch_one("SELECT invoice_id FROM sales WHERE invoice_id = ?", (invoice_id,))
        purchase_exists = db.fetch_one("SELECT invoice_id FROM purchases WHERE invoice_id = ?", (invoice_id,))
        deposit_exists = db.fetch_one("SELECT deposit_invoice_id FROM udhaar_deposits WHERE deposit_invoice_id = ?", (invoice_id,))

        if not sale_exists and not purchase_exists and not deposit_exists:
            st.error(f"Bill with Invoice ID '{invoice_id}' not found.")
            return

        deletion_successful = False
        
        # Delete from sales and related tables
        if sale_exists:
            db.execute_query("DELETE FROM sales WHERE invoice_id = ?", (invoice_id,))
            st.success(f"Sale bill with Invoice ID '{invoice_id}' and associated records deleted successfully.")
            deletion_successful = True
            # Decrement invoice number for reuse
            db.execute_query("UPDATE invoice_numbers SET invoice_number = invoice_number - 1 WHERE prefix = ?", ('SALES',))
            print(f"Debug: Decremented SALES invoice number.")
            
        # Delete from purchases and related tables
        elif purchase_exists: # Use elif to ensure only one type of bill is deleted per call
            db.execute_query("DELETE FROM purchases WHERE invoice_id = ?", (invoice_id,))
            st.success(f"Purchase bill with Invoice ID '{invoice_id}' and associated records deleted successfully.")
            deletion_successful = True
            # Decrement invoice number for reuse
            db.execute_query("UPDATE invoice_numbers SET invoice_number = invoice_number - 1 WHERE prefix = ?", ('PURCHASE',))
            print(f"Debug: Decremented PURCHASE invoice number.")

        # Delete from udhaar_deposits and reverse effects
        elif deposit_exists: # Use elif
            if delete_udhaar_deposit_and_reverse(invoice_id):
                st.success(f"Deposit record with Invoice ID '{invoice_id}' deleted and associated balances reversed successfully.")
                deletion_successful = True
                # Decrement invoice number for reuse (requires customer_id for prefix)
                if latest_deposit_customer_id: # Use the customer_id fetched earlier for the latest deposit
                    db.execute_query("UPDATE invoice_numbers SET invoice_number = invoice_number - 1 WHERE prefix = ?", (f'UDHAAR-{latest_deposit_customer_id}',))
                    print(f"Debug: Decremented UDHAAR invoice number for customer {latest_deposit_customer_id}.")
                else:
                    print(f"Warning: Could not decrement UDHAAR invoice number for {invoice_id} as customer_id was not found.")
            else:
                st.error(f"Error deleting deposit record with Invoice ID '{invoice_id}' or reversing its effects. Check logs.")
                # Deletion_successful remains False

        if deletion_successful:
            st.rerun() # Rerun to reflect changes in UI (e.g., updated pending amounts, cleared forms)

    except Exception as e:
        st.error(f"Error deleting bill: {str(e)}")
        print(f"Debug: Error in delete_bill: {e}")
