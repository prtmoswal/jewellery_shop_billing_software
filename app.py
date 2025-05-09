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
            cheque_amount REAL DEFAULT 0.0,
            online_amount REAL DEFAULT 0.0,
            upi_amount REAL DEFAULT 0.0,
            cash_amount REAL DEFAULT 0.0,
            old_gold_amount REAL DEFAULT 0.0,
            amount_balance REAL NOT NULL,
            payment_mode TEXT,
            payment_other_info TEXT,
            sale_date TEXT NOT NULL
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

def update_customer(phone, name=None, address=None, pan=None, aadhaar=None):
    # Phone number validation (basic - can be extended)
    if pan and len(pan) < 10:
        st.error("Please enter a valid PAN (10 characters)")
        return None
    if aadhaar and len(aadhaar) < 10:
        st.error("Please enter a valid Adhaar (at least 12 characters)")
        return None
    
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    cursor.execute("UPDATE customers SET name=?, address=?, pan=?, aadhaar=? WHERE phone=?", (name, address, pan, aadhaar, phone,))
    conn.commit()
    print(f"Updating customer with phone: {phone} with details: Name={name}, Address={address}, PAN={pan}, Aadhaar={aadhaar}")
    conn.close()
    return True # Return True if update was successful
    
def get_customer_details_for_update(selected_phone):
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT name, phone, address, pan, aadhaar FROM customers WHERE phone = ?", (selected_phone,))
    result = cursor.fetchone()
    conn.close()
    #print(f"details : Name={result[0]}")
    if result:
        return {"name": result[0], "phone": result[1], "address": result[2], "pan": result[3], "aadhaar": result[4]}
        st.success(f"Customer '{name}' details fetched")
    else:
        st.success(f"Customer not fetched")
        return None

def get_all_customer_phones():
     conn=sqlite3.connect(DATABASE_NAME)
     cursor=conn.cursor()
     cursor.execute("SELECT DISTINCT phone FROM customers")
     phones = [row[0] for row in cursor.fetchall()]
     return phones
    

