from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.colors import HexColor

def create_ready_front_page(output_path="standard_front_page.pdf"):
    c = canvas.Canvas(output_path, pagesize=A4)
    width, height = A4

    # Title
    c.setFont("Helvetica-Bold", 22)
    c.drawCentredString(width / 2, height - 80, "Student Test Front Page")

    # Draw boxes with light borders for handwritten input
    box_color = HexColor("#000000")  # black border

    # Name field
    c.setFont("Helvetica", 14)
    c.drawString(100, height - 160, "Name:")
    c.setLineWidth(1)
    c.rect(160, height - 180, 350, 25, stroke=1, fill=0)

    # ID field
    c.drawString(100, height - 220, "ID:")
    c.rect(160, height - 240, 200, 25, stroke=1, fill=0)

    # Optional instructions
    c.setFont("Helvetica-Oblique", 10)
    c.drawString(100, height - 300, "Please write clearly inside the boxes. Do not write outside the boxes.")

    # Optional: Draw a faint grid or markers for OCR reference
    # e.g., c.line(95, height - 190, 515, height - 190)

    # Save PDF
    c.showPage()
    c.save()
    print(f"Standard front page saved as {output_path}")


if __name__ == "__main__":
    create_ready_front_page()
