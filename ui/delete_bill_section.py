import streamlit as st

# Import necessary utility functions
from utils.delete_bill import delete_bill
#from utils.delete_udhaar_bill import delete_udhaar_bill

def delete_bill_section():
    st.subheader("Delete Bills")
    st.warning("Use this section with caution. Deleting a bill is irreversible.")

    invoice_id_to_delete = st.text_input("Enter Invoice ID to Delete (e.g., SAL-YYYY-NNNNN, PUR-YYYY-NNNNN, UDH-YYYY-CUSTOMERID-NNN)")

    if st.button("Delete Bill", key="confirm_delete_bill"):
        if invoice_id_to_delete:
            # Call the delete_bill function
            delete_bill(invoice_id_to_delete)
            #st.rerun() # Refresh the page after deletion attempt
        else:
            st.error("Please enter an Invoice ID to delete.")
    
    st.markdown("---")
    st.subheader("Delete Udhaar Deposit")
    st.warning("This will reverse an udhaar deposit and increase the pending balance of the associated sale invoice.")
    deposit_invoice_id_to_delete = st.text_input("Enter Udhaar Deposit Invoice ID to Delete (e.g., UDH-YYYY-CUSTOMERID-NNN)", key="delete_udhaar_deposit_input")

    if st.button("Delete Udhaar Deposit", key="confirm_delete_udhaar_deposit"):
        if deposit_invoice_id_to_delete:
            if delete_udhaar_bill(deposit_invoice_id_to_delete):
                st.success(f"Udhaar Deposit '{deposit_invoice_id_to_delete}' deleted and associated pending balance adjusted.")
                #st.rerun()
            else:
                st.error(f"Failed to delete Udhaar Deposit '{deposit_invoice_id_to_delete}'. Check console for details.")
        else:
            st.error("Please enter an Udhaar Deposit Invoice ID to delete.")