# --- Helper Functions for Database Operations ---
def fetch_all_customers():
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT customer_id, phone FROM customers")
    customers = cursor.fetchall()
    conn.close()
    return {cust_id: phone for cust_id, phone in customers}
    

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
                next_value INTEGER NOT NULL DEFAULT 0
            )
        """)
        # Insert the sequence name if it doesn't exist
        cursor.execute("INSERT OR IGNORE INTO invoice_sequences (sequence_name, next_value) VALUES (?, 0)", (sequence_name,))

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
            return f"IS-{year_suffix}-{next_number:04d}" # Example format with leading zeros
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


def convert_amount_to_words(amount):
    """Converts a numerical amount to words (Indian numbering system)."""
    if amount == 0:
        return "Zero"

    def twodigits(num):
        tens = ["", "", "Twenty", "Thirty", "Forty", "Fifty", "Sixty", "Seventy", "Eighty", "Ninety"]
        teens = ["Ten", "Eleven", "Twelve", "Thirteen", "Fourteen", "Fifteen", "Sixteen", "Seventeen", "Eighteen", "Nineteen"]

        if num < 10:
            return ["", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine"][num]
        elif num < 20:
            return teens[num - 10]
        else:
            return tens[num // 10] + (" " + ["", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine"][num % 10])

    def process(num):
        parts = []
        crores = num // 10000000
        num %= 10000000
        lakhs = num // 100000
        num %= 100000
        thousands = num // 1000
        num %= 1000
        hundreds = num // 100
        num %= 100
        tens = num

        if crores:
            parts.append(twodigits(crores) + " Crore")
        if lakhs:
            parts.append(twodigits(lakhs) + " Lakh")
        if thousands:
            parts.append(twodigits(thousands) + " Thousand")
        if hundreds:
            parts.append(twodigits(hundreds) + " Hundred")
        if tens:
            if parts:
                parts.append("and")
            parts.append(twodigits(tens))
        return " ".join(parts).strip()

    integer_part = int(amount)
    decimal_part = round((amount - integer_part) * 100)

    words = process(integer_part)

    if decimal_part > 0:
        words += f" and {twodigits(decimal_part)} Paise"

    return words

def save_sale(invoice_id,customer_id,total_amount, cheque_amount,online_amount,upi_amount,cash_amount, old_gold_amount, amount_balance, payment_mode, payment_other_info, sale_date, sale_items_data):
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
        #invoice_id = generate_sales_invoice_id(sale_items_data[0]['metal'] if sale_items_data else 'Gold')
        date = datetime.now().strftime('%Y-%m-%d')
        cursor.execute("INSERT INTO sales (invoice_id, date, customer_id, total_amount, cheque_amount,online_amount,upi_amount,cash_amount,  old_gold_amount, amount_balance, payment_mode, payment_other_info, sale_date) VALUES (?, ?, ?, ?, ?, ?, ?, ?,?, ?, ?, ?,?)",
                      (invoice_id, date, customer_id, total_amount,cheque_amount,online_amount,upi_amount,cash_amount,  old_gold_amount, amount_balance, payment_mode, payment_other_info, sale_date))
        
        for item in sale_items_data:
            taxable_amount = item['amount']
            cgst = taxable_amount * item.get('cgst_rate', 0.015)
            sgst = taxable_amount * item.get('sgst_rate', 0.015)
            cursor.execute('''
                INSERT INTO sale_items (invoice_id, metal, metal_rate, description, qty, net_wt, purity, amount, cgst_rate, sgst_rate, hsn)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (invoice_id, item['metal'], item['metal_rate'], item['description'], item['qty'], item['net_wt'], item['purity'], item['amount'], item.get('cgst_rate', 0.015), item.get('sgst_rate', 0.015), item.get('hsn', '7113')))
        
        if amount_balance != 0:
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

def save_purchase(invoice_id,customer_id,total_amount, payment_mode, payment_other_info, purchase_items_data):
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
        date = datetime.now().strftime('%Y-%m-%d')
        cursor.execute("INSERT INTO purchases (invoice_id, date, customer_id, total_amount, payment_mode, payment_other_info) VALUES (?, ?, ?, ?, ?, ?)",
                      (invoice_id, date, customer_id,total_amount, payment_mode, payment_other_info))
        
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

def save_udhaar_deposit(invoice_id,sell_invoice_id, customer_id, deposit_amount, payment_mode, payment_other_info):
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
            deposit_invoice_id = invoice_id
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
        cursor.execute("SELECT invoice_id FROM sales WHERE invoice_id = ? UNION SELECT invoice_id FROM purchases WHERE invoice_id = ? UNION SELECT deposit_invoice_id from udhaar_deposits where deposit_invoice_id= ?", 
                       (invoice_id, invoice_id,invoice_id))
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
        cursor.execute("DELETE FROM udhaar_deposits WHERE deposit_invoice_id = ?", (invoice_id,))
        conn.commit()
        st.success(f"Bill with Invoice ID '{invoice_id}' deleted.")
    except Exception as e:
        conn.rollback()
        st.error(f"Error deleting bill: {str(e)}")
    finally:
        conn.close()

def delete_udhaar_bill(deposit_invoice_id_to_delete):
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()

    try:
        # 1. Retrieve the deposit amount and sell_invoice_id of the deposit to be deleted
        cursor.execute("SELECT sell_invoice_id, deposit_amount FROM udhaar_deposits WHERE deposit_invoice_id = ?", (deposit_invoice_id_to_delete,))
        deposit_info = cursor.fetchone()

        if deposit_info:
            sell_invoice_id, deposit_amount = deposit_info

            # 2. Delete the udhaar_deposit record
            cursor.execute("DELETE FROM udhaar_deposits WHERE deposit_invoice_id = ?", (deposit_invoice_id_to_delete,))

            # 3. Check if a corresponding entry exists in the udhaar table
            cursor.execute("SELECT pending_amount FROM udhaar WHERE sell_invoice_id = ?", (sell_invoice_id,))
            udhaar_record = cursor.fetchone()

            if udhaar_record:
                current_pending = udhaar_record[0]
                new_pending_amount = current_pending + deposit_amount

                # Update the existing udhaar record by adding back the deposit amount
                cursor.execute("UPDATE udhaar SET pending_amount = ? WHERE sell_invoice_id = ?", (new_pending_amount, sell_invoice_id))
                st.success(f"Deposit with Invoice ID '{deposit_invoice_id_to_delete}' deleted. Pending amount for Sell Invoice '{sell_invoice_id}' increased by {deposit_amount:.2f}. New pending amount: {new_pending_amount:.2f}")
            else:
                # If no corresponding udhaar entry exists, create one
                # You'll likely need the customer_id as well. You might need to fetch it from the deleted udhaar_deposits record.
                cursor.execute("SELECT customer_id FROM udhaar_deposits WHERE deposit_invoice_id = ?", (deposit_invoice_id_to_delete,))
                deposit_customer_info = cursor.fetchone()
                if deposit_customer_info:
                    customer_id = deposit_customer_info[0]
                    cursor.execute("INSERT INTO udhaar (sell_invoice_id, customer_id, pending_amount) VALUES (?, ?, ?)", (sell_invoice_id, customer_id, deposit_amount))
                    st.success(f"Deposit with Invoice ID '{deposit_invoice_id_to_delete}' deleted. No existing pending invoice found for Sell Invoice '{sell_invoice_id}'. A new pending invoice with amount {deposit_amount:.2f} created.")
                else:
                    st.error(f"Error: Could not retrieve customer_id for the deleted deposit '{deposit_invoice_id_to_delete}'. Cannot create a new udhaar entry.")
                    conn.rollback()
                    return False

            conn.commit()
            return True

        else:
            st.error(f"Error: Udhaar Deposit with Invoice ID '{deposit_invoice_id_to_delete}' not found.")
            return False

    except Exception as e:
        conn.rollback()
        st.error(f"Error reversing udhaar deposit deletion: {str(e)}")
        return False
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
    styles['h4'].fontName = font_name
    styles['h4'].fontSize = 10
    #styles['h4'].fontColor='red'
    
    # Build document content
    elements = []
    
    # Header with customer details
    
    elements.append(Paragraph(f"<b>Invoice: {sale_data[0]}</b>", styles['h4']))
    elements.append(Paragraph(f"Date: {sale_data[12]}", styles['h4']))
    #elements.append(Spacer(1, 10))
    #elements.append(Paragraph(f"<b>Customer Details:</b>", styles['h3']))
    elements.append(Paragraph(f"Customer Name: {customer_details.get('name', '')}", styles['h4']))
    #elements.append(Paragraph(f"Address: {customer_details.get('address', '')}", styles['h3']))
    #elements.append(Paragraph(f"Phone: {customer_details.get('phone', '')}", styles['h3']))
    
    if customer_details.get('pan'):
        elements.append(Paragraph(f"PAN: {customer_details.get('pan', '')}", styles['h4']))
    if customer_details.get('aadhaar'):
        elements.append(Paragraph(f"Aadhaar: {customer_details.get('aadhaar', '')}", styles['h4']))
    
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
    #data1 = [['', '']]
    data1 = [
        ['Metal','Desc', 'Qty', 'HSN', 'Nt Wt', 'Purity', 'Rate', 'Amount']
    ]
    data1.append(['','','','','','','Taxable Amount:', f"{total_taxable:.2f}"])
    data1.append(['','','','','','','CGST (1.5%):', f"{cgst:.2f}"])
    data1.append(['','','','','','','SGST (1.5%):', f"{sgst:.2f}"])
    data1.append(['','','','','','','Round Off:', f"{round_off:.2f}"])
    data1.append(['','','','','','','Total:', f"{total:.2f}"])
    
    # Add old gold and balance
    cheque_amount = sale_data[4]
    online_amount = sale_data[5]
    upi_amount = sale_data[6]
    cash_amount = sale_data[7]
    old_gold_amount = sale_data[8]
    amount_balance = sale_data[9]
    if cheque_amount > 0:
        data1.append(['','','','','','','Cheque Amount:', f"{cheque_amount:.2f}"])
    if online_amount > 0:
        data1.append(['','','','','','','Online Amount:', f"{online_amount:.2f}"])
    if upi_amount > 0:
        data1.append(['','','','','','','UPI Amount:', f"{upi_amount:.2f}"])
    if cash_amount > 0:
        data1.append(['','','','','','','Cash Amount:', f"{cash_amount:.2f}"])
    if old_gold_amount > 0:
        data1.append(['','','','','','','Old Gold Amount:', f"{old_gold_amount:.2f}"])    
    data1.append(['','','','','','','Balance:', f"{amount_balance:.2f}"])
    
    # Create the table
    table = Table(data)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.red),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), font_name),
        ('FONTSIZE', (0, 0), (-1, 0), 14),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.white),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('ALIGN', (1, 1), (-1, -1), 'RIGHT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))

    # Create the table
    table1 = Table(data1)
    table1.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.white),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), font_name),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.white),
        ('GRID', (0, 0), (-1, -1), 1, colors.white),
        ('ALIGN', (1, 1), (-1, -1), 'RIGHT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))

    elements.append(table)
    elements.append(Spacer(1, 1))
    elements.append(table1)
    elements.append(Spacer(1, 2))
    
    # Payment details
    #elements.append(Paragraph(f"<b>Payment Details:</b>", styles['h3']))
    #elements.append(Paragraph(f"Payment Mode: {sale_data[10] or 'N/A'}", styles['h3']))
    if sale_data[7]:
        elements.append(Paragraph(f"Other Info: {sale_data[11]}", styles['h3']))
    amount_in_words = convert_amount_to_words(total)    
    elements.append(Paragraph(f"Total Amount: Rupees {amount_in_words} Only /-", styles['h3']))
    balance_amount_in_words = convert_amount_to_words(amount_balance)
    elements.append(Paragraph(f"<font color='red'>Balance Amount: Rupees {balance_amount_in_words} Only /-</font>", styles['h4']))
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
    amount_in_words = convert_amount_to_words(purchase_data[3])    
    elements.append(Paragraph(f"Amount in Words: Rupees {amount_in_words} Only", styles['h3']))
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
    # Option to use a deleted invoice ID
    use_deleted_invoice = st.checkbox("Use a deleted Invoice ID?")
    #deleted_invoice_options = ["Select Deleted Invoice ID"] + fetch_deleted_invoice_ids()
    #selected_deleted_invoice_id = None

    if use_deleted_invoice:
        #selected_deleted_invoice_id = st.selectbox("Select Deleted Invoice ID", deleted_invoice_options)
        selected_deleted_invoice_id = st.text_input("Select Deleted Invoice ID")
        #if selected_deleted_invoice_id == "Select Deleted Invoice ID":
        #    selected_deleted_invoice_id = None # Ensure it's None if not selected

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
    
        selected_date = st.date_input("Select Bill Date", value=datetime.now().date())
        
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
            
            
            # Calculate GST
            total_taxable = total_amount
            cgst = total_taxable * 0.015
            sgst = total_taxable * 0.015
            grand_total = total_taxable + cgst + sgst
                
            st.write(f"Subtotal: {total_taxable:.2f}")
            st.write(f"CGST (1.5%): {cgst:.2f}")
            st.write(f"SGST (1.5%): {sgst:.2f}")
            st.markdown(f"**Grand Total: {grand_total:.2f}**")
               
            col1, col2 = st.columns(2)
            with col1:
                cheque_amount = st.number_input("Cheque Amount", min_value=0.0, step=100.0)
                online_amount = st.number_input("Online Amount", min_value=0.0, step=100.0)
                upi_amount = st.number_input("UPI Amount", min_value=0.0, step=100.0)
                old_gold_amount = st.number_input("Old Gold Amount", min_value=0.0, step=100.0)
                
                
            with col2:    
                cash_amount = st.number_input("Cash Amount", min_value=0.0, step=100.0)
                payment_mode = st.selectbox("Payment Mode", ["Cash", "Online", "Cheque", "UPI", "Other"])
                payment_other_info = st.text_input("Payment Details (Cheque/UPI/etc.)")
                
                # Calculate receivable amount
                receivable_amount = grand_total - old_gold_amount 
                
                
                #paid_amount = st.number_input("Paid Amount", min_value=0.0, max_value=float(receivable_amount), step=100.0, value=float(receivable_amount))
                paid_amount=  cheque_amount + online_amount + upi_amount + cash_amount
                balance_amount = receivable_amount - paid_amount
            st.markdown(f"**Balance Amount: {balance_amount:.2f}**")
            
            
            st.write("**Bill Preview**")
            st.write(f"Customer: {selected_customer_name}")
            st.write(f"Items: {len(st.session_state.sale_items)}")
            st.write(f"Total: {grand_total:.2f}")
            st.write(f"Old Gold: {old_gold_amount:.2f}")
            st.write(f"Receivable: {receivable_amount:.2f}")
            #st.write(f"Balance: {balance_amount:.2f}")
            st.markdown(f"<p style='color:red;'>Balance: {balance_amount:.2f}", unsafe_allow_html=True)
            # Save bill button
            if st.button("Save Bill"):
                if len(st.session_state.sale_items) == 0:
                    st.error("Please add at least one item to the bill.")
                else:
                    invoice_id_to_use = None
                    if use_deleted_invoice and selected_deleted_invoice_id:
                        invoice_id_to_use = selected_deleted_invoice_id

                    # Determine the invoice ID to use
                    if invoice_id_to_use:
                        invoice_id = invoice_id_to_use
                    else:
                        invoice_id = generate_sales_invoice_id(metal)
                        
                    # Save to database
                    invoice_id = save_sale(
                        invoice_id,
                        customer_id, 
                        grand_total, 
                        cheque_amount,
                        online_amount,
                        upi_amount,
                        cash_amount,
                        old_gold_amount, 
                        balance_amount, 
                        payment_mode, 
                        payment_other_info,
                        selected_date,
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
    use_deleted_invoice = st.checkbox("Use a deleted Invoice ID?")
    #deleted_invoice_options = ["Select Deleted Invoice ID"] + fetch_deleted_invoice_ids()
    #selected_deleted_invoice_id = None

    if use_deleted_invoice:
        #selected_deleted_invoice_id = st.selectbox("Select Deleted Invoice ID", deleted_invoice_options)
        selected_deleted_invoice_id = st.text_input("Select Deleted Invoice ID")
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
                    invoice_id_to_use = None
                    if use_deleted_invoice and selected_deleted_invoice_id:
                        invoice_id_to_use = selected_deleted_invoice_id

                    # Determine the invoice ID to use
                    if invoice_id_to_use:
                        invoice_id = invoice_id_to_use
                    else:
                        invoice_id = generate_purchase_invoice_id()

                    # Save to database
                    invoice_id = save_purchase(
                        invoice_id,
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
    use_deleted_invoice = st.checkbox("Use a deleted Invoice ID?")
    #deleted_invoice_options = ["Select Deleted Invoice ID"] + fetch_deleted_invoice_ids()
    #selected_deleted_invoice_id = None

    if use_deleted_invoice:
        #selected_deleted_invoice_id = st.selectbox("Select Deleted Invoice ID", deleted_invoice_options)
        selected_deleted_invoice_id = st.text_input("Select Deleted Invoice ID")
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
                invoice_id_to_use = None
                if use_deleted_invoice and selected_deleted_invoice_id:
                    invoice_id_to_use = selected_deleted_invoice_id

                # Determine the invoice ID to use
                if invoice_id_to_use:
                    invoice_id = invoice_id_to_use
                else:
                    invoice_id = generate_udhaar_invoice_id()    
                        
                deposit_id = save_udhaar_deposit(
                    invoice_id,
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
    tab1, tab2 = st.tabs(["Delete Bill", "Delete Udhaar Deposit"])
    # Invoice ID input
    with tab1:
        invoice_id = st.text_input("Enter Invoice ID to Delete")
    
        # Confirmation checkbox
        confirmation = st.checkbox("I confirm that I want to permanently delete this bill", key="delete_confirmation")
        
        # Delete button
        if st.button("Delete Bill", disabled=not confirmation or not invoice_id):
            if invoice_id and confirmation:
                delete_bill(invoice_id)
                # Clear confirmation
                st.session_state.delete_confirmation = False

    with tab2:
        deposit_invoice_id_to_delete = st.text_input("Enter Udhaar Deposit ID to Delete")
        
        # Confirmation checkbox
        confirmation2 = st.checkbox("I confirm that I want to permanently delete this bill", key="delete_confirmation2")
        
        # Delete button
        if st.button("Delete Udhaar Deposit", disabled=not confirmation2 or not deposit_invoice_id_to_delete):
            if deposit_invoice_id_to_delete and confirmation2:
                delete_udhaar_bill(deposit_invoice_id_to_delete)
                # Clear confirmation
                st.session_state.delete_confirmation2 = False

def fetch_bill_data(invoice_id):
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    customer_details = {}
    sale_data = None
    sale_items = []

    # Fetch sale header
    cursor.execute("SELECT * FROM sales WHERE invoice_id = ?", (invoice_id,))
    sale_record = cursor.fetchone()
    if sale_record:
        sale_columns = [description[0] for description in cursor.description]
        sale_data = list(sale_record)

        # Fetch customer details
        customer_id = sale_record[2] # Assuming customer_id is at index 2
        cursor.execute("SELECT * FROM customers WHERE customer_id = ?", (customer_id,))
        customer_record = cursor.fetchone()
        if customer_record:
            customer_columns = [description[0] for description in cursor.description]
            customer_details = dict(zip(customer_columns, customer_record))

        # Fetch sale items
        cursor.execute("SELECT * FROM sale_items WHERE invoice_id = ?", (invoice_id,))
        sale_items = cursor.fetchall()

    conn.close()
    return customer_details, sale_data, sale_items
    
def reprint_bill_section():
# --- Streamlit UI for Reprinting ---
    st.title("Reprint Bill")

    reprint_invoice_id = st.text_input("Enter Invoice ID to Reprint:")
    reprint_button = st.button("Reprint Bill")

    if reprint_button and reprint_invoice_id:
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
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT invoice_id FROM sales")
    invoice_ids = [row[0] for row in cursor.fetchall()]
    conn.close()

    if invoice_ids:
        selected_invoice_reprint = st.selectbox("Select Invoice ID to Reprint:", invoice_ids)
        reprint_button_select = st.button("Reprint Selected Bill")

        if reprint_button_select and selected_invoice_reprint:
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


# --- Function to fetch bill data for editing ---
# def fetch_bill_data_for_edit(invoice_id):
#     conn = sqlite3.connect(DATABASE_NAME)
#     cursor = conn.cursor()
#     bill_data = None
#     items_data = []

#     # Fetch sale header
#     cursor.execute("SELECT * FROM sales WHERE invoice_id = ?", (invoice_id,))
#     sale_record = cursor.fetchone()
#     if sale_record:
#         columns = [description[0] for description in cursor.description]
#         bill_data = dict(zip(columns, sale_record))
#         cursor.execute("SELECT * FROM sale_items WHERE invoice_id = ?", (invoice_id,))
#         items_columns = [description[0] for description in cursor.description]
#         items = cursor.fetchall()
#         items_data = [dict(zip(items_columns, item)) for item in items]

#     conn.close()
#     return bill_data, items_data

# --- Function to save the updated bill ---
# def save_updated_bill(invoice_id, bill_data, items_data):
#     conn = sqlite3.connect(DATABASE_NAME)
#     cursor = conn.cursor()
#     try:
#         # Update the sales table
#         cursor.execute("""
#             UPDATE sales
#             SET date=?, customer_id=?, total_amount=?, cheque_amount=?,
#                 online_amount=?, upi_amount=?, cash_amount=?, old_gold_amount=?,
#                 amount_balance=?, payment_mode=?, payment_other_info=?
#             WHERE invoice_id=?
#         """, (bill_data['date'], bill_data['customer_id'], bill_data['total_amount'],
#               bill_data['cheque_amount'], bill_data['online_amount'], bill_data['upi_amount'],
#               bill_data['cash_amount'], bill_data['old_gold_amount'], bill_data['amount_balance'],
#               bill_data['payment_mode'], bill_data['payment_other_info'],
#               invoice_id))

