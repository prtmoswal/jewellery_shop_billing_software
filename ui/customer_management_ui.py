import streamlit as st
import sqlite3
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

def customer_management():
    st.header("Customer Management")
    
    # Customer list
    customers = fetch_all_customers()
    
    tab1, tab2,tab3 = st.tabs(["View/Search Customers", "Add New Customer","Update Customers"])
    
    with tab1:
        # Search by name
        search_name = st.text_input("Search Customer by Name")
        
        if search_name:
            filtered_customers = {k: v for k, v in customers.items() if search_name.lower() in v.lower()}
        else:
            filtered_customers = customers
        
        if filtered_customers:
            customer_ids = list(filtered_customers.keys())
            customer_names = list(filtered_customers.values())
            
            # Create a DataFrame for display
            customers_df = pd.DataFrame({
                "ID": customer_ids,
                "Name": customer_names
            })
            
            st.dataframe(customers_df.head(5))
            
            # Select customer to view details
            selected_customer = st.selectbox("Select Customer to View Details", ["Select Customer"] + customer_names)
            
            if selected_customer != "Select Customer":
                selected_id = [k for k, v in filtered_customers.items() if v == selected_customer][0]
                customer_details = get_customer_details(selected_id)
                
                # Display customer details
                st.subheader(f"Details for {selected_customer}")
                col1,col2,col3=st.columns(3)
                col1.write(f"**Name:** {customer_details.get('name', 'N/A')}")
                col2.write(f"**Phone:** {customer_details.get('phone', 'N/A')}")
                col3.write(f"**Address:** {customer_details.get('address', 'N/A')}")
                if customer_details.get('pan','N/A'):
                     col1.write(f"**PAN:** {customer_details.get('pan')}")
                if customer_details.get('aadhaar'):
                     col2.write(f"**Aadhaar:** {customer_details.get('aadhaar')}")
                if customer_details.get('alternate_phone'):
                     col3.write(f"**Contact Phone:** {customer_details.get('alternate_phone')}")
                if customer_details.get('alternate_phone2'):
                     col1.write(f"**Alternate Phone:** {customer_details.get('alternate_phone2')}")
                if customer_details.get('landline_phone'):
                     col2.write(f"**Landline Number:** {customer_details.get('landline_phone')}")
                
                
                # Get customer transactions
                conn = sqlite3.connect(DATABASE_NAME)
                cursor = conn.cursor()
                
                # Get sales
                cursor.execute("""
                    SELECT invoice_id, sale_date, total_amount, old_gold_amount, amount_balance 
                    FROM sales 
                    WHERE customer_id = ? 
                    ORDER BY sale_date DESC
                """, (selected_id,))
                sales = cursor.fetchall()
                
                # Get purchases
                cursor.execute("""
                    SELECT invoice_id, purchase_date, total_amount 
                    FROM purchases 
                    WHERE supplier_id = ? 
                    ORDER BY purchase_date DESC
                """, (selected_id,))
                purchases = cursor.fetchall()
                # Get deposits
                cursor.execute("""
                    SELECT deposit_invoice_id , sell_invoice_id , deposit_amount 
                    FROM udhaar_deposits 
                    WHERE customer_id = ? 
                    
                """, (selected_id,))
                deposits = cursor.fetchall()
                
                conn.close()
                
                # Display transactions
                if sales:
                    st.subheader("Sales Transactions")
                    sales_df = pd.DataFrame(sales, columns=["Invoice ID", "Date", "Total Amount", "Old Gold Amount", "Balance"])
                    st.dataframe(sales_df)
                
                if purchases:
                    st.subheader("Purchase Transactions")
                    purchases_df = pd.DataFrame(purchases, columns=["Invoice ID", "Date", "Total Amount"])
                    st.dataframe(purchases_df)
                    
                if deposits:
                    st.subheader("Udhaar Deposits Transactions")
                    deposits_df = pd.DataFrame(deposits, columns=["Deposit Invoice ID", "Sell Invoice ID", "Deposit Amount"])
                    st.dataframe(purchases_df)
                
                # Get pending udhaar
                pending_df = get_pending_udhaar(selected_id)
                if not pending_df>0:
                    st.subheader("Pending Amounts")
                    st.dataframe(pending_df)
        else:
            st.info("No customers found with that name.")
    
    with tab2:
        # New customer form
        col1,col2,col3=st.columns(3)
        name = col1.text_input("Customer Name", key="new_cust_name")
        phone = col1.text_input("Phone Number", key="new_cust_phone")
        address = col1.text_input("Address", key="new_cust_address")
        pan = col2.text_input("PAN (Optional)", key="new_cust_pan")
        aadhaar = col2.text_input("Aadhaar (Optional)", key="new_cust_aadhaar")
        alternate_phone = col2.text_input("Alternate Contact", key="alternate_contact")
        alternate_phone2 = col3.text_input("Alternate Contact 2", key="alternate_contact2")
        landline_phone = col3.text_input("Landline Phone", key="landline_phone")
        
        if st.button("Add Customer", key="add_new_cust_btn"):
            if name and phone:
                customer_id = add_new_customer(name, phone, address, pan, aadhaar,alternate_phone,alternate_phone2, landline_phone)
                if customer_id:
                    # Clear form
                    st.session_state.new_cust_name = ""
                    st.session_state.new_cust_phone = ""
                    st.session_state.new_cust_address = ""
                    st.session_state.new_cust_pan = ""
                    st.session_state.new_cust_aadhaar = ""
                    st.session_state.alternate_phone = ""
                    st.session_state.alternate_phone2 = ""
                    st.session_state.landline_phone = ""
                    st.rerun()
            else:
                st.error("Customer name and phone number are required!")
    
    with tab3:
        all_names = get_all_customer_names()
        selected_name = st.selectbox("Select Customer by Name", ["Select Customer"] + all_names)

        customer_details = None
        if selected_name:
            customer_details = get_customer_details_for_update(selected_name)
        name = ""
        phone = ""
        address = ""
        pan = ""
        aadhaar = ""
        alternate_phone=""
        alternate_phone2=""
        landline_phone=""
            
        #box=st.selectbox("abc",customer_details.get("name",""),key="update_cust_name")
        
        if customer_details:
            col1,col2,col3=st.columns(3)
            name = col1.text_input("Customer Name", value=customer_details.get("name", ""), key="update_cust_name")
            phone = col1.text_input("Phone Number", value=customer_details.get("phone", ""), key="update_cust_phone", disabled=True) # Disable phone for editing
            address = col1.text_input("Address", value=customer_details.get("address", ""), key="update_cust_address")
            pan = col2.text_input("PAN", value=customer_details.get("pan", ""), key="update_cust_pan")
            aadhaar = col2.text_input("Aadhaar", value=customer_details.get("aadhaar", ""), key="update_cust_aadhaar")
            alternate_phone = col2.text_input("Alternate Phone", value=customer_details.get("alternate_phone", ""), key="update_alternate_phone")
            alternate_phone2 = col3.text_input("Alternate Phone 2", value=customer_details.get("alternate_phone2", ""), key="update_alternate_phone2")
            landline_phone = col3.text_input("Landline Phone", value=customer_details.get("landline_phone", ""), key="update_landline_phone")
        
            if st.button("Update Customer", key="update_cust_btn"):
                updated = update_customer(
                    phone=phone,
                    name=name,
                    address=address,
                    pan=pan,
                    aadhaar=aadhaar,
                    alternate_phone=alternate_phone,
                    alternate_phone2=alternate_phone2,
                    landline_phone=landline_phone
                )
                if updated:
                    st.success(f"Customer with name '{selected_name}' details updated successfully!")
                    # Optionally clear the form or reload customer details
                    # st.session_state.update_cust_name = ""
                    # st.session_state.update_cust_address = ""
                    # st.session_state.update_cust_pan = ""
                    # st.session_state.update_cust_aadhaar = ""
                    # st.rerun() # To reload the selectbox and potentially clear fields
                else:
                    st.error(f"Failed to update customer with phone name '{selected_name}'. Please check logs or database connection.")
        
        else:
            st.info("Please select a customer by name to update their details.")
