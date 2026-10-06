"""
Gün Sonu Kasa Kapanış Z-Raporu PDF Üretim Servisi (ReportLab).
"""

import io
from datetime import date
from typing import Optional, Dict, Any
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle


def generate_z_report_pdf(
    tenant_name: str,
    branch_name: str,
    report_date: date,
    register_data: Optional[Dict[str, Any]],
    sales_data: Dict[str, Any],
    created_by: str
) -> bytes:
    """
    Z-Raporu PDF dokümanı oluşturur ve bayt çıktısı verir.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=1.5 * cm,
        leftMargin=1.5 * cm,
        topMargin=1.5 * cm,
        bottomMargin=1.5 * cm
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "ZTitle",
        parent=styles["Heading1"],
        fontSize=20,
        leading=24,
        textColor=colors.HexColor("#0F172A"),
        alignment=1  # Center
    )
    subtitle_style = ParagraphStyle(
        "ZSubTitle",
        parent=styles["Normal"],
        fontSize=12,
        leading=16,
        textColor=colors.HexColor("#475569"),
        alignment=1
    )
    section_style = ParagraphStyle(
        "ZSection",
        parent=styles["Heading2"],
        fontSize=13,
        leading=18,
        textColor=colors.HexColor("#1E293B"),
        spaceAfter=6
    )
    cell_style = ParagraphStyle(
        "ZCell",
        parent=styles["Normal"],
        fontSize=10,
        leading=13,
        textColor=colors.HexColor("#1E293B")
    )
    cell_bold = ParagraphStyle(
        "ZCellBold",
        parent=styles["Normal"],
        fontSize=10,
        leading=13,
        fontName="Helvetica-Bold",
        textColor=colors.HexColor("#0F172A")
    )

    elements = []

    # Başlık ve Üst Bilgi
    elements.append(Paragraph(f"KANTİNPOS — GÜN SONU Z-RAPORU", title_style))
    elements.append(Spacer(1, 4))
    elements.append(Paragraph(f"<b>İşletme:</b> {tenant_name} | <b>Şube:</b> {branch_name}", subtitle_style))
    elements.append(Paragraph(f"<b>Tarih:</b> {report_date.strftime('%d.%m.%Y')} | <b>Raporu Alan:</b> {created_by}", subtitle_style))
    elements.append(Spacer(1, 12))
    elements.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#CBD5E1"), spaceAfter=15))

    # Kasa Sayımı Özeti
    elements.append(Paragraph("1. FİZİKİ KASA SAYIM BİLGİLERİ", section_style))

    if register_data:
        c200 = register_data.get("Count200", 0)
        c100 = register_data.get("Count100", 0)
        c50 = register_data.get("Count50", 0)
        c20 = register_data.get("Count20", 0)
        c10 = register_data.get("Count10", 0)
        c5 = register_data.get("Count5", 0)
        direct_cash = register_data.get("DirectCashTotal")
        cash_tot = register_data.get("CashTotal", 0.0)
        card_tot = register_data.get("CreditCardTotal", 0.0)
        exp_tot = register_data.get("ExpenseTotal", 0.0)
        open_cash = register_data.get("OpeningCash", 0.0)
        notes = register_data.get("Notes") or "Belirtilmedi"

        if direct_cash is not None:
            cash_detail = f"Direkt Giriş: {direct_cash:,.2f} ₺"
        else:
            cash_detail = (
                f"200x{c200} ({c200*200}₺) | 100x{c100} ({c100*100}₺) | 50x{c50} ({c50*50}₺)<br/>"
                f"20x{c200} ({c20*20}₺) | 10x{c10} ({c10*10}₺) | 5x{c5} ({c5*5}₺)"
            )

        reg_table_data = [
            [Paragraph("Açılış Devir Kasa:", cell_style), Paragraph(f"{open_cash:,.2f} ₺", cell_bold)],
            [Paragraph("Fiziki Nakit Sayımı Toplamı:", cell_style), Paragraph(f"{cash_tot:,.2f} ₺", cell_bold)],
            [Paragraph("Banknot Detayları:", cell_style), Paragraph(cash_detail, cell_style)],
            [Paragraph("POS / Kredi Kartı Gün Sonu:", cell_style), Paragraph(f"{card_tot:,.2f} ₺", cell_bold)],
            [Paragraph("Kasadan Çıkan Masraflar:", cell_style), Paragraph(f"{exp_tot:,.2f} ₺", cell_bold)],
            [Paragraph("Kasa Açıklama / Not:", cell_style), Paragraph(notes, cell_style)],
        ]
    else:
        reg_table_data = [
            [Paragraph("Durum:", cell_style), Paragraph("Bu tarih için henüz fiziki kasa sayımı kaydedilmemiş.", cell_style)]
        ]

    t1 = Table(reg_table_data, colWidths=[6.5 * cm, 11 * cm])
    t1.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    elements.append(t1)
    elements.append(Spacer(1, 15))

    # Sistem Satışları ve Fark Analizi
    elements.append(Paragraph("2. SİSTEM SATIŞ CİROSU VE KASA MUTABAKATI", section_style))

    sys_cash = float(sales_data.get("cash_revenue", 0.0))
    sys_card = float(sales_data.get("card_revenue", 0.0))
    sys_total = float(sales_data.get("total_revenue", 0.0))
    tx_count = int(sales_data.get("transaction_count", 0))

    actual_cash = float(register_data.get("CashTotal", 0.0)) if register_data else 0.0
    actual_card = float(register_data.get("CreditCardTotal", 0.0)) if register_data else 0.0

    cash_diff = round(actual_cash - sys_cash, 2)
    card_diff = round(actual_card - sys_card, 2)

    diff_cash_str = f"+{cash_diff:,.2f} ₺ (Fazla)" if cash_diff > 0 else (f"{cash_diff:,.2f} ₺ (Açık)" if cash_diff < 0 else "0,00 ₺ (Tam)")
    diff_card_str = f"+{card_diff:,.2f} ₺ (Fazla)" if card_diff > 0 else (f"{card_diff:,.2f} ₺ (Açık)" if card_diff < 0 else "0,00 ₺ (Tam)")

    diff_table_data = [
        [Paragraph("Kalem", cell_bold), Paragraph("Sistem Kaydı", cell_bold), Paragraph("Fiziki / Beyan", cell_bold), Paragraph("Fark (Mutabakat)", cell_bold)],
        [Paragraph("Nakit Ciro", cell_style), Paragraph(f"{sys_cash:,.2f} ₺", cell_style), Paragraph(f"{actual_cash:,.2f} ₺", cell_style), Paragraph(diff_cash_str, cell_bold)],
        [Paragraph("Kredi Kartı Ciro", cell_style), Paragraph(f"{sys_card:,.2f} ₺", cell_style), Paragraph(f"{actual_card:,.2f} ₺", cell_style), Paragraph(diff_card_str, cell_bold)],
        [Paragraph("Toplam Ciro", cell_bold), Paragraph(f"{sys_total:,.2f} ₺", cell_bold), Paragraph(f"{(actual_cash + actual_card):,.2f} ₺", cell_bold), Paragraph(f"{(cash_diff + card_diff):,.2f} ₺", cell_bold)],
        [Paragraph("İşlem / Fiş Adedi", cell_style), Paragraph(f"{tx_count} işlem", cell_style), Paragraph("-", cell_style), Paragraph("-", cell_style)],
    ]

    t2 = Table(diff_table_data, colWidths=[4 * cm, 4.5 * cm, 4.5 * cm, 4.5 * cm])
    t2.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#0F172A")),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ]))
    elements.append(t2)
    elements.append(Spacer(1, 25))

    # İmza Blokları
    imza_data = [
        [Paragraph("<b>Teslim Eden (Kasiyer / Personel):</b><br/><br/><br/>İmza: _______________________", cell_style),
         Paragraph("<b>Teslim Alan (Kantin Yöneticisi):</b><br/><br/><br/>İmza: _______________________", cell_style)]
    ]
    t3 = Table(imza_data, colWidths=[8.5 * cm, 9 * cm])
    t3.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, -1), 10),
    ]))
    elements.append(t3)

    doc.build(elements)
    buffer.seek(0)
    return buffer.getvalue()
