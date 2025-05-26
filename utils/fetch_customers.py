import streamlit as st
import sqlite3
from utils.config import DATABASE_NAME
from utils.db_manager import DBManager

def get_customer_details_for_update(selected_name):
    db = DBManager(DATABASE_NAME)
    # Using fetch_one directly
    result = db.fetch_one(
        "SELECT name, phone, address, pan, aadhaar, alternate_phone, alternate_phone2, landline_phone FROM customers WHERE name = ?",
        (selected_name,)
    )

    if result:
        # st.success(f"Customer '{selected_name}' details fetched") # Moved outside, if you want it after return
        return {
            "name": result[0],
            "phone": result[1],
            "address": result[2],
            "pan": result[3],
            "aadhaar": result[4],
            "alternate_phone": result[5],
            "alternate_phone2": result[6],
            "landline_phone": result[7]
        }
    else:
        st.info(f"Customer '{selected_name}' not found.") # Changed to info for clarity
        return None

def get_all_customer_names():
    db = DBManager(DATABASE_NAME)
    # Using fetch_all directly
    rows = db.fetch_all("SELECT DISTINCT name FROM customers")
    names = [row[0] for row in rows] # Extract names from tuples
    return names

def fetch_all_customers():
    db = DBManager(DATABASE_NAME)
    # Using fetch_all directly
    customers = db.fetch_all("SELECT customer_id, name FROM customers")

    # Return as a dictionary {customer_id: name}
    return {cust_id: name for cust_id, name in customers}

def update_customer(phone, name=None, address=None, pan=None, aadhaar=None, alternate_phone=None, alternate_phone2=None, landline_phone=None):
    # Phone number validation (basic - can be extended)
    if pan and len(pan) != 10: # PAN is typically 10 chars
        st.error("Please enter a valid PAN (10 characters)")
        return False # Return False on validation failure
    if aadhaar and len(aadhaar) != 12: # Aadhaar is 12 digits
        st.error("Please enter a valid Aadhaar (12 digits)")
        return False # Return False on validation failure

    db = DBManager(DATABASE_NAME)
    try:
        db.execute_query(
            "UPDATE customers SET name=?, address=?, pan=?, aadhaar=?, alternate_phone=?, alternate_phone2=?, landline_phone=?, updated_at=CURRENT_TIMESTAMP WHERE phone=?",
            (name, address, pan, aadhaar, alternate_phone, alternate_phone2, landline_phone, phone)
        )
        print(f"Updating customer with phone: {phone} with details: Name={name}, Address={address}, PAN={pan}, Aadhaar={aadhaar}")
        st.success(f"Customer with phone '{phone}' updated successfully!") # Added success message
        return True
    except Exception as e:
        st.error(f"Error updating customer: {str(e)}")
        return False

def add_new_customer(name, phone, address="", pan="", aadhaar="", alternate_phone="", alternate_phone2="", landline_phone=""):
    # Input validation
    if not name or not phone:
        st.error("Customer name and phone number are required!")
        return None

    # Phone number validation
    if not phone.isdigit() or len(phone) < 10 or len(phone) > 15: # Added max length for phone
        st.error("Please enter a valid phone number (10-15 digits)")
        return None

    if pan and len(pan) != 10:
        st.error("Please enter a valid PAN (10 characters)")
        return None
    if aadhaar and len(aadhaar) != 12:
        st.error("Please enter a valid Aadhaar (12 digits)")
        return None

    db = DBManager(DATABASE_NAME)
    try:
        db.execute_query(
            "INSERT INTO customers (name, phone, address, pan, aadhaar, alternate_phone, alternate_phone2, landline_phone) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (name, phone, address, pan, aadhaar, alternate_phone, alternate_phone2, landline_phone)
        )
        # Fetch the last inserted ID if needed, though DBManager's execute_query doesn't return it directly.
        # If you need lastrowid, you'd extend DBManager or fetch by unique phone/name after insert.
        # For now, we assume successful insertion is enough.
        st.success(f"Customer '{name}' added successfully!")
        # To get the ID, you might need a separate query, e.g.:
        # customer_id = db.fetch_one("SELECT customer_id FROM customers WHERE phone = ?", (phone,))[0]
        # return customer_id
        return True # Return True for success, as we can't directly get lastrowid from DBManager's execute_query
    except sqlite3.IntegrityError as e:
        if "UNIQUE constraint failed: customers.phone" in str(e):
            st.error(f"Phone number '{phone}' already exists.")
        elif "UNIQUE constraint failed: customers.name" in str(e):
            st.error(f"Customer name '{name}' already exists.")
        else:
            st.error(f"An unexpected database error occurred: {str(e)}")
        return False
    except Exception as e:
        st.error(f"Error adding customer: {str(e)}")
        return False

def get_customer_details(customer_id):
    if not customer_id:
        return {}

    db = DBManager(DATABASE_NAME)
    try:
        details = db.fetch_one(
            "SELECT name, address, phone, pan, aadhaar, alternate_phone, alternate_phone2, landline_phone FROM customers WHERE customer_id = ?",
            (customer_id,)
        )
        if details:
            return {
                "name": details[0],
                "address": details[1],
                "phone": details[2],
                "pan": details[3],
                "aadhaar": details[4],
                "alternate_phone": details[5],
                "alternate_phone2": details[6],
                "landline_phone": details[7]
            }
        return {}
    except Exception as e:
        st.error(f"Error fetching customer details: {str(e)}")
        return {}