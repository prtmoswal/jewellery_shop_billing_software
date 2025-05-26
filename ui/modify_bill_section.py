import streamlit as st
import pandas as pd
from utils.db_manager import DBManager
from utils.config import DATABASE_NAME
from utils.fetch_customers import fetch_all_customers, get_customer_details
from utils.update_sale_bill import update_sale_bill
from utils.update_purchase_bill import update_purchase_bill
from utils.update_udhaar_deposit import update_udhaar_deposit
from utils.get_pending_udhaar_sale import get_all_pending_udhaar
from datetime import datetime
import math # Import math for isnan check

def modify_bill_section():
    st.subheader("Modify Existing Bills")
    st.write("Select a bill type and enter the Invoice ID to modify its details.")

    # Define payment_modes_list here so it's accessible to all tabs
    payment_modes_list = ["Cash", "Online", "Cheque", "UPI", "Other"]

    # Tabs for different bill types
    modify_sale_tab, modify_purchase_tab, modify_udhaar_tab = st.tabs(["Sale Bills", "Purchase Bills", "Udhaar Deposits"])

    with modify_sale_tab:
        st.subheader("Modify Sale Bill")

        db = DBManager(DATABASE_NAME)
        # Fetch all sale invoices for selection
        all_sale_invoices_raw = db.fetch_all("SELECT invoice_id, customer_id, total_amount, sale_date, created_at FROM sales ORDER BY created_at DESC")
        
        all_customers_dict = fetch_all_customers() # Get customer ID to name mapping
        
        sale_invoices_for_dropdown = []
        if all_sale_invoices_raw:
            for inv in all_sale_invoices_raw:
                invoice_id, customer_id, total_bill, sale_date, created_at = inv
                customer_name = all_customers_dict.get(customer_id, "Unknown Customer")
                sale_invoices_for_dropdown.append(f"{invoice_id} - {customer_name} (₹{total_bill:.2f})")
        
        selected_invoice_display = st.selectbox(
            "Select Sale Invoice to Modify",
            ["Select Invoice"] + sale_invoices_for_dropdown,
            key="modify_sale_invoice_select"
        )

        selected_sale_invoice_id = None
        if selected_invoice_display != "Select Invoice":
            selected_sale_invoice_id = selected_invoice_display.split(' ')[0] # Extract only the Invoice ID

        st.markdown("---")

        if selected_sale_invoice_id:
            st.write(f"**Modifying Sale Invoice ID:** `{selected_sale_invoice_id}`")

            # Fetch current details of the selected sale bill
            current_sale_details_raw = db.fetch_one("SELECT invoice_id, customer_id, total_amount, cheque_amount, online_amount, upi_amount, cash_amount, old_gold_amount, amount_balance, payment_mode, payment_other_info, sale_date, created_at, updated_at FROM sales WHERE invoice_id = ?", (selected_sale_invoice_id,))
            
            # Fetch sale items with all relevant columns
            current_sale_items_raw = db.fetch_all("SELECT item_id, product_id, metal, metal_rate, description, qty, net_wt, purity, gross_wt, loss_wt, making_charge, making_charge_type, stone_weight, stone_charge, wastage_percentage, amount, cgst_rate, sgst_rate, hsn FROM sale_items WHERE invoice_id = ?", (selected_sale_invoice_id,))

            if current_sale_details_raw:
                # Convert current_sale_details_raw to a dictionary for easier access
                sales_columns = [
                    'invoice_id', 'customer_id', 'total_amount', 'cheque_amount', 'online_amount',
                    'upi_amount', 'cash_amount', 'old_gold_amount', 'amount_balance', 'payment_mode',
                    'payment_other_info', 'sale_date', 'created_at', 'updated_at'
                ]
                current_sale_details = dict(zip(sales_columns, current_sale_details_raw))


                current_customer_name = all_customers_dict.get(current_sale_details['customer_id'], "Unknown")
                
                # Try parsing with microseconds first, then fallback to without
                try:
                    current_sale_date = datetime.strptime(current_sale_details['sale_date'], '%Y-%m-%dT%H:%M:%S.%f')
                except ValueError:
                    current_sale_date = datetime.strptime(current_sale_details['sale_date'], '%Y-%m-%d %H:%M:%S')

                # --- START: Wrap all modifiable inputs in a single form ---
                with st.form("modify_sale_bill_form", clear_on_submit=False):
                    # --- Input Fields for Modification ---
                    st.subheader("Invoice Details")
                    
                    # Customer selection
                    customers = fetch_all_customers()
                    customer_options = list(customers.values())
                    default_customer_index = customer_options.index(current_customer_name) if current_customer_name in customer_options else 0
                    new_customer_name = st.selectbox("Customer", customer_options, index=default_customer_index, key="modify_sale_customer_form") # Changed key
                    new_customer_id = [k for k, v in customers.items() if v == new_customer_name][0]

                    # Sale Date
                    new_sale_date = st.date_input("Sale Date", value=current_sale_date.date(), key="modify_sale_date_form") # Changed key

                    # Payment Details
                    st.subheader("Payment Details")
                    default_payment_mode_index = payment_modes_list.index(current_sale_details['payment_mode']) if current_sale_details['payment_mode'] in payment_modes_list else 0
                    new_payment_mode = st.selectbox("Payment Mode", payment_modes_list, index=default_payment_mode_index, key="modify_sale_payment_mode_form") # Changed key
                    new_payment_info = st.text_input("Payment Other Info", value=current_sale_details['payment_other_info'] or "", key="modify_sale_payment_info_form") # Changed key
                    
                    # The amount_paid in the sales table is actually the sum of cheque, online, upi, cash.
                    # For modification, we should display the *total* initial payment made.
                    current_initial_payment_sum = (
                        current_sale_details.get('cheque_amount', 0.0) +
                        current_sale_details.get('online_amount', 0.0) +
                        current_sale_details.get('upi_amount', 0.0) +
                        current_sale_details.get('cash_amount', 0.0)
                    )
                    new_amount_paid = st.number_input("Amount Paid (Initial Payment)", min_value=0.0, value=float(current_initial_payment_sum), step=100.0, key="modify_sale_amount_paid_form") # Changed key


                    # Items Section
                    st.subheader("Items in Bill")
                    
                    # Convert current_sale_items_raw to a list of dicts for easier DataFrame manipulation
                    # Ensure column names match the expected input for the data editor
                    items_data = []
                    # Columns from sale_items query: item_id, product_id, metal, metal_rate, description, qty, net_wt, purity, gross_wt, loss_wt, making_charge, making_charge_type, stone_weight, stone_charge, wastage_percentage, amount, cgst_rate, sgst_rate, hsn
                    item_cols = [
                        "item_id", "product_id", "metal", "metal_rate", "description", "qty", "net_wt",
                        "purity", "gross_wt", "loss_wt", "making_charge", "making_charge_type",
                        "stone_weight", "stone_charge", "wastage_percentage", "amount",
                        "cgst_rate", "sgst_rate", "hsn"
                    ]
                    for item_tuple in current_sale_items_raw:
                        item_dict = dict(zip(item_cols, item_tuple))
                        items_data.append({
                            "Item Name": item_dict.get("description", ""), # Using description as Item Name for display
                            "Metal": item_dict.get("metal", ""),
                            "Quantity": item_dict.get("qty", 0),
                            "Net Weight (gms)": item_dict.get("net_wt", 0.0),
                            "Metal Rate (per gram)": item_dict.get("metal_rate", 0.0),
                            "Purity": item_dict.get("purity", ""),
                            "Gross Weight (gms)": item_dict.get("gross_wt", 0.0),
                            "Loss Weight (gms)": item_dict.get("loss_wt", 0.0),
                            "Making Charge": item_dict.get("making_charge", 0.0),
                            "Making Charge Type": item_dict.get("making_charge_type", "fixed"),
                            "Stone Weight (carats)": item_dict.get("stone_weight", 0.0),
                            "Stone Charge": item_dict.get("stone_charge", 0.0),
                            "Wastage Percentage (%)": item_dict.get("wastage_percentage", 0.0),
                            "Amount": item_dict.get("amount", 0.0), # This is the item's total amount
                            # --- CHANGE MADE HERE: Ensure CGST/SGST/HSN are floats/strings with defaults ---
                            "CGST Rate (%)": float(item_dict.get("cgst_rate", 1.5)) if item_dict.get("cgst_rate") is not None else 1.5,
                            "SGST Rate (%)": float(item_dict.get("sgst_rate", 1.5)) if item_dict.get("sgst_rate") is not None else 1.5,
                            "HSN Code": str(item_dict.get("hsn", "7113")) if item_dict.get("hsn") is not None else "7113",
                            # --- END CHANGE ---
                            "product_id": item_dict.get("product_id") # Keep product_id for backend
                        })
                    
                    # Initialize session state for the DataFrame if not already present or if a new invoice is selected
                    # This logic remains outside the form, but the data editor itself is inside
                    if 'modified_sale_items_df' not in st.session_state or st.session_state.get('last_selected_sale_invoice_id') != selected_sale_invoice_id:
                        if items_data:
                            st.session_state.modified_sale_items_df = pd.DataFrame(items_data)
                        else:
                            st.session_state.modified_sale_items_df = pd.DataFrame(columns=[
                                "Item Name", "Metal", "Quantity", "Net Weight (gms)", "Metal Rate (per gram)", "Purity",
                                "Gross Weight (gms)", "Loss Weight (gms)", "Making Charge", "Making Charge Type",
                                "Stone Weight (carats)", "Stone Charge", "Wastage Percentage (%)", "Amount",
                                "CGST Rate (%)", "SGST Rate (%)", "HSN Code", "product_id"
                            ])
                        st.session_state.last_selected_sale_invoice_id = selected_sale_invoice_id
                    
                    # Editable DataFrame for items
                    modified_items_df = st.data_editor(
                        st.session_state.modified_sale_items_df,
                        num_rows="dynamic",
                        column_config={
                            "Item Name": st.column_config.TextColumn("Item Name", required=True),
                            "Metal": st.column_config.SelectboxColumn("Metal", options=["Gold", "Silver", "Platinum", "Diamond", "Other"], required=True),
                            "Quantity": st.column_config.NumberColumn("Quantity", min_value=1, required=True),
                            "Net Weight (gms)": st.column_config.NumberColumn("Net Weight (gms)", min_value=0.0, format="%.3f"),
                            "Metal Rate (per gram)": st.column_config.NumberColumn("Metal Rate (per gram)", min_value=0.0, format="%.2f"),
                            "Purity": st.column_config.TextColumn("Purity"),
                            "Gross Weight (gms)": st.column_config.NumberColumn("Gross Weight (gms)", min_value=0.0, format="%.3f"),
                            "Loss Weight (gms)": st.column_config.NumberColumn("Loss Weight (gms)", min_value=0.0, format="%.3f"),
                            "Making Charge": st.column_config.NumberColumn("Making Charge", min_value=0.0, format="%.2f"),
                            "Making Charge Type": st.column_config.SelectboxColumn("Making Charge Type", options=["fixed", "per_gram", "percentage"]),
                            "Stone Weight (carats)": st.column_config.NumberColumn("Stone Weight (carats)", min_value=0.0, format="%.2f"),
                            "Stone Charge": st.column_config.NumberColumn("Stone Charge", min_value=0.0, format="%.2f"),
                            "Wastage Percentage (%)": st.column_config.NumberColumn("Wastage Percentage (%)", min_value=0.0, max_value=100.0, format="%.2f"),
                            "Amount": st.column_config.NumberColumn("Amount", format="%.2f"), # This can be manually edited or calculated
                            "CGST Rate (%)": st.column_config.NumberColumn("CGST Rate (%)", min_value=0.0, max_value=100.0, format="%.2f", default=1.5), # Added default
                            "SGST Rate (%)": st.column_config.NumberColumn("SGST Rate (%)", min_value=0.0, max_value=100.0, format="%.2f", default=1.5), # Added default
                            "HSN Code": st.column_config.TextColumn("HSN Code", default="7113"), # Added default
                            "product_id": None # Hidden column for internal use
                        },
                        hide_index=True,
                        key="modify_sale_data_editor_form" # Changed key
                    )
                    
                    # Display calculated total amount (this will update on each rerun, showing current state)
                    # The actual total for submission will be calculated inside the submit button block
                    current_calculated_sale_total = 0.0
                    for index, row in modified_items_df.iterrows():
                        quantity = float(row.get("Quantity")) if row.get("Quantity") is not None else 0.0
                        net_wt = float(row.get("Net Weight (gms)")) if row.get("Net Weight (gms)") is not None else 0.0
                        metal_rate = float(row.get("Metal Rate (per gram)")) if row.get("Metal Rate (per gram)") is not None else 0.0
                        making_charge = float(row.get("Making Charge")) if row.get("Making Charge") is not None else 0.0
                        stone_charge = float(row.get("Stone Charge")) if row.get("Stone Charge") is not None else 0.0
                        wastage_percentage = float(row.get("Wastage Percentage (%)")) if row.get("Wastage Percentage (%)") is not None else 0.0
                        amount_from_editor = float(row.get("Amount")) if row.get("Amount") is not None else 0.0

                        calculated_amount_for_item_display = amount_from_editor
                        if calculated_amount_for_item_display <= 0 and net_wt > 0 and metal_rate > 0:
                            calculated_amount_for_item_display = net_wt * metal_rate

                        final_item_amount_display = calculated_amount_for_item_display + making_charge + stone_charge
                        if wastage_percentage > 0:
                            final_item_amount_display += (calculated_amount_for_item_display * (wastage_percentage / 100))
                        
                        current_calculated_sale_total += final_item_amount_display

                    st.info(f"Calculated Total Bill Amount (from modified items): ₹{current_calculated_sale_total:.2f}")

                    st.markdown("---")

                    # Update Button (now a form_submit_button)
                    if st.form_submit_button("Update Sale Bill"): # No key needed for form_submit_button if it's the only one
                        # Update the session state DataFrame with the modified data from the editor
                        st.session_state.modified_sale_items_df = modified_items_df

                        # Recalculate total amount from modified items (this logic runs on form submission)
                        total_bill_after_item_modify = 0.0
                        valid_items_for_db = [] # This list will be passed to the update function
                        for index, row in modified_items_df.iterrows():
                            item_name = row.get("Item Name")
                            metal = row.get("Metal")
                            quantity = row.get("Quantity")
                            net_wt = row.get("Net Weight (gms)")
                            metal_rate = row.get("Metal Rate (per gram)")
                            purity = row.get("Purity")
                            gross_wt = row.get("Gross Weight (gms)")
                            loss_wt = row.get("Loss Weight (gms)")
                            making_charge = row.get("Making Charge")
                            making_charge_type = row.get("Making Charge Type")
                            stone_weight = row.get("Stone Weight (carats)")
                            stone_charge = row.get("Stone Charge")
                            wastage_percentage = row.get("Wastage Percentage (%)")
                            amount_from_editor = row.get("Amount") # Amount as entered/calculated in editor
                            cgst_rate = row.get("CGST Rate (%)")
                            sgst_rate = row.get("SGST Rate (%)")
                            hsn = row.get("HSN Code")
                            product_id = row.get("product_id")

                            # Robustly convert all numerical inputs to float, defaulting to 0.0
                            quantity = float(quantity) if quantity is not None else 0.0
                            net_wt = float(net_wt) if net_wt is not None else 0.0
                            metal_rate = float(metal_rate) if metal_rate is not None else 0.0
                            making_charge = float(making_charge) if making_charge is not None else 0.0
                            stone_weight = float(stone_weight) if stone_weight is not None else 0.0
                            stone_charge = float(stone_charge) if stone_charge is not None else 0.0
                            wastage_percentage = float(wastage_percentage) if wastage_percentage is not None else 0.0
                            amount_from_editor = float(amount_from_editor) if amount_from_editor is not None else 0.0
                            cgst_rate = float(cgst_rate) if cgst_rate is not None else 0.0
                            sgst_rate = float(sgst_rate) if sgst_rate is not None else 0.0
                            gross_wt = float(gross_wt) if gross_wt is not None else 0.0
                            loss_wt = float(loss_wt) if loss_wt is not None else 0.0
                            # Ensure HSN code defaults if None
                            hsn = hsn if hsn is not None else "7113"

                            # Basic validation and calculation for each item
                            if item_name and metal and quantity > 0:
                                calculated_amount_for_item = 0.0
                                # Prioritize manual amount from editor
                                if amount_from_editor > 0: # If amount is explicitly entered/modified
                                    calculated_amount_for_item = amount_from_editor
                                elif net_wt > 0 and metal_rate > 0: # Fallback to calculation if no manual amount
                                    calculated_amount_for_item = net_wt * metal_rate
                                else:
                                    calculated_amount_for_item = 0.0 # Default if no valid amount source

                                # Add making_charge, stone_charge, wastage to item's base amount for total item amount
                                # This logic should mirror how the original sale item amount was calculated
                                final_item_amount = calculated_amount_for_item + making_charge + stone_charge
                                if wastage_percentage > 0:
                                    final_item_amount += (calculated_amount_for_item * (wastage_percentage / 100))

                                total_bill_after_item_modify += final_item_amount
                                
                                valid_items_for_db.append({
                                    "item_name": item_name, # This maps to 'description' in DB
                                    "metal": metal,
                                    "qty": quantity,
                                    "net_wt": net_wt,
                                    "metal_rate": metal_rate,
                                    "purity": purity,
                                    "gross_wt": gross_wt,
                                    "loss_wt": loss_wt,
                                    "making_charge": making_charge,
                                    "making_charge_type": making_charge_type,
                                    "stone_weight": stone_weight,
                                    "stone_charge": stone_charge,
                                    "wastage_percentage": wastage_percentage,
                                    "amount": final_item_amount, # This is the total amount for the item
                                    "cgst_rate": cgst_rate,
                                    "sgst_rate": sgst_rate,
                                    "hsn": hsn,
                                    "product_id": product_id
                                })
                            else:
                                print(f"Skipping item due to invalid input: Item Name={item_name}, Metal={metal}, Quantity={quantity}")
                        
                        # Ensure total_bill_after_item_modify is explicitly a float
                        final_total_bill_to_pass = float(total_bill_after_item_modify)

                        # ADDED NAN CHECK
                        if math.isnan(final_total_bill_to_pass):
                            st.error("Calculated total bill amount is invalid (NaN). Please check item inputs.")
                        elif not valid_items_for_db:
                            st.error("Please add at least one valid item to the bill.")
                        elif final_total_bill_to_pass <= 0:
                            st.error("Calculated total bill amount must be greater than zero.")
                        elif new_amount_paid > final_total_bill_to_pass:
                            st.error("Amount paid cannot exceed the total bill amount.")
                        else:
                            # Call the update function
                            if update_sale_bill(
                                selected_sale_invoice_id,
                                new_customer_id,
                                new_sale_date,
                                valid_items_for_db, # Pass the correctly formatted items
                                new_payment_mode,
                                new_payment_info,
                                new_amount_paid,
                                final_total_bill_to_pass # Pass the recalculated total bill amount
                            ):
                                st.success(f"Sale Invoice `{selected_sale_invoice_id}` updated successfully!")
                                st.info("Please refresh the page or select another invoice to see changes.")
                                # Clear session state for the data editor to re-load correctly on next selection
                                if 'modified_sale_items_df' in st.session_state:
                                    del st.session_state.modified_sale_items_df
                                if 'last_selected_sale_invoice_id' in st.session_state:
                                    del st.session_state.last_selected_sale_invoice_id
                                # st.rerun() # REMOVED THIS LINE
                            else:
                                st.error(f"Failed to update Sale Invoice `{selected_sale_invoice_id}`.")
                # --- END: Wrap all modifiable inputs in a single form ---
            else:
                st.error("Could not fetch details for the selected invoice. It might have been deleted.")

    with modify_purchase_tab:
        st.subheader("Modify Purchase Bill")

        db = DBManager(DATABASE_NAME)
        # Fetch all purchase invoices for selection
        all_purchase_invoices_raw = db.fetch_all("SELECT invoice_id, supplier_id, total_amount, purchase_date, created_at FROM purchases ORDER BY created_at DESC")
        
        all_customers_dict = fetch_all_customers() # Get customer ID to name mapping (suppliers are also customers)
        
        purchase_invoices_for_dropdown = []
        if all_purchase_invoices_raw:
            for inv in all_purchase_invoices_raw:
                invoice_id, supplier_id, total_bill, purchase_date, created_at = inv
                supplier_name = all_customers_dict.get(supplier_id, "Unknown Supplier")
                purchase_invoices_for_dropdown.append(f"{invoice_id} - {supplier_name} (₹{total_bill:.2f})")
        
        selected_purchase_invoice_display = st.selectbox(
            "Select Purchase Invoice to Modify",
            ["Select Invoice"] + purchase_invoices_for_dropdown,
            key="modify_purchase_invoice_select"
        )

        selected_purchase_invoice_id = None
        if selected_purchase_invoice_display != "Select Invoice":
            selected_purchase_invoice_id = selected_purchase_invoice_display.split(' ')[0]

        st.markdown("---")

        if selected_purchase_invoice_id:
            st.write(f"**Modifying Purchase Invoice ID:** `{selected_purchase_invoice_id}`")

            # Fetch current details of the selected purchase bill
            current_purchase_details_raw = db.fetch_one("SELECT invoice_id, supplier_id, total_amount, cheque_amount, online_amount, upi_amount, cash_amount, amount_balance, payment_mode, payment_other_info, purchase_date, created_at, updated_at FROM purchases WHERE invoice_id = ?", (selected_purchase_invoice_id,))
            
            # Fetch purchase items with all relevant columns
            current_purchase_items_raw = db.fetch_all("SELECT item_id, product_id, metal, qty, net_wt, price, amount, gross_wt, loss_wt, metal_rate, description, purity, cgst_rate, sgst_rate, hsn, making_charge, making_charge_type, stone_weight, stone_charge, wastage_percentage FROM purchase_items WHERE invoice_id = ?", (selected_purchase_invoice_id,))

            if current_purchase_details_raw:
                purchase_columns = [
                    'invoice_id', 'supplier_id', 'total_amount', 'cheque_amount', 'online_amount',
                    'upi_amount', 'cash_amount', 'amount_balance', 'payment_mode',
                    'payment_other_info', 'purchase_date', 'created_at', 'updated_at'
                ]
                current_purchase_details = dict(zip(purchase_columns, current_purchase_details_raw))

                current_supplier_name = all_customers_dict.get(current_purchase_details['supplier_id'], "Unknown")
                
                try:
                    current_purchase_date = datetime.strptime(current_purchase_details['purchase_date'], '%Y-%m-%dT%H:%M:%S.%f')
                except ValueError:
                    current_purchase_date = datetime.strptime(current_purchase_details['purchase_date'], '%Y-%m-%d %H:%M:%S')

                with st.form("modify_purchase_bill_form", clear_on_submit=False):
                    st.subheader("Invoice Details")
                    
                    suppliers = fetch_all_customers() # Re-use customer fetch for suppliers
                    supplier_options = list(suppliers.values())
                    default_supplier_index = supplier_options.index(current_supplier_name) if current_supplier_name in supplier_options else 0
                    new_supplier_name = st.selectbox("Supplier", supplier_options, index=default_supplier_index, key="modify_purchase_supplier_form")
                    new_supplier_id = [k for k, v in suppliers.items() if v == new_supplier_name][0]

                    new_purchase_date = st.date_input("Purchase Date", value=current_purchase_date.date(), key="modify_purchase_date_form")

                    st.subheader("Payment Details")
                    default_payment_mode_index = payment_modes_list.index(current_purchase_details['payment_mode']) if current_purchase_details['payment_mode'] in payment_modes_list else 0
                    new_payment_mode = st.selectbox("Payment Mode", payment_modes_list, index=default_payment_mode_index, key="modify_purchase_payment_mode_form")
                    new_payment_info = st.text_input("Payment Other Info", value=current_purchase_details['payment_other_info'] or "", key="modify_purchase_payment_info_form")
                    
                    current_initial_payment_sum_purchase = (
                        current_purchase_details.get('cheque_amount', 0.0) +
                        current_purchase_details.get('online_amount', 0.0) +
                        current_purchase_details.get('upi_amount', 0.0) +
                        current_purchase_details.get('cash_amount', 0.0)
                    )
                    new_amount_paid_purchase = st.number_input("Amount Paid", min_value=0.0, value=float(current_initial_payment_sum_purchase), step=100.0, key="modify_purchase_amount_paid_form")

                    st.subheader("Items in Bill")
                    
                    purchase_items_data = []
                    item_cols_purchase = [
                        "item_id", "product_id", "metal", "qty", "net_wt", "price", "amount",
                        "gross_wt", "loss_wt", "metal_rate", "description", "purity",
                        "cgst_rate", "sgst_rate", "hsn", "making_charge", "making_charge_type",
                        "stone_weight", "stone_charge", "wastage_percentage"
                    ]
                    for item_tuple in current_purchase_items_raw:
                        item_dict = dict(zip(item_cols_purchase, item_tuple))
                        purchase_items_data.append({
                            "Item Name": item_dict.get("description", ""),
                            "Metal": item_dict.get("metal", ""),
                            "Quantity": item_dict.get("qty", 0),
                            "Net Weight (gms)": item_dict.get("net_wt", 0.0),
                            "Metal Rate (per gram)": item_dict.get("metal_rate", 0.0),
                            "Price (per unit/gm)": item_dict.get("price", 0.0),
                            "Amount": item_dict.get("amount", 0.0),
                            "Purity": item_dict.get("purity", ""),
                            "Gross Weight (gms)": item_dict.get("gross_wt", 0.0),
                            "Loss Weight (gms)": item_dict.get("loss_wt", 0.0),
                            "Making Charge": item_dict.get("making_charge", 0.0),
                            "Making Charge Type": item_dict.get("making_charge_type", "fixed"),
                            "Stone Weight (carats)": item_dict.get("stone_weight", 0.0),
                            "Stone Charge": item_dict.get("stone_charge", 0.0),
                            "Wastage Percentage (%)": item_dict.get("wastage_percentage", 0.0),
                            "CGST Rate (%)": float(item_dict.get("cgst_rate", 1.5)) if item_dict.get("cgst_rate") is not None else 1.5,
                            "SGST Rate (%)": float(item_dict.get("sgst_rate", 1.5)) if item_dict.get("sgst_rate") is not None else 1.5,
                            "HSN Code": str(item_dict.get("hsn", "7113")) if item_dict.get("hsn") is not None else "7113",
                            "product_id": item_dict.get("product_id")
                        })
                    
                    if 'modified_purchase_items_df' not in st.session_state or st.session_state.get('last_selected_purchase_invoice_id') != selected_purchase_invoice_id:
                        if purchase_items_data:
                            st.session_state.modified_purchase_items_df = pd.DataFrame(purchase_items_data)
                        else:
                            st.session_state.modified_purchase_items_df = pd.DataFrame(columns=[
                                "Item Name", "Metal", "Quantity", "Net Weight (gms)", "Metal Rate (per gram)", "Price (per unit/gm)", "Amount", "Purity",
                                "Gross Weight (gms)", "Loss Weight (gms)", "Making Charge", "Making Charge Type",
                                "Stone Weight (carats)", "Stone Charge", "Wastage Percentage (%)",
                                "CGST Rate (%)", "SGST Rate (%)", "HSN Code", "product_id"
                            ])
                        st.session_state.last_selected_purchase_invoice_id = selected_purchase_invoice_id
                    
                    modified_purchase_items_df = st.data_editor(
                        st.session_state.modified_purchase_items_df,
                        num_rows="dynamic",
                        column_config={
                            "Item Name": st.column_config.TextColumn("Item Name", required=True),
                            "Metal": st.column_config.SelectboxColumn("Metal", options=["Gold", "Silver", "Platinum", "Diamond", "Other"], required=True),
                            "Quantity": st.column_config.NumberColumn("Quantity", min_value=1, required=True),
                            "Net Weight (gms)": st.column_config.NumberColumn("Net Weight (gms)", min_value=0.0, format="%.3f"),
                            "Metal Rate (per gram)": st.column_config.NumberColumn("Metal Rate (per gram)", min_value=0.0, format="%.2f"),
                            "Price (per unit/gm)": st.column_config.NumberColumn("Price (per unit/gm)", min_value=0.0, format="%.2f"),
                            "Amount": st.column_config.NumberColumn("Amount", format="%.2f"),
                            "Purity": st.column_config.TextColumn("Purity"),
                            "Gross Weight (gms)": st.column_config.NumberColumn("Gross Weight (gms)", min_value=0.0, format="%.3f"),
                            "Loss Weight (gms)": st.column_config.NumberColumn("Loss Weight (gms)", min_value=0.0, format="%.3f"),
                            "Making Charge": st.column_config.NumberColumn("Making Charge", min_value=0.0, format="%.2f"),
                            "Making Charge Type": st.column_config.SelectboxColumn("Making Charge Type", options=["fixed", "per_gram", "percentage"]),
                            "Stone Weight (carats)": st.column_config.NumberColumn("Stone Weight (carats)", min_value=0.0, format="%.2f"),
                            "Stone Charge": st.column_config.NumberColumn("Stone Charge", min_value=0.0, format="%.2f"),
                            "Wastage Percentage (%)": st.column_config.NumberColumn("Wastage Percentage (%)", min_value=0.0, max_value=100.0, format="%.2f"),
                            "CGST Rate (%)": st.column_config.NumberColumn("CGST Rate (%)", min_value=0.0, max_value=100.0, format="%.2f", default=1.5),
                            "SGST Rate (%)": st.column_config.NumberColumn("SGST Rate (%)", min_value=0.0, max_value=100.0, format="%.2f", default=1.5),
                            "HSN Code": st.column_config.TextColumn("HSN Code", default="7113"),
                            "product_id": None
                        },
                        hide_index=True,
                        key="modify_purchase_data_editor_form"
                    )
                    
                    # Display calculated total amount for purchase (updates on each rerun)
                    current_calculated_purchase_total = 0.0
                    for index, row in modified_purchase_items_df.iterrows():
                        quantity = float(row.get("Quantity")) if row.get("Quantity") is not None else 0.0
                        net_wt = float(row.get("Net Weight (gms)")) if row.get("Net Weight (gms)") is not None else 0.0
                        metal_rate = float(row.get("Metal Rate (per gram)")) if row.get("Metal Rate (per gram)") is not None else 0.0
                        price_per_unit = float(row.get("Price (per unit/gm)")) if row.get("Price (per unit/gm)") is not None else 0.0
                        amount_from_editor = float(row.get("Amount")) if row.get("Amount") is not None else 0.0
                        making_charge = float(row.get("Making Charge")) if row.get("Making Charge") is not None else 0.0
                        stone_charge = float(row.get("Stone Charge")) if row.get("Stone Charge") is not None else 0.0
                        wastage_percentage = float(row.get("Wastage Percentage (%)")) if row.get("Wastage Percentage (%)") is not None else 0.0
                        
                        calculated_amount_for_item_display = amount_from_editor
                        if calculated_amount_for_item_display <= 0:
                            if net_wt > 0 and metal_rate > 0:
                                calculated_amount_for_item_display = net_wt * metal_rate
                            elif price_per_unit > 0 and quantity > 0:
                                calculated_amount_for_item_display = price_per_unit * quantity
                        
                        final_item_amount_display = calculated_amount_for_item_display + making_charge + stone_charge
                        if wastage_percentage > 0:
                            final_item_amount_display += (calculated_amount_for_item_display * (wastage_percentage / 100))
                        
                        current_calculated_purchase_total += final_item_amount_display

                    st.info(f"Calculated Total Bill Amount (from modified items): ₹{current_calculated_purchase_total:.2f}")

                    st.markdown("---")

                    if st.form_submit_button("Update Purchase Bill"):
                        st.session_state.modified_purchase_items_df = modified_purchase_items_df

                        total_bill_after_item_modify_purchase = 0.0
                        valid_purchase_items_for_db = []
                        for index, row in modified_purchase_items_df.iterrows():
                            item_name = row.get("Item Name")
                            metal = row.get("Metal")
                            quantity = float(row.get("Quantity")) if row.get("Quantity") is not None else 0.0
                            net_wt = float(row.get("Net Weight (gms)")) if row.get("Net Weight (gms)") is not None else 0.0
                            metal_rate = float(row.get("Metal Rate (per gram)")) if row.get("Metal Rate (per gram)") is not None else 0.0
                            price_per_unit = float(row.get("Price (per unit/gm)")) if row.get("Price (per unit/gm)") is not None else 0.0
                            amount_from_editor = float(row.get("Amount")) if row.get("Amount") is not None else 0.0
                            purity = row.get("Purity")
                            gross_wt = float(row.get("Gross Weight (gms)")) if row.get("Gross Weight (gms)") is not None else 0.0
                            loss_wt = float(row.get("Loss Weight (gms)")) if row.get("Loss Weight (gms)") is not None else 0.0
                            making_charge = float(row.get("Making Charge")) if row.get("Making Charge") is not None else 0.0
                            making_charge_type = row.get("Making Charge Type")
                            stone_weight = float(row.get("Stone Weight (carats)")) if row.get("Stone Weight (carats)") is not None else 0.0
                            stone_charge = float(row.get("Stone Charge")) if row.get("Stone Charge") is not None else 0.0
                            wastage_percentage = float(row.get("Wastage Percentage (%)")) if row.get("Wastage Percentage (%)") is not None else 0.0
                            cgst_rate = float(row.get("CGST Rate (%)")) if row.get("CGST Rate (%)") is not None else 0.0
                            sgst_rate = float(row.get("SGST Rate (%)")) if row.get("SGST Rate (%)") is not None else 0.0
                            hsn = row.get("HSN Code") if row.get("HSN Code") is not None else "7113"
                            product_id = row.get("product_id")
                            description = row.get("Item Name") # Use "Item Name" as description for purchase items

                            if item_name and metal and quantity > 0:
                                calculated_amount_for_item = 0.0
                                if amount_from_editor > 0:
                                    calculated_amount_for_item = amount_from_editor
                                elif net_wt > 0 and metal_rate > 0:
                                    calculated_amount_for_item = net_wt * metal_rate
                                elif price_per_unit > 0 and quantity > 0:
                                    calculated_amount_for_item = price_per_unit * quantity
                                else:
                                    calculated_amount_for_item = 0.0

                                final_item_amount = calculated_amount_for_item + making_charge + stone_charge
                                if wastage_percentage > 0:
                                    final_item_amount += (calculated_amount_for_item * (wastage_percentage / 100))

                                total_bill_after_item_modify_purchase += final_item_amount
                                
                                valid_purchase_items_for_db.append({
                                    "item_name": item_name, "metal": metal, "qty": quantity, "net_wt": net_wt,
                                    "price": price_per_unit, "amount": final_item_amount, "gross_wt": gross_wt,
                                    "loss_wt": loss_wt, "metal_rate": metal_rate, "description": description,
                                    "purity": purity, "cgst_rate": cgst_rate, "sgst_rate": sgst_rate, "hsn": hsn,
                                    "making_charge": making_charge, "making_charge_type": making_charge_type,
                                    "stone_weight": stone_weight, "stone_charge": stone_charge,
                                    "wastage_percentage": wastage_percentage, "product_id": product_id
                                })
                        
                        final_total_bill_to_pass_purchase = float(total_bill_after_item_modify_purchase)

                        if math.isnan(final_total_bill_to_pass_purchase):
                            st.error("Calculated total bill amount is invalid (NaN). Please check item inputs.")
                        elif not valid_purchase_items_for_db:
                            st.error("Please add at least one valid item to the bill.")
                        elif final_total_bill_to_pass_purchase <= 0:
                            st.error("Calculated total bill amount must be greater than zero.")
                        elif new_amount_paid_purchase > final_total_bill_to_pass_purchase:
                            st.error("Amount paid cannot exceed the total bill amount.")
                        else:
                            if update_purchase_bill(
                                selected_purchase_invoice_id,
                                new_supplier_id,
                                new_purchase_date,
                                valid_purchase_items_for_db,
                                new_payment_mode,
                                new_payment_info,
                                new_amount_paid_purchase,
                                final_total_bill_to_pass_purchase
                            ):
                                st.success(f"Purchase Invoice `{selected_purchase_invoice_id}` updated successfully!")
                                st.info("Please refresh the page or select another invoice to see changes.")
                                if 'modified_purchase_items_df' in st.session_state:
                                    del st.session_state.modified_purchase_items_df
                                if 'last_selected_purchase_invoice_id' in st.session_state:
                                    del st.session_state.last_selected_purchase_invoice_id
                                # st.rerun() # REMOVED THIS LINE
                            else:
                                st.error(f"Failed to update Purchase Invoice `{selected_purchase_invoice_id}`.")
            else:
                st.error("Could not fetch details for the selected invoice. It might have been deleted.")

    with modify_udhaar_tab:
        st.subheader("Modify Udhaar Deposit")

        db = DBManager(DATABASE_NAME)
        # Fetch all udhaar deposits for selection
        all_udhaar_deposits_raw = db.fetch_all("SELECT deposit_invoice_id, customer_id, deposit_amount, deposit_date, sell_invoice_id FROM udhaar_deposits ORDER BY deposit_date DESC")
        
        all_customers_dict = fetch_all_customers()
        all_pending_sales_udhaar = get_all_pending_udhaar() # For linking to existing sales invoices
        
        udhaar_deposits_for_dropdown = []
        if all_udhaar_deposits_raw:
            for dep in all_udhaar_deposits_raw:
                deposit_invoice_id, customer_id, deposit_amount, deposit_date, sell_invoice_id = dep
                customer_name = all_customers_dict.get(customer_id, "Unknown Customer")
                udhaar_deposits_for_dropdown.append(f"{deposit_invoice_id} - {customer_name} (₹{deposit_amount:.2f})")
        
        selected_udhaar_deposit_display = st.selectbox(
            "Select Udhaar Deposit to Modify",
            ["Select Deposit"] + udhaar_deposits_for_dropdown,
            key="modify_udhaar_deposit_select"
        )

        selected_udhaar_deposit_id = None
        if selected_udhaar_deposit_display != "Select Deposit":
            selected_udhaar_deposit_id = selected_udhaar_deposit_display.split(' ')[0]

        st.markdown("---")

        if selected_udhaar_deposit_id:
            st.write(f"**Modifying Udhaar Deposit ID:** `{selected_udhaar_deposit_id}`")

            current_udhaar_deposit_details_raw = db.fetch_one("SELECT deposit_invoice_id, sell_invoice_id, customer_id, deposit_amount, deposit_date, payment_mode, payment_other_info FROM udhaar_deposits WHERE deposit_invoice_id = ?", (selected_udhaar_deposit_id,))
            
            if current_udhaar_deposit_details_raw:
                deposit_columns = [
                    'deposit_invoice_id', 'sell_invoice_id', 'customer_id', 'deposit_amount',
                    'deposit_date', 'payment_mode', 'payment_other_info'
                ]
                current_udhaar_deposit_details = dict(zip(deposit_columns, current_udhaar_deposit_details_raw))

                current_customer_name_deposit = all_customers_dict.get(current_udhaar_deposit_details['customer_id'], "Unknown")
                
                try:
                    current_deposit_date = datetime.strptime(current_udhaar_deposit_details['deposit_date'], '%Y-%m-%dT%H:%M:%S.%f')
                except ValueError:
                    current_deposit_date = datetime.strptime(current_udhaar_deposit_details['deposit_date'], '%Y-%m-%d %H:%M:%S')

                with st.form("modify_udhaar_deposit_form", clear_on_submit=False):
                    st.subheader("Deposit Details")
                    
                    customers_deposit = fetch_all_customers()
                    customer_options_deposit = list(customers_deposit.values())
                    default_customer_index_deposit = customer_options_deposit.index(current_customer_name_deposit) if current_customer_name_deposit in customer_options_deposit else 0
                    new_customer_name_deposit = st.selectbox("Customer", customer_options_deposit, index=default_customer_index_deposit, key="modify_udhaar_customer_form")
                    new_customer_id_deposit = [k for k, v in customers_deposit.items() if v == new_customer_name_deposit][0]

                    # Link to existing pending sale invoice
                    pending_sales_for_deposit_customer = [
                        s for s in all_pending_sales_udhaar if s['customer_id'] == new_customer_id_deposit
                    ]
                    
                    linked_invoice_options = ["(No specific invoice - General Deposit)"] + [
                        f"{s['sell_invoice_id']} (Balance: ₹{s['current_balance']:.2f})" for s in pending_sales_for_deposit_customer
                    ]
                    
                    default_linked_invoice_index = 0
                    if current_udhaar_deposit_details['sell_invoice_id']:
                        try:
                            # Find the index of the currently linked invoice in the options
                            # This needs to be more robust, matching the exact string from linked_invoice_options
                            for i, opt in enumerate(linked_invoice_options):
                                if current_udhaar_deposit_details['sell_invoice_id'] in opt:
                                    default_linked_invoice_index = i
                                    break
                        except ValueError:
                            pass # Keep default_linked_invoice_index as 0 if not found

                    new_linked_invoice_display = st.selectbox(
                        "Link Deposit to Pending Sale Invoice (Optional)",
                        linked_invoice_options,
                        index=default_linked_invoice_index,
                        key="modify_udhaar_link_invoice_form"
                    )
                    
                    new_sell_invoice_id_deposit = None
                    if new_linked_invoice_display != "(No specific invoice - General Deposit)":
                        new_sell_invoice_id_deposit = new_linked_invoice_display.split(' ')[0]

                    new_deposit_amount = st.number_input("Deposit Amount", min_value=0.0, value=float(current_udhaar_deposit_details['deposit_amount']), step=100.0, key="modify_udhaar_deposit_amount_form")
                    new_payment_mode_deposit = st.selectbox("Payment Mode", payment_modes_list, index=payment_modes_list.index(current_udhaar_deposit_details['payment_mode']) if current_udhaar_deposit_details['payment_mode'] in payment_modes_list else 0, key="modify_udhaar_payment_mode_form")
                    new_payment_info_deposit = st.text_input("Payment Other Info", value=current_udhaar_deposit_details['payment_other_info'] or "", key="modify_udhaar_payment_info_form")

                    if st.form_submit_button("Update Udhaar Deposit"):
                        if new_customer_id_deposit and new_deposit_amount > 0:
                            if update_udhaar_deposit(
                                selected_udhaar_deposit_id,
                                new_sell_invoice_id_deposit,
                                new_customer_id_deposit,
                                new_deposit_amount,
                                new_payment_mode_deposit,
                                new_payment_info_deposit
                            ):
                                st.success(f"Udhaar Deposit `{selected_udhaar_deposit_id}` updated successfully!")
                                st.info("Please refresh the page or select another deposit to see changes.")
                                # st.rerun() # REMOVED THIS LINE
                            else:
                                st.error(f"Failed to update Udhaar Deposit `{selected_udhaar_deposit_id}`.")
                        else:
                            st.error("Please select a customer and enter a valid deposit amount.")
            else:
                st.error("Could not fetch details for the selected deposit. It might have been deleted.")
