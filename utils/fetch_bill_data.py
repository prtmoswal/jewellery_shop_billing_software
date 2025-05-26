import streamlit as st
import sqlite3
from utils.config import DATABASE_NAME, BILLS_FOLDER
from utils.db_manager import DBManager


def fetch_bill_data(invoice_id):
    db = DBManager(DATABASE_NAME)
    customer_details = {}
    sale_data = None
    sale_items = []

    # Fetch sale header
    sale_record = db.fetch_one("SELECT * FROM sales WHERE invoice_id = ?", (invoice_id,))
    if sale_record:
        sale_data = sale_record

        # Fetch customer details
        customer_id = sale_record[2]  # Assuming customer_id is at index 2
        customer_record = db.fetch_one(
            "SELECT * FROM customers WHERE customer_id = ?", (customer_id,)
        )
        if customer_record:
            # Assuming fetch_one returns a tuple, we create a dictionary manually, if needed.
            # If your DBManager already returns a dict, you can skip this.
            customer_details = dict(zip(['customer_id', 'name', 'phone', 'address', 'pan', 'aadhaar', 'firstname', 'lastname', 'gender', 'email', 'alternate_phone', 'alternate_phone2', 'landline_phone', 'city', 'state', 'country', 'pincode', 'created_at', 'updated_at'], customer_record))


        # Fetch sale items
        sale_items = db.fetch_all("SELECT * FROM sale_items WHERE invoice_id = ?", (invoice_id,))

    return customer_details, sale_data, sale_items