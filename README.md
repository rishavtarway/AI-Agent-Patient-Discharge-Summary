# AI Agent: Patient Discharge Summary Generator

A production-ready discharge summary agent for medical records processing using multi-engine OCR extraction and intelligent agentic decision-making.

## 🎯 Overview

This project builds an AI agent that:
1. **Extracts patient data** from handwritten medical PDFs using multi-engine OCR (Tesseract + EasyOCR)
2. **Processes structured data** through medication reconciliation, conflict detection, and drug interaction checking
3. **Generates clinical-safe discharge summaries** with full reasoning traces and flagging for manual review

**Key Features:**
- ✅ Real agent loop with planning/re-planning
- ✅ Multiple OCR engines for robust handwriting recognition
- ✅ Medication reconciliation with conflict detection
- ✅ Drug interaction checking
- ✅ Complete step tracing for observability
- ✅ Zero hallucination - all data from OCR only
- ✅ Explicit flagging of unknowns and conflicts

## 📋 Project Structure

```
├── discharge_agent.py              # Main agent (meets all 10 Part 1 requirements)
├── Medical_OCR_Extractor_Colab.ipynb  # Google Colab notebook for OCR
├── multi_ocr_extractor.py          # Multi-engine OCR implementation
├── requirements.txt                 # Python dependencies
├── README.md                        # This file
├── REQUIREMENTS_COVERAGE.md         # Detailed requirement mapping
├── AGENT_ENHANCEMENT_SUMMARY.md     # Feature documentation
├── GOOGLE_COLAB_QUICK_START.md      # Colab setup guide
└── extracted_data/                  # Output directory for extracted data
```

## 🚀 Quick Start

### Local Setup (for agent execution)

```bash
# Install dependencies
pip install -r requirements.txt

# Run agent on extracted data
python discharge_agent.py patient_data.json

# Output: discharge_summary.json with full trace
```

### Google Colab (for OCR extraction)

1. Open `Medical_OCR_Extractor_Colab.ipynb` in Google Colab
2. Follow [GOOGLE_COLAB_QUICK_START.md](GOOGLE_COLAB_QUICK_START.md) for step-by-step instructions
3. Upload your PDF (no Google Drive connection needed)
4. Run cells 1-5 to extract patient data
5. Download `patient_data.json`

## 🔧 Components

### 1. Multi-Engine OCR Extraction

**Engines:**
- **Tesseract** - Best for printed/typed text (fast, accurate on clean text)
- **EasyOCR** - Best for handwriting (deep learning, handles cursive)
- **Intelligent Merging** - Picks highest confidence result, adds unique lines from backup engines

**Output:** `patient_data.json` with structured medical fields

### 2. Discharge Summary Agent

**Real Agent Loop:**
```
Assess State → Decide Action → Execute → Handle Result → Loop
```

**Tools (5 available):**
1. `aggregate_data` - Consolidate patient information
2. `reconcile_medications` - Track medication changes and flag inconsistencies
3. `detect_conflicts` - Find conflicting values across pages
4. `check_drug_interactions` - Identify potential interactions
5. `flag_missing_fields` - Mark fields needing manual review

**Output:** `discharge_summary.json` with:
- Consolidated patient data
- All reasoning steps
- Conflict flags
- Medication change explanations
- Complete step trace

## 📊 Part 1 Requirements Coverage

All 10 hard requirements implemented and verified:

| # | Requirement | Status | Implementation |
|---|-------------|--------|-----------------|
| 1 | Real agent loop | ✅ | assess_state → decide_action → execute → handle_result |
| 2 | Tool use with decisions | ✅ | Agent chooses which of 5 tools to call |
| 3 | Medication reconciliation | ✅ | Tracks changes, flags inconsistencies |
| 4 | Conflict detection | ✅ | Page-by-page value comparison |
| 5 | Drug interaction checking | ✅ | Mock interaction database with escalation |
| 6 | Step tracing | ✅ | Full JSON trace of all decisions |
| 7 | No hallucination | ✅ | All data from OCR, no LLM generation |
| 8 | Unknown handling | ✅ | Explicit "not_documented" flags |
| 9 | Confidence scores | ✅ | OCR confidence tracked throughout |
| 10 | Explainability | ✅ | Every action logged with reasoning |

