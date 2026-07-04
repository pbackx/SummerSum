import fitz

def render_page(filepath, page_num, output_path):
    doc = fitz.open(filepath)
    page = doc[page_num]
    pix = page.get_pixmap(dpi=150)
    pix.save(output_path)
    print(f"Rendered page {page_num+1} of {filepath} to {output_path}")

# Render page 15 (index 14) and page 16 (index 15) of the 25-page PDF
render_page("Herhalingsbundel van 2 naar 3 vakantietaak.pdf", 14, "temp/vakantietaak_p15.png")
render_page("Herhalingsbundel van 2 naar 3 vakantietaak.pdf", 15, "temp/vakantietaak_p16.png")
