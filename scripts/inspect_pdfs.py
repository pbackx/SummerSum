import fitz  # PyMuPDF
import sys

def inspect_pdf(filepath):
    print(f"Inspecting {filepath}...")
    doc = fitz.open(filepath)
    print(f"Number of pages: {len(doc)}")
    print(f"Metadata: {doc.metadata}")
    print("-" * 40)

if __name__ == "__main__":
    inspect_pdf("Herhalingsbundel van 2 naar 3 vakantietaak.pdf")
    inspect_pdf("Herhalingsbundel van 2 naar 3 vakantietaak correctiesleutel.pdf")
