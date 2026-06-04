#!/usr/bin/env python3
import json
import sys
from pathlib import Path
from pdf2image import convert_from_path
import easyocr
import re
from datetime import datetime

def extract_ocr_from_pdf(pdf_path, output_dir="extracted_data"):
    """Extract text from PDF using EasyOCR"""
    
    output_dir = Path(output_dir)
    output_dir.mkdir(exist_ok=True)
    
    print(f"[*] Converting PDF to images: {pdf_path}")
    try:
        images = convert_from_path(pdf_path)
        print(f"[+] Extracted {len(images)} pages from PDF")
    except Exception as e:
        print(f"[!] Error converting PDF: {e}")
        sys.exit(1)
    
    print(f"[*] Initializing EasyOCR (handwriting optimized)...")
    reader = easyocr.Reader(['en'], gpu=False)
    print(f"[+] EasyOCR ready!\n")
    
    all_results = []
    
    for page_idx, image in enumerate(images, 1):
        print(f"[{page_idx}/{len(images)}] Processing page...")
        
        # Save image temporarily
        img_path = output_dir / f"page_{page_idx:03d}.png"
        image.save(img_path)
        
        # OCR extraction
        try:
            results = reader.readtext(str(img_path))
            extracted_text = "\n".join([item[1] for item in results])
            avg_confidence = sum([item[2] for item in results]) / len(results) if results else 0
            
            # Parse medical fields
            medical_data = parse_medical_fields(extracted_text)
            
            page_data = {
                "page": page_idx,
                "filename": img_path.name,
                "timestamp": datetime.now().isoformat(),
                "raw_text": extracted_text,
                "confidence": round(avg_confidence, 3),
                "medical_fields": medical_data,
                "num_lines_detected": len(results)
            }
            
            all_results.append(page_data)
            
            # Show sample
            print(f"  ✓ Extracted {len(results)} text regions, confidence: {avg_confidence:.1%}")
            if extracted_text:
                print(f"  ✓ Sample: {extracted_text[:80]}...\n")
        
        except Exception as e:
            print(f"[!] Error processing page {page_idx}: {e}\n")
            all_results.append({
                "page": page_idx,
                "filename": img_path.name,
                "error": str(e)
            })
    
    # Save results
    output_file = output_dir / "extraction_results.json"
    with open(output_file, 'w') as f:
        json.dump(all_results, f, indent=2)
    
    print(f"\n[+] DONE!")
    print(f"[+] Processed {len(images)} pages")
    print(f"[+] Results saved to: {output_file}")
    print(f"[+] Images saved to: {output_dir}")
    
    return output_file

def parse_medical_fields(text):
    """Extract structured medical fields from OCR text"""
    lines = text.split('\n')
    
    fields = {
        "vital_signs": {},
        "medications": [],
        "diagnosis": [],
        "dates": [],
        "numbers": [],
        "all_text": text
    }
    
    # Pattern matching for medical fields
    for line in lines:
        line_lower = line.lower().strip()
        
        # Vital signs
        if any(x in line_lower for x in ['pulse', 'hr:', 'heart rate', 'bpm']):
            fields["vital_signs"]["pulse"] = line.strip()
        elif any(x in line_lower for x in ['bp:', 'blood pressure', 'mmhg']):
            fields["vital_signs"]["bp"] = line.strip()
        elif any(x in line_lower for x in ['temp', 'temperature', 'fever', '°f', '°c']):
            fields["vital_signs"]["temperature"] = line.strip()
        elif any(x in line_lower for x in ['glucose', 'blood sugar', 'mg/dl']):
            fields["vital_signs"]["glucose"] = line.strip()
        elif any(x in line_lower for x in ['oxygen', 'spo2', 'o2 sat']):
            fields["vital_signs"]["oxygen"] = line.strip()
        
        # Dates
        if re.search(r'\d{1,2}[/-]\d{1,2}[/-]\d{2,4}', line):
            fields["dates"].append(line.strip())
        
        # Numbers
        numbers = re.findall(r'\d+\.?\d*', line)
        if numbers and len(line) < 100:  # Avoid extracting from long text blocks
            fields["numbers"].extend(numbers)
    
    return fields

if __name__ == "__main__":
    pdf_file = '/Users/tarway/6th sem/DSA/SAMPLE_PAPERS_SOFTWARE_TESTING_&_AUTOMATION.pdf'
    
    if not Path(pdf_file).exists():
        print(f"[!] File not found: {pdf_file}")
        sys.exit(1)
    
    extract_ocr_from_pdf(pdf_file)