#         # Delete existing sale items
#         cursor.execute("DELETE FROM sale_items WHERE invoice_id = ?", (invoice_id))

#         # Insert updated sale items
#         for item in items_data:
#             cursor.execute("""
#                 INSERT INTO sale_items (invoice_id, metal, rate, description, qty, net_wt, purity, amount, hsn)
#                 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
#             """, (invoice_id, item['metal'], item['rate'], item['description'], item['qty'],
#                   item['net_wt'], item['purity'], item['amount'], item['hsn']))

#         conn.commit()
#         st.success(f"Bill with Invoice ID '{invoice_id}' updated successfully!")
#         return True
#     except Exception as e:
#         conn.rollback()
#         st.error(f"Error updating bill: {e}")
#         return False
#     finally:
#         conn.close()

# def update_bill_section():
#     st.header("Update bill section")
# --- Function to fetch bill data for editing ---

# def fetch_bill_data_for_edit(invoice_id):
#     conn = sqlite3.connect(DATABASE_NAME)
#     cursor = conn.cursor()
#     bill_data = None
#     items_data = []

#     # Fetch sale header
#     cursor.execute("SELECT * FROM sales WHERE invoice_id = ?", (invoice_id,))
#     sale_record = cursor.fetchone()
#     if sale_record:
#         columns = [description[0] for description in cursor.description]
#         bill_data = dict(zip(columns, sale_record))
#         cursor.execute("SELECT * FROM sale_items WHERE invoice_id = ?", (invoice_id,))
#         items_columns = [description[0] for description in cursor.description]
#         items = cursor.fetchall()
#         items_data = [dict(zip(items_columns, item)) for item in items]

