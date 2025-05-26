import streamlit as st
import pandas as pd
import sqlite3
import os
import base64
from datetime import datetime
import io

# Import necessary functions and constants from utils
# Removed daily_bills_folder from import as it's not a direct export
from utils.config import DATABASE_NAME, BILLS_FOLDER, create_bills_directory, create_tables 
from utils.fetch_customers import get_customer_details_for_update, get_all_customer_names, fetch_all_customers, update_customer, add_new_customer, get_customer_details
from utils.invoice_id_creation import generate_udhaar_invoice_id, generate_purchase_invoice_id, generate_sales_invoice_id, get_next_invoice_number
from utils.save_sale import save_sale
from utils.get_pending_udhaar_sale import get_pending_udhaar, get_all_pending_udhaar, get_sale_details, update_udhaar_balance
from utils.generate_sell_pdf import generate_sell_pdf
from utils.get_download_link import get_download_link
from utils.load_and_display_pdf import load_and_display_pdf
from utils.save_purchase import save_purchase
from utils.generate_purchase_pdf import generate_purchase_pdf
from utils.get_pending_purchase_udhaar import get_pending_purchase_udhaar, get_all_pending_purchase_udhaar, update_purchase_udhaar
from utils.save_udhaar import save_udhaar_deposit
from utils.delete_bill import delete_bill
#from utils.delete_udhaar_bill import delete_udhaar_bill
from utils.fetch_bill_data import fetch_bill_data
from utils.db_manager import DBManager # Ensure DBManager is imported

# Import UI sections
from ui.sell_section_ui import sell_section
from ui.purchase_section_ui import purchase_section
from ui.udhaar_section_ui import udhaar_section
from ui.delete_bill_section import delete_bill_section
from ui.reprint_section import reprint_bill_section
from ui.customer_management_ui import customer_management
from ui.reports_section import reports_section
from ui.login_page import login_page
from ui.modify_bill_section import modify_bill_section # NEW IMPORT

# --- Page Configuration ---
st.set_page_config(
    page_title="Jewellery Shop Management",
    page_icon="💎",
    layout="wide",
    initial_sidebar_state="expanded",
)

# --- Initialize Database (Crucial: Call create_tables at the very beginning) ---
create_tables()


# --- Main App ---
def main():
    st.title("Jewellery Shop Management System")
    
    # Sidebar menu
    st.sidebar.title("Navigation")
    menu = st.sidebar.radio("Select Option", [
        "Sell Jewellery", 
        "Purchase Jewellery", 
        "Udhaar Management", 
        "Delete Bill",
        "Reprint Bill",
        "Customer Management",
        "Reports & Analytics",
        "Modify Bills"
    ])
    
    # Display appropriate section based on menu selection
    if menu == "Sell Jewellery":
        sell_section()
    elif menu == "Purchase Jewellery":
        purchase_section()
    elif menu == "Udhaar Management":
        udhaar_section()
    elif menu == "Delete Bill":
        delete_bill_section()
    elif menu == "Reprint Bill":
        reprint_bill_section()    
    elif menu == "Customer Management":
        customer_management()
    elif menu == "Reports & Analytics":
        reports_section()
    elif menu == "Modify Bills": # NEW OPTION
        modify_bill_section() 

    
    # Copyright information in the sidebar (Recommended)
    st.sidebar.markdown("""
    ---
    © 2025 Preetam Oswal <br>
    Contact: 7387682502 <br>
    Email: prtmoswal@gmail.com
    """, unsafe_allow_html=True)
    
    if st.sidebar.button("Logout", key="logout_button"):
        st.session_state.logged_in = False
        del st.session_state.username # Clear username from session
        st.rerun() # Rerun to show login page
    # Removed the extra </div> tag here, as it's not needed and can cause issues.
    # st.markdown('</div>', unsafe_allow_html=True) # This line was removed


# --- Main Application Logic ---
if __name__ == "__main__":
    # Initialize session state variables if they don't exist
    if 'logged_in' not in st.session_state:
        st.session_state.logged_in = False
    if 'username' not in st.session_state:
        st.session_state.username = None

    if st.session_state.logged_in:
        main()
    else:
        login_page()
