import fitz
import sys

# Reconfigure stdout to use UTF-8 to avoid encoding issues in Windows terminal
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

def get_page_info(filepath):
    doc = fitz.open(filepath)
    info = []
    for i, page in enumerate(doc):
        # Extract first 200 chars of text to identify headings or page numbers
        text = page.get_text()
        first_lines = [line.strip() for line in text.split('\n') if line.strip()][:3]
        info.append((i+1, " | ".join(first_lines)))
    return info

print("--- OPDRACHTEN ---")
for num, line in get_page_info("Herhalingsbundel van 2 naar 3 vakantietaak.pdf"):
    print(f"Page {num}: {line}")

print("\n--- SLEUTEL ---")
for num, line in get_page_info("Herhalingsbundel van 2 naar 3 vakantietaak correctiesleutel.pdf"):
    print(f"Page {num}: {line}")
