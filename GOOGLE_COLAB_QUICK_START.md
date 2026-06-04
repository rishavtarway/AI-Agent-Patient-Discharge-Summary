# 🚀 URGENT: 30-MINUTE SETUP GUIDE FOR GOOGLE COLAB

## Quick Start (Copy-Paste to Colab)

### Option A: USE COLAB DIRECTLY (FASTEST - 5 minutes)

1. **Open Google Colab:**
   https://colab.research.google.com

2. **Create NEW Notebook**

3. **Copy-paste this entire code block into first cell:**

```python
# Install dependencies
!pip install -q easyocr paddleocr pytesseract pdf2image opencv-python numpy pillow
!apt-get update -qq && apt-get install -y -qq tesseract-ocr poppler-utils

# Mount Drive
from google.colab import drive
drive.mount('/content/drive')

# Upload PDF
from google.colab import files
print('[*] Upload your PDF file...')
uploaded = files.upload()
pdf_file = list(uploaded.keys())[0]
print(f'[+] File uploaded: {pdf_file}')

# Import libraries
import json, cv2, numpy as np
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from pdf2image import convert_from_path
from datetime import datetime
import re
from difflib import SequenceMatcher
import pytesseract, easyocr, paddleocr

# Multi-OCR Extractor (FULL CODE BELOW)
class MultiOCRExtractor:
    def __init__(self, output_dir="/content/extracted_data"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        print("[*] Initializing OCR engines...\n")
        
        self.pytesseract = pytesseract
        self.easyocr_reader = easyocr.Reader(['en'], gpu=False, model_storage_directory='/tmp/easyocr')
        self.paddleocr_reader = paddleocr.PaddleOCR(use_angle_cls=True, lang='en')
        print("\n[+] All OCR engines initialized!\n")
    
    def extract_from_pdf(self, pdf_path):
        print(f"[*] Converting PDF: {pdf_path}")
        images = convert_from_path(pdf_path)
        print(f"[+] Extracted {len(images)} pages\n")
        image_paths = []
        for idx, image in enumerate(images, 1):
            img_path = self.output_dir / f"page_{idx:03d}.png"
            image.save(img_path)
            image_paths.append(str(img_path))
        return image_paths
    
    def ocr_tesseract(self, image_path):
        try:
            img = cv2.imread(image_path)
            text = self.pytesseract.image_to_string(img)
            data = self.pytesseract.image_to_data(img, output_type=self.pytesseract.Output.DICT)
            confidences = [int(x) for x in data['conf'] if int(x) > 0]
            avg_confidence = np.mean(confidences) / 100 if confidences else 0.5
            return {"text": text, "confidence": round(avg_confidence, 3), "engine": "tesseract", "status": "success"}
        except:
            return {"text": "", "confidence": 0, "engine": "tesseract", "status": "error"}
    
    def ocr_easyocr(self, image_path):
        try:
            results = self.easyocr_reader.readtext(image_path)
            text = "\n".join([d[1] for d in results])
            conf = np.mean([d[2] for d in results]) if results else 0.5
            return {"text": text, "confidence": round(conf, 3), "engine": "easyocr", "status": "success"}
        except:
            return {"text": "", "confidence": 0, "engine": "easyocr", "status": "error"}
    
    def ocr_paddleocr(self, image_path):
        try:
            results = self.paddleocr_reader.ocr(image_path, cls=True)
            text_lines, confidences = [], []
            if results:
                for line in results:
                    for item in line:
                        text_lines.append(item[1])
                        confidences.append(item[2])
            text = "\n".join(text_lines)
            conf = np.mean(confidences) if confidences else 0.5
            return {"text": text, "confidence": round(conf, 3), "engine": "paddleocr", "status": "success"}
        except:
            return {"text": "", "confidence": 0, "engine": "paddleocr", "status": "error"}
    
    def merge_ocr_results(self, results):
        available = [r for r in results if r.get("status") == "success" and r.get("text")]
        if not available:
            return {"merged_text": "", "confidence": 0, "engines_used": 0}
        
        primary = max(available, key=lambda x: x.get("confidence", 0))
        return {
            "merged_text": primary["text"],
            "confidence": primary["confidence"],
            "engines_used": len(available),
            "primary_engine": primary["engine"]
        }
    
    def parse_medical_fields(self, text):
        lines = text.split('\n')
        fields = {
            "vital_signs": {},
            "medications": [],
            "allergies": [],
            "diagnosis": [],
            "dates": []
        }
        
        for line in lines:
            line_lower = line.lower()
            if any(x in line_lower for x in ['pulse', 'hr', 'heart rate']):
                fields["vital_signs"]["pulse"] = line
            elif any(x in line_lower for x in ['bp:', 'blood pressure']):
                fields["vital_signs"]["bp"] = line
            elif any(x in line_lower for x in ['temp', 'temperature']):
                fields["vital_signs"]["temperature"] = line
            elif any(x in line_lower for x in ['glucose', 'blood sugar']):
                fields["vital_signs"]["glucose"] = line
            elif any(x in line_lower for x in ['oxygen', 'spo2']):
                fields["vital_signs"]["oxygen"] = line
            
            if any(x in line_lower for x in ['medication', 'drug', 'medicine']):
                fields["medications"].append(line)
            if any(x in line_lower for x in ['allergy', 'allergic']):
                fields["allergies"].append(line)
            if any(x in line_lower for x in ['diagnosis', 'diagnosed']):
                fields["diagnosis"].append(line)
            if re.search(r'\d{1,2}[/-]\d{1,2}[/-]\d{2,4}', line):
                fields["dates"].append(line)
        
        return fields
    
    def process_image(self, image_path, page_num, total):
        print(f"[{page_num}/{total}] Processing...")
        
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = {
                'tesseract': executor.submit(self.ocr_tesseract, image_path),
                'easyocr': executor.submit(self.ocr_easyocr, image_path),
                'paddleocr': executor.submit(self.ocr_paddleocr, image_path),
            }
            results = {name: future.result(timeout=120) for name, future in futures.items()}
        
        merged = self.merge_ocr_results(list(results.values()))
        medical = self.parse_medical_fields(merged["merged_text"])
        
        return {
            "page": page_num,
            "confidence": merged["confidence"],
            "engines_used": merged["engines_used"],
            "medical_fields": medical,
            "full_text": merged["merged_text"]
        }
    
    def process_batch(self, image_paths):
        return [self.process_image(img, i, len(image_paths)) for i, img in enumerate(image_paths, 1)]
    
    def save_results(self, results):
        output_json = self.output_dir / "patient_data.json"
        with open(output_json, 'w') as f:
            json.dump(results, f, indent=2)
        return output_json

# RUN EXTRACTION
print("\n" + "="*80)
print("[*] STARTING MULTI-ENGINE OCR EXTRACTION")
print("="*80 + "\n")

extractor = MultiOCRExtractor()
image_paths = extractor.extract_from_pdf(pdf_file)
results = extractor.process_batch(image_paths)
output_file = extractor.save_results(results)

print("\n" + "="*80)
print("[+] EXTRACTION COMPLETE!")
print("="*80)
print(f"[+] Pages processed: {len(results)}")
print(f"[+] Output: /content/extracted_data/patient_data.json")
print("\n[+] Ready for download!\n")

# Download JSON
from google.colab import files
files.download('/content/extracted_data/patient_data.json')
print("[+] Downloaded: patient_data.json")

# Show preview
print("\n" + "="*80)
print("📊 PREVIEW OF EXTRACTED DATA")
print("="*80)
for i, page in enumerate(results[:2]):
    print(f"\nPage {page['page']}:")
    print(f"  Confidence: {page['confidence']:.1%}")
    print(f"  Engines used: {page['engines_used']}")
    print(f"  Medical fields: {page['medical_fields']}")
    print(f"  Text (first 200 chars): {page['full_text'][:200]}...")
```

