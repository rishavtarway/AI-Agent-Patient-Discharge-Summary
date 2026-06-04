#!/usr/bin/env python3
"""
Fast PDF extraction to JSON using multiple methods
Falls back gracefully if OCR unavailable
"""

import json
import sys
from pathlib import Path
from pdf2image import convert_from_path
from datetime import datetime
import re

def extract_pdf_to_json(pdf_path, output_dir="extracted_data"):
    """Extract PDF pages and prepare for OCR"""
    
    output_dir = Path(output_dir)
    output_dir.mkdir(exist_ok=True)
    
    print(f"[*] Converting PDF: {pdf_path}")
    
    try:
        pages = convert_from_path(pdf_path)
        print(f"[+] Extracted {len(pages)} pages\n")
    except Exception as e:
        print(f"[!] Error: {e}")
        return None
    
    results = []
    
    for idx, page in enumerate(pages, 1):
        img_path = output_dir / f"page_{idx:03d}.png"
        page.save(img_path)
        
        page_data = {
            "page_number": idx,
            "image_file": img_path.name,
            "image_path": str(img_path),
            "timestamp": datetime.now().isoformat(),
            "status": "pending_ocr"
        }
        results.append(page_data)
        print(f"[{idx}/{len(pages)}] Saved page to: {img_path.name}")
    
    # Save metadata
    meta_file = output_dir / "pdf_extraction_metadata.json"
    with open(meta_file, 'w') as f:
        json.dump({
            "source_pdf": str(pdf_path),
            "total_pages": len(pages),
            "extraction_date": datetime.now().isoformat(),
            "pages": results
        }, f, indent=2)
    
    print(f"\n[+] Metadata saved to: {meta_file}")
    return output_dir, results


def apply_tesseract_ocr(image_dir, output_file="ocr_results.json"):
    """Apply Tesseract OCR to all images"""
    
    try:
        import pytesseract
    except ImportError:
        print("[!] pytesseract not available")
        return None
    
    print("\n[*] Starting Tesseract OCR extraction...\n")
    
    results = []
    image_files = sorted(Path(image_dir).glob("page_*.png"))
    
    for idx, img_path in enumerate(image_files, 1):
        print(f"[{idx}/{len(image_files)}] Processing: {img_path.name}")
        
        try:
            text = pytesseract.image_to_string(str(img_path))
            
            result = {
                "page": idx,
                "image": img_path.name,
                "extracted_text": text,
                "method": "tesseract",
                "status": "success"
            }
            results.append(result)
            print(f"  ✓ Extracted {len(text)} characters\n")
            
        except Exception as e:
            print(f"  [!] Error: {e}\n")
            results.append({
                "page": idx,
                "image": img_path.name,
                "error": str(e),
                "status": "failed"
            })
    
    output_path = Path(image_dir) / output_file
    with open(output_path, 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"[+] OCR results saved to: {output_path}")
    return results


if __name__ == "__main__":
    pdf_file = '/Users/tarway/6th sem/DSA/SAMPLE_PAPERS_SOFTWARE_TESTING_&_AUTOMATION.pdf'
    
    if not Path(pdf_file).exists():
        print(f"[!] File not found: {pdf_file}")
        sys.exit(1)
    
    # Step 1: Extract PDF to images
    output_dir, pages = extract_pdf_to_json(pdf_file)
    
    # Step 2: Try Tesseract OCR
    if output_dir:
        apply_tesseract_ocr(output_dir)
