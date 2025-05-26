import streamlit as st
import sqlite3
import os
import io

from datetime import datetime

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

from utils.config import DATABASE_NAME, BILLS_FOLDER, create_bills_directory
from utils.convert_amount_to_word import convert_amount_to_words
from utils.get_download_link import get_download_link
from utils.load_and_display_pdf import load_and_display_pdf
from utils.db_manager import DBManager


def generate_purchase_pdf(supplier_details, purchase_data, purchase_items, download=False):
    """
    Generates a PDF invoice for a purchase transaction.

    Args:
        supplier_details (dict): Dictionary of supplier (customer) details.
        purchase_data (tuple): Tuple containing purchase details from the 'purchases' table.
        purchase_items (list of tuples): List of purchase item details from the 'purchase_items' table.
        download (bool): If True, returns PDF content and filename for download.

    Returns:
        tuple or str: (pdf_content, filename) if download=True, else file_path.
    """
    current_daily_bills_folder = create_bills_directory()

    supplier_name = supplier_details.get("name", "supplier").replace(" ", "_")
    invoice_id = purchase_data[0].replace("/", "_") if purchase_data else "unknown_invoice"
    filename = f"purchase_{supplier_name}_{invoice_id}.pdf"
    file_path = os.path.join(current_daily_bills_folder, filename)

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=(210 * mm, 297 * mm * 0.75),
        topMargin=45 * mm, bottomMargin=25 * mm, leftMargin=8 * mm, rightMargin=8 * mm
    )

    # --- Font Registration and Selection (Copied from generate_sell_pdf) ---
    font_name = 'Helvetica' # Default fallback
    bold_font_name = 'Helvetica-Bold' # Default bold fallback

    try:
        if os.path.exists('arial.ttf'):
            pdfmetrics.registerFont(TTFont('Arial', 'arial.ttf'))
            font_name = 'Arial'
            if os.path.exists('arialbd.ttf'):
                pdfmetrics.registerFont(TTFont('Arial-Bold', 'arialbd.ttf'))
                bold_font_name = 'Arial-Bold'
            else:
                bold_font_name = 'Helvetica-Bold'
        else:
            font_name = 'Helvetica'
            bold_font_name = 'Helvetica-Bold'
    except Exception as e:
        print(f"Warning: Could not register Arial fonts. Falling back to Helvetica. Error: {e}")
        font_name = 'Helvetica'
        bold_font_name = 'Helvetica-Bold'

    styles = getSampleStyleSheet()
    for style in ['Normal', 'h1', 'h2', 'h3', 'h4']:
        styles[style].fontName = font_name
    styles['Normal'].fontSize = 12
    styles['h1'].fontSize = 16
    styles['h2'].fontSize = 14
    styles['h3'].fontSize = 10
    styles['h4'].fontSize = 10

    elements = []

    elements.append(Paragraph(f"<b>Purchase Invoice: {purchase_data[0]}</b>", styles['h2']))

    purchase_date_str = purchase_data[1]
    try:
        formatted_purchase_date = datetime.strptime(purchase_date_str, '%Y-%m-%dT%H:%M:%S.%f').strftime('%Y-%m-%d')
    except ValueError:
        try:
            formatted_purchase_date = datetime.strptime(purchase_date_str, '%Y-%m-%d %H:%M:%S').strftime('%Y-%m-%d')
        except ValueError:
            formatted_purchase_date = purchase_date_str.split(' ')[0] if ' ' in purchase_date_str else purchase_date_str

    elements.append(Paragraph(f"Date: {formatted_purchase_date}", styles['h3']))
    elements.append(Spacer(1, 10))
    elements.append(Paragraph(f"<b>Bill From:</b>", styles['h3']))
    elements.append(Paragraph(f"Name: {supplier_details.get('name', '')}", styles['h3']))
    if supplier_details.get('pan'):
        elements.append(Paragraph(f"PAN: {supplier_details.get('pan', '')}", styles['h3']))
    if supplier_details.get('aadhaar'):
        elements.append(Paragraph(f"Aadhaar: {supplier_details.get('aadhaar', '')}", styles['h3']))
    elements.append(Spacer(1, 1))

    # Items table headers - Now includes CGST %, SGST %, CGST Amt, SGST Amt, and Total Amount (Incl. GST)
    # Number of columns: 12
    data = [
        ['Metal', 'Desc', 'Qty', 'Nt Wt', 'Purity', 'Rate', 'HSN', 'CGST %', 'SGST %', 'CGST', 'SGST', 'Total']
    ]

    total_taxable_overall = 0
    total_cgst_overall = 0
    total_sgst_overall = 0
    grand_total_items_incl_gst = 0

    for item in purchase_items:
        metal = item[3]
        qty = item[4]
        net_wt = item[5]
        metal_rate = item[10]
        description = item[11]
        purity = item[12] if item[12] else ''
        hsn = item[15] if item[15] else '7113'
        # Ensure item_taxable_amount is float
        item_taxable_amount = float(item[7]) # This is the 'amount' from the original purchase_items, treated as taxable

        # Reverting to fixed 1.5% for CGST and SGST for purchase items
        # as the 'purchase_items' schema does not seem to contain GST rates at indices 17 and 18.
        # If you intend to pass manual GST rates for purchases, ensure your
        # 'purchase_items' data structure includes these rates as floats/numbers
        # at specific indices, and then update this logic accordingly.
        cgst_rate_item = 1.5
        sgst_rate_item = 1.5

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

    table = Table(data)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.red),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), font_name),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
        ('BACKGROUND', (0, 1), (-1, -1), colors.white),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('ALIGN', (0, 1), (1, -1), 'LEFT'),
        ('ALIGN', (2, 1), (-1, -1), 'RIGHT'), # All numeric values are right-aligned
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))

    elements.append(table)
    #elements.append(Spacer(1, 5)) # Add some space after the consolidated table

    # Add overall totals to a separate table only if multiple items
    if len(purchase_items) > 1:
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

    # Add payment details from purchase_data separately
    cheque_amount = purchase_data[6]
    online_amount = purchase_data[7]
    upi_amount = purchase_data[8]
    cash_amount = purchase_data[9]
    amount_balance = purchase_data[10]

    elements.append(Paragraph(f"<b>Payment Details:</b>", styles['h3']))
    if cheque_amount > 0:
        elements.append(Paragraph(f"Cheque Amount: {cheque_amount:.2f}", styles['h3']))
    if online_amount > 0:
        elements.append(Paragraph(f"Online Amount: {online_amount:.2f}", styles['h3']))
    if upi_amount > 0:
        elements.append(Paragraph(f"UPI Amount: {upi_amount:.2f}", styles['h3']))
    if cash_amount > 0:
        elements.append(Paragraph(f"Cash Amount: {cash_amount:.2f}", styles['h3']))
    # Note: Old Gold Value is typically for sales, not purchases. Assuming it's not applicable here.
    # if old_gold_amount > 0:
    #     elements.append(Paragraph(f"Old Gold Value: {old_gold_amount:.2f}", styles['h3']))


    #elements.append(Spacer(1, 5))

    amount_in_words = convert_amount_to_words(total)
    elements.append(Paragraph(f"Total Amount: Rupees {amount_in_words} Only /-", styles['h3']))
    balance_amount_in_words = convert_amount_to_words(amount_balance)
    elements.append(Paragraph(
        f"<font color='red'>Balance Amount: Rupees {balance_amount_in_words} Only /-</font>",
        styles['h4']
    ))

    #elements.append(Spacer(1, 10))
    elements.append(Paragraph("<i>Note: Total amount is inclusive of making and other charges</i>", styles['h3']))

    doc.build(elements)

    with open(file_path, 'wb') as f:
        f.write(buffer.getvalue())

    return (buffer.getvalue(), filename) if download else file_path
