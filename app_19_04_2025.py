import streamlit as st
import pandas as pd
import sqlite3
import os
import base64
from datetime import datetime
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import io

# --- Page Configuration ---
st.set_page_config(
    page_title="Jewellery Shop Management",
    page_icon="💎",
    layout="wide",
    initial_sidebar_state="expanded",
)

# --- Database Setup ---
DATABASE_NAME = 'jewellery_app.db'
BILLS_FOLDER = 'bills'

# Create bills directory structure
def create_bills_directory():
    os.makedirs(BILLS_FOLDER, exist_ok=True)
    today_date = datetime.now().strftime('%Y-%m-%d')
    daily_folder = os.path.join(BILLS_FOLDER, today_date)
    os.makedirs(daily_folder, exist_ok=True)
    return daily_folder

daily_bills_folder = create_bills_directory()

def create_tables():
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    # Customers Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS customers (
            customer_id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            phone TEXT UNIQUE,
            address TEXT,
            pan TEXT,
            aadhaar TEXT
        )
    ''')
    # Sales Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sales (
            invoice_id TEXT PRIMARY KEY,
            date TEXT NOT NULL,
            customer_id INTEGER NOT NULL,
            total_amount REAL NOT NULL,
            old_gold_amount REAL DEFAULT 0.0,
            amount_balance REAL NOT NULL,
            payment_mode TEXT,
            payment_other_info TEXT
        )
    ''')
    # Sale Items Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sale_items (
            item_id INTEGER PRIMARY KEY AUTOINCREMENT,
            invoice_id TEXT NOT NULL,
            metal TEXT NOT NULL,
            metal_rate REAL NOT NULL,
            description TEXT NOT NULL,
            qty INTEGER NOT NULL,
            net_wt REAL NOT NULL,
            purity TEXT,
            amount REAL NOT NULL,
            cgst_rate REAL DEFAULT 1.5,
            sgst_rate REAL DEFAULT 1.5,
            hsn TEXT DEFAULT '7113'
        )
    ''')
    # Purchases Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS purchases (
            invoice_id TEXT PRIMARY KEY,
            date TEXT NOT NULL,
            customer_id INTEGER NOT NULL, -- Customer acting as supplier
            total_amount REAL NOT NULL,
            payment_mode TEXT,
            payment_other_info TEXT
        )
    ''')
    # Purchase Items Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS purchase_items (
            item_id INTEGER PRIMARY KEY AUTOINCREMENT,
            invoice_id TEXT NOT NULL,
            metal TEXT NOT NULL,
            qty INTEGER NOT NULL,
            net_wt REAL NOT NULL,
            price REAL NOT NULL,
            amount REAL NOT NULL
        )
    ''')
    # Udhaar (Pending Amounts) Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS udhaar (
            udhaar_id INTEGER PRIMARY KEY AUTOINCREMENT,
            sell_invoice_id TEXT NOT NULL,
            customer_id INTEGER NOT NULL,
            pending_amount REAL NOT NULL
        )
    ''')
    # Udhaar Deposits Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS udhaar_deposits (
            deposit_invoice_id TEXT PRIMARY KEY,
            sell_invoice_id TEXT NOT NULL,
            date TEXT NOT NULL,
            customer_id INTEGER NOT NULL,
            deposit_amount REAL NOT NULL,
            remaining_amount REAL NOT NULL,
            payment_mode TEXT,
            payment_other_info TEXT
        )
    ''')
    conn.commit()
    conn.close()

create_tables()

# --- Helper Functions for Database Operations ---
def fetch_all_customers():
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT customer_id, name FROM customers")
    customers = cursor.fetchall()
    conn.close()
    return {cust_id: name for cust_id, name in customers}

def add_new_customer(name, phone, address="", pan="", aadhaar=""):
    # Input validation
    if not name or not phone:
        st.error("Customer name and phone number are required!")
        return None
    
    # Phone number validation (basic - can be extended)
    if not phone.isdigit() or len(phone) < 10:
        st.error("Please enter a valid phone number (at least 10 digits)")
        return None
    
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO customers (name, phone, address, pan, aadhaar) VALUES (?, ?, ?, ?, ?)",
                       (name, phone, address, pan, aadhaar))
        conn.commit()
        customer_id = cursor.lastrowid
        conn.close()
        st.success(f"Customer '{name}' added successfully with ID: {customer_id}")
        return customer_id
    except sqlite3.IntegrityError:
        st.error(f"Phone number '{phone}' already exists.")
        conn.close()
        return None
    except Exception as e:
        st.error(f"Error adding customer: {str(e)}")
        conn.close()
        return None
        
def get_next_invoice_number(sequence_name):
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    next_number = -1
    try:
        # Check if the table exists and create it if not
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS invoice_sequences (
                sequence_name TEXT PRIMARY KEY,
                next_value INTEGER NOT NULL DEFAULT 1
            )
        """)
        # Insert the sequence name if it doesn't exist
        cursor.execute("INSERT OR IGNORE INTO invoice_sequences (sequence_name, next_value) VALUES (?, 1)", (sequence_name,))

        cursor.execute(
            "UPDATE invoice_sequences SET next_value = next_value + 1 WHERE sequence_name = ? RETURNING next_value",
            (sequence_name,)
        )
        result = cursor.fetchone()
        if result:
            next_number = result[0]
        conn.commit()
    except sqlite3.Error as e:
        conn.rollback()
        print(f"Error getting next invoice number for {sequence_name}: {e}")
    finally:
        conn.close()
    return next_number

def generate_sales_invoice_id(metal):
    next_number = get_next_invoice_number('sales')
    if metal=='Gold':
        if next_number != -1:
            year_suffix = datetime.now().strftime('%y%m') # Example year-month suffix
            return f"IG-{year_suffix}-{next_number:04d}" # Example format with leading zeros
    if metal=='Silver':
        if next_number != -1:
            year_suffix = datetime.now().strftime('%y%m') # Example year-month suffix
            return f"IG-{year_suffix}-{next_number:04d}" # Example format with leading zeros
    else:
        return "INV-ERROR"

def generate_purchase_invoice_id():
    next_number = get_next_invoice_number('purchase')
    if next_number != -1:
        year_suffix = datetime.now().strftime('%y%m')
        return f"IP-{year_suffix}-{next_number:04d}"
    else:
        return "IP-ERROR"

def generate_udhaar_invoice_id():
    next_number = get_next_invoice_number('udhaar_deposit')
    if next_number != -1:
        year_suffix = datetime.now().strftime('%y%m')
        return f"UD-{year_suffix}-{next_number:04d}"
    else:
        return "UD-ERROR"

def save_sale(customer_id, total_amount, old_gold_amount, amount_balance, payment_mode, payment_other_info, sale_items_data):
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
    
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    try:
        invoice_id = generate_sales_invoice_id(sale_items_data[0]['metal'] if sale_items_data else 'Gold')
        date = datetime.now().strftime('%Y-%m-%d')
        cursor.execute("INSERT INTO sales (invoice_id, date, customer_id, total_amount, old_gold_amount, amount_balance, payment_mode, payment_other_info) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                      (invoice_id, date, customer_id, total_amount, old_gold_amount, amount_balance, payment_mode, payment_other_info))
        
        for item in sale_items_data:
            taxable_amount = item['amount']
            cgst = taxable_amount * item.get('cgst_rate', 0.015)
            sgst = taxable_amount * item.get('sgst_rate', 0.015)
            cursor.execute('''
                INSERT INTO sale_items (invoice_id, metal, metal_rate, description, qty, net_wt, purity, amount, cgst_rate, sgst_rate, hsn)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (invoice_id, item['metal'], item['metal_rate'], item['description'], item['qty'], item['net_wt'], item['purity'], item['amount'], item.get('cgst_rate', 0.015), item.get('sgst_rate', 0.015), item.get('hsn', '7113')))
        
        if amount_balance > 0:
            cursor.execute("INSERT INTO udhaar (sell_invoice_id, customer_id, pending_amount) VALUES (?, ?, ?)",
                          (invoice_id, customer_id, amount_balance))
        
        conn.commit()
        return invoice_id
    except Exception as e:
        conn.rollback()
        st.error(f"Error saving sale: {str(e)}")
        return None
    finally:
        conn.close()