4. **DONE!** JSON file downloads automatically. Use in your agent.

---

## What You Get

✅ **patient_data.json** — Complete extracted data with:
- OCR confidence scores
- Vital signs
- Medications
- Allergies
- Diagnoses
- All handwritten text captured

---

## Upload to Colab via Notebook File

**Instead of copy-pasting, use the notebook file:**

1. Go to Google Colab: https://colab.research.google.com
2. Click **File → Open notebook**
3. Click **Upload**
4. Select: `Medical_OCR_Extractor_Colab.ipynb` (the .ipynb file from this folder)
5. Run cells in order (Step 1 → Step 7)

---

## Performance

- **Google Colab:** Fast (GPU available if needed)
- **All 3 OCR engines:** Tesseract + EasyOCR + PaddleOCR
- **Time:** ~5-15 minutes for typical patient PDF
- **Memory:** No issues (Colab has plenty)

---

## If You're Out of Time

**Minimum viable approach (2 minutes):**
1. Open Colab
2. Install: `!pip install easyocr pdf2image && !apt-get install tesseract-ocr`
3. Upload PDF
4. Run EasyOCR only (single engine, but fastest)
5. Download JSON
6. Feed to agent

---

## Questions?

- **File not found:** Upload PDF in Colab's upload step
- **Memory error:** Colab has more RAM than your system
- **Slow:** Try smaller PDFs first to test
- **No output:** Check cell error messages

---

**You have this! 30 minutes is plenty.** ⏱️

Start with: https://colab.research.google.com/notebook#create=true
