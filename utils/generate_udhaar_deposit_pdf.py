import streamlit as st
import sqlite3
# Corrected import: use create_bills_directory function instead of direct variable
from utils.config import DATABASE_NAME, BILLS_FOLDER, create_bills_directory
import os
import io
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from datetime import datetime # Import datetime for date formatting
from utils.convert_amount_to_word import convert_amount_to_words 
from utils.get_download_link import get_download_link
from utils.load_and_display_pdf import load_and_display_pdf
from utils.db_manager import DBManager

def generate_udhaar_deposit_pdf(customer_details, deposit_data, original_invoice_data, download=False):
    # Ensure the daily bills directory exists and get its path
    current_daily_bills_folder = create_bills_directory()

    # Get customer name for filename
    customer_name = customer_details.get("name", "customer").replace(" ", "_")
    invoice_id = deposit_data[0].replace("/", "_") if deposit_data else "unknown_invoice"
    filename = f"deposit_{customer_name}_{invoice_id}.pdf"
    # Use the path returned by create_bills_directory()
    file_path = os.path.join(current_daily_bills_folder, filename)
    
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
