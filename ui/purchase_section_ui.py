import streamlit as st
import pandas as pd
from datetime import datetime
import json # Import the json library for serialization

# Import necessary utility functions
from utils.config import DATABASE_NAME # Only for DBManager, not direct use
from utils.fetch_customers import fetch_all_customers, add_new_customer, get_customer_details
from utils.invoice_id_creation import generate_purchase_invoice_id
from utils.save_purchase import save_purchase
from utils.generate_purchase_pdf import generate_purchase_pdf
from utils.get_download_link import get_download_link
from utils.db_manager import DBManager # Import DBManager for specific fetches if needed

def purchase_section():
    st.title("📦 Purchase Jewellery") # Changed to title for more prominence

    # Initialize DBManager
    db_manager_instance = DBManager(DATABASE_NAME)

    # --- Supplier Selection Section ---
    st.subheader("Supplier Information")
    supplier_col1, supplier_col2 = st.columns([0.7, 0.3])

    with supplier_col1:
        customers = fetch_all_customers()
        customer_options = ["Select Supplier"] + list(customers.values())
        selected_customer_name = st.selectbox("Select Existing Supplier", customer_options, key="purchase_customer")

    customer_id = None
    customer_details = {}

    if selected_customer_name == "Select Supplier":
        with supplier_col2:
            st.write("Or Add New Supplier")
            add_new_supplier_button = st.button("➕ Add New Supplier", key="show_add_supplier_form")

        if add_new_supplier_button:
            with st.expander("Enter New Supplier Details", expanded=True):
                col1, col2, col3 = st.columns(3)
                name = col1.text_input("Supplier Name", key="add_purchase_supplier_name")
                phone = col1.text_input("Phone Number", key="add_purchase_supplier_phone")
                address = col3.text_input("Address", key="add_purchase_supplier_address")
                pan = col2.text_input("PAN (Optional)", key="add_purchase_supplier_pan")
                aadhaar = col2.text_input("Aadhaar (Optional)", key="add_purchase_supplier_adhaar")
                alternate_phone = col3.text_input("Alternate Phone", key="add_purchase_supplier_alternate_phone")
                alternate_phone2 = col1.text_input("Alternate Phone2", key="add_purchase_supplier_alternate_phone2")
                landline_phone = col2.text_input("Landline Phone", key="add_purchase_supplier_landline_phone")

                if st.button("💾 Save New Supplier", key="add_purchase_supplier_button"):
                    if name and phone:
                        success = add_new_customer(name, phone, address, pan, aadhaar, alternate_phone, alternate_phone2, landline_phone)
                        if success:
                            st.success(f"Supplier '{name}' added successfully! Please select from the dropdown.")
                            st.rerun()
                        else:
                            st.error(f"Failed to add supplier '{name}'.")
                    else:
                        st.error("Supplier name and phone number are required!")
    else:
        customer_id = [k for k, v in customers.items() if v == selected_customer_name][0]
        customer_details = get_customer_details(customer_id)

        st.markdown("---")
        st.subheader("Selected Supplier Details")
        details_col1, details_col2, details_col3 = st.columns(3)
        details_col1.write(f"**Name:** {customer_details.get('name', 'N/A')}")
        details_col2.write(f"**Primary Phone:** {customer_details.get('phone', 'N/A')}")
        details_col3.write(f"**Address:** {customer_details.get('address', 'N/A')}")
        if customer_details.get('pan'):
            details_col1.write(f"**PAN:** {customer_details.get('pan')}")
        if customer_details.get('aadhaar'):
            details_col2.write(f"**Aadhaar:** {customer_details.get('aadhaar')}")
        if customer_details.get('alternate_phone'):
            details_col3.write(f"**Contact Phone:** {customer_details.get('alternate_phone')}")
        if customer_details.get('alternate_phone2'):
            details_col1.write(f"**Alternate Phone:** {customer_details.get('alternate_phone2')}")
        if customer_details.get('landline_phone'):
            details_col2.write(f"**Landline Number:** {customer_details.get('landline_phone')}")

        st.markdown("---")
        st.subheader("Add Purchase Items")

        if 'purchase_items' not in st.session_state:
            st.session_state.purchase_items = []

        with st.form("add_purchase_item_form", clear_on_submit=True): # clear_on_submit set to True
            item_col1, item_col2, item_col3 = st.columns(3)
            with item_col1:
                metal = st.selectbox("Metal", ["Gold", "Silver", "Platinum", "Diamond", "Other"], key="purchase_metal_form")
                purity = st.text_input("Purity (e.g., 24K, 92.5%)", key="purchase_purity_form")
                description = st.text_area("Description", key="purchase_description_form")
            with item_col2:
                qty = st.number_input("Quantity", min_value=1, step=1, key="purchase_qty_form")
                gross_wt = st.number_input("Gross Weight (grams)", min_value=0.0, step=0.1, format="%.3f", key="purchase_gross_wt_form")
                loss_wt = st.number_input("Loss Weight (grams)", min_value=0.0, step=0.001, format="%.3f", key="purchase_loss_wt_form")
            with item_col3:
                net_wt = gross_wt - loss_wt
                st.info(f"**Net Weight (grams): {net_wt:.3f}**") # Changed to st.info for prominence
                metal_rate = st.number_input("Metal Rate per gram", min_value=0.0, step=10.0, key="purchase_metal_rate_form")
                price = st.number_input("Price per item (if fixed)", min_value=0.0, step=10.0, key="purchase_price_per_item_form")
                amount = st.number_input("Total Item Amount (before GST)", min_value=0.0, step=100.0, key="purchase_item_amount_form")

            st.markdown("---")
            tax_col1, tax_col2, tax_col3, tax_col4 = st.columns(4)
            with tax_col1:
                making_charge = st.number_input("Making Charge", min_value=0.0, step=1.0, key="purchase_making_charge_form")
                wastage_percentage = st.number_input("Wastage Percentage (%)", min_value=0.0, max_value=100.0, step=0.1, format="%.2f", key="purchase_wastage_percentage_form")
            with tax_col2:
                making_charge_type = st.selectbox("Making Charge Type", ["fixed", "per_gram", "percentage"], key="purchase_making_charge_type_form")
                cgst_rate = st.number_input("CGST Rate (%)", min_value=0.0, max_value=100.0, step=0.1, format="%.2f", value=1.5, key="purchase_cgst_rate_form")
            with tax_col3:
                stone_weight = st.number_input("Stone Weight (carats)", min_value=0.0, step=0.01, format="%.2f", key="purchase_stone_weight_form")
                sgst_rate = st.number_input("SGST Rate (%)", min_value=0.0, max_value=100.0, step=0.1, format="%.2f", value=1.5, key="purchase_sgst_rate_form")
            with tax_col4:
                stone_charge = st.number_input("Stone Charge", min_value=0.0, step=1.0, key="purchase_stone_charge_form")
                hsn = st.text_input("HSN Code", value="7113", key="purchase_hsn_form")

            add_item = st.form_submit_button("➕ Add Item to Purchase")

            if add_item:
                if (net_wt <= 0 and amount <= 0) or (metal_rate <= 0 and amount <= 0):
                    st.error("Please fill Net Weight/Metal Rate and Total Item Amount with valid values.")
                else:
                    calculated_amount = amount
                    if metal_rate > 0 and net_wt > 0 and amount == 0:
                        calculated_amount = net_wt * metal_rate
                    elif price > 0 and qty > 0 and amount == 0:
                        calculated_amount = price * qty

                    if calculated_amount <= 0:
                        st.error("Calculated item amount must be greater than zero. Adjust inputs.")
                    else:
                        new_item = {
                            'metal': metal,
                            'qty': qty,
                            'net_wt': net_wt,
                            'price': price,
                            'amount': calculated_amount,
                            'gross_wt': gross_wt,
                            'loss_wt': loss_wt,
                            'metal_rate': metal_rate,
                            'description': description,
                            'purity': purity,
                            'cgst_rate': cgst_rate,
                            'sgst_rate': sgst_rate,
                            'hsn': hsn,
                            'making_charge': making_charge,
                            'making_charge_type': making_charge_type,
                            'stone_weight': stone_weight,
                            'stone_charge': stone_charge,
                            'wastage_percentage': wastage_percentage,
                            'product_id': None
                        }
                        st.session_state.purchase_items.append(new_item)
                        st.success(f"Added {qty} {metal} item(s) to purchase bill. Amount: ₹{calculated_amount:.2f}")

        # Display added items
        if st.session_state.purchase_items:
            st.subheader("Current Purchase Items")
            items_df = pd.DataFrame(st.session_state.purchase_items)
            display_cols = ['metal', 'description', 'qty', 'net_wt', 'metal_rate', 'price', 'amount',
                            'making_charge', 'stone_charge', 'wastage_percentage', 'cgst_rate', 'sgst_rate', 'hsn']
            st.dataframe(items_df[display_cols], use_container_width=True)

            # Calculate totals for display
            total_taxable_amount_ui = sum(item.get('amount', 0.0) for item in st.session_state.purchase_items)
            
            # Recalculate overall GST based on current form rates for display purposes
            cgst_rate_overall = st.session_state.get('purchase_cgst_rate_form', 1.5) # Use _form key
            sgst_rate_overall = st.session_state.get('purchase_sgst_rate_form', 1.5) # Use _form key

            total_cgst = total_taxable_amount_ui * (cgst_rate_overall / 100)
            total_sgst = total_taxable_amount_ui * (sgst_rate_overall / 100)
            
            grand_total_bill = total_taxable_amount_ui + total_cgst + total_sgst
            round_off = round(grand_total_bill) - grand_total_bill
            grand_total_bill_rounded = round(grand_total_bill)

            st.markdown("---")
            st.subheader("Payment Details")

            payment_input_col, summary_display_col = st.columns([0.6, 0.4])

            with payment_input_col:
                st.metric(label="Overall Grand Total (incl. GST)", value=f"₹{grand_total_bill_rounded:.2f}")

                st.markdown("---")
                st.write("#### Enter New Payment Breakdown")
                bcol1, bcol2, bcol3, bcol4 = st.columns(4)
                with bcol1:
                    cash_amount = st.number_input("Cash Amount", min_value=0.0, step=100.0, key="cash_amount_purchase")
                with bcol2:
                    online_amount = st.number_input("Online Amount", min_value=0.0, step=100.0, key="online_amount_purchase")
                with bcol3:
                    cheque_amount = st.number_input("Cheque Amount", min_value=0.0, step=100.0, key="cheque_amount_purchase")
                with bcol4:
                    upi_amount = st.number_input("UPI Amount", min_value=0.0, step=100.0, key="upi_amount_purchase")
                
                total_paid = cash_amount + online_amount + cheque_amount + upi_amount
                balance_amount = grand_total_bill_rounded - total_paid

                ccol1, ccol2 = st.columns(2)
                with ccol1:
                    payment_mode = st.selectbox("Overall Payment Mode", ["Cash", "Online", "Cheque", "UPI", "Other", "Mixed"], key="purchase_payment_mode_overall")
                with ccol2:
                    payment_other_info = st.text_input("Payment Details (e.g., Txn IDs, Cheque No.s)", key="purchase_payment_info")

            with summary_display_col:
                st.write("#### Purchase Summary")
                st.write(f"**Supplier:** {selected_customer_name}")
                st.write(f"**Items:** {len(st.session_state.purchase_items)}")
                st.write(f"Taxable Value: ₹{total_taxable_amount_ui:.2f}")
                
                summary_gst_col1, summary_gst_col2 = st.columns(2)
                with summary_gst_col1:
                    st.write(f"Total CGST: ₹{total_cgst:.2f}")
                with summary_gst_col2:
                    st.write(f"Total SGST: ₹{total_sgst:.2f}")
                
                st.metric(label="Grand Total (incl. GST)", value=f"₹{grand_total_bill_rounded:.2f}")
                st.metric(label="Total Paid", value=f"₹{total_paid:.2f}")
                st.metric(label="Balance Due", value=f"₹{balance_amount:.2f}", delta=f"₹{-balance_amount:.2f}" if balance_amount < 0 else None, delta_color="inverse")


            st.markdown("---")
            col_buttons = st.columns(2)
            with col_buttons[0]:
                if st.button("✅ Save Purchase", key="save_purchase_button", use_container_width=True):
                    if len(st.session_state.purchase_items) == 0:
                        st.error("Please add at least one item to the purchase.")
                    elif customer_id is None:
                        st.error("Please select a valid supplier.")
                    else:
                        invoice_id = generate_purchase_invoice_id()
                        purchase_date = datetime.now().isoformat() # Get current date for purchase_date

                        # Serialize purchase_items to JSON string before saving
                        purchase_items_json = json.dumps(st.session_state.purchase_items)

                        saved_invoice_id = save_purchase(
                            invoice_id,
                            customer_id,
                            total_taxable_amount_ui, # This is the taxable amount (pre-GST)
                            cheque_amount,
                            online_amount,
                            upi_amount,
                            cash_amount,
                            payment_mode, # Overall payment mode
                            payment_other_info,
                            purchase_date, # Pass the purchase date
                            purchase_items_json, # Pass the JSON string of purchase items
                            balance_amount # Re-add balance_amount as the 12th argument
                        )

                        if saved_invoice_id:
                            purchase_data = db_manager_instance.fetch_one("SELECT * FROM purchases WHERE invoice_id = ?", (saved_invoice_id,))
                            # When fetching, remember to json.loads() purchase_items_data if it's stored as JSON
                            # For now, we're fetching all columns, so purchase_items_data will be a list of tuples
                            # We need to ensure the generate_purchase_pdf function can handle the data structure
                            purchase_items_data_raw = db_manager_instance.fetch_all("SELECT * FROM purchase_items WHERE invoice_id = ?", (saved_invoice_id,))
                            
                            # If purchase_items are stored as a single JSON string in 'purchases' table,
                            # you'd need to fetch that specific column and parse it.
                            # For now, assuming 'purchase_items' table is still used for individual items.
                            # If 'purchase_items_data_raw' contains the JSON string, it needs parsing here.
                            # Example: purchase_items_data = json.loads(purchase_items_data_raw[0][idx_of_json_column])
                            # If purchase_items_data_raw is already a list of tuples, no change needed here.


                            if purchase_data and purchase_items_data_raw: # Use purchase_items_data_raw for now
                                pdf_content, filename = generate_purchase_pdf(
                                    customer_details, # Supplier details
                                    purchase_data,
                                    purchase_items_data_raw, # Pass the raw fetched data
                                    download=True
                                )

                                st.success(f"Purchase saved successfully! Invoice ID: {saved_invoice_id}")
                                st.download_button(
                                    label="⬇️ Download Purchase Invoice PDF",
                                    data=pdf_content,
                                    file_name=filename,
                                    mime="application/pdf",
                                    key=f"download_purchase_pdf_{saved_invoice_id}",
                                    use_container_width=True
                                )
                                st.session_state.purchase_items = []
                                #st.rerun()
                            else:
                                st.error("Error retrieving purchase details after saving.")
                        else:
                            st.error("Error saving purchase. Please try again.")

            with col_buttons[1]:
                if st.button("🗑️ Clear Purchase Form", key="clear_purchase_form_button", use_container_width=True):
                    st.session_state.purchase_items = []
                    st.rerun()