def save_purchase(customer_id, total_amount, payment_mode, payment_other_info, purchase_items_data):
    # Validation
    if not customer_id:
        st.error("Customer/Supplier is required for purchase!")
        return None
    
    if not purchase_items_data:
        st.error("At least one purchase item is required!")
        return None
    
    if total_amount <= 0:
        st.error("Total amount must be greater than zero!")
        return None
    
    # Validate each item has required fields
    for item in purchase_items_data:
        if not all(key in item for key in ['metal', 'qty', 'net_wt', 'price', 'amount']):
            st.error("All item details are required (metal, quantity, weight, price, amount)")
            return None
        
        if item['qty'] <= 0 or item['net_wt'] <= 0 or item['price'] <= 0 or item['amount'] <= 0:
            st.error("Quantity, weight, price, and amount must be greater than zero!")
            return None
    
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    try:
        invoice_id = generate_purchase_invoice_id()
        date = datetime.now().strftime('%Y-%m-%d')
        cursor.execute("INSERT INTO purchases (invoice_id, date, customer_id, total_amount, payment_mode, payment_other_info) VALUES (?, ?, ?, ?, ?, ?)",
                      (invoice_id, date, customer_id, total_amount, payment_mode, payment_other_info))
        
        for item in purchase_items_data:
            cursor.execute('''
                INSERT INTO purchase_items (invoice_id, metal, qty, net_wt, price, amount)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (invoice_id, item['metal'], item['qty'], item['net_wt'], item['price'], item['amount']))
        
        conn.commit()
        return invoice_id
    except Exception as e:
        conn.rollback()
        st.error(f"Error saving purchase: {str(e)}")
        return None
    finally:
        conn.close()

def get_customer_details(customer_id):
    if not customer_id:
        return {}
    
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT name, address, phone, pan, aadhaar FROM customers WHERE customer_id = ?", (customer_id,))
        details = cursor.fetchone()
        if details:
            return {"name": details[0], "address": details[1], "phone": details[2], "pan": details[3], "aadhaar": details[4]}
        return {}
    except Exception as e:
        st.error(f"Error fetching customer details: {str(e)}")
        return {}
    finally:
        conn.close()

def get_pending_udhaar(customer_id):
    if not customer_id:
        return pd.DataFrame(columns=['Invoice ID', 'Date', 'Total Bill Amount', 'Pending Amount'])
    
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    try:
        cursor.execute('''
            SELECT u.sell_invoice_id, s.date, s.total_amount, u.pending_amount
            FROM udhaar u
            JOIN sales s ON u.sell_invoice_id = s.invoice_id
            WHERE u.customer_id = ?
        ''', (customer_id,))
        pending = cursor.fetchall()
        return pd.DataFrame(pending, columns=['Invoice ID', 'Date', 'Total Bill Amount', 'Pending Amount'])
    except Exception as e:
        st.error(f"Error fetching pending udhaar: {str(e)}")
        return pd.DataFrame(columns=['Invoice ID', 'Date', 'Total Bill Amount', 'Pending Amount'])
    finally:
        conn.close()

def get_sale_details(invoice_id):
    if not invoice_id:
        return None, None
    
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM sales WHERE invoice_id = ?", (invoice_id,))
        sale = cursor.fetchone()
        cursor.execute("SELECT * FROM sale_items WHERE invoice_id = ?", (invoice_id,))
        items = cursor.fetchall()
        return sale, items
    except Exception as e:
        st.error(f"Error fetching sale details: {str(e)}")
        return None, None
    finally:
        conn.close()

def save_udhaar_deposit(sell_invoice_id, customer_id, deposit_amount, payment_mode, payment_other_info):
    # Validation
    if not sell_invoice_id or not customer_id:
        st.error("Invoice ID and customer are required!")
        return None
    
    if deposit_amount <= 0:
        st.error("Deposit amount must be greater than zero!")
        return None
    
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    try:
        date = datetime.now().strftime('%Y-%m-%d')
        # Get current pending amount
        cursor.execute("SELECT pending_amount FROM udhaar WHERE sell_invoice_id = ? AND customer_id = ?", (sell_invoice_id, customer_id))
        result = cursor.fetchone()
        if result:
            current_pending = result[0]
            if deposit_amount > current_pending:
                st.error(f"Deposit amount ({deposit_amount}) exceeds pending amount ({current_pending})")
                conn.close()
                return None
                
            remaining_amount = current_pending - deposit_amount
            deposit_invoice_id = generate_udhaar_invoice_id()
            cursor.execute("INSERT INTO udhaar_deposits (deposit_invoice_id, sell_invoice_id, date, customer_id, deposit_amount, remaining_amount, payment_mode, payment_other_info) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                          (deposit_invoice_id, sell_invoice_id, date, customer_id, deposit_amount, remaining_amount, payment_mode, payment_other_info))
            
            # Update pending amount in udhaar table
            if remaining_amount <= 0:
                cursor.execute("DELETE FROM udhaar WHERE sell_invoice_id = ? AND customer_id = ?", (sell_invoice_id, customer_id))
            else:
                cursor.execute("UPDATE udhaar SET pending_amount = ? WHERE sell_invoice_id = ? AND customer_id = ?", (remaining_amount, sell_invoice_id, customer_id))
            
            conn.commit()
            st.success(f"Deposit of {deposit_amount} recorded for Invoice ID: {sell_invoice_id}. Remaining: {remaining_amount:.2f}")
            return deposit_invoice_id
        else:
            st.error("Pending invoice not found for this customer.")
            return None
    except Exception as e:
        conn.rollback()
        st.error(f"Error saving udhaar deposit: {str(e)}")
        return None
    finally:
        conn.close()

def delete_bill(invoice_id):
    if not invoice_id:
        st.error("Invoice ID is required for deletion!")
        return
    
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    try:
        # First check if the bill exists
        cursor.execute("SELECT invoice_id FROM sales WHERE invoice_id = ? UNION SELECT invoice_id FROM purchases WHERE invoice_id = ?", 
                       (invoice_id, invoice_id))
        if not cursor.fetchone():
            st.error(f"Bill with Invoice ID '{invoice_id}' not found.")
            conn.close()
            return
        
        cursor.execute("DELETE FROM sales WHERE invoice_id = ?", (invoice_id,))
        cursor.execute("DELETE FROM sale_items WHERE invoice_id = ?", (invoice_id,))
        cursor.execute("DELETE FROM purchases WHERE invoice_id = ?", (invoice_id,))
        cursor.execute("DELETE FROM purchase_items WHERE invoice_id = ?", (invoice_id,))
        cursor.execute("DELETE FROM udhaar WHERE sell_invoice_id = ?", (invoice_id,))
        cursor.execute("DELETE FROM udhaar_deposits WHERE sell_invoice_id = ?", (invoice_id,))
        conn.commit()
        st.success(f"Bill with Invoice ID '{invoice_id}' deleted.")
    except Exception as e:
        conn.rollback()
        st.error(f"Error deleting bill: {str(e)}")
    finally:
        conn.close()

# --- PDF Generation ---
def generate_sell_pdf(customer_details, sale_data, sale_items, download=False):
    # Get customer name for filename
    customer_name = customer_details.get("name", "customer").replace(" ", "_")
    invoice_id = sale_data[0].replace("/", "_") if sale_data else "unknown_invoice"
    filename = f"{customer_name}_{invoice_id}.pdf"
    file_path = os.path.join(daily_bills_folder, filename)
    
    # Create PDF
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=(210 * mm, 297 * mm * 0.75),
                          topMargin=45 * mm, bottomMargin=25 * mm, leftMargin=8 * mm, rightMargin=8 * mm)
    
    # Try to register font, with error handling
    try:
        pdfmetrics.registerFont(TTFont('Arial', 'arial.ttf'))
        font_name = 'Arial'
    except:
        font_name = 'Helvetica'  # Fallback to a built-in font
    
    styles = getSampleStyleSheet()
    styles['Normal'].fontName = font_name
    styles['Normal'].fontSize = 12
    styles['h1'].fontName = font_name
    styles['h1'].fontSize = 16
    styles['h2'].fontName = font_name
    styles['h2'].fontSize = 14
    styles['h3'].fontName = font_name
    styles['h3'].fontSize = 10
    
    # Build document content
    elements = []
    
    # Header with customer details
    
    elements.append(Paragraph(f"<b>Invoice: {sale_data[0]}</b>", styles['h2']))
    elements.append(Paragraph(f"Date: {sale_data[1]}", styles['h3']))
    #elements.append(Spacer(1, 10))
    #elements.append(Paragraph(f"<b>Customer Details:</b>", styles['h3']))
    elements.append(Paragraph(f"Customer Name: {customer_details.get('name', '')}", styles['h3']))
    #elements.append(Paragraph(f"Address: {customer_details.get('address', '')}", styles['h3']))
    #elements.append(Paragraph(f"Phone: {customer_details.get('phone', '')}", styles['h3']))
    
    if customer_details.get('pan'):
        elements.append(Paragraph(f"PAN: {customer_details.get('pan', '')}", styles['h3']))
    if customer_details.get('aadhaar'):
        elements.append(Paragraph(f"Aadhaar: {customer_details.get('aadhaar', '')}", styles['h3']))
    
    elements.append(Spacer(1, 3))
    
    # Items table
    data = [
        ['Metal','Desc', 'Qty', 'HSN', 'Nt Wt', 'Purity', 'Rate', 'Amount']
    ]
    
    total_taxable = 0
    
    for item in sale_items:
        # Extract item details (adjust indices based on your schema)
        metal = item[2]
        description = item[4]  # Assuming description is at index 3
        qty = item[5]
        hsn = item[11] if len(item) > 11 else '7113'
        net_wt = item[6]
        purity = item[7] if item[7] else ''
        rate = item[3]
        amount = item[8]
        
        data.append([metal,description, str(qty), hsn, f"{float(net_wt):.3f}", purity, f"{float(rate):.2f}", f"{amount:.2f}"])
        total_taxable += amount
    
    # Calculate GST
    cgst = total_taxable * 0.015
    sgst = total_taxable * 0.015
    round_off = round(total_taxable + cgst + sgst) - (total_taxable + cgst + sgst)
    total = total_taxable + cgst + sgst + round_off
    
    # Add totals to the table
    data.append(['','', '', '', '', '', 'Taxable Amount:', f"{total_taxable:.2f}"])
    data.append(['','', '', '', '', '', 'CGST (1.5%):', f"{cgst:.2f}"])
    data.append(['','', '', '', '', '', 'SGST (1.5%):', f"{sgst:.2f}"])
    data.append(['','', '', '', '', '', 'Round Off:', f"{round_off:.2f}"])
    data.append(['','', '', '', '', '', 'Total:', f"{total:.2f}"])
    
    # Add old gold and balance
    old_gold_amount = sale_data[4]
    amount_balance = sale_data[5]
    if old_gold_amount > 0:
        data.append(['','', '', '', '', '', 'Old Gold Amount:', f"{old_gold_amount:.2f}"])
    data.append(['','', '', '', '', '', 'Balance:', f"{amount_balance:.2f}"])
    
    # Create the table
    table = Table(data)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), font_name),
        ('FONTSIZE', (0, 0), (-1, 0), 14),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.white),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('ALIGN', (1, 1), (-1, -1), 'RIGHT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    
    elements.append(table)
    elements.append(Spacer(1, 5))
    
    # Payment details
    elements.append(Paragraph(f"<b>Payment Details:</b>", styles['h3']))
    elements.append(Paragraph(f"Payment Mode: {sale_data[6] or 'N/A'}", styles['h3']))
    if sale_data[7]:
        elements.append(Paragraph(f"Other Info: {sale_data[7]}", styles['h3']))
    
    # Note at bottom
    elements.append(Spacer(1, 10))
    elements.append(Paragraph("<i>Note: Taxable amount is inclusive of making and other charges</i>", styles['h3']))
    
    # Build the PDF
    doc.build(elements)
    
    # Save to file
    with open(file_path, 'wb') as f:
        f.write(buffer.getvalue())
    
    if download:
        return buffer.getvalue(), filename
    else:
        return file_path

def generate_purchase_pdf(customer_details, purchase_data, purchase_items, download=False):
    # Get customer name for filename
    customer_name = customer_details.get("name", "supplier").replace(" ", "_")
    invoice_id = purchase_data[0].replace("/", "_") if purchase_data else "unknown_invoice"
    filename = f"{customer_name}_{invoice_id}.pdf"
    file_path = os.path.join(daily_bills_folder, filename)
    
    # Create PDF
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=(210 * mm, 297 * mm * 0.75),
                          topMargin=45 * mm, bottomMargin=25 * mm, leftMargin=8 * mm, rightMargin=8 * mm)
    
    # Try to register font, with error handling
    try:
        pdfmetrics.registerFont(TTFont('Arial', 'arial.ttf'))
        font_name = 'Arial'
    except:
        font_name = 'Helvetica'  # Fallback to a built-in font
    
    styles = getSampleStyleSheet()
    styles['Normal'].fontName = font_name
    styles['Normal'].fontSize = 12
    styles['h1'].fontName = font_name
    styles['h1'].fontSize = 16
    styles['h2'].fontName = font_name
    styles['h2'].fontSize = 14
    styles['h3'].fontName = font_name
    styles['h3'].fontSize = 10
    
    # Build document content
    elements = []
    
    # Header with purchase details
    #elements.append(Spacer(1, 20))
    elements.append(Paragraph(f"<b>Invoice: {purchase_data[0]}</b>", styles['h2']))
    elements.append(Paragraph(f"Date: {purchase_data[1]}", styles['h3']))
    elements.append(Spacer(1, 10))
    elements.append(Paragraph(f"<b>Bill From:</b>", styles['h3']))
    elements.append(Paragraph(f"Name: {customer_details.get('name', '')}", styles['h3']))
    #elements.append(Paragraph(f"Address: {customer_details.get('address', '')}", styles['h3']))
    #elements.append(Paragraph(f"Phone: {customer_details.get('phone', '')}", styles['h3']))
    
    elements.append(Spacer(1, 20))
    
    # Items table
    data = [
        ['IT ID', 'Desc', 'Qty', 'GS WT', 'Rate', 'Amount']
    ]
    
    for item in purchase_items:
        # Extract item details (adjust indices based on your schema)
        metal = item[2]  # Assuming metal is at index 2
        qty = item[3]
        gs_wt = item[4]
        price = item[5]
        amount = item[6]
        
        data.append([metal, metal, str(qty), f"{gs_wt:.3f}", f"{price:.2f}", f"{amount:.2f}"])
    
    # Add total
    total_amount = purchase_data[3]
    data.append(['', '', '', '', 'Total:', f"{total_amount:.2f}"])
    
    # Create the table
    table = Table(data)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), font_name),
        ('FONTSIZE', (0, 0), (-1, 0), 14),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.white),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('ALIGN', (1, 1), (-1, -1), 'RIGHT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    
    elements.append(table)
    elements.append(Spacer(1, 15))
    
    # Payment details
    elements.append(Paragraph(f"<b>Payment Details:</b>", styles['h3']))
    elements.append(Paragraph(f"Payment Mode: {purchase_data[4] or 'N/A'}", styles['h3']))
    if purchase_data[5]:
        elements.append(Paragraph(f"Other Info: {purchase_data[5]}", styles['h3']))
    
    # Build the PDF
    doc.build(elements)
    
    # Save to file
    with open(file_path, 'wb') as f:
        f.write(buffer.getvalue())
    
    if download:
        return buffer.getvalue(), filename
    else:
        return file_path

def generate_udhaar_deposit_pdf(customer_details, deposit_data, original_invoice_data, download=False):
    # Get customer name for filename
    customer_name = customer_details.get("name", "customer").replace(" ", "_")
    invoice_id = deposit_data[0].replace("/", "_") if deposit_data else "unknown_invoice"
    filename = f"deposit_{customer_name}_{invoice_id}.pdf"
    file_path = os.path.join(daily_bills_folder, filename)
    
    # Create PDF
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=(210 * mm, 297 * mm * 0.75),
                          topMargin=45 * mm, bottomMargin=25 * mm, leftMargin=8 * mm, rightMargin=8 * mm)
    
    # Try to register font, with error handling
    try:
        pdfmetrics.registerFont(TTFont('Arial', 'arial.ttf'))
        font_name = 'Arial'
    except:
        font_name = 'Helvetica'  # Fallback to a built-in font
    
    styles = getSampleStyleSheet()
    styles['Normal'].fontName = font_name
    styles['Normal'].fontSize = 12
    styles['h1'].fontName = font_name
    styles['h1'].fontSize = 16
    styles['h2'].fontName = font_name
    styles['h2'].fontSize = 14
    styles['h3'].fontName = font_name
    styles['h3'].fontSize = 10
    
    # Build document content
    elements = []
    
    # Header with deposit details
    elements.append(Paragraph(f"<b>Udhaar Deposit Receipt: {deposit_data[0]}</b>", styles['h2']))
    elements.append(Paragraph(f"Date: {deposit_data[2]}", styles['h3']))
    elements.append(Spacer(1, 10))
    #elements.append(Paragraph(f"<b>Customer Details:</b>", styles['h2']))
    elements.append(Paragraph(f"Customer Name: {customer_details.get('name', '')}", styles['h3']))
    #elements.append(Paragraph(f"Address: {customer_details.get('address', '')}", styles['h3']))
    #elements.append(Paragraph(f"Phone: {customer_details.get('phone', '')}", styles['h3']))
    
    elements.append(Spacer(1, 20))
    
    # Deposit details
    #elements.append(Paragraph(f"<b>Deposit Details:</b>", styles['h3']))
    #elements.append(Paragraph(f"Original Invoice: {deposit_data[1]}", styles['h3']))
    #elements.append(Paragraph(f"Original Invoice Date: {original_invoice_data.get('date', 'N/A')}", styles['h3']))
    #elements.append(Paragraph(f"Original Bill Amount: {original_invoice_data.get('total_amount', 0):.2f}", styles['h3']))
    elements.append(Spacer(1, 10))
    
    elements.append(Paragraph(f"<b>Deposit Amount: {deposit_data[4]:.2f}</b>", styles['h3']))
    #elements.append(Paragraph(f"Remaining Amount: {deposit_data[5]:.2f}", styles['h3']))
    
    # Payment details
    elements.append(Spacer(1, 20))
    elements.append(Paragraph(f"<b>Payment Details:</b>", styles['h3']))
    elements.append(Paragraph(f"Payment Mode: {deposit_data[6] or 'N/A'}", styles['h3']))
    if deposit_data[7]:
        elements.append(Paragraph(f"Other Info: {deposit_data[7]}", styles['h3']))
    
    # Build the PDF
    doc.build(elements)
    
    # Save to file
    with open(file_path, 'wb') as f:
        f.write(buffer.getvalue())
    
    if download:
        return buffer.getvalue(), filename
    else:
        return file_path

# Function to create a download link for a file
def get_download_link(file_content, filename):
    b64 = base64.b64encode(file_content).decode()
    return f'<a href="data:application/octet-stream;base64,{b64}" download="{filename}">Download PDF</a>'

# Function to load and display PDF bill
def load_and_display_pdf(file_path):
    try:
        with open(file_path, "rb") as file:
            pdf_bytes = file.read()
            b64_pdf = base64.b64encode(pdf_bytes).decode('utf-8')
            pdf_display = f'<iframe src="data:application/pdf;base64,{b64_pdf}" width="800" height="600" type="application/pdf"></iframe>'
            st.markdown(pdf_display, unsafe_allow_html=True)
            
            # Create download button
            st.markdown(get_download_link(pdf_bytes, os.path.basename(file_path)), unsafe_allow_html=True)
    except Exception as e:
        st.error(f"Error displaying PDF: {str(e)}")

# --- Menu Functions ---
def sell_section():
    st.header("Sell Jewellery")
    
    # Customer selection
    customers = fetch_all_customers()
    customer_options = ["Select Customer"] + list(customers.values())
    selected_customer_name = st.selectbox("Select Customer", customer_options)
    
    if selected_customer_name == "Select Customer":
        st.warning("Please select a customer or add a new one.")
        # New customer form
        with st.expander("Add New Customer"):
            name = st.text_input("Customer Name")
            phone = st.text_input("Phone Number")
            address = st.text_input("Address")
            pan = st.text_input("PAN (Optional)")
            aadhaar = st.text_input("Aadhaar (Optional)")
            
            if st.button("Add Customer"):
                if name and phone:
                    customer_id = add_new_customer(name, phone, address, pan, aadhaar)
                    if customer_id:
                        # Refresh customers list
                        st.rerun()
                else:
                    st.error("Customer name and phone number are required!")
        
        customer_id = None
    else:
        # Get customer_id from name
        customer_id = [k for k, v in customers.items() if v == selected_customer_name][0]
        customer_details = get_customer_details(customer_id)
        
        # Display customer info
        st.write(f"**Phone:** {customer_details.get('phone', 'N/A')}")
        st.write(f"**Address:** {customer_details.get('address', 'N/A')}")
        
        # Item entry section
        st.subheader("Add Items")
        
        # Container for all items
        if 'sale_items' not in st.session_state:
            st.session_state.sale_items = []
        
        # Add item form
        with st.form("add_item_form"):
            col1, col2 = st.columns(2)
            with col1:
                metal = st.selectbox("Metal", ["Gold", "Silver"])
                metal_rate = st.number_input("Metal Rate (per 10g)", min_value=0.0, step=100.0)
                description = st.text_input("Item Description")
            
            with col2:
                qty = st.number_input("Quantity", min_value=1, step=1)
                net_wt = st.number_input("Net Weight (grams)", min_value=0.0, step=0.1, format="%.3f")
                purity = st.text_input("Purity")
            
            amount = st.number_input("Final Amount", min_value=0.0, step=100.0)
            
            add_item = st.form_submit_button("Add Item")
            
            if add_item:
                if not description or metal_rate <= 0 or net_wt <= 0 or amount <= 0:
                    st.error("Please fill all required fields with valid values.")
                else:
                    new_item = {
                        'metal': metal,
                        'metal_rate': metal_rate,
                        'description': description,
                        'qty': qty,
                        'net_wt': net_wt,
                        'purity': purity,
                        'amount': amount,
                        'cgst_rate': 0.015,
                        'sgst_rate': 0.015,
                        'hsn': '7113'
                    }
                    st.session_state.sale_items.append(new_item)
                    st.success(f"Added {qty} {description} to bill")
        
        # Display added items
        if st.session_state.sale_items:
            st.subheader("Bill Items")
            
            items_df = pd.DataFrame(st.session_state.sale_items)
            st.dataframe(items_df[['metal','description', 'qty', 'net_wt', 'purity', 'amount']])
            
            # Calculate totals
            total_amount = sum(item['amount'] for item in st.session_state.sale_items)
            
            # Summary and payment section
            st.subheader("Payment Details")
            
            col1, col2 = st.columns(2)
            with col1:
                # Calculate GST
                total_taxable = total_amount
                cgst = total_taxable * 0.015
                sgst = total_taxable * 0.015
                grand_total = total_taxable + cgst + sgst
                
                st.write(f"Subtotal: {total_taxable:.2f}")
                st.write(f"CGST (1.5%): {cgst:.2f}")
                st.write(f"SGST (1.5%): {sgst:.2f}")
                st.markdown(f"**Grand Total: {grand_total:.2f}**")
                
                old_gold_amount = st.number_input("Old Gold Amount", min_value=0.0, step=100.0)
                payment_mode = st.selectbox("Payment Mode", ["Cash", "Online", "Cheque", "Other"])
                payment_other_info = st.text_input("Payment Details (Cheque/UPI/etc.)")
                
                # Calculate receivable amount
                receivable_amount = grand_total - old_gold_amount
                st.markdown(f"**Receivable Amount: {receivable_amount:.2f}**")
                
                paid_amount = st.number_input("Paid Amount", min_value=0.0, max_value=float(receivable_amount), step=100.0, value=float(receivable_amount))
                balance_amount = receivable_amount - paid_amount
            
            with col2:
                st.write("**Bill Preview**")
                st.write(f"Customer: {selected_customer_name}")
                st.write(f"Items: {len(st.session_state.sale_items)}")
                st.write(f"Total: {grand_total:.2f}")
                st.write(f"Old Gold: {old_gold_amount:.2f}")
                st.write(f"Receivable: {receivable_amount:.2f}")
                st.write(f"Balance: {balance_amount:.2f}")
            
            # Save bill button
            if st.button("Save Bill"):
                if len(st.session_state.sale_items) == 0:
                    st.error("Please add at least one item to the bill.")
                else:
                    # Save to database
                    invoice_id = save_sale(
                        customer_id, 
                        grand_total, 
                        old_gold_amount, 
                        balance_amount, 
                        payment_mode, 
                        payment_other_info, 
                        st.session_state.sale_items
                    )
                    
                    if invoice_id:
                        # Get sale details
                        sale_data, sale_items_data = get_sale_details(invoice_id)
                        
                        if sale_data and sale_items_data:
                            # Generate PDF
                            pdf_content, filename = generate_sell_pdf(
                                customer_details, 
                                sale_data, 
                                sale_items_data,
                                download=True
                            )
                            
                            # Success message with download link
                            st.success(f"Bill saved successfully! Invoice ID: {invoice_id}")
                            
                            # Download link
                            st.markdown(get_download_link(pdf_content, filename), unsafe_allow_html=True)
                            
                            # Clear items
                            st.session_state.sale_items = []
                        else:
                            st.error("Error retrieving sale details.")
                    else:
                        st.error("Error saving bill. Please try again.")
            
            # Clear form button
            if st.button("Clear Form"):
                st.session_state.sale_items = []
                st.rerun()

def purchase_section():
    st.header("Purchase Jewellery")
    
    # Customer/Supplier selection
    customers = fetch_all_customers()
    customer_options = ["Select Supplier"] + list(customers.values())
    selected_customer_name = st.selectbox("Select Supplier", customer_options, key="purchase_customer")
    
    if selected_customer_name == "Select Supplier":
        st.warning("Please select a supplier or add a new one.")
        # New customer/supplier form
        with st.expander("Add New Supplier"):
            name = st.text_input("Supplier Name")
            phone = st.text_input("Phone Number", key="supplier_phone")
            address = st.text_input("Address", key="supplier_address")
            
            if st.button("Add Supplier"):
                if name and phone:
                    customer_id = add_new_customer(name, phone, address)
                    if customer_id:
                        # Refresh customers list
                        st.rerun()
                else:
                    st.error("Supplier name and phone number are required!")
        
        customer_id = None
    else:
        # Get customer_id from name
        customer_id = [k for k, v in customers.items() if v == selected_customer_name][0]
        customer_details = get_customer_details(customer_id)
        
        # Display customer info
        st.write(f"**Phone:** {customer_details.get('phone', 'N/A')}")
        st.write(f"**Address:** {customer_details.get('address', 'N/A')}")
        
        # Item entry section
        st.subheader("Add Purchase Items")
        
        # Container for all items
        if 'purchase_items' not in st.session_state:
            st.session_state.purchase_items = []
        
        # Add item form
        with st.form("add_purchase_item_form"):
            col1, col2 = st.columns(2)
            with col1:
                metal = st.selectbox("Metal", ["Gold", "Silver"], key="purchase_metal")
                qty = st.number_input("Quantity", min_value=1, step=1, key="purchase_qty")
            
            with col2:
                net_wt = st.number_input("Gross Weight (grams)", min_value=0.0, step=0.1, format="%.3f", key="purchase_wt")
                price = st.number_input("Price per gram", min_value=0.0, step=10.0, key="purchase_price")
            
            amount = st.number_input("Total Amount", min_value=0.0, step=100.0, key="purchase_amount")
            
            add_item = st.form_submit_button("Add Item")
            
            if add_item:
                if price <= 0 or net_wt <= 0 or amount <= 0:
                    st.error("Please fill all required fields with valid values.")
                else:
                    new_item = {
                        'metal': metal,
                        'qty': qty,
                        'net_wt': net_wt,
                        'price': price,
                        'amount': amount
                    }
                    st.session_state.purchase_items.append(new_item)
                    st.success(f"Added {qty} {metal} item(s) to purchase bill")
        
        # Display added items
        if st.session_state.purchase_items:
            st.subheader("Purchase Items")
            
            items_df = pd.DataFrame(st.session_state.purchase_items)
            st.dataframe(items_df[['metal', 'qty', 'net_wt', 'price', 'amount']])
            
            # Calculate totals
            total_amount = sum(item['amount'] for item in st.session_state.purchase_items)
            
            # Payment section
            st.subheader("Payment Details")
            
            col1, col2 = st.columns(2)
            with col1:
                st.markdown(f"**Total Amount: {total_amount:.2f}**")
                payment_mode = st.selectbox("Payment Mode", ["Cash", "Online", "Cheque", "Other"], key="purchase_payment")
                payment_other_info = st.text_input("Payment Details (Cheque/UPI/etc.)", key="purchase_payment_info")
            
            with col2:
                st.write("**Purchase Preview**")
                st.write(f"Supplier: {selected_customer_name}")
                st.write(f"Items: {len(st.session_state.purchase_items)}")
                st.write(f"Total: {total_amount:.2f}")
            
            # Save bill button
            if st.button("Save Purchase"):
                if len(st.session_state.purchase_items) == 0:
                    st.error("Please add at least one item to the purchase.")
                else:
                    # Save to database
                    invoice_id = save_purchase(
                        customer_id, 
                        total_amount, 
                        payment_mode, 
                        payment_other_info, 
                        st.session_state.purchase_items
                    )
                    
                    if invoice_id:
                        # Get purchase details from database
                        conn = sqlite3.connect(DATABASE_NAME)
                        cursor = conn.cursor()
                        cursor.execute("SELECT * FROM purchases WHERE invoice_id = ?", (invoice_id,))
                        purchase_data = cursor.fetchone()
                        
                        cursor.execute("SELECT * FROM purchase_items WHERE invoice_id = ?", (invoice_id,))
                        purchase_items_data = cursor.fetchall()
                        conn.close()
                        
                        if purchase_data and purchase_items_data:
                            # Generate PDF
                            pdf_content, filename = generate_purchase_pdf(
                                customer_details, 
                                purchase_data, 
                                purchase_items_data,
                                download=True
                            )
                            
                            # Success message with download link
                            st.success(f"Purchase saved successfully! Invoice ID: {invoice_id}")
                            
                            # Download link
                            st.markdown(get_download_link(pdf_content, filename), unsafe_allow_html=True)
                            
                            # Clear items
                            st.session_state.purchase_items = []
                        else:
                            st.error("Error retrieving purchase details.")
                    else:
                        st.error("Error saving purchase. Please try again.")
            
            # Clear form button
            if st.button("Clear Purchase Form"):
                st.session_state.purchase_items = []
                st.rerun()

def udhaar_section():
    st.header("Udhaar (Credit) Management")
    
    # Customer selection
    customers = fetch_all_customers()
    customer_options = ["Select Customer"] + list(customers.values())
    selected_customer_name = st.selectbox("Select Customer", customer_options, key="udhaar_customer")
    
    if selected_customer_name != "Select Customer":
        # Get customer_id from name
        customer_id = [k for k, v in customers.items() if v == selected_customer_name][0]
        customer_details = get_customer_details(customer_id)
        
        # Display customer info
        st.write(f"**Phone:** {customer_details.get('phone', 'N/A')}")
        st.write(f"**Address:** {customer_details.get('address', 'N/A')}")
        
        # Get pending udhaar
        pending_df = get_pending_udhaar(customer_id)
        
        if not pending_df.empty:
            st.subheader("Pending Amounts")
            st.dataframe(pending_df)
            
            # Deposit form
            st.subheader("Make Deposit")
            
            # Select invoice
            invoice_options = pending_df['Invoice ID'].tolist()
            selected_invoice = st.selectbox("Select Invoice", invoice_options)
            
            # Get selected invoice details
            selected_row = pending_df[pending_df['Invoice ID'] == selected_invoice].iloc[0]
            pending_amount = selected_row['Pending Amount']
            
            st.write(f"Pending Amount: {pending_amount:.2f}")
            
            deposit_amount = st.number_input("Deposit Amount", min_value=0.01, max_value=float(pending_amount), step=100.0, value=float(pending_amount))
            payment_mode = st.selectbox("Payment Mode", ["Cash", "Online", "Cheque", "Other"], key="deposit_payment")
            payment_other_info = st.text_input("Payment Details (Cheque/UPI/etc.)", key="deposit_payment_info")
            
            if st.button("Save Deposit"):
                # Save deposit
                deposit_id = save_udhaar_deposit(
                    selected_invoice, 
                    customer_id, 
                    deposit_amount, 
                    payment_mode, 
                    payment_other_info
                )
                
                if deposit_id:
                    # Get deposit details from database
                    conn = sqlite3.connect(DATABASE_NAME)
                    cursor = conn.cursor()
                    cursor.execute("SELECT * FROM udhaar_deposits WHERE deposit_invoice_id = ?", (deposit_id,))
                    deposit_data = cursor.fetchone()
                    
                    # Get original invoice details
                    cursor.execute("SELECT date, total_amount FROM sales WHERE invoice_id = ?", (selected_invoice,))
                    original_data = cursor.fetchone()
                    original_invoice_data = {"date": original_data[0], "total_amount": original_data[1]} if original_data else {}
                    
                    conn.close()
                    
                    if deposit_data:
                        # Generate PDF
                        pdf_content, filename = generate_udhaar_deposit_pdf(
                            customer_details, 
                            deposit_data, 
                            original_invoice_data,
                            download=True
                        )
                        
                        # Success message with download link
                        st.success(f"Deposit saved successfully! Receipt ID: {deposit_id}")
                        
                        # Download link
                        st.markdown(get_download_link(pdf_content, filename), unsafe_allow_html=True)
                        
                        # Refresh the page to show updated pending amounts
                        #st.rerun()
                    else:
                        st.error("Error retrieving deposit details.")
                else:
                    st.error("Error saving deposit. Please check the amount and try again.")
        else:
            st.info(f"No pending amounts for {selected_customer_name}.")
    else:
        st.info("Please select a customer to view pending amounts.")

def delete_bill_section():
    st.header("Delete Bill")
    
    # Invoice ID input
    invoice_id = st.text_input("Enter Invoice ID to Delete")
    
    # Confirmation checkbox
    confirmation = st.checkbox("I confirm that I want to permanently delete this bill", key="delete_confirmation")
    
    # Delete button
    if st.button("Delete Bill", disabled=not confirmation or not invoice_id):
        if invoice_id and confirmation:
            delete_bill(invoice_id)
            # Clear confirmation
            st.session_state.delete_confirmation = False

def customer_management():
    st.header("Customer Management")
    
    # Customer list
    customers = fetch_all_customers()
    
    tab1, tab2 = st.tabs(["View/Search Customers", "Add New Customer"])
    
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
            
            st.dataframe(customers_df)
            
            # Select customer to view details
            selected_customer = st.selectbox("Select Customer to View Details", ["Select Customer"] + customer_names)
            
            if selected_customer != "Select Customer":
                selected_id = [k for k, v in filtered_customers.items() if v == selected_customer][0]
                customer_details = get_customer_details(selected_id)
                
                # Display customer details
                st.subheader(f"Details for {selected_customer}")
                st.write(f"**Phone:** {customer_details.get('phone', 'N/A')}")
                st.write(f"**Address:** {customer_details.get('address', 'N/A')}")
                if customer_details.get('pan'):
                    st.write(f"**PAN:** {customer_details.get('pan')}")
                if customer_details.get('aadhaar'):
                    st.write(f"**Aadhaar:** {customer_details.get('aadhaar')}")
                
                # Get customer transactions
                conn = sqlite3.connect(DATABASE_NAME)
                cursor = conn.cursor()
                
                # Get sales
                cursor.execute("""
                    SELECT invoice_id, date, total_amount, old_gold_amount, amount_balance 
                    FROM sales 
                    WHERE customer_id = ? 
                    ORDER BY date DESC
                """, (selected_id,))
                sales = cursor.fetchall()
                
                # Get purchases
                cursor.execute("""
                    SELECT invoice_id, date, total_amount 
                    FROM purchases 
                    WHERE customer_id = ? 
                    ORDER BY date DESC
                """, (selected_id,))
                purchases = cursor.fetchall()
                
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
                
                # Get pending udhaar
                pending_df = get_pending_udhaar(selected_id)
                if not pending_df.empty:
                    st.subheader("Pending Amounts")
                    st.dataframe(pending_df)
        else:
            st.info("No customers found with that name.")
    
    with tab2:
        # New customer form
        name = st.text_input("Customer Name", key="new_cust_name")
        phone = st.text_input("Phone Number", key="new_cust_phone")
        address = st.text_input("Address", key="new_cust_address")
        pan = st.text_input("PAN (Optional)", key="new_cust_pan")
        aadhaar = st.text_input("Aadhaar (Optional)", key="new_cust_aadhaar")
        
        if st.button("Add Customer", key="add_new_cust_btn"):
            if name and phone:
                customer_id = add_new_customer(name, phone, address, pan, aadhaar)
                if customer_id:
                    # Clear form
                    st.session_state.new_cust_name = ""
                    st.session_state.new_cust_phone = ""
                    st.session_state.new_cust_address = ""
                    st.session_state.new_cust_pan = ""
                    st.session_state.new_cust_aadhaar = ""
                    st.rerun()
            else:
                st.error("Customer name and phone number are required!")

def reports_section():
    st.header("Reports & Analytics")
    
    report_type = st.selectbox("Select Report Type", [
        "Daily Sales Report", 
        "Monthly Sales Report", 
        "Inventory Value Report", 
        "Top Customers",
        "Outstanding Balances"
    ])
    
    if report_type == "Daily Sales Report":
        selected_date = st.date_input("Select Date", value=datetime.now().date())
        date_str = selected_date.strftime('%Y-%m-%d')
        
        conn = sqlite3.connect(DATABASE_NAME)
        cursor = conn.cursor()
        
        # Get daily sales
        cursor.execute("""
            SELECT s.invoice_id, c.name, s.total_amount, s.old_gold_amount, s.amount_balance, s.payment_mode
            FROM sales s
            JOIN customers c ON s.customer_id = c.customer_id
            WHERE s.date = ?
            ORDER BY s.invoice_id
        """, (date_str,))
        sales = cursor.fetchall()
        
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
        cursor.execute("""
            SELECT p.invoice_id, c.name, p.total_amount, p.payment_mode
            FROM purchases p
            JOIN customers c ON p.customer_id = c.customer_id
            WHERE p.date = ?
            ORDER BY p.invoice_id
        """, (date_str,))
        purchases = cursor.fetchall()
        
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
        
        conn.close()
    
    elif report_type == "Monthly Sales Report":
        current_year = datetime.now().year
        current_month = datetime.now().month
        
        year = st.selectbox("Select Year", list(range(current_year-5, current_year+1)), index=5)
        month = st.selectbox("Select Month", list(range(1, 13)), index=current_month-1)
        
        # Format month for filtering
        month_str = f"{year}-{month:02d}"
        
        conn = sqlite3.connect(DATABASE_NAME)
        cursor = conn.cursor()
        
        # Get monthly sales
        cursor.execute("""
            SELECT s.date, COUNT(s.invoice_id) as count, SUM(s.total_amount) as total,
                   SUM(s.old_gold_amount) as old_gold, SUM(s.amount_balance) as balance
            FROM sales s
            WHERE s.date LIKE ?
            GROUP BY s.date
            ORDER BY s.date
        """, (f"{month_str}%",))
        sales = cursor.fetchall()
        
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
        cursor.execute("""
            SELECT p.date, COUNT(p.invoice_id) as count, SUM(p.total_amount) as total
            FROM purchases p
            WHERE p.date LIKE ?
            GROUP BY p.date
            ORDER BY p.date
        """, (f"{month_str}%",))
        purchases = cursor.fetchall()
        
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
        
        conn.close()
    
    elif report_type == "Inventory Value Report":
        st.info("This report provides an estimated inventory value based on sales and purchases.")
        
        conn = sqlite3.connect(DATABASE_NAME)
        cursor = conn.cursor()
        
        # Get all sale items
        cursor.execute("""
            SELECT si.metal, SUM(si.net_wt) as total_weight
            FROM sale_items si
            GROUP BY si.metal
        """)
        sold_items = {metal: weight for metal, weight in cursor.fetchall()}
        
        # Get all purchase items
        cursor.execute("""
            SELECT pi.metal, SUM(pi.net_wt) as total_weight
            FROM purchase_items pi
            GROUP BY pi.metal
        """)
        purchased_items = {metal: weight for metal, weight in cursor.fetchall()}
        
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
        
        conn.close()
    
    elif report_type == "Top Customers":
        conn = sqlite3.connect(DATABASE_NAME)
        cursor = conn.cursor()
        
        # Get top customers by sales
        cursor.execute("""
            SELECT c.name, COUNT(s.invoice_id) as sales_count, SUM(s.total_amount) as total_sales
            FROM sales s
            JOIN customers c ON s.customer_id = c.customer_id
            GROUP BY s.customer_id
            ORDER BY total_sales DESC
            LIMIT 10
        """)
        top_customers = cursor.fetchall()
        
        if top_customers:
            top_df = pd.DataFrame(top_customers, columns=["Customer", "Number of Sales", "Total Sales"])
            
            st.subheader("Top 10 Customers by Sales")
            st.dataframe(top_df)
            
            # Chart
            st.bar_chart(top_df.set_index("Customer")["Total Sales"])
        else:
            st.info("No customer data available.")
        
        conn.close()
    
    elif report_type == "Outstanding Balances":
        conn = sqlite3.connect(DATABASE_NAME)
        cursor = conn.cursor()
        
        # Get all outstanding balances
        cursor.execute("""
            SELECT c.name, u.sell_invoice_id, s.date, u.pending_amount
            FROM udhaar u
            JOIN customers c ON u.customer_id = c.customer_id
            JOIN sales s ON u.sell_invoice_id = s.invoice_id
            ORDER BY u.pending_amount DESC
        """)
        balances = cursor.fetchall()
        
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
        
        conn.close()

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
        "Customer Management",
        "Reports & Analytics"
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
    elif menu == "Customer Management":
        customer_management()
    elif menu == "Reports & Analytics":
        reports_section()

# Copyright information in the sidebar (Recommended)
    st.sidebar.markdown("""
    ---
    © 2025 Preetam Oswal <br>
    Contact: 7387682502 <br>
    Email: prtmoswal@gmail.com
    """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()
