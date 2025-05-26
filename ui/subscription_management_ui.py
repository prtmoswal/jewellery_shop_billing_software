import streamlit as st
from datetime import datetime, timedelta
import sqlite3
import pandas as pd

# Assuming DBManager and get_all_customer_names are available from your utils
from utils.db_manager import DBManager
from utils.fetch_customers import get_all_customer_names

# Initialize DBManager
db_manager = DBManager(st.secrets["database"]["path"]) # Adjust path if needed, or pass it from app_v2.py

def add_subscription(customer_id, subscription_code, plan_type):
    """Adds a new subscription to the database."""
    conn = db_manager.get_connection()
    cursor = conn.cursor()
    try:
        start_date = datetime.now()
        end_date = None

        if plan_type == "Weekly":
            end_date = start_date + timedelta(weeks=1)
        elif plan_type == "Monthly":
            end_date = start_date + timedelta(days=30) # Simple monthly, consider calendar months for precision
        elif plan_type == "Quarterly":
            end_date = start_date + timedelta(days=90) # Simple quarterly
        elif plan_type == "Yearly":
            end_date = start_date + timedelta(days=365) # Simple yearly

        if end_date:
            cursor.execute(
                """
                INSERT INTO subscriptions (customer_id, subscription_code, plan_type, start_date, end_date, is_active, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (customer_id, subscription_code, plan_type, start_date.isoformat(), end_date.isoformat(), 1, datetime.now().isoformat(), datetime.now().isoformat())
            )
            conn.commit()
            return True
        else:
            st.error("Invalid plan type selected.")
            return False
    except sqlite3.IntegrityError:
        st.error(f"Subscription code '{subscription_code}' already exists. Please use a unique code.")
        return False
    except Exception as e:
        st.error(f"Error adding subscription: {e}")
        return False
    finally:
        conn.close()

def get_all_subscriptions():
    """Fetches all subscriptions from the database."""
    conn = db_manager.get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT
                s.id,
                c.name AS customer_name,
                s.subscription_code,
                s.plan_type,
                s.start_date,
                s.end_date,
                s.is_active
            FROM
                subscriptions s
            JOIN
                customers c ON s.customer_id = c.id
            ORDER BY
                s.end_date DESC
        """)
        subscriptions = cursor.fetchall()
        return subscriptions
    except Exception as e:
        st.error(f"Error fetching subscriptions: {e}")
        return []
    finally:
        conn.close()

def deactivate_subscription(subscription_id):
    """Deactivates a subscription by setting is_active to 0."""
    conn = db_manager.get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "UPDATE subscriptions SET is_active = 0, updated_at = ? WHERE id = ?",
            (datetime.now().isoformat(), subscription_id)
        )
        conn.commit()
        return True
    except Exception as e:
        st.error(f"Error deactivating subscription: {e}")
        return False
    finally:
        conn.close()


def subscription_section():
    st.header("Subscription Management")

    st.subheader("Add New Subscription")

    all_customer_names = get_all_customer_names()
    customer_name = st.selectbox("Select Customer", [""] + all_customer_names, key="sub_customer_select")

    subscription_code = st.text_input("Subscription Code", key="sub_code_input")
    plan_type = st.selectbox("Plan Type", ["Weekly", "Monthly", "Quarterly", "Yearly"], key="plan_type_select")

    if st.button("Add Subscription", key="add_sub_button"):
        if customer_name and subscription_code and plan_type:
            customer_details = db_manager.fetch_data("customers", {"name": customer_name})
            if customer_details:
                customer_id = customer_details[0][0] # Assuming id is the first column
                if add_subscription(customer_id, subscription_code, plan_type):
                    st.success(f"Subscription '{subscription_code}' added successfully for {customer_name}!")
                    st.experimental_rerun() # Rerun to refresh the list
            else:
                st.error("Selected customer not found.")
        else:
            st.warning("Please fill in all subscription details.")

    st.subheader("Current Subscriptions")

    subscriptions_data = get_all_subscriptions()

    if subscriptions_data:
        df = pd.DataFrame(subscriptions_data, columns=[
            "ID", "Customer Name", "Subscription Code", "Plan Type", "Start Date", "End Date", "Is Active"
        ])
        df["Is Active"] = df["Is Active"].apply(lambda x: "Active" if x == 1 else "Inactive")
        df["Start Date"] = pd.to_datetime(df["Start Date"]).dt.strftime('%Y-%m-%d')
        df["End Date"] = pd.to_datetime(df["End Date"]).dt.strftime('%Y-%m-%d')

        st.dataframe(df, use_container_width=True)

        # Option to deactivate a subscription
        st.subheader("Deactivate Subscription")
        sub_ids = [sub[0] for sub in subscriptions_data if sub[6] == 1] # Only active subscriptions
        if sub_ids:
            selected_sub_id = st.selectbox("Select Subscription ID to Deactivate", [""] + sub_ids, key="deactivate_sub_select")
            if selected_sub_id and st.button("Deactivate Selected Subscription", key="deactivate_button"):
                if deactivate_subscription(selected_sub_id):
                    st.success(f"Subscription ID {selected_sub_id} deactivated successfully.")
                    st.experimental_rerun()
        else:
            st.info("No active subscriptions to deactivate.")
    else:
        st.info("No subscriptions found.")