#     conn.close()
#     return bill_data, items_data

# # --- Function to save the updated bill data to the database ---
# def save_updated_bill_data(invoice_id, bill_data, items_data):
#     conn = sqlite3.connect(DATABASE_NAME)
#     cursor = conn.cursor()
#     try:
#         # Update the sales table
#         cursor.execute("""
#             UPDATE sales
#             SET date=?, customer_id=?, total_amount=?, cheque_amount=?,
#                 online_amount=?, upi_amount=?, cash_amount=?, old_gold_amount=?,
#                 amount_balance=?, payment_mode=?, payment_other_info=?, hsn_sac_code=?
#             WHERE invoice_id=?
#         """, (bill_data['date'], bill_data['customer_id'], bill_data['total_amount'],
#               bill_data['cheque_amount'], bill_data['online_amount'], bill_data['upi_amount'],
#               bill_data['cash_amount'], bill_data['old_gold_amount'], bill_data['amount_balance'],
#               bill_data['payment_mode'], bill_data['payment_other_info'], bill_data['hsn_sac_code'],
#               invoice_id))

#         # Delete existing sale items
#         cursor.execute("DELETE FROM sale_items WHERE invoice_id = ?", (invoice_id,))

#         # Insert updated sale items
#         for item in items_data:
#             cursor.execute("""
#                 INSERT INTO sale_items (invoice_id, metal, rate, description, qty, net_wt, purity, amount, hsn)
#                 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
#             """, (invoice_id, item['metal'], item['rate'], item['description'], item['qty'],
#                   item['net_wt'], item['purity'], item['amount'], item['hsn']))