See [REQUIREMENTS_COVERAGE.md](REQUIREMENTS_COVERAGE.md) for detailed mapping.

## 📖 Usage Examples

### Extract OCR Data (Colab)

```python
# In Colab Cell 5
extractor = MultiOCRExtractor()
image_paths = extractor.extract_from_pdf(pdf_file)
results = extractor.process_batch(image_paths)
extractor.save_results(results)
# Download patient_data.json
```

### Run Agent Locally

```python
from discharge_agent import DischargeAgent

agent = DischargeAgent()
summary = agent.run('patient_data.json')

print(json.dumps(summary, indent=2))
# Output includes:
# - patient_demographics
# - clinical_summary
# - medications_reconciled
# - conflicts_detected
# - trace (all agent steps)
```

## 🔍 Output Example

**patient_data.json** (from OCR):
```json
{
  "page": 1,
  "confidence": 0.92,
  "medical_fields": {
    "vital_signs": {
      "pulse": "HR: 78 bpm",
      "bp": "BP: 120/80",
      "temperature": "Temp: 98.6°F"
    },
    "medications": ["Aspirin 500mg daily"],
    "allergies": ["Penicillin"],
    "diagnosis": ["Hypertension"]
  },
  "full_text": "..."
}
```

**discharge_summary.json** (from agent):
```json
{
  "patient_demographics": {...},
  "clinical_summary": {...},
  "medications_reconciled": [...],
  "conflicts_detected": [...],
  "trace": [
    {
      "step": 1,
      "action": "assess_state",
      "reasoning": "Patient has 3 pages, reviewing medications...",
      "result": "Found 2 medications, 1 allergy",
      "next_decision": "reconcile_medications"
    },
    ...
  ]
}
```

## 📚 Documentation

- **[GOOGLE_COLAB_QUICK_START.md](GOOGLE_COLAB_QUICK_START.md)** - Step-by-step Colab setup
- **[AGENT_ENHANCEMENT_SUMMARY.md](AGENT_ENHANCEMENT_SUMMARY.md)** - Agent features and design
- **[REQUIREMENTS_COVERAGE.md](REQUIREMENTS_COVERAGE.md)** - Requirement-to-code mapping
- **[README_SETUP.md](README_SETUP.md)** - Detailed setup guide

## 🛠️ Dependencies

```
easyocr>=1.7.0
pdf2image>=1.16.3
opencv-python>=4.8.0
pytesseract>=0.3.10
numpy>=1.24.0
pillow>=10.0.0
```

Install: `pip install -r requirements.txt`

## 💡 Key Design Decisions

1. **Multi-Engine OCR** - Redundancy ensures no data loss from handwritten text
2. **Agent Loop** - Non-deterministic planning allows adaptation to data patterns
3. **No LLM Generation** - Eliminates hallucination risk in medical context
4. **Complete Tracing** - Every decision logged for audit and debugging
5. **Clinical Safety** - Unknown fields marked explicitly, conflicts flagged

## 🔄 Workflow

1. **Upload PDF** to Colab
2. **Extract with OCR** (Cells 1-5) → `patient_data.json`
3. **Download** JSON locally
4. **Run agent** → `python discharge_agent.py patient_data.json`
5. **Review output** → `discharge_summary.json`
6. **Manual verification** for flagged items

## 📝 Part 2 (Optional)

Learning from user edits to improve extraction accuracy. Not included in Part 1.

## 🤝 Contributing

For questions or improvements, please open an issue or PR.

## 📄 License

This project is part of the Dscribe assignment.

---

**Last Updated:** June 4, 2024  
**Author:** Rishav Tarway
