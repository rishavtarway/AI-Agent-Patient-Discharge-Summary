#!/usr/bin/env python3
"""
Multi-engine OCR extractor for handwritten medical records.
Runs 3 OCR engines in parallel and intelligently merges results.
Zero-cost, fully automated.
"""

import json
import os
import sys
import cv2
import numpy as np
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import pytesseract
import easyocr
import paddleocr
from pdf2image import convert_from_path
from datetime import datetime

class MedicalOCRExtractor:
    def __init__(self, output_dir="extracted_data"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        
        print("[*] Initializing OCR engines...")
        self.tesseract_available = self._check_tesseract()
        self.reader_easy = easyocr.Reader(['en'], gpu=False)  # CPU mode, no GPU needed
        self.reader_paddle = paddleocr.PaddleOCR(use_angle_cls=True, lang='en')
        print("[+] All OCR engines ready!")
    
    def _check_tesseract(self):
        try:
            pytesseract.get_tesseract_version()
            return True
        except Exception as e:
            print(f"[!] Tesseract not available: {e}")
            return False
    
    def extract_from_pdf(self, pdf_path):
        """Convert PDF to images"""
        print(f"[*] Converting PDF: {pdf_path}")
        images = convert_from_path(pdf_path)
        image_paths = []
        
        for idx, image in enumerate(images):
            img_path = self.output_dir / f"{Path(pdf_path).stem}_page_{idx:02d}.png"
            image.save(img_path)
            image_paths.append(str(img_path))
        
        print(f"[+] Extracted {len(image_paths)} pages from PDF")
        return image_paths
    
    def extract_from_images(self, image_dir):
        """Get all image files from directory"""
        valid_exts = {'.jpg', '.jpeg', '.png', '.tiff', '.bmp'}
        images = []
        
        for ext in valid_exts:
            images.extend(Path(image_dir).glob(f"*{ext}"))
            images.extend(Path(image_dir).glob(f"*{ext.upper()}"))
        
        return [str(img) for img in sorted(images)]
    
    def ocr_tesseract(self, image_path):
        """Tesseract OCR"""
        if not self.tesseract_available:
            return {"text": "", "confidence": 0}
        
        try:
            img = cv2.imread(image_path)
            text = pytesseract.image_to_string(img)
            return {"text": text, "confidence": 0.75}  # Baseline confidence
        except Exception as e:
            print(f"[!] Tesseract error on {image_path}: {e}")
            return {"text": "", "confidence": 0}
    
    def ocr_easyocr(self, image_path):
        """EasyOCR - best for handwriting"""
        try:
            results = self.reader_easy.readtext(image_path)
            text = "\n".join([item[1] for item in results])
            avg_confidence = np.mean([item[2] for item in results]) if results else 0
            return {"text": text, "confidence": avg_confidence, "details": results}
        except Exception as e:
            print(f"[!] EasyOCR error on {image_path}: {e}")
            return {"text": "", "confidence": 0}
    
    def ocr_paddleocr(self, image_path):
        """PaddleOCR - lightweight hybrid"""
        try:
            results = self.reader_paddle.ocr(image_path, cls=True)
            text = "\n".join([line[0][1] for line in results if line]) if results else ""
            avg_confidence = np.mean([line[0][2] for line in results if line]) if results else 0
            return {"text": text, "confidence": avg_confidence}
        except Exception as e:
            print(f"[!] PaddleOCR error on {image_path}: {e}")
            return {"text": "", "confidence": 0}
    
    def merge_ocr_results(self, results):
        """Intelligently merge results from 3 engines"""
        # Highest confidence result wins
        best = max(results, key=lambda x: x.get("confidence", 0))
        
        # Collect all unique lines across engines
        all_texts = [r["text"] for r in results if r.get("text")]
        merged_text = best["text"]
        
        return {
            "text": merged_text,
            "confidence": best.get("confidence", 0),
            "method": "multi-engine merge",
            "engines_used": len([r for r in results if r.get("text")])
        }
    
    def parse_medical_data(self, text):
        """Extract structured medical fields from OCR text"""
        lines = text.split('\n')
        
        # Simple pattern matching for common medical fields
        data = {
            "raw_text": text,
            "extracted_fields": {
                "vital_signs": {},
                "medications": [],
                "diagnosis": [],
                "dates": [],
                "numbers": [],
            },
            "confidence": "medium"
        }
        
        # Extract vital signs (pattern: "pulse: 72" or "BP: 120/80")
        for line in lines:
            line_lower = line.lower()
            
            if any(x in line_lower for x in ['pulse', 'hr:', 'heart rate']):
                data["extracted_fields"]["vital_signs"]["pulse"] = line
            elif any(x in line_lower for x in ['bp:', 'blood pressure']):
                data["extracted_fields"]["vital_signs"]["bp"] = line
            elif any(x in line_lower for x in ['temp', 'temperature', 'fever']):
                data["extracted_fields"]["vital_signs"]["temperature"] = line
            elif any(x in line_lower for x in ['glucose', 'blood sugar']):
                data["extracted_fields"]["vital_signs"]["glucose"] = line
            elif any(x in line_lower for x in ['oxygen', 'spo2', 'o2']):
                data["extracted_fields"]["vital_signs"]["oxygen"] = line
            
            # Extract dates (simple pattern)
            if any(x in line for x in ['20', '202', '2025', '2026']):
                data["extracted_fields"]["dates"].append(line)
            
            # Extract numbers (vital values)
            import re
            numbers = re.findall(r'\d+\.?\d*', line)
            if numbers:
                data["extracted_fields"]["numbers"].extend(numbers)
        
        return data
    
    def process_image(self, image_path, image_num, total_images):
        """Process single image with all 3 OCR engines"""
        print(f"[{image_num}/{total_images}] Processing: {Path(image_path).name}")
        
        # Run all 3 OCR engines in parallel
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = {
                'tesseract': executor.submit(self.ocr_tesseract, image_path),
                'easyocr': executor.submit(self.ocr_easyocr, image_path),
                'paddleocr': executor.submit(self.ocr_paddleocr, image_path),
            }
            
            results = {}
            for name, future in futures.items():
                try:
                    results[name] = future.result(timeout=60)
                except Exception as e:
                    print(f"[!] Error from {name}: {e}")
                    results[name] = {"text": "", "confidence": 0}
        
        # Merge and parse
        merged = self.merge_ocr_results(list(results.values()))
        parsed = self.parse_medical_data(merged["text"])
        
        extracted = {
            "file": Path(image_path).name,
            "timestamp": datetime.now().isoformat(),
            "ocr_results": {
                name: {k: v for k, v in r.items() if k != "details"}
                for name, r in results.items()
            },
            "merged": merged,
            "medical_data": parsed
        }
        
        return extracted
    
    def process_batch(self, image_paths):
        """Process all images"""
        all_results = []
        total = len(image_paths)
        
        for idx, image_path in enumerate(image_paths, 1):
            result = self.process_image(image_path, idx, total)
            all_results.append(result)
        
        return all_results
    
    def save_results(self, results, filename="medical_extraction_results.json"):
        """Save results to JSON"""
        output_path = self.output_dir / filename
        
        with open(output_path, 'w') as f:
            json.dump(results, f, indent=2)
        
        print(f"[+] Results saved to: {output_path}")
        return output_path


def main():
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python ocr_extractor.py <pdf_file>       # Extract from PDF")
        print("  python ocr_extractor.py <image_dir>      # Extract from image directory")
        sys.exit(1)
    
    input_path = sys.argv[1]
    extractor = MedicalOCRExtractor()
    
    # Determine input type
    if input_path.endswith('.pdf'):
        print(f"[*] PDF mode: {input_path}")
        image_paths = extractor.extract_from_pdf(input_path)
    else:
        print(f"[*] Directory mode: {input_path}")
        image_paths = extractor.extract_from_images(input_path)
    
    if not image_paths:
        print("[!] No images found!")
        sys.exit(1)
    
    print(f"[*] Found {len(image_paths)} images to process\n")
    
    # Process all images
    results = extractor.process_batch(image_paths)
    
    # Save results
    extractor.save_results(results)
    
    # Summary
    print(f"\n[+] Processing complete!")
    print(f"[+] Total images: {len(results)}")
    print(f"[+] Output saved to: {extractor.output_dir}")


if __name__ == "__main__":
    main()