#         conn.commit()
#         st.success(f"Bill with Invoice ID '{invoice_id}' data updated successfully!")
#         return True
#     except Exception as e:
#         conn.rollback()
#         st.error(f"Error updating bill data: {e}")
#         return False
#     finally:
#         conn.close()

# # --- Streamlit UI for Editing Bill Data ---
# def update_bill_section():
#     st.title("Edit Bill Data")

#     edit_invoice_id = st.text_input("Enter Invoice ID to Edit:")

#     if st.button("Load Bill Data for Edit"):
#         if edit_invoice_id:
#             bill_data, items_data = fetch_bill_data_for_edit(edit_invoice_id)
#             if bill_data:
#                 st.subheader(f"Edit Bill Data: {edit_invoice_id}")
#                 with st.form(key=f"edit_bill_form_{edit_invoice_id}"):
#                     col1, col2 = st.columns(2)
#                     bill_data['date'] = col1.date_input("Date:", datetime.strptime(bill_data['date'], '%Y-%m-%d').date() if bill_data.get('date') else datetime.now().date())
#                     bill_data['customer_id'] = col2.number_input("Customer ID:", value=bill_data.get('customer_id', 0), min_value=0, step=1)
#                     bill_data['total_amount'] = col1.number_input("Total Amount:", value=bill_data.get('total_amount', 0.0), min_value=0.0)
#                     bill_data['cheque_amount'] = col2.number_input("Cheque Amount:", value=bill_data.get('cheque_amount', 0.0), min_value=0.0)
#                     bill_data['online_amount'] = col1.number_input("Online Amount:", value=bill_data.get('online_amount', 0.0), min_value=0.0)
#                     bill_data['upi_amount'] = col2.number_input("UPI Amount:", value=bill_data.get('upi_amount', 0.0), min_value=0.0)
#                     bill_data['cash_amount'] = col1.number_input("Cash Amount:", value=bill_data.get('cash_amount', 0.0), min_value=0.0)
#                     bill_data['old_gold_amount'] = col2.number_input("Old Gold Amount:", value=bill_data.get('old_gold_amount', 0.0), min_value=0.0)
#                     bill_data['amount_balance'] = col1.number_input("Balance:", value=bill_data.get('amount_balance', 0.0), min_value=0.0)
#                     bill_data['payment_mode'] = col2.selectbox("Payment Mode:", ["Cash", "Cheque", "Online", "UPI", None], index=["Cash", "Cheque", "Online", "UPI", None].index(bill_data.get('payment_mode')))
#                     bill_data['payment_other_info'] = col1.text_input("Payment Info:", value=bill_data.get('payment_other_info', ''))
#                     bill_data['hsn_sac_code'] = col2.text_input("HSN/SAC Code:", value=bill_data.get('hsn_sac_code', '7113'))

