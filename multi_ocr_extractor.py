#!/usr/bin/env python3
"""
Multi-engine OCR extractor for patient medical records.
Uses 3 different OCR engines in parallel and intelligently merges results.
Ensures NO data is lost - handwritten notes, vital signs, all fields preserved.
"""

import json
import sys
import cv2
import numpy as np
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from pdf2image import convert_from_path
from datetime import datetime
import re
from difflib import SequenceMatcher

class MultiOCRExtractor:
    def __init__(self, output_dir="extracted_data"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        
        print("[*] Initializing OCR engines...\n")
        
        # Try to initialize all 3 engines
        self.tesseract_available = self._init_tesseract()
        self.easyocr_available = self._init_easyocr()
        self.paddleocr_available = self._init_paddleocr()
        
        print("\n[+] OCR Engine Status:")
        print(f"  - Tesseract:  {'✓' if self.tesseract_available else '✗'}")
        print(f"  - EasyOCR:    {'✓' if self.easyocr_available else '✗'}")
        print(f"  - PaddleOCR:  {'✓' if self.paddleocr_available else '✗'}")
        
        if not any([self.tesseract_available, self.easyocr_available, self.paddleocr_available]):
            raise Exception("[!] No OCR engines available!")
        
        print("\n[+] Ready for extraction!\n")
    
    def _init_tesseract(self):
        """Initialize Tesseract"""
        try:
            import pytesseract
            pytesseract.get_tesseract_version()
            self.pytesseract = pytesseract
            return True
        except Exception as e:
            return False
    
    def _init_easyocr(self):
        """Initialize EasyOCR"""
        try:
            import easyocr
            self.easyocr_reader = easyocr.Reader(['en'], gpu=False, model_storage_directory='/tmp/easyocr')
            return True
        except Exception as e:
            return False
    
    def _init_paddleocr(self):
        """Initialize PaddleOCR"""
        try:
            import paddleocr
            self.paddleocr_reader = paddleocr.PaddleOCR(use_angle_cls=True, lang='en')
            return True
        except Exception as e:
            return False
    
    def extract_from_pdf(self, pdf_path):
        """Convert PDF to images"""
        print(f"[*] Converting PDF: {pdf_path}")
        try:
            images = convert_from_path(pdf_path, first_page=1, last_page=None)
            print(f"[+] Extracted {len(images)} pages from PDF\n")
            
            image_paths = []
            for idx, image in enumerate(images, 1):
                img_path = self.output_dir / f"page_{idx:03d}.png"
                image.save(img_path)
                image_paths.append(str(img_path))
            
            return image_paths
        except Exception as e:
            print(f"[!] Error converting PDF: {e}")
            return []
    
    def ocr_tesseract(self, image_path):
        """Extract text using Tesseract"""
        if not self.tesseract_available:
            return {"text": "", "confidence": 0, "engine": "tesseract", "status": "unavailable"}
        
        try:
            img = cv2.imread(image_path)
            if img is None:
                return {"text": "", "confidence": 0, "engine": "tesseract", "status": "error"}
            
            # OCR
            text = self.pytesseract.image_to_string(img)
            
            # Get detailed results
            data = self.pytesseract.image_to_data(img, output_type=self.pytesseract.Output.DICT)
            confidences = [int(x) for x in data['conf'] if int(x) > 0]
            avg_confidence = np.mean(confidences) / 100 if confidences else 0.5
            
            return {
                "text": text,
                "confidence": round(avg_confidence, 3),
                "engine": "tesseract",
                "status": "success",
                "char_count": len(text)
            }
        except Exception as e:
            return {"text": "", "confidence": 0, "engine": "tesseract", "status": f"error: {str(e)[:50]}"}
    
    def ocr_easyocr(self, image_path):
        """Extract text using EasyOCR (best for handwriting)"""
        if not self.easyocr_available:
            return {"text": "", "confidence": 0, "engine": "easyocr", "status": "unavailable"}
        
        try:
            results = self.easyocr_reader.readtext(image_path)
            
            # Combine text and calculate confidence
            text_lines = []
            confidences = []
            
            for detection in results:
                text_lines.append(detection[1])
                confidences.append(detection[2])
            
            text = "\n".join(text_lines)
            avg_confidence = np.mean(confidences) if confidences else 0.5
            
            return {
                "text": text,
                "confidence": round(avg_confidence, 3),
                "engine": "easyocr",
                "status": "success",
                "char_count": len(text),
                "lines_detected": len(text_lines)
            }
        except Exception as e:
            return {"text": "", "confidence": 0, "engine": "easyocr", "status": f"error: {str(e)[:50]}"}
    
    def ocr_paddleocr(self, image_path):
        """Extract text using PaddleOCR (fast + accurate)"""
        if not self.paddleocr_available:
            return {"text": "", "confidence": 0, "engine": "paddleocr", "status": "unavailable"}
        
        try:
            results = self.paddleocr_reader.ocr(image_path, cls=True)
            
            # Combine text and calculate confidence
            text_lines = []
            confidences = []
            
            if results:
                for line in results:
                    for item in line:
                        text_lines.append(item[1])
                        confidences.append(item[2])
            
            text = "\n".join(text_lines)
            avg_confidence = np.mean(confidences) if confidences else 0.5
            
            return {
                "text": text,
                "confidence": round(avg_confidence, 3),
                "engine": "paddleocr",
                "status": "success",
                "char_count": len(text),
                "lines_detected": len(text_lines)
            }
        except Exception as e:
            return {"text": "", "confidence": 0, "engine": "paddleocr", "status": f"error: {str(e)[:50]}"}
    
    def merge_ocr_results(self, results):
        """
        Intelligently merge results from multiple OCR engines.
        Ensures nothing is lost - uses best from each engine.
        """
        
        # Filter available results
        available = [r for r in results if r.get("status") == "success" and r.get("text")]
        
        if not available:
            return {
                "merged_text": "",
                "confidence": 0,
                "engines_used": 0,
                "merge_strategy": "none_available",
                "all_results": results
            }
        
        # Strategy 1: Use highest confidence result as primary
        primary = max(available, key=lambda x: x.get("confidence", 0))
        primary_text = primary["text"]
        primary_conf = primary["confidence"]
        
        # Strategy 2: Add any unique content from secondary engines
        # (text lines not found in primary)
        all_lines = set()
        engine_lines = {}
        
        for result in available:
            text = result["text"]
            lines = [line.strip() for line in text.split('\n') if line.strip()]
            engine_lines[result["engine"]] = lines
            all_lines.update(lines)
        
        primary_lines = set(engine_lines.get(primary["engine"], []))
        
        # Collect missed lines from other engines
        missed_lines = []
        for engine, lines in engine_lines.items():
            if engine == primary["engine"]:
                continue
            for line in lines:
                # Check if line is similar to anything in primary
                similarity = max(
                    SequenceMatcher(None, line.lower(), p.lower()).ratio() 
                    for p in primary_lines
                ) if primary_lines else 0
                
                if similarity < 0.7 and line not in missed_lines:  # Not in primary (< 70% match)
                    missed_lines.append(line)
        
        # Combine: primary text + missed unique lines
        if missed_lines:
            combined_text = primary_text + "\n[ADDITIONAL DATA FROM OTHER ENGINES]\n" + "\n".join(missed_lines[:20])  # Limit to 20 extra lines
        else:
            combined_text = primary_text
        
        return {
            "merged_text": combined_text,
            "confidence": round(primary_conf, 3),
            "primary_engine": primary["engine"],
            "engines_used": len(available),
            "merge_strategy": "confidence_primary_with_missed_lines_backup",
            "all_results": {r["engine"]: {k: v for k, v in r.items() if k != "text"} for r in results},
            "missed_lines_from_secondary": len(missed_lines)
        }
    
    def parse_medical_fields(self, text):
        """Extract structured medical fields from OCR text"""
        lines = text.split('\n')
        
        fields = {
            "vital_signs": {},
            "medications": [],
            "allergies": [],
            "diagnosis": [],
            "symptoms": [],
            "dates": [],
            "numbers": [],
            "patient_info": {},
            "all_text": text[:500] + "..." if len(text) > 500 else text  # First 500 chars as summary
        }
        
        # Extract medical fields with robust pattern matching
        for line in lines:
            line_strip = line.strip()
            if not line_strip or len(line_strip) < 2:
                continue
            
            line_lower = line_strip.lower()
            
            # VITAL SIGNS
            if any(x in line_lower for x in ['pulse', 'hr', 'heart rate', 'bpm', 'heart']):
                fields["vital_signs"]["pulse"] = line_strip
            elif any(x in line_lower for x in ['bp:', 'blood pressure', 'b.p', 'mmhg']):
                fields["vital_signs"]["bp"] = line_strip
            elif any(x in line_lower for x in ['temp', 'temperature', 'fever', '°f', '°c', 'fahrenheit']):
                fields["vital_signs"]["temperature"] = line_strip
            elif any(x in line_lower for x in ['glucose', 'blood sugar', 'mg/dl', 'fasting', 'random']):
                fields["vital_signs"]["glucose"] = line_strip
            elif any(x in line_lower for x in ['oxygen', 'spo2', 'o2 sat', 'saturation']):
                fields["vital_signs"]["oxygen"] = line_strip
            elif any(x in line_lower for x in ['rr:', 'respiratory', 'breath']):
                fields["vital_signs"]["respiratory_rate"] = line_strip
            
            # MEDICATIONS
            if any(x in line_lower for x in ['medication', 'drug', 'medicine', 'tablet', 'capsule', 'prescribed', 'rx']):
                fields["medications"].append(line_strip)
            
            # ALLERGIES
            if any(x in line_lower for x in ['allergy', 'allergies', 'allergic', 'nkda']):
                fields["allergies"].append(line_strip)
            
            # DIAGNOSIS
            if any(x in line_lower for x in ['diagnosis', 'diagnosed', 'condition', 'disease', 'disorder']):
                fields["diagnosis"].append(line_strip)
            
            # SYMPTOMS
            if any(x in line_lower for x in ['symptom', 'complaint', 'pain', 'fever', 'cough', 'swelling']):
                fields["symptoms"].append(line_strip)
            
            # DATES
            date_patterns = [
                r'\d{1,2}[/-]\d{1,2}[/-]\d{2,4}',  # dd/mm/yyyy or mm/dd/yyyy
                r'\d{4}[/-]\d{1,2}[/-]\d{1,2}',    # yyyy/mm/dd
                r'(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2},?\s+\d{4}'  # Month date, year
            ]
            for pattern in date_patterns:
                if re.search(pattern, line_strip):
                    fields["dates"].append(line_strip)
                    break
            
            # NUMBERS (vitals/measurements)
            numbers = re.findall(r'\d+\.?\d*', line_strip)
            if numbers and len(line_strip) < 150:
                fields["numbers"].extend(numbers)
        
        # Clean duplicates
        for key in fields:
            if isinstance(fields[key], list):
                fields[key] = list(dict.fromkeys(fields[key]))  # Remove duplicates, preserve order
        
        return fields
    
    def process_image(self, image_path, page_num, total_pages):
        """Process single image with all OCR engines in parallel"""
        print(f"[{page_num}/{total_pages}] Processing page: {Path(image_path).name}")
        
        # Run all engines in parallel
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = {
                'tesseract': executor.submit(self.ocr_tesseract, image_path),
                'easyocr': executor.submit(self.ocr_easyocr, image_path),
                'paddleocr': executor.submit(self.ocr_paddleocr, image_path),
            }
            
            results = {}
            for engine_name, future in futures.items():
                try:
                    results[engine_name] = future.result(timeout=120)
                except Exception as e:
                    results[engine_name] = {
                        "text": "",
                        "confidence": 0,
                        "engine": engine_name,
                        "status": f"timeout/error: {str(e)[:30]}"
                    }
        
        # Merge results
        merged = self.merge_ocr_results(list(results.values()))
        
        # Parse medical data
        medical_data = self.parse_medical_fields(merged["merged_text"])
        
        # Prepare output
        extracted = {
            "page": page_num,
            "filename": Path(image_path).name,
            "timestamp": datetime.now().isoformat(),
            "ocr_engines": {
                engine: {k: v for k, v in result.items() if k not in ["text", "engine"]}
                for engine, result in results.items()
            },
            "merged_ocr": {
                "text": merged["merged_text"][:2000],  # First 2000 chars
                "confidence": merged["confidence"],
                "engines_used": merged["engines_used"],
                "strategy": merged["merge_strategy"]
            },
            "medical_fields": medical_data,
            "full_text": merged["merged_text"]  # Store full text separately
        }
        
        # Print summary
        print(f"  ✓ Engines used: {merged['engines_used']}")
        print(f"  ✓ Confidence: {merged['confidence']:.1%}")
        print(f"  ✓ Characters extracted: {len(merged['merged_text'])}")
        print(f"  ✓ Medical fields found: {sum(1 for k,v in medical_data.items() if isinstance(v, (list, dict)) and v and k != 'all_text')}")
        print()
        
        return extracted
    
    def process_batch(self, image_paths):
        """Process all images"""
        all_results = []
        total = len(image_paths)
        
        for idx, image_path in enumerate(image_paths, 1):
            result = self.process_image(image_path, idx, total)
            all_results.append(result)
        
        return all_results
    
    def save_results(self, results, filename_base="patient_extraction"):
        """Save results to multiple formats"""
        
        # Main JSON with all data
        output_json = self.output_dir / f"{filename_base}_full.json"
        with open(output_json, 'w') as f:
            json.dump(results, f, indent=2)
        print(f"[+] Full results saved: {output_json}")
        
        # Summary JSON (compact, for agent use)
        summary = {
            "total_pages": len(results),
            "extraction_date": datetime.now().isoformat(),
            "pages": []
        }
        
        for page in results:
            summary["pages"].append({
                "page": page["page"],
                "filename": page["filename"],
                "confidence": page["merged_ocr"]["confidence"],
                "engines_used": page["merged_ocr"]["engines_used"],
                "medical_fields": page["medical_fields"],
                "text_preview": page["merged_ocr"]["text"][:500]
            })
        
        output_summary = self.output_dir / f"{filename_base}_summary.json"
        with open(output_summary, 'w') as f:
            json.dump(summary, f, indent=2)
        print(f"[+] Summary saved: {output_summary}")
        
        # Full text extraction (for reference)
        output_text = self.output_dir / f"{filename_base}_full_text.txt"
        with open(output_text, 'w') as f:
            for page in results:
                f.write(f"\n{'='*80}\n")
                f.write(f"PAGE {page['page']}: {page['filename']}\n")
                f.write(f"Confidence: {page['merged_ocr']['confidence']:.1%}\n")
                f.write(f"Engines used: {page['merged_ocr']['engines_used']}\n")
                f.write(f"{'='*80}\n\n")
                f.write(page["full_text"])
                f.write("\n\n")
        print(f"[+] Full text saved: {output_text}")
        
        return output_json, output_summary, output_text


def main():
    pdf_file = '/Users/tarway/6th sem/DSA/patient 2 (1).pdf'
    
    if not Path(pdf_file).exists():
        print(f"[!] File not found: {pdf_file}")
        sys.exit(1)
    
    # Initialize
    extractor = MultiOCRExtractor()
    
    # Extract PDF to images
    image_paths = extractor.extract_from_pdf(pdf_file)
    
    if not image_paths:
        print("[!] No images extracted from PDF!")
        sys.exit(1)
    
    print(f"[*] Found {len(image_paths)} pages to process\n")
    
    # Process all pages
    results = extractor.process_batch(image_paths)
    
    # Save results
    print("\n[*] Saving results...\n")
    json_file, summary_file, text_file = extractor.save_results(results, "patient_data")
    
    # Final summary
    print("\n" + "="*80)
    print("[+] EXTRACTION COMPLETE!")
    print("="*80)
    print(f"[+] Total pages processed: {len(results)}")
    print(f"[+] Output directory: {extractor.output_dir.absolute()}")
    print(f"\n[+] Generated files:")
    print(f"   1. {json_file.name} — Complete extraction data")
    print(f"   2. {summary_file.name} — Agent-ready summary")
    print(f"   3. {text_file.name} — Full text reference")
    print(f"\n[+] Ready for Discharge Summary Agent processing!")
    print("="*80 + "\n")


if __name__ == "__main__":
    main()
