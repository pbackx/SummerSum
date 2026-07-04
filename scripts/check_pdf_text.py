import fitz
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

def check_text(filepath):
    print(f"=== {filepath} ===")
    doc = fitz.open(filepath)
    page = doc[1] # Page 2 (index 1)
    print(page.get_text()[:600])
    print("-" * 50)

check_text("Herhalingsbundel van 2 naar 3 vakantietaak.pdf")
check_text("Herhalingsbundel van 2 naar 3 vakantietaak correctiesleutel.pdf")