#                     st.subheader("Bill Items")
                    
#                     for i, item in enumerate(items_data):
#                         st.subheader(f"Item {i+1}")
#                         col_item1, col_item2,col_item3 = st.columns(3)
#                         item['metal'] = col_item1.text_input("Metal:", value=item.get('metal', ''))
#                         item['purity'] = col_item1.text_input("Purity:", value=item.get('purity', ''))
#                         item['description'] = col_item1.text_input("Description:", value=item.get('description', ''))
#                         item['qty'] = col_item2.number_input("Quantity:", value=item.get('qty', 1), min_value=1, step=1)
#                         item['net_wt'] = col_item2.number_input("Net Wt:", value=item.get('net_wt', 0.0), min_value=0.0, step=0.001)
#                         item['rate'] = col_item2.number_input("Rate:", value=item.get('rate', 0.0), min_value=0.00, step=0.01)
#                         item['amount'] = col_item3.number_input("Amount:", value=item.get('amount', 0.0), min_value=0.0)
#                         item['hsn'] = col_item3.text_input("HSN:", value=item.get('hsn', '7113'))
            
#                     if st.form_submit_button("Save Updated Bill Data"):
#                         if save_updated_bill_data(edit_invoice_id, bill_data, items_data):
#                             st.info("Bill data updated successfully!")
#             else:
#                 st.error(f"Bill with Invoice ID '{edit_invoice_id}' not found.")
#         else:
#             st.warning("Please enter an Invoice ID to edit.")    

