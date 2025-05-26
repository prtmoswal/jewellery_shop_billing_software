import streamlit as st
import sqlite3 # Keep for type hinting if needed, but direct use will be removed
from utils.config import DATABASE_NAME,BILLS_FOLDER
from utils.fetch_customers import get_customer_details_for_update,get_all_customer_names,fetch_all_customers,update_customer,add_new_customer,get_customer_details
from datetime import datetime
import pandas as pd
from utils.invoice_id_creation import generate_udhaar_invoice_id,generate_purchase_invoice_id,generate_sales_invoice_id,get_next_invoice_number
from utils.save_sale import save_sale
from utils.get_pending_udhaar_sale import get_pending_udhaar,get_sale_details
from utils.generate_sell_pdf import generate_sell_pdf
from utils.get_download_link import get_download_link
from utils.load_and_display_pdf import load_and_display_pdf
from utils.fetch_bill_data import fetch_bill_data # Ensure this is imported
from utils.db_manager import DBManager # Import DBManager

def reprint_bill_section():
    # --- Streamlit UI for Reprinting ---
    st.title("Reprint Bill")

    # Initialize DBManager
    db = DBManager(DATABASE_NAME)

    reprint_invoice_id = st.text_input("Enter Invoice ID to Reprint:")
    reprint_button = st.button("Reprint Bill")

    if reprint_button and reprint_invoice_id:
        # fetch_bill_data already uses DBManager internally
        customer_details, sale_data, sale_items = fetch_bill_data(reprint_invoice_id)

        if sale_data:
            pdf_bytes, filename = generate_sell_pdf(customer_details, sale_data, sale_items, download=True)
            st.download_button(
                label="Download Reprinted Bill PDF",
                data=pdf_bytes,
                file_name=filename,
                mime="application/pdf",
                key=f"reprint_download_{reprint_invoice_id}"
            )
            st.success(f"PDF for Invoice ID '{reprint_invoice_id}' generated. Click the button to download.")
        else:
            st.error(f"Bill with Invoice ID '{reprint_invoice_id}' not found.")

    # --- Optional: Dropdown to select Invoice ID ---
    st.subheader("Reprint Bill (Select from List)")
    
    # Use DBManager to fetch invoice IDs
    invoice_ids_raw = db.fetch_all("SELECT invoice_id FROM sales ORDER BY invoice_id DESC")
    invoice_ids = [row[0] for row in invoice_ids_raw] if invoice_ids_raw else []

    if invoice_ids:
        selected_invoice_reprint = st.selectbox("Select Invoice ID to Reprint:", invoice_ids)
        reprint_button_select = st.button("Reprint Selected Bill")

        if reprint_button_select and selected_invoice_reprint:
            # fetch_bill_data already uses DBManager internally
            customer_details, sale_data, sale_items = fetch_bill_data(selected_invoice_reprint)
            if sale_data:
                pdf_bytes, filename = generate_sell_pdf(customer_details, sale_data, sale_items, download=True)
                st.download_button(
                    label=f"Download Reprinted Bill PDF for {selected_invoice_reprint}",
                    data=pdf_bytes,
                    file_name=filename,
                    mime="application/pdf",
                    key=f"reprint_download_select_{selected_invoice_reprint}"
                )
                st.success(f"PDF for Invoice ID '{selected_invoice_reprint}' generated. Click the button to download.")
            else:
                st.error(f"Bill with Invoice ID '{selected_invoice_reprint}' not found.")
    else:
        st.info("No sales invoices found to reprint.")

