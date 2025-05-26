import streamlit as st
import sqlite3
from utils.config import DATABASE_NAME, BILLS_FOLDER
from utils.fetch_customers import get_customer_details_for_update, get_all_customer_names, fetch_all_customers, update_customer, add_new_customer, get_customer_details
from datetime import datetime
import pandas as pd
from utils.invoice_id_creation import generate_udhaar_invoice_id, generate_purchase_invoice_id, generate_sales_invoice_id, get_next_invoice_number
from utils.save_sale import save_sale
from utils.get_pending_udhaar_sale import get_pending_udhaar, get_sale_details, get_all_pending_udhaar # Added get_all_pending_udhaar
from utils.generate_sell_pdf import generate_sell_pdf
from utils.get_download_link import get_download_link
from utils.load_and_display_pdf import load_and_display_pdf
from utils.db_manager import DBManager # Import DBManager

def reports_section():
    st.header("Reports & Analytics")
    
    report_type = st.selectbox("Select Report Type", [
        "Daily Sales Report", 
        "Monthly Sales Report", 
        "Inventory Value Report", 
        "Top Customers",
        "Outstanding Balances"
    ])
    
    db = DBManager(DATABASE_NAME) # Initialize DBManager once for the section

    if report_type == "Daily Sales Report":
        selected_date = st.date_input("Select Date", value=datetime.now().date())
        date_str = selected_date.strftime('%Y-%m-%d')
        
        # Get daily sales
        # Changed s.date to s.sale_date as per schema
        sales = db.fetch_all("""
            SELECT s.invoice_id, c.name, s.total_amount, s.old_gold_amount, s.amount_balance, s.payment_mode
            FROM sales s
            JOIN customers c ON s.customer_id = c.customer_id
            WHERE s.sale_date LIKE ? -- Use LIKE for date string matching
            ORDER BY s.invoice_id
        """, (f"{date_str}%",)) # Use % to match any time part of the date

        if sales:
            sales_df = pd.DataFrame(sales, columns=["Invoice ID", "Customer", "Total Amount", "Old Gold Amount", "Balance", "Payment Mode"])
            
            # Calculate totals
            total_sales = sales_df["Total Amount"].sum()
            total_old_gold = sales_df["Old Gold Amount"].sum()
            total_balance = sales_df["Balance"].sum()
            total_received = total_sales - total_balance
            
            st.subheader(f"Sales for {date_str}")
            st.dataframe(sales_df)
            
            # Summary
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Total Sales", f"{total_sales:.2f}")
            col2.metric("Old Gold", f"{total_old_gold:.2f}")
            col3.metric("Received", f"{total_received:.2f}")
            col4.metric("Balance", f"{total_balance:.2f}")
        else:
            st.info(f"No sales found for {date_str}")
        
        # Get daily purchases
        # Changed p.date to p.purchase_date as per schema
        purchases = db.fetch_all("""
            SELECT p.invoice_id, c.name, p.total_amount, p.payment_mode
            FROM purchases p
            JOIN customers c ON p.supplier_id = c.customer_id -- Join on supplier_id
            WHERE p.purchase_date LIKE ? -- Use LIKE for date string matching
            ORDER BY p.invoice_id
        """, (f"{date_str}%",))
        
        if purchases:
            purchases_df = pd.DataFrame(purchases, columns=["Invoice ID", "Supplier", "Total Amount", "Payment Mode"])
            
            # Calculate totals
            total_purchases = purchases_df["Total Amount"].sum()
            
            st.subheader(f"Purchases for {date_str}")
            st.dataframe(purchases_df)
            
            # Summary
            st.metric("Total Purchases", f"{total_purchases:.2f}")
        else:
            st.info(f"No purchases found for {date_str}")
    
    elif report_type == "Monthly Sales Report":
        current_year = datetime.now().year
        current_month = datetime.now().month
        
        year = st.selectbox("Select Year", list(range(current_year-5, current_year+1)), index=5)
        month = st.selectbox("Select Month", list(range(1, 13)), index=current_month-1)
        
        # Format month for filtering
        month_str = f"{year}-{month:02d}"
        
        # Get monthly sales
        # Changed s.date to s.sale_date as per schema
        sales = db.fetch_all("""
            SELECT s.sale_date, COUNT(s.invoice_id) as count, SUM(s.total_amount) as total,
                   SUM(s.old_gold_amount) as old_gold, SUM(s.amount_balance) as balance
            FROM sales s
            WHERE s.sale_date LIKE ?
            GROUP BY s.sale_date
            ORDER BY s.sale_date
        """, (f"{month_str}%",))
        
        if sales:
            sales_df = pd.DataFrame(sales, columns=["Date", "Number of Sales", "Total Amount", "Old Gold Amount", "Balance"])
            
            # Calculate totals
            total_sales = sales_df["Total Amount"].sum()
            total_old_gold = sales_df["Old Gold Amount"].sum()
            total_balance = sales_df["Balance"].sum()
            total_received = total_sales - total_balance
            
            st.subheader(f"Sales for {month_str}")
            st.dataframe(sales_df)
            
            # Summary
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Total Sales", f"{total_sales:.2f}")
            col2.metric("Old Gold", f"{total_old_gold:.2f}")
            col3.metric("Received", f"{total_received:.2f}")
            col4.metric("Balance", f"{total_balance:.2f}")
            
            # Chart
            st.subheader("Daily Sales Chart")
            st.line_chart(sales_df.set_index("Date")["Total Amount"])
        else:
            st.info(f"No sales found for {month_str}")
        
        # Get monthly purchases
        # Changed p.date to p.purchase_date as per schema
        purchases = db.fetch_all("""
            SELECT p.purchase_date, COUNT(p.invoice_id) as count, SUM(p.total_amount) as total
            FROM purchases p
            WHERE p.purchase_date LIKE ?
            GROUP BY p.purchase_date
            ORDER BY p.purchase_date
        """, (f"{month_str}%",))
        
        if purchases:
            purchases_df = pd.DataFrame(purchases, columns=["Date", "Number of Purchases", "Total Amount"])
            
            # Calculate totals
            total_purchases = purchases_df["Total Amount"].sum()
            
            st.subheader(f"Purchases for {month_str}")
            st.dataframe(purchases_df)
            
            # Summary
            st.metric("Total Purchases", f"{total_purchases:.2f}")
        else:
            st.info(f"No purchases found for {month_str}")
    
    elif report_type == "Inventory Value Report":
        st.info("This report provides an estimated inventory value based on sales and purchases.")
        
        # Get all sale items
        sold_items_raw = db.fetch_all("""
            SELECT si.metal, SUM(si.net_wt) as total_weight
            FROM sale_items si
            GROUP BY si.metal
        """)
        sold_items = {metal: weight for metal, weight in sold_items_raw}
        
        # Get all purchase items
        purchased_items_raw = db.fetch_all("""
            SELECT pi.metal, SUM(pi.net_wt) as total_weight
            FROM purchase_items pi
            GROUP BY pi.metal
        """)
        purchased_items = {metal: weight for metal, weight in purchased_items_raw}
        
        # Current metal rates
        gold_rate = st.number_input("Current Gold Rate (per 10g)", min_value=0.0, step=100.0, value=60000.0)
        silver_rate = st.number_input("Current Silver Rate (per 10g)", min_value=0.0, step=100.0, value=8000.0)
        
        # Calculate inventory
        gold_inventory = (purchased_items.get('Gold', 0) - sold_items.get('Gold', 0))
        silver_inventory = (purchased_items.get('Silver', 0) - sold_items.get('Silver', 0))
        
        # Create report
        inventory_data = {
            "Metal": ["Gold", "Silver"],
            "Purchased (g)": [purchased_items.get('Gold', 0), purchased_items.get('Silver', 0)],
            "Sold (g)": [sold_items.get('Gold', 0), sold_items.get('Silver', 0)],
            "Inventory (g)": [gold_inventory, silver_inventory],
            "Rate (per 10g)": [gold_rate, silver_rate],
            "Value": [gold_inventory * gold_rate / 10, silver_inventory * silver_rate / 10]
        }
        
        inventory_df = pd.DataFrame(inventory_data)
        
        st.subheader("Inventory Summary")
        st.dataframe(inventory_df)
        
        # Total inventory value
        total_value = inventory_df["Value"].sum()
        st.metric("Total Inventory Value", f"{total_value:.2f}")
    
    elif report_type == "Top Customers":
        # Get top customers by sales
        top_customers = db.fetch_all("""
            SELECT c.name, COUNT(s.invoice_id) as sales_count, SUM(s.total_amount) as total_sales
            FROM sales s
            JOIN customers c ON s.customer_id = c.customer_id
            GROUP BY s.customer_id
            ORDER BY total_sales DESC
            LIMIT 10
        """)
        
        if top_customers:
            top_df = pd.DataFrame(top_customers, columns=["Customer", "Number of Sales", "Total Sales"])
            
            st.subheader("Top 10 Customers by Sales")
            st.dataframe(top_df)
            
            # Chart
            st.bar_chart(top_df.set_index("Customer")["Total Sales"])
        else:
            st.info("No customer data available.")
    
    elif report_type == "Outstanding Balances":
        # Get all outstanding balances
        # Changed u.pending_amount to u.current_balance as per schema
        # Changed s.date to s.sale_date as per schema
        balances = db.fetch_all("""
            SELECT c.name, u.sell_invoice_id, s.sale_date, u.current_balance
            FROM udhaar u
            JOIN customers c ON u.customer_id = c.customer_id
            JOIN sales s ON u.sell_invoice_id = s.invoice_id
            WHERE u.current_balance > 0 -- Only show truly pending
            ORDER BY u.current_balance DESC
        """)
        
        if balances:
            balances_df = pd.DataFrame(balances, columns=["Customer", "Invoice ID", "Date", "Pending Amount"])
            
            # Calculate total outstanding
            total_pending = balances_df["Pending Amount"].sum()
            
            st.subheader("Outstanding Balances")
            st.dataframe(balances_df)
            
            # Summary
            st.metric("Total Outstanding", f"{total_pending:.2f}")
            
            # Group by customer
            customer_totals = balances_df.groupby("Customer")["Pending Amount"].sum().reset_index()
            customer_totals = customer_totals.sort_values("Pending Amount", ascending=False)
            
            st.subheader("Outstanding by Customer")
            st.dataframe(customer_totals)
            
            # Chart
            st.bar_chart(customer_totals.set_index("Customer")["Pending Amount"])
        else:
            st.info("No outstanding balances.")
