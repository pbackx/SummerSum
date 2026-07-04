import fitz
import os

os.makedirs("temp", exist_ok=True)

def render_page(filepath, page_num, output_path):
    doc = fitz.open(filepath)
    page = doc[page_num]
    pix = page.get_pixmap(dpi=150)
    pix.save(output_path)
    print(f"Rendered page {page_num+1} of {filepath} to {output_path}")

render_page("Herhalingsbundel van 2 naar 3 vakantietaak.pdf", 1, "temp/vakantietaak_p2.png")
render_page("Herhalingsbundel van 2 naar 3 vakantietaak correctiesleutel.pdf", 1, "temp/correctiesleutel_p2.png")
