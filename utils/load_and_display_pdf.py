import streamlit as st
import sqlite3
from utils.config import DATABASE_NAME,BILLS_FOLDER


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
