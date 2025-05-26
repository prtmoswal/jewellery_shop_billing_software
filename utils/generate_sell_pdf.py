import streamlit as st
import sqlite3
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
from datetime import datetime
from utils.convert_amount_to_word import convert_amount_to_words
from utils.get_download_link import get_download_link
from utils.load_and_display_pdf import load_and_display_pdf
from utils.db_manager import DBManager

# --- PDF Generation ---
def generate_sell_pdf(customer_details, sale_data, sale_items, download=False):
    """
    Generates a PDF invoice for a sale transaction.

    Args:
        customer_details (dict): Dictionary of customer details.
        sale_data (tuple): Tuple containing sale details from the 'sales' table.
                            Expected order based on 'sales' table schema:
                            (invoice_id, sale_date, customer_id, total_amount,
                            cheque_amount, online_amount, upi_amount, cash_amount,
                            old_gold_amount, amount_balance, payment_mode, payment_other_info,
                            created_at, updated_at)
        sale_items (list of tuples): List of sale item details from the 'sale_items' table.
                                     Expected order based on 'sale_items' table schema:
                                     (item_id, invoice_id, product_id, metal, metal_rate, description, qty, net_wt,
                                     purity, gross_wt, loss_wt, making_charge, making_charge_type,
                                     stone_weight, stone_charge, wastage_percentage, amount,
                                     cgst_rate, sgst_rate, hsn, created_at, updated_at)
        download (bool): If True, returns PDF content and filename for download.
                         If False, saves PDF to file_path and returns file_path.

    Returns:
        tuple or str: (pdf_content, filename) if download=True, else file_path.
    """
    # Ensure the daily bills directory exists
    current_daily_bills_folder = create_bills_directory()

    # Get customer name for filename
    customer_name = customer_details.get("name", "customer").replace(" ", "_")
    invoice_id = sale_data[0].replace("/", "_") if sale_data else "unknown_invoice"
    filename = f"sale_{customer_name}_{invoice_id}.pdf"
    file_path = os.path.join(current_daily_bills_folder, filename)

    # Create PDF
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=(210 * mm, 297 * mm * 0.75),
                            topMargin=45 * mm, bottomMargin=25 * mm, leftMargin=8 * mm, rightMargin=8 * mm)

    # --- Font Registration and Selection ---
    # Attempt to register Arial and Arial-Bold. If not found, fallback to Helvetica and Helvetica-Bold.
    font_name = 'Helvetica' # Default fallback
    bold_font_name = 'Helvetica-Bold' # Default bold fallback

    try:
        # Check if 'arial.ttf' exists in the current directory or accessible path
        if os.path.exists('arial.ttf'):
            pdfmetrics.registerFont(TTFont('Arial', 'arial.ttf'))
            font_name = 'Arial'
            # Try to register Arial-Bold if arial.ttf was found.
            # Assuming 'arialbd.ttf' is the bold version. If not, this will fail gracefully.
            if os.path.exists('arialbd.ttf'):
                pdfmetrics.registerFont(TTFont('Arial-Bold', 'arialbd.ttf'))
                bold_font_name = 'Arial-Bold'
            else:
                # If Arial exists but Arial-Bold.ttf doesn't, use Arial for normal and Helvetica-Bold for bold
                bold_font_name = 'Helvetica-Bold'
        else:
            # If arial.ttf is not found, stick with Helvetica and Helvetica-Bold
            font_name = 'Helvetica'
            bold_font_name = 'Helvetica-Bold'
    except Exception as e:
        # Fallback to Helvetica if any font registration fails
        print(f"Warning: Could not register Arial fonts. Falling back to Helvetica. Error: {e}")
        font_name = 'Helvetica'
        bold_font_name = 'Helvetica-Bold'

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

    # Build document content
    elements = []

    # Header with sale details
    elements.append(Paragraph(f"<b>Sale Invoice: {sale_data[0]}</b>", styles['h2']))

    # --- Date Formatting Change ---
    sale_date_str = sale_data[1]
    try:
        formatted_sale_date = datetime.strptime(sale_date_str, '%Y-%m-%dT%H:%M:%S.%f').strftime('%Y-%m-%d')
    except ValueError:
        try:
            formatted_sale_date = datetime.strptime(sale_date_str, '%Y-%m-%d %H:%M:%S').strftime('%Y-%m-%d')
        except ValueError:
            formatted_sale_date = sale_date_str.split(' ')[0] if ' ' in sale_date_str else sale_date_str

    elements.append(Paragraph(f"Date: {formatted_sale_date}", styles['h3']))
    elements.append(Paragraph(f"<b>Bill To:</b>", styles['h3']))
    elements.append(Paragraph(f"Name: {customer_details.get('name', '')}", styles['h3']))

    if customer_details.get('pan'):
        elements.append(Paragraph(f"PAN: {customer_details.get('pan', '')}", styles['h3']))
    if customer_details.get('aadhaar'):
        elements.append(Paragraph(f"Aadhaar: {customer_details.get('aadhaar', '')}", styles['h3']))

    # Items table headers - Now includes CGST %, SGST %, CGST Amt, SGST Amt, and Total Amount (Incl. GST)
    # Number of columns: 12
    data = [
        ['Metal', 'Desc', 'Qty', 'Nt Wt', 'Purity', 'Rate', 'HSN', 'CGST %', 'SGST %', 'CGST', 'SGST', 'Total']
    ]

    total_taxable_overall = 0 # To calculate overall GST
    total_cgst_overall = 0
    total_sgst_overall = 0
    grand_total_items_incl_gst = 0 # Sum of item-wise total amounts including GST

    for item in sale_items:
        metal = item[3]
        metal_rate = item[4]
        description = item[5]
        qty = item[6]
        net_wt = item[7]
        purity = item[8] if item[8] else ''
        item_taxable_amount = item[16] # This is the amount before GST for this item
        cgst_rate_item = item[17] if item[17] is not None else 0
        sgst_rate_item = item[18] if item[18] is not None else 0
        hsn = item[19] if item[19] else '7113'

        # Calculate item-wise GST amounts
        item_cgst_amount = item_taxable_amount * (cgst_rate_item / 100.0)
        item_sgst_amount = item_taxable_amount * (sgst_rate_item / 100.0)
        item_total_amount_incl_gst = item_taxable_amount + item_cgst_amount + item_sgst_amount

        # Add to overall totals
        total_taxable_overall += item_taxable_amount
        total_cgst_overall += item_cgst_amount
        total_sgst_overall += item_sgst_amount
        grand_total_items_incl_gst += item_total_amount_incl_gst

        data.append([
            metal,
            description,
            str(qty),
            f"{float(net_wt):.3f}",
            purity,
            f"{float(metal_rate):.2f}",
            hsn,
            f"{cgst_rate_item:.2f}%", # CGST %
            f"{sgst_rate_item:.2f}%", # SGST %
            f"{item_cgst_amount:.2f}",
            f"{item_sgst_amount:.2f}",
            f"{item_total_amount_incl_gst:.2f}"
        ])

    # Calculate overall round off and final total based on sum of item-wise totals
    round_off = round(grand_total_items_incl_gst) - grand_total_items_incl_gst
    total = grand_total_items_incl_gst + round_off

    # Create the main item table
    table = Table(data)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.red), # Header row background
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.black), # Header row text color
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'), # Header row alignment
        ('FONTNAME', (0, 0), (-1, 0), font_name),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
        ('BACKGROUND', (0, 1), (-1, -1), colors.white), # All other rows background
        ('GRID', (0, 0), (-1, -1), 1, colors.black), # Grid for all rows
        ('ALIGN', (0, 1), (1, -1), 'LEFT'), # First two columns (Metal, Desc) left-aligned
        ('ALIGN', (2, 1), (-1, -1), 'RIGHT'), # All numeric values right-aligned
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))

    elements.append(table)
    #elements.append(Spacer(1, 5)) # Add some space after the consolidated table

    # Add overall totals to a separate table only if multiple items
    if len(sale_items) > 1:
        # Create data for the separate totals table
        totals_data = [
            [''] * 10 + ['Total CGST:', f"{total_cgst_overall:.2f}"], # 10 empty strings for 12 columns - 2 label/value columns
            [''] * 10 + ['Total SGST:', f"{total_sgst_overall:.2f}"],
            [''] * 10 + ['Round Off:', f"{round_off:.2f}"],
            [''] * 10 + ['Grand Total:', f"{total:.2f}"]
        ]
        totals_table = Table(totals_data)
        totals_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.white),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
            ('ALIGN', (0, 0), (-1, -1), 'RIGHT'), # Align all content to the right
            ('FONTNAME', (0, 0), (-1, -1), font_name),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('GRID', (0, 0), (-1, -1), 1, colors.white), # Keep grid lines white for a cleaner look
            ('FONTNAME', (10, 0), (10, -1), bold_font_name), # Make labels bold for totals (column 10)
            ('LINEABOVE', (0, 0), (-1, 0), 1, colors.black), # Line above the first total row
        ]))
        elements.append(totals_table)
        #elements.append(Spacer(1, 5))

    # Add payment details from sale_data (sales table) separately
    cheque_amount = sale_data[4]
    online_amount = sale_data[5]
    upi_amount = sale_data[6]
    cash_amount = sale_data[7]
    old_gold_amount = sale_data[8]
    amount_balance = sale_data[9]

    # Reintroduce Payment Details header
    elements.append(Paragraph(f"<b>Payment Details:</b>", styles['h3']))

    # Add individual payment mode lines if amount > 0
    if cheque_amount > 0:
        elements.append(Paragraph(f"Cheque Amount: {cheque_amount:.2f}", styles['h3']))
    if online_amount > 0:
        elements.append(Paragraph(f"Online Amount: {online_amount:.2f}", styles['h3']))
    if upi_amount > 0:
        elements.append(Paragraph(f"UPI Amount: {upi_amount:.2f}", styles['h3']))
    if cash_amount > 0:
        elements.append(Paragraph(f"Cash Amount: {cash_amount:.2f}", styles['h3']))
    if old_gold_amount > 0:
        elements.append(Paragraph(f"Old Gold Value: {old_gold_amount:.2f}", styles['h3']))

    #elements.append(Spacer(1, 5)) # Add some space after payment details

    amount_in_words = convert_amount_to_words(total)
    elements.append(Paragraph(f"Total Amount: Rupees {amount_in_words} Only /-", styles['h3']))
    balance_amount_in_words = convert_amount_to_words(amount_balance)
    elements.append(Paragraph(f"<font color='red'>Balance Amount: Rupees {balance_amount_in_words} Only /-</font>", styles['h4']))

    # Note at bottom
    #elements.append(Spacer(1, 5))
    elements.append(Paragraph("<i>Note: Total amount is inclusive of making and other charges</i>", styles['h3']))

    # Build the PDF
    doc.build(elements)

    # Save to file
    with open(file_path, 'wb') as f:
        f.write(buffer.getvalue())

    if download:
        return buffer.getvalue(), filename
    else:
        return file_path
