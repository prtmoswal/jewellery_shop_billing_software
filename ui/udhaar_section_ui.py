import streamlit as st
import pandas as pd
from datetime import datetime

# Import necessary utility functions
from utils.config import DATABASE_NAME # Only for DBManager, not direct use
from utils.fetch_customers import fetch_all_customers, get_customer_details
from utils.invoice_id_creation import generate_udhaar_invoice_id
from utils.get_pending_udhaar_sale import get_all_pending_udhaar, update_udhaar_balance
from utils.get_pending_purchase_udhaar import get_all_pending_purchase_udhaar, update_purchase_udhaar
from utils.save_udhaar import save_udhaar_deposit
from utils.generate_udhaar_deposit_pdf import generate_udhaar_deposit_pdf
from utils.fetch_bill_data import fetch_bill_data # To get original invoice data for deposit PDF
from utils.get_download_link import get_download_link
from utils.db_manager import DBManager # Import DBManager for direct fetches

def udhaar_section():
    st.subheader("Manage Udhaar Section")
    st.write("Here you can manage pending payments for sales and purchases.")

    # Tabbed interface for Sale Udhaar and Purchase Udhaar
    udhaar_tab, purchase_udhaar_tab, deposit_tab = st.tabs(["Sale Udhaar (Customer Owed)", "Purchase Udhaar (You Owed)", "Record Deposit"])

    with udhaar_tab:
        st.subheader("Customer Pending Sale Amounts")
        pending_sales = get_all_pending_udhaar() # Fetch all pending sales udhaar

        if pending_sales:
            df_pending_sales = pd.DataFrame(pending_sales)
            # Fix: Use format='mixed' to handle various datetime string formats from the database
            df_pending_sales['bill_date'] = pd.to_datetime(df_pending_sales['bill_date'], format='mixed').dt.strftime('%Y-%m-%d')
            st.dataframe(df_pending_sales[['customer_name', 'sell_invoice_id', 'total_bill_amount', 'current_balance', 'bill_date', 'status']])

            st.markdown("---")
            st.subheader("Record Payment for Sale Udhaar")
            selected_udhaar_invoice_id = st.selectbox(
                "Select Sale Invoice ID to Record Payment",
                ["Select Invoice"] + df_pending_sales['sell_invoice_id'].tolist(),
                key="pay_sale_udhaar_invoice_id"
            )

            if selected_udhaar_invoice_id != "Select Invoice":
                # Get the specific udhaar record details from the currently fetched list
                selected_udhaar_record = df_pending_sales[df_pending_sales['sell_invoice_id'] == selected_udhaar_invoice_id].iloc[0]
                
                st.info(f"Customer: {selected_udhaar_record['customer_name']}")
                st.info(f"Current Pending Amount: ₹{selected_udhaar_record['current_balance']:.2f}")

                payment_amount = st.number_input(
                    "Amount Paid by Customer",
                    min_value=0.0,
                    max_value=float(selected_udhaar_record['current_balance']),
                    value=float(selected_udhaar_record['current_balance']),
                    step=100.0,
                    key="sale_udhaar_payment_amount"
                )
                payment_mode = st.selectbox(
                    "Payment Mode",
                    ["Cash", "Online", "Cheque", "UPI", "Other"],
                    key="sale_udhaar_payment_mode"
                )
                payment_info = st.text_input(
                    "Payment Details (e.g., Transaction ID, Cheque No.)",
                    key="sale_udhaar_payment_info"
                )

                if st.button("Record Sale Payment", key="record_sale_udhaar_payment_button"):
                    if payment_amount > 0:
                        udhaar_id_to_update = selected_udhaar_record['udhaar_id']
                        current_balance_check = selected_udhaar_record['current_balance']

                        if current_balance_check > 0: # Check if balance is still positive
                            if update_udhaar_balance(udhaar_id_to_update, payment_amount, payment_mode, payment_info):
                                st.success(f"Payment of ₹{payment_amount:.2f} recorded for Invoice ID {selected_udhaar_invoice_id}.")
                                
                                # --- Reusing generate_udhaar_deposit_pdf for payment receipt ---
                                customer_details_for_pdf = get_customer_details(selected_udhaar_record['customer_id'])
                                
                                # Generate a unique transaction ID for this payment receipt
                                receipt_timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
                                payment_receipt_id = f"PAY-REC-{receipt_timestamp}-{selected_udhaar_record['sell_invoice_id'].replace('/', '_')}"

                                # Construct the deposit_data tuple to fit generate_udhaar_deposit_pdf's expected arguments
                                # (deposit_invoice_id, sell_invoice_id, deposit_date, customer_id, deposit_amount, remaining_amount, payment_mode, payment_other_info)
                                deposit_data_for_pdf = (
                                    payment_receipt_id,                                    # Will appear as "Udhaar Deposit Receipt: [ID]"
                                    selected_udhaar_record['sell_invoice_id'],             # Original Invoice ID
                                    datetime.now().strftime('%Y-%m-%d'),                   # Payment Date
                                    selected_udhaar_record['customer_id'],                 # Customer ID
                                    payment_amount,                                        # Amount Paid
                                    max(0.0, selected_udhaar_record['current_balance'] - payment_amount), # Remaining Balance
                                    payment_mode,                                          # Payment Mode
                                    payment_info                                           # Payment Other Info
                                )

                                # Pass an empty dict for original_invoice_data as it's not used in current generate_udhaar_deposit_pdf display
                                pdf_content, filename = generate_udhaar_deposit_pdf(
                                    customer_details_for_pdf,
                                    deposit_data_for_pdf,
                                    {}, 
                                    download=True
                                )
                                st.markdown(get_download_link(pdf_content, filename), unsafe_allow_html=True)
                                # --- END Reusing ---

                                # Instead of immediate rerun, offer a button to clear/refresh
                                if st.button("Clear Payment Form / Refresh List", key="clear_sale_payment_form_button"):
                                    st.rerun()
                            else:
                                st.error("Failed to record payment. An internal error occurred.")
                        else:
                            st.error(f"Invoice ID '{selected_udhaar_invoice_id}' has no pending balance.")
                            st.rerun() # Rerun to refresh the list of pending invoices
                    else:
                        st.warning("Please enter a valid payment amount.")
        else:
            st.info("No pending sale amounts found.")

    with purchase_udhaar_tab:
        st.subheader("Your Pending Purchase Amounts (You Owe Suppliers)")
        pending_purchases = get_all_pending_purchase_udhaar() # Fetch all pending purchase udhaar

        if pending_purchases:
            df_pending_purchases = pd.DataFrame(pending_purchases)
            # Ensure 'created_at' is parsed as datetime and formatted
            # Fix: Use format='mixed' to handle various datetime string formats from the database
            df_pending_purchases['created_at'] = pd.to_datetime(df_pending_purchases['created_at'], format='mixed').dt.strftime('%Y-%m-%d')
            
            # Fetch supplier names
            all_customers = fetch_all_customers()
            df_pending_purchases['supplier_name'] = df_pending_purchases['supplier_id'].map(all_customers)

            st.dataframe(df_pending_purchases[['supplier_name', 'purchase_invoice_id', 'initial_balance', 'current_balance', 'created_at', 'status']])

            st.markdown("---")
            st.subheader("Record Payment for Purchase Udhaar")
            selected_purchase_invoice_id = st.selectbox(
                "Select Purchase Invoice ID to Record Payment",
                ["Select Invoice"] + df_pending_purchases['purchase_invoice_id'].tolist(),
                key="pay_purchase_udhaar_invoice_id"
            )

            if selected_purchase_invoice_id != "Select Invoice":
                # Get the specific udhaar record details
                selected_purchase_record = df_pending_purchases[df_pending_purchases['purchase_invoice_id'] == selected_purchase_invoice_id].iloc[0]
                
                st.info(f"Supplier: {selected_purchase_record['supplier_name']}")
                st.info(f"Current Pending Amount: ₹{selected_purchase_record['current_balance']:.2f}")

                payment_amount = st.number_input(
                    "Amount Paid to Supplier",
                    min_value=0.0,
                    max_value=float(selected_purchase_record['current_balance']),
                    value=float(selected_purchase_record['current_balance']),
                    step=100.0,
                    key="purchase_udhaar_payment_amount"
                )
                payment_mode = st.selectbox(
                    "Payment Mode",
                    ["Cash", "Online", "Cheque", "UPI", "Other"],
                    key="purchase_udhaar_payment_mode"
                )
                payment_info = st.text_input(
                    "Payment Details (e.g., Transaction ID, Cheque No.)",
                    key="purchase_udhaar_payment_info"
                )

                if st.button("Record Purchase Payment", key="record_purchase_udhaar_payment_button"):
                    if payment_amount > 0:
                        purchase_invoice_id_to_update = selected_purchase_record['purchase_invoice_id']
                        current_balance_check = selected_purchase_record['current_balance']

                        if current_balance_check > 0: # Check if balance is still positive
                            if update_purchase_udhaar(purchase_invoice_id_to_update, payment_amount):
                                st.success(f"Payment of ₹{payment_amount:.2f} recorded for Purchase Invoice ID {selected_purchase_invoice_id}.")
                                # No PDF for purchase payments currently, but can be added similarly
                                if st.button("Clear Payment Form / Refresh List", key="clear_purchase_payment_form_button"):
                                    st.rerun()
                            else:
                                st.error("Failed to record payment. An internal error occurred.")
                        else:
                            st.error(f"Purchase Invoice ID '{selected_purchase_invoice_id}' is no longer pending or does not exist.")
                            st.rerun()
                    else:
                        st.warning("Please enter a valid payment amount.")
        else:
            st.info("No pending purchase amounts found.")

    with deposit_tab:
        st.subheader("Record New Udhaar Deposit (Advance Payment)")
        
        deposit_customers = fetch_all_customers()
        deposit_customer_options = ["Select Customer"] + list(deposit_customers.values())
        selected_deposit_customer_name = st.selectbox("Select Customer for Deposit", deposit_customer_options, key="deposit_customer_select")

        deposit_customer_id = None
        if selected_deposit_customer_name != "Select Customer":
            deposit_customer_id = [k for k, v in deposit_customers.items() if v == selected_deposit_customer_name][0]
            st.info(f"Selected Customer: {selected_deposit_customer_name}")

            # Option to link to an existing pending sale invoice
            pending_sales_for_deposit_customer = [
                s for s in get_all_pending_udhaar() if s['customer_id'] == deposit_customer_id
            ]
            
            linked_invoice_options = ["(No specific invoice - General Deposit)"] + [
                f"{s['sell_invoice_id']} (Balance: ₹{s['current_balance']:.2f})" for s in pending_sales_for_deposit_customer
            ]
            selected_linked_invoice = st.selectbox(
                "Link Deposit to Pending Sale Invoice (Optional)",
                linked_invoice_options,
                key="deposit_link_invoice"
            )
            
            deposit_linked_sell_invoice_id = None
            if selected_linked_invoice != "(No specific invoice - General Deposit)":
                deposit_linked_sell_invoice_id = selected_linked_invoice.split(' ')[0] # Extract invoice ID

            # --- Option to link to an existing pending purchase invoice ---
            db_manager = DBManager(DATABASE_NAME)
            pending_purchases_for_deposit_customer_raw = db_manager.fetch_all(
                "SELECT purchase_invoice_id, current_balance FROM purchase_udhaar WHERE supplier_id = ? AND current_balance > 0",
                (deposit_customer_id,)
            )
            pending_purchases_for_deposit_customer = [
                {'purchase_invoice_id': row[0], 'current_balance': row[1]} for row in pending_purchases_for_deposit_customer_raw
            ]

            linked_purchase_invoice_options = ["(No specific purchase invoice - General Deposit)"] + [
                f"{p['purchase_invoice_id']} (Balance: ₹{p['current_balance']:.2f})" for p in pending_purchases_for_deposit_customer
            ]
            selected_linked_purchase_invoice = st.selectbox(
                "Link Deposit to Pending Purchase Invoice (Optional)",
                linked_purchase_invoice_options,
                key="deposit_link_purchase_invoice"
            )

            deposit_linked_purchase_invoice_id = None
            if selected_linked_purchase_invoice != "(No specific purchase invoice - General Deposit)":
                deposit_linked_purchase_invoice_id = selected_linked_purchase_invoice.split(' ')[0] # Extract invoice ID
            # --- End Option ---

            deposit_amount = st.number_input("Deposit Amount", min_value=0.0, step=100.0, key="deposit_amount_input")
            deposit_payment_mode = st.selectbox("Payment Mode", ["Cash", "Online", "Cheque", "UPI", "Other"], key="deposit_payment_mode")
            deposit_payment_info = st.text_input("Payment Details (e.g., Transaction ID, Cheque No.)", key="deposit_payment_info")

            if st.button("Record Deposit", key="record_deposit_button"):
                if deposit_customer_id and deposit_amount > 0:
                    deposit_invoice_id = generate_udhaar_invoice_id(deposit_customer_id) # Use udhaar invoice ID for deposits
                    
                    # Call save_udhaar_deposit and check its return value
                    saved_deposit_id = save_udhaar_deposit(
                        deposit_invoice_id,
                        deposit_linked_sell_invoice_id, # Can be None for general deposit
                        deposit_customer_id,
                        deposit_amount,
                        deposit_payment_mode,
                        deposit_payment_info,
                        linked_purchase_invoice_id=deposit_linked_purchase_invoice_id # Pass the new parameter
                    )

                    if saved_deposit_id: # Check if saving was successful
                        st.success(f"Deposit recorded successfully with ID: {saved_deposit_id}")
                        
                        # Fetch customer details for PDF
                        customer_details_for_pdf = get_customer_details(deposit_customer_id)
                        
                        # A simple mock for deposit_data based on save_udhaar_deposit inputs:
                        deposit_data_for_pdf = (
                            saved_deposit_id, # Use the actual saved ID
                            deposit_linked_sell_invoice_id, # sell_invoice_id
                            datetime.now().strftime('%Y-%m-%d'), # deposit_date (approx)
                            deposit_customer_id, # customer_id
                            deposit_amount, # deposit_amount
                            None, # remaining_amount (not stored in udhaar_deposits directly)
                            deposit_payment_mode, # payment_mode
                            deposit_payment_info # payment_other_info
                        )
                        
                        # original_invoice_data is not directly available here, pass empty dict
                        pdf_content, filename = generate_udhaar_deposit_pdf(
                            customer_details_for_pdf,
                            deposit_data_for_pdf,
                            {}, # Pass empty dict for original_invoice_data if not available
                            download=True
                        )
                        st.markdown(get_download_link(pdf_content, filename), unsafe_allow_html=True)
                        
                        # Add a button to clear/refresh the form after successful deposit
                        if st.button("Clear Deposit Form / Refresh List", key="clear_deposit_form_button"):
                            st.rerun()
                    else:
                        st.error("Failed to record deposit. Please check inputs and try again.")
                else:
                    st.error("Please select a customer and enter a valid deposit amount.")
        else:
            st.info("Please select a customer to record a deposit.")