def customer_management():
    st.header("Customer Management")
    
    # Customer list
    customers = fetch_all_customers()
    
    tab1, tab2,tab3 = st.tabs(["View/Search Customers", "Add New Customer","Update Customers"])
    
    with tab1:
        # Search by name
        search_name = st.text_input("Search Customer by Phone")
        
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
                "Phone": customer_names
            })
            
            st.dataframe(customers_df.head(5))
            
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
    
    with tab3:
        all_phones = get_all_customer_phones()
        selected_phone = st.selectbox("Select Customer by Phone", ["Select Customer"] + all_phones)

        customer_details = None
        if selected_phone:
            customer_details = get_customer_details_for_update(selected_phone)
        name = ""
        phone = ""
        address = ""
        pan = ""
        aadhaar = ""
            
        #box=st.selectbox("abc",customer_details.get("name",""),key="update_cust_name")
        
        if customer_details:
            name = st.text_input("Customer Name", value=customer_details.get("name", ""), key="update_cust_name")
            phone = st.text_input("Phone Number", value=customer_details.get("phone", ""), key="update_cust_phone", disabled=True) # Disable phone for editing
            address = st.text_input("Address", value=customer_details.get("address", ""), key="update_cust_address")
            pan = st.text_input("PAN (Optional)", value=customer_details.get("pan", ""), key="update_cust_pan")
            aadhaar = st.text_input("Aadhaar (Optional)", value=customer_details.get("aadhaar", ""), key="update_cust_aadhaar")
        
            if st.button("Update Customer", key="update_cust_btn"):
                updated = update_customer(
                    selected_phone,
                    name=name,
                    address=address,
                    pan=pan,
                    aadhaar=aadhaar
                )
                if updated:
                    st.success(f"Customer with phone number '{selected_phone}' details updated successfully!")
                    # Optionally clear the form or reload customer details
                    # st.session_state.update_cust_name = ""
                    # st.session_state.update_cust_address = ""
                    # st.session_state.update_cust_pan = ""
                    # st.session_state.update_cust_aadhaar = ""
                    # st.rerun() # To reload the selectbox and potentially clear fields
                else:
                    st.error(f"Failed to update customer with phone number '{selected_phone}'. Please check logs or database connection.")
        
        else:
            st.info("Please select a customer by phone number to update their details.")

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
        "Reprint Bill",
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
    elif menu == "Reprint Bill":
        reprint_bill_section()    
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
