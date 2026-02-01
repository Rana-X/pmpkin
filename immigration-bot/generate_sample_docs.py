"""Generate sample RFE and Profile PDFs for the demo flow."""

from pathlib import Path
from fpdf import FPDF

SAMPLE_DIR = Path(__file__).parent / "sample_docs"
SAMPLE_DIR.mkdir(exist_ok=True)


def generate_rfe_pdf():
    pdf = FPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=25)

    # Header
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 12, "U.S. Citizenship and Immigration Services", ln=True, align="C")
    pdf.set_font("Helvetica", "B", 14)
    pdf.cell(0, 10, "Request for Evidence (RFE)", ln=True, align="C")
    pdf.ln(8)

    # Divider
    pdf.set_draw_color(200, 200, 200)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(6)

    # Case info
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(50, 7, "Receipt Number:", ln=False)
    pdf.set_font("Helvetica", "", 11)
    pdf.cell(0, 7, "WAC-25-123-45678", ln=True)

    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(50, 7, "Beneficiary:", ln=False)
    pdf.set_font("Helvetica", "", 11)
    pdf.cell(0, 7, "McLovin", ln=True)

    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(50, 7, "Petitioner:", ln=False)
    pdf.set_font("Helvetica", "", 11)
    pdf.cell(0, 7, "Pumpkin Tech Consulting LLC", ln=True)

    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(50, 7, "Classification:", ln=False)
    pdf.set_font("Helvetica", "", 11)
    pdf.cell(0, 7, "H-1B Specialty Occupation (INA 101(a)(15)(H)(i)(b))", ln=True)

    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(50, 7, "Service Center:", ln=False)
    pdf.set_font("Helvetica", "", 11)
    pdf.cell(0, 7, "California Service Center", ln=True)

    pdf.ln(6)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(6)

    # Issue
    pdf.set_font("Helvetica", "B", 13)
    pdf.cell(0, 9, "Issue: Specialty Occupation", ln=True)
    pdf.ln(4)

    pdf.set_font("Helvetica", "", 11)
    body = (
        "The Service requests additional evidence to establish that the proffered "
        "position of Software Developer qualifies as a specialty occupation under "
        "8 CFR 214.2(h)(4)(ii).\n\n"
        "Specifically, USCIS requires evidence demonstrating:\n\n"
        "1. The position requires a minimum of a bachelor's degree or equivalent "
        "in a specific specialty directly related to the position.\n\n"
        "2. The degree requirement is common to the industry in parallel positions "
        "among similar organizations, or the position is so complex or unique that "
        "it can only be performed by an individual with a degree.\n\n"
        "3. The employer normally requires a degree or its equivalent for the position.\n\n"
        "4. The nature of the specific duties are so specialized and complex that "
        "knowledge required to perform the duties is usually associated with the "
        "attainment of a bachelor's or higher degree."
    )
    pdf.multi_cell(0, 6, body)
    pdf.ln(6)

    # Additional details
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, "Additional Information", ln=True)
    pdf.ln(2)

    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(50, 7, "Wage Level:", ln=False)
    pdf.set_font("Helvetica", "", 11)
    pdf.cell(0, 7, "Level I ($73,000/year)", ln=True)

    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(50, 7, "SOC Code:", ln=False)
    pdf.set_font("Helvetica", "", 11)
    pdf.cell(0, 7, "15-1252.00 (Software Developers)", ln=True)

    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(50, 7, "Response Due:", ln=False)
    pdf.set_font("Helvetica", "", 11)
    pdf.cell(0, 7, "84 days from date of this notice", ln=True)

    out_path = SAMPLE_DIR / "mclovin_rfe.pdf"
    pdf.output(str(out_path))
    print(f"Created: {out_path}")


def generate_profile_pdf():
    pdf = FPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=25)

    # Header
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 12, "Candidate Profile", ln=True, align="C")
    pdf.ln(6)

    pdf.set_draw_color(200, 200, 200)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(6)

    # Personal info
    pdf.set_font("Helvetica", "B", 13)
    pdf.cell(0, 9, "Personal Information", ln=True)
    pdf.ln(2)

    fields = [
        ("Full Name", "McLovin"),
        ("Email", "mclovin@hawaii.gov"),
        ("Phone", "808-555-0123"),
        ("Address", "892 Momona St, Honolulu, HI 96820"),
    ]
    for label, value in fields:
        pdf.set_font("Helvetica", "B", 11)
        pdf.cell(50, 7, f"{label}:", ln=False)
        pdf.set_font("Helvetica", "", 11)
        pdf.cell(0, 7, value, ln=True)

    pdf.ln(6)

    # Employment
    pdf.set_font("Helvetica", "B", 13)
    pdf.cell(0, 9, "Employment Details", ln=True)
    pdf.ln(2)

    emp_fields = [
        ("Current Position", "Software Developer"),
        ("Company", "Pumpkin Tech Consulting LLC"),
        ("Company Type", "Consulting"),
        ("Wage Level", "Level I"),
        ("Years of Experience", "2"),
    ]
    for label, value in emp_fields:
        pdf.set_font("Helvetica", "B", 11)
        pdf.cell(50, 7, f"{label}:", ln=False)
        pdf.set_font("Helvetica", "", 11)
        pdf.cell(0, 7, value, ln=True)

    pdf.ln(6)

    # Education
    pdf.set_font("Helvetica", "B", 13)
    pdf.cell(0, 9, "Education", ln=True)
    pdf.ln(2)

    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(50, 7, "Degree:", ln=False)
    pdf.set_font("Helvetica", "", 11)
    pdf.cell(0, 7, "B.S. Computer Science", ln=True)

    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(50, 7, "University:", ln=False)
    pdf.set_font("Helvetica", "", 11)
    pdf.cell(0, 7, "University of Hawaii at Manoa", ln=True)

    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(50, 7, "Graduation:", ln=False)
    pdf.set_font("Helvetica", "", 11)
    pdf.cell(0, 7, "2022", ln=True)

    pdf.ln(6)

    # H-1B case info
    pdf.set_font("Helvetica", "B", 13)
    pdf.cell(0, 9, "H-1B Case Information", ln=True)
    pdf.ln(2)

    h1b_fields = [
        ("RFE Issues", "Specialty Occupation"),
        ("Current Arguments", "O*NET Citation"),
        ("Filing Status", "Initial H-1B petition"),
    ]
    for label, value in h1b_fields:
        pdf.set_font("Helvetica", "B", 11)
        pdf.cell(50, 7, f"{label}:", ln=False)
        pdf.set_font("Helvetica", "", 11)
        pdf.cell(0, 7, value, ln=True)

    pdf.ln(6)

    # Notes
    pdf.set_font("Helvetica", "B", 13)
    pdf.cell(0, 9, "Additional Notes", ln=True)
    pdf.ln(2)
    pdf.set_font("Helvetica", "", 11)
    pdf.multi_cell(0, 6, (
        "Entry-level software developer position at an IT consulting firm. "
        "Client is placed at end-client site. Petitioner seeks to demonstrate "
        "that the position requires specialized knowledge in computer science "
        "and that a bachelor's degree in a specific specialty is the minimum "
        "requirement for entry into the occupation."
    ))

    out_path = SAMPLE_DIR / "mclovin_profile.pdf"
    pdf.output(str(out_path))
    print(f"Created: {out_path}")


if __name__ == "__main__":
    generate_rfe_pdf()
    generate_profile_pdf()
    print("Done! Sample documents generated in sample_docs/")
