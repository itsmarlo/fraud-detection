from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    HRFlowable,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


OUTPUT_DIR = Path(__file__).resolve().parents[1] / "sample_documents"
NAVY = colors.HexColor("#071A36")
BLUE = colors.HexColor("#0875D1")
YELLOW = colors.HexColor("#F5C400")
PALE_BLUE = colors.HexColor("#F3F7FB")
MID_GREY = colors.HexColor("#5C687C")
LINE = colors.HexColor("#DCE1E8")


styles = getSampleStyleSheet()
styles.add(
    ParagraphStyle(
        "DocumentTitle",
        parent=styles["Title"],
        fontName="Helvetica-Bold",
        fontSize=22,
        leading=26,
        textColor=NAVY,
        spaceAfter=5 * mm,
    )
)
styles.add(
    ParagraphStyle(
        "Section",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=11,
        leading=14,
        textColor=BLUE,
        spaceBefore=5 * mm,
        spaceAfter=2 * mm,
    )
)
styles.add(
    ParagraphStyle(
        "BodySmall",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=9,
        leading=13,
        textColor=NAVY,
    )
)
styles.add(
    ParagraphStyle(
        "FinePrint",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=7.5,
        leading=10,
        textColor=MID_GREY,
    )
)
styles.add(
    ParagraphStyle(
        "RightSmall",
        parent=styles["BodySmall"],
        alignment=TA_RIGHT,
    )
)


def page_header_footer(canvas, doc):
    canvas.saveState()
    width, height = A4
    canvas.setFillColor(NAVY)
    canvas.rect(0, height - 22 * mm, width, 22 * mm, fill=1, stroke=0)
    canvas.setFillColor(colors.white)
    canvas.setFont("Helvetica-Bold", 15)
    canvas.drawString(18 * mm, height - 14 * mm, "SAP Fioneer")

    canvas.setFillColor(YELLOW)
    for row, count in enumerate((5, 4, 3)):
        for column in range(count):
            canvas.rect(
                53 * mm + column * 2.6 * mm,
                height - (10.3 + row * 2.6) * mm,
                1.7 * mm,
                1.7 * mm,
                fill=1,
                stroke=0,
            )

    canvas.setFillColor(colors.HexColor("#FFE676"))
    canvas.setFont("Helvetica-Bold", 8)
    canvas.drawRightString(width - 18 * mm, height - 14 * mm, "CLAIMS INTELLIGENCE DEMO")

    canvas.setStrokeColor(YELLOW)
    canvas.setLineWidth(2)
    canvas.line(0, height - 22 * mm, width, height - 22 * mm)

    canvas.setFillColor(colors.HexColor("#B9C0CB"))
    canvas.setFont("Helvetica-Bold", 34)
    canvas.translate(width / 2, height / 2)
    canvas.rotate(32)
    canvas.drawCentredString(0, 0, "DEMO - NOT A REAL DOCUMENT")
    canvas.rotate(-32)
    canvas.translate(-width / 2, -height / 2)

    canvas.setFillColor(MID_GREY)
    canvas.setFont("Helvetica", 7)
    canvas.drawString(18 * mm, 12 * mm, "Synthetic evidence generated for fraud-detection testing only.")
    canvas.drawRightString(width - 18 * mm, 12 * mm, f"Page {doc.page}")
    canvas.restoreState()


def key_value_table(rows, widths=(52 * mm, 104 * mm)):
    table = Table(rows, colWidths=list(widths), hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("FONTNAME", (1, 0), (1, -1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("TEXTCOLOR", (0, 0), (0, -1), MID_GREY),
                ("TEXTCOLOR", (1, 0), (1, -1), NAVY),
                ("BACKGROUND", (0, 0), (-1, -1), PALE_BLUE),
                ("GRID", (0, 0), (-1, -1), 0.35, LINE),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("LEFTPADDING", (0, 0), (-1, -1), 7),
            ]
        )
    )
    return table


def section(title):
    return Paragraph(title.upper(), styles["Section"])


