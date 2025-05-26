import streamlit as st
import sqlite3
from utils.config import DATABASE_NAME,BILLS_FOLDER
import base64

# Function to create a download link for a file
def get_download_link(file_content, filename):
    b64 = base64.b64encode(file_content).decode()
    return f'<a href="data:application/octet-stream;base64,{b64}" download="{filename}">Download PDF</a>'

