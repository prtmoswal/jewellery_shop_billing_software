import streamlit as st
import pandas as pd
from datetime import datetime

# Import necessary utility functions
from utils.config import DATABASE_NAME # Only for DBManager, not direct use
from utils.fetch_customers import fetch_all_customers, add_new_customer, get_customer_details
from utils.invoice_id_creation import generate_sales_invoice_id
from utils.save_sale import save_sale
from utils.get_pending_udhaar_sale import get_pending_udhaar
from utils.get_pending_purchase_udhaar import get_pending_purchase_udhaar
from utils.generate_sell_pdf import generate_sell_pdf
from utils.get_download_link import get_download_link
from utils.db_manager import DBManager # Import DBManager for specific fetches if needed

def sell_section():
    st.title("🛍️ Sell Jewellery") # Changed to title for more prominence

    # Initialize DBManager
    db_manager_instance = DBManager(DATABASE_NAME)

    # --- Customer Selection Section ---
    st.subheader("Customer Information")
    customer_col1, customer_col2 = st.columns([0.7, 0.3])

    with customer_col1:
        customers = fetch_all_customers()
        customer_options = ["Select Customer"] + list(customers.values())
        selected_customer_name = st.selectbox("Select Existing Customer", customer_options, key="sell_customer")

    customer_id = None
    customer_details = {}
    pending_udhaar_for_customer = 0.0
    pending_purchase_udhaar_for_customer = 0.0

    if selected_customer_name == "Select Customer":
        with customer_col2:
            st.write("Or Add New Customer")
            add_new_customer_button = st.button("➕ Add New Customer", key="show_add_customer_form")

        if add_new_customer_button:
            with st.expander("Enter New Customer Details", expanded=True):
                col1, col2, col3 = st.columns(3)
                name = col1.text_input("Customer Name", key="add_sell_customer_name")
                phone = col1.text_input("Phone Number", key="add_sell_customer_phone")
                address = col3.text_input("Address", key="add_sell_customer_address")
                pan = col2.text_input("PAN (Optional)", key="add_sell_customer_pan")
                aadhaar = col2.text_input("Aadhaar (Optional)", key="add_sell_customer_aadhaar")
                alternate_phone = col3.text_input("Alternate Phone", key="add_sell_customer_alternate_phone")
                alternate_phone2 = col1.text_input("Alternate Phone2", key="add_sell_customer_alternate_phone2")
                landline_phone = col2.text_input("Landline Phone", key="add_sell_customer_landline_phone")

                if st.button("💾 Save New Customer", key="add_sell_customer_button"):
                    if name and phone:
                        success = add_new_customer(name, phone, address, pan, aadhaar, alternate_phone, alternate_phone2, landline_phone)
                        if success:
                            st.success(f"Customer '{name}' added successfully! Please select from the dropdown.")
                            st.rerun()
                        else:
                            st.error(f"Failed to add customer '{name}'.")
                    else:
                        st.error("Customer name and phone number are required!")
    else:
        customer_id = [k for k, v in customers.items() if v == selected_customer_name][0]
        customer_details = get_customer_details(customer_id)

        st.markdown("---")
        st.subheader("Selected Customer Details")
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
        st.subheader("Customer Balances")
        pending_udhaar_for_customer = get_pending_udhaar(customer_id)
        pending_purchase_udhaar_for_customer = get_pending_purchase_udhaar(customer_id)

        balance_col1, balance_col2 = st.columns(2)
        balance_col1.metric(label="Customer's Pending Sale Amount (Owed to you)", value=f"₹{pending_udhaar_for_customer:.2f}")
        balance_col2.metric(label="Your Pending Purchase Amount (You owe them)", value=f"₹{pending_purchase_udhaar_for_customer:.2f}")

        # Debug print to console (can be removed in production)
        # print(f"Debug: Pending sale udhaar for customer {customer_id} ({selected_customer_name}): {pending_udhaar_for_customer}")
        # print(f"Debug: Pending purchase udhaar for customer {customer_id} ({selected_customer_name}): {pending_purchase_udhaar_for_customer}")

        st.markdown("---")
        st.subheader("Add Sale Items")

        if 'sale_items' not in st.session_state:
            st.session_state.sale_items = []

        with st.form("add_sale_item_form", clear_on_submit=True): # clear_on_submit set to True
            item_col1, item_col2, item_col3 = st.columns(3)
            with item_col1:
                metal = st.selectbox("Metal", ["Gold", "Silver", "Platinum", "Diamond", "Other"], key="sale_metal_form")
                purity = st.text_input("Purity (e.g., 24K, 92.5%)", key="sale_purity_form")
                description = st.text_area("Description", key="sale_description_form")
            with item_col2:
                qty = st.number_input("Quantity", min_value=1, step=1, key="sale_qty_form")
                gross_wt = st.number_input("Gross Weight (grams)", min_value=0.0, step=0.1, format="%.3f", key="sale_gross_wt_form")
                loss_wt = st.number_input("Loss Weight (grams)", min_value=0.0, step=0.001, format="%.3f", key="sale_loss_wt_form")
            with item_col3:
                net_wt = gross_wt - loss_wt
                st.info(f"**Net Weight (grams): {net_wt:.3f}**") # Changed to st.info for prominence
                metal_rate = st.number_input("Metal Rate per gram", min_value=0.0, step=10.0, key="sale_metal_rate_form")
                amount = st.number_input("Total Item Amount (before GST)", min_value=0.0, step=100.0, key="sale_item_amount_form")

            st.markdown("---")
            tax_col1, tax_col2, tax_col3, tax_col4 = st.columns(4)
            with tax_col1:
                making_charge = st.number_input("Making Charge", min_value=0.0, step=1.0, key="sale_making_charge_form")
                wastage_percentage = st.number_input("Wastage Percentage (%)", min_value=0.0, max_value=100.0, step=0.1, format="%.2f", key="sale_wastage_percentage_form")
            with tax_col2:
                making_charge_type = st.selectbox("Making Charge Type", ["fixed", "per_gram", "percentage"], key="sale_making_charge_type_form")
                cgst_rate = st.number_input("CGST Rate (%)", min_value=0.0, max_value=100.0, step=0.1, format="%.2f", value=1.5, key="sale_cgst_rate_form")
            with tax_col3:
                stone_weight = st.number_input("Stone Weight (carats)", min_value=0.0, step=0.01, format="%.2f", key="sale_stone_weight_form")
                sgst_rate = st.number_input("SGST Rate (%)", min_value=0.0, max_value=100.0, step=0.1, format="%.2f", value=1.5, key="sale_sgst_rate_form")
            with tax_col4:
                stone_charge = st.number_input("Stone Charge", min_value=0.0, step=1.0, key="sale_stone_charge_form")
                hsn = st.text_input("HSN Code", value="7113", key="sale_hsn_form")

            add_item = st.form_submit_button("➕ Add Item to Sale")

            if add_item:
                if (net_wt <= 0 and amount <= 0) or (metal_rate <= 0 and amount == 0):
                    st.error("Please fill Net Weight/Metal Rate and Total Item Amount with valid values.")
                else:
                    calculated_amount = amount
                    if metal_rate > 0 and net_wt > 0 and amount == 0:
                        calculated_amount = net_wt * metal_rate

                    calculated_making_charge = 0.0
                    if making_charge_type == "fixed":
                        calculated_making_charge = making_charge
                    elif making_charge_type == "per_gram":
                        calculated_making_charge = making_charge * net_wt
                    elif making_charge_type == "percentage":
                        calculated_making_charge = calculated_amount * (making_charge / 100.0)

                    wastage_amount = calculated_amount * (wastage_percentage / 100.0)

                    # Subtotal before GST (Amount + Making Charge + Stone Charge + Wastage)
                    subtotal_before_gst = calculated_amount + calculated_making_charge + stone_charge + wastage_amount

                    # Calculate GST
                    total_gst_rate = cgst_rate + sgst_rate
                    gst_amount = subtotal_before_gst * (total_gst_rate / 100.0)

                    # Total amount for the item including GST
                    item_total_with_gst = subtotal_before_gst + gst_amount

                    if item_total_with_gst <= 0:
                        st.error("Calculated item amount must be greater than zero. Adjust inputs.")
                    else:
                        new_item = {
                            'metal': metal,
                            'qty': qty,
                            'net_wt': net_wt,
                            'metal_rate': metal_rate,
                            'description': description,
                            'purity': purity,
                            'gross_wt': gross_wt,
                            'loss_wt': loss_wt,
                            'making_charge': calculated_making_charge,
                            'making_charge_type': making_charge_type,
                            'stone_weight': stone_weight,
                            'stone_charge': stone_charge,
                            'wastage_percentage': wastage_percentage,
                            'wastage_amount': wastage_amount,
                            'amount': calculated_amount,
                            'cgst_rate': cgst_rate,
                            'sgst_rate': sgst_rate,
                            'gst_amount': gst_amount,
                            'item_total_with_gst': item_total_with_gst,
                            'hsn': hsn,
                            'product_id': None
                        }
                        st.session_state.sale_items.append(new_item)
                        st.success(f"Added {qty} {metal} item(s) to sale bill. Total for item: ₹{item_total_with_gst:.2f}")
                        # No rerun here, let the form clear and item list update

        # Display added items
        if st.session_state.sale_items:
            st.subheader("Current Sale Items")
            items_df = pd.DataFrame(st.session_state.sale_items)
            display_cols = ['metal', 'description', 'qty', 'net_wt', 'metal_rate', 'amount',
                            'making_charge', 'stone_charge', 'wastage_amount', 'gst_amount', 'item_total_with_gst']
            st.dataframe(items_df[display_cols], use_container_width=True)

            grand_total_sale_amount = sum(item['item_total_with_gst'] for item in st.session_state.sale_items)

            st.markdown("---")
            st.subheader("Payment Details")

            payment_input_col, summary_display_col = st.columns([0.6, 0.4])

            with payment_input_col:
                st.metric(label="Overall Grand Total (incl. GST)", value=f"₹{grand_total_sale_amount:.2f}")

                # Option to use pending purchase amount
                use_pending_purchase_amount = False
                applied_purchase_udhaar = 0.0
                if pending_purchase_udhaar_for_customer > 0:
                    use_pending_purchase_amount = st.checkbox(
                        f"Apply Pending Purchase Amount (₹{pending_purchase_udhaar_for_customer:.2f}) from supplier balance",
                        key="apply_pending_purchase"
                    )
                    if use_pending_purchase_amount:
                        applied_purchase_udhaar = min(pending_purchase_udhaar_for_customer, grand_total_sale_amount)
                        st.info(f"₹{applied_purchase_udhaar:.2f} of purchase balance will be applied.")

                st.markdown("---")
                st.write("#### Enter New Payment Breakdown")
                bcol1, bcol2, bcol3, bcol4 = st.columns(4)
                with bcol1:
                    cash_amount = st.number_input("Cash Amount", min_value=0.0, step=100.0, key="cash_amount_sale")
                with bcol2:
                    online_amount = st.number_input("Online Amount", min_value=0.0, step=100.0, key="online_amount_sale")
                with bcol3:
                    cheque_amount = st.number_input("Cheque Amount", min_value=0.0, step=100.0, key="cheque_amount_sale")
                with bcol4:
                    upi_amount = st.number_input("UPI Amount", min_value=0.0, step=100.0, key="upi_amount_sale")

                new_payment_total = cash_amount + online_amount + cheque_amount + upi_amount
                old_gold_amount = st.number_input("Old Gold Amount", min_value=0.0, step=100.0, key="old_gold_amount")

                total_received_from_customer = new_payment_total + old_gold_amount + applied_purchase_udhaar
                amount_balance = grand_total_sale_amount - total_received_from_customer

                ccol1, ccol2 = st.columns(2)
                with ccol1:
                    payment_mode = st.selectbox("Overall Payment Mode", ["Cash", "Online", "Cheque", "UPI", "Other", "Mixed"], key="sale_payment_mode")
                with ccol2:
                    payment_other_info = st.text_input("Payment Details (e.g., Txn IDs, Cheque No.s)", key="sale_payment_info")

            with summary_display_col:
                st.write("#### Sale Summary")
                st.write(f"**Customer:** {selected_customer_name}")
                st.write(f"**Items:** {len(st.session_state.sale_items)}")
                st.metric(label="Total Received", value=f"₹{total_received_from_customer:.2f}")
                st.metric(label="Balance Outstanding", value=f"₹{amount_balance:.2f}", delta=f"₹{-amount_balance:.2f}" if amount_balance < 0 else None, delta_color="inverse")
                
                st.markdown("---")
                st.write("**Payment Breakdown:**")
                st.write(f"Cash: ₹{cash_amount:.2f}")
                st.write(f"Online: ₹{online_amount:.2f}")
                st.write(f"Cheque: ₹{cheque_amount:.2f}")
                st.write(f"UPI: ₹{upi_amount:.2f}")
                st.write(f"Old Gold: ₹{old_gold_amount:.2f}")
                if use_pending_purchase_amount:
                    st.write(f"Applied Purchase Udhaar: ₹{applied_purchase_udhaar:.2f}")


            st.markdown("---")
            col_buttons = st.columns(2)
            with col_buttons[0]:
                if st.button("✅ Save Sale", key="save_sale_button", use_container_width=True):
                    if len(st.session_state.sale_items) == 0:
                        st.error("Please add at least one item to the sale.")
                    elif customer_id is None:
                        st.error("Please select a valid customer.")
                    else:
                        invoice_id = generate_sales_invoice_id()
                        sale_date = datetime.now().isoformat()

                        saved_invoice_id = save_sale(
                            invoice_id,
                            customer_id,
                            grand_total_sale_amount,
                            cheque_amount,
                            online_amount,
                            upi_amount,
                            cash_amount,
                            old_gold_amount,
                            amount_balance,
                            payment_mode,
                            payment_other_info,
                            sale_date,
                            st.session_state.sale_items,
                            applied_purchase_udhaar
                        )

                        if saved_invoice_id:
                            sale_data = db_manager_instance.fetch_one("SELECT * FROM sales WHERE invoice_id = ?", (saved_invoice_id,))
                            sale_items_data = db_manager_instance.fetch_all("SELECT * FROM sale_items WHERE invoice_id = ?", (saved_invoice_id,))

                            if sale_data and sale_items_data:
                                pdf_content, filename = generate_sell_pdf(
                                    customer_details,
                                    sale_data,
                                    sale_items_data,
                                    download=True
                                )

                                st.success(f"Sale saved successfully! Invoice ID: {saved_invoice_id}")
                                st.download_button(
                                    label="⬇️ Download Sale Invoice PDF",
                                    data=pdf_content,
                                    file_name=filename,
                                    mime="application/pdf",
                                    key=f"download_sale_pdf_{saved_invoice_id}",
                                    use_container_width=True
                                )
                                st.session_state.sale_items = []
                                #st.rerun()
                            else:
                                st.error("Error retrieving sale details after saving.")
                        else:
                            st.error("Error saving sale. Please try again.")

            with col_buttons[1]:
                if st.button("🗑️ Clear Sale Form", key="clear_sale_form_button", use_container_width=True):
                    st.session_state.sale_items = []
                    st.rerun()