def build_pdf(filename, title, subtitle, story):
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    document = SimpleDocTemplate(
        str(OUTPUT_DIR / filename),
        pagesize=A4,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=31 * mm,
        bottomMargin=20 * mm,
        title=title,
        author="SAP Fioneer Claims Intelligence Demo",
        subject="Synthetic insurance claim evidence",
    )
    content = [
        Paragraph(title, styles["DocumentTitle"]),
        Paragraph(subtitle, styles["FinePrint"]),
        Spacer(1, 3 * mm),
        HRFlowable(width="100%", thickness=1, color=LINE),
        Spacer(1, 2 * mm),
        *story,
    ]
    document.build(content, onFirstPage=page_header_footer, onLaterPages=page_header_footer)


def repair_invoice(filename, invoice_number, invoice_date, total, suspicious=False):
    label = "SUSPICIOUS TEST VARIANT" if suspicious else "Supporting document"
    line_items = [
        ["Repair item", "Qty", "Unit price", "Amount"],
        ["Front bumper assembly", "1", "EUR 2,400.00", "EUR 2,400.00"],
        ["Left LED headlamp", "1", "EUR 1,650.00", "EUR 1,650.00"],
        ["Paint and body work", "12 h", "EUR 145.00", "EUR 1,740.00"],
        ["Diagnostics and calibration", "1", "EUR 890.00", "EUR 890.00"],
        ["Parts and workshop materials", "1", "EUR 1,120.00", "EUR 1,120.00"],
    ]
    if suspicious:
        line_items = [
            ["Repair item", "Qty", "Unit price", "Amount"],
            ["Complete front assembly replacement", "1", "EUR 5,900.00", "EUR 5,900.00"],
            ["Lighting and sensor package", "1", "EUR 3,950.00", "EUR 3,950.00"],
            ["Body, paint, and calibration", "1", "EUR 2,750.00", "EUR 2,750.00"],
        ]

    items = Table(line_items, colWidths=[83 * mm, 16 * mm, 28 * mm, 29 * mm])
    items.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), NAVY),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), 8.5),
                ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
                ("GRID", (0, 0), (-1, -1), 0.35, LINE),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, PALE_BLUE]),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    story = [
        key_value_table(
            [
                ["Invoice number", invoice_number],
                ["Invoice date", invoice_date],
                ["Claim ID", "CLM-DEMO-10001"],
                ["Policy ID", "POL-20001"],
                ["Customer", "Alex Demo"],
                ["Vehicle", "2020 Demo Motors Sedan / DEMO-VIN-0042"],
            ]
        ),
        section("Repair facility"),
        Paragraph(
            "Fictional Auto Repair GmbH<br/>Demo Street 18, 10115 Berlin<br/>Garage ID: GAR-009",
            styles["BodySmall"],
        ),
        section("Repair details"),
        items,
        Spacer(1, 4 * mm),
        key_value_table(
            [
                ["Repair total", f"EUR {total}"],
                ["Payment status", "Outstanding"],
                ["Synthetic bank reference", "DE00 0000 0000 0000 0000 00"],
            ]
        ),
        section("Workshop statement"),
        Paragraph(
            "Repairs relate to front bumper and left headlamp damage reported after the "
            "collision on 2026-05-10. This document contains synthetic test data.",
            styles["BodySmall"],
        ),
    ]
    build_pdf(filename, "VEHICLE REPAIR STATEMENT", label, story)


def police_report():
    story = [
        key_value_table(
            [
                ["Police report number", "BER-DEMO-2026-0510-1842"],
                ["Police report date", "2026-05-10"],
                ["Incident date", "2026-05-10"],
                ["Incident time", "02:15"],
                ["Claim ID", "CLM-DEMO-10001"],
                ["Location", "Invalidenstrasse, Berlin"],
            ]
        ),
        section("Parties"),
        key_value_table(
            [
                ["Vehicle A", "Demo Motors Sedan / driver Alex Demo"],
                ["Vehicle B", "Fictional Compact / driver Jordan Example"],
                ["Injuries", "None reported"],
                ["Third party involved", "Yes"],
            ]
        ),
        section("Incident summary"),
        Paragraph(
            "Vehicle A and Vehicle B made contact at low speed near an intersection. "
            "Vehicle A showed visible damage to the front bumper and left headlamp. "
            "Both drivers exchanged synthetic insurance details. No towing was required.",
            styles["BodySmall"],
        ),
        section("Officer observations"),
        Paragraph(
            "Road surface was dry and street lighting was operational. Photographs were "
            "declared by the claimant. This is a fictional police report created only for "
            "software demonstration and testing.",
            styles["BodySmall"],
        ),
        section("Recorded by"),
        Paragraph("Officer DEMO-417 · Berlin Test Precinct", styles["BodySmall"]),
    ]
    build_pdf("02_police_report.pdf", "POLICE REPORT", "Supporting document", story)


def accident_report():
    story = [
        key_value_table(
            [
                ["Accident report number", "AR-CLM-DEMO-10001"],
                ["Claim ID", "CLM-DEMO-10001"],
                ["Accident date", "2026-05-10"],
                ["Report date", "2026-05-20"],
                ["Policy ID", "POL-20001"],
                ["Coverage", "COMPREHENSIVE"],
            ]
        ),
        section("Claimant description"),
        Paragraph(
            "At approximately 02:15, I entered the intersection at low speed. The other "
            "vehicle moved into my lane and contact occurred at the front-left area of my "
            "vehicle. I stopped immediately and exchanged details with the other driver.",
            styles["BodySmall"],
        ),
        section("Reported damage"),
        key_value_table(
            [
                ["Primary area", "Front bumper"],
                ["Secondary area", "Left headlamp"],
                ["Vehicle drivable", "Yes"],
                ["Estimated repair cost", "EUR 7,800.00"],
                ["Damage photos available", "Yes"],
            ]
        ),
        section("Declaration"),
        Paragraph(
            "I confirm that the information above is complete to the best of my knowledge. "
            "Signed electronically by Alex Demo on 2026-05-20. Synthetic test record.",
            styles["BodySmall"],
        ),
    ]
    build_pdf("03_accident_report.pdf", "ACCIDENT REPORT", "Claimant statement", story)


def witness_statement():
    story = [
        key_value_table(
            [
                ["Statement number", "WS-DEMO-10001-01"],
                ["Claim ID", "CLM-DEMO-10001"],
                ["Witness", "Taylor Sample"],
                ["Statement date", "2026-05-12"],
                ["Incident date", "2026-05-10"],
                ["Relationship to parties", "None"],
            ]
        ),
        section("Witness account"),
        Paragraph(
            "I was walking on the north side of the intersection and heard braking before "
            "seeing the two vehicles make contact. The impact appeared to involve the front "
            "left side of the dark sedan. Both drivers exited their vehicles and spoke calmly.",
            styles["BodySmall"],
        ),
        section("Additional observations"),
        Paragraph(
            "Traffic was light. Visibility was adequate under street lighting. I did not "
            "observe any person leave the scene and did not see an injury. This witness and "
            "statement are entirely fictional and intended only for application testing.",
            styles["BodySmall"],
        ),
        section("Declaration"),
        Paragraph(
            "Electronically acknowledged by Taylor Sample on 2026-05-12.",
            styles["BodySmall"],
        ),
    ]
    build_pdf("04_witness_statement.pdf", "WITNESS STATEMENT", "Independent account", story)


def main():
    repair_invoice(
        "01_repair_invoice.pdf",
        invoice_number="INV-DEMO-2026-0511",
        invoice_date="2026-05-11",
        total="7,800.00",
    )
    police_report()
    accident_report()
    witness_statement()
    repair_invoice(
        "05_suspicious_repair_invoice.pdf",
        invoice_number="INV-RISK-2026-0508",
        invoice_date="2026-05-08",
        total="12,600.00",
        suspicious=True,
    )
    print(f"Generated sample PDFs in {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
