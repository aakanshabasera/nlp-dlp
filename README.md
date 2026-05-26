# nlp-dlp
# NLP-Based DLP (Data Loss Prevention)

A Chrome extension that detects sensitive data in real-time as you type, powered by a fine-tuned DistilBERT NER model. Built to prevent accidental data leaks before you hit send.

## What It Does

Most DLP tools use regex rules that break easily. This project uses an NLP model that understands context — it reads your text like a human would and identifies sensitive information even in non-standard formats.

Type something like `my api key is sk-abc123xyz` in any text box on any website — the extension scans it in real-time and shows a warning popup before you send.

## Demo

![Warning popup showing API_KEY detected with Don't Send and Send Anyway buttons]

Detects 8 entity types:
- EMAIL
- API_KEY
- PASSWORD
- SSN
- CREDIT_CARD
- PHONE
- NAME
- ADDRESS

## How It Works

1. User types in any text box on any website
2. Chrome extension captures the text after 800ms of inactivity
3. Text is sent to a local Flask API
4. Fine-tuned DistilBERT NER model scans for sensitive entities
5. If found, a warning popup appears with entity type and confidence score
6. User can choose to cancel or send anyway

## Project Structure
nlp-dlp/
├── data_gen/
│   └── generate.py          # Synthetic data generation via OpenRouter
├── dataset/
│   ├── bio_convert.py        # Convert to BIO tagging format
│   ├── train.json            # 3140 training samples
│   ├── val.json              # 392 validation samples
│   └── test.json             # 393 test samples
├── inference/
│   └── app.py               # Flask REST API
├── extension/
│   ├── manifest.json         # Chrome extension config (Manifest V3)
│   ├── content.js            # Content script injected into all pages
│   ├── popup.html            # Extension popup UI
│   └── test.html             # Local test page
└── README.md

## Setup

### Requirements
- Python 3.8+
- Google Chrome
- OpenRouter API key (free tier)

### 1. Generate Training Data
```bash
cd data_gen
pip install requests tqdm
# Add your OpenRouter API key to generate.py
python generate.py
```
Generates ~500 samples per entity type using Llama 3 via OpenRouter free tier.

### 2. Convert to BIO Format
```bash
python dataset/bio_convert.py
```
Converts raw JSON to BIO-tagged NER format. Splits 80/10/10 train/val/test.

### 3. Train Model
Upload train.json, val.json, test.json to Google Colab (free T4 GPU).
Model: distilbert-base-uncased fine-tuned for token classification.
Training time: ~15 minutes on T4 GPU.

### 4. Run Flask API
```bash
pip install flask flask-cors transformers torch
python inference/app.py
```
API runs on http://localhost:5000

Test it:
```bash
curl -X POST http://localhost:5000/scan \
  -H "Content-Type: application/json" \
  -d '{"text": "my api key is sk-abc123xyz"}'
```

### 5. Load Chrome Extension
1. Open chrome://extensions
2. Enable Developer Mode (top right toggle)
3. Click Load Unpacked
4. Select the extension/ folder
5. Make sure Flask API is running

## Tech Stack

- Model: DistilBERT (distilbert-base-uncased) fine-tuned for NER
- Training Data: 4000+ synthetic samples generated via OpenRouter (Llama 3, free tier)
- Data Format: BIO tagging (B-EMAIL, I-EMAIL, O, etc.)
- Backend: Flask REST API with CORS
- Frontend: Chrome Extension Manifest V3
- Training: HuggingFace Transformers + Google Colab

## Results

| Entity | F1 Score |
|--------|----------|
| EMAIL | 99.6% |
| API_KEY | 99.8% |
| SSN | 99.4% |
| CREDIT_CARD | 99.2% |
| PASSWORD | 99.1% |
| PHONE | 99.3% |
| NAME | 99.0% |
| ADDRESS | 98.9% |
| Overall | 99.4% |

## Limitations

- Flask API must be running locally for extension to work
- Some heavily sandboxed sites (Claude.ai, ChatGPT) block content script injection
- Model trained on synthetic data — real-world performance may vary
- EMAIL entity sometimes captures only local part due to DistilBERT subword tokenization

## Future Work

- Convert model to ONNX for fully offline browser inference
- Expand training data to 50k+ samples
- Add redaction feature (auto-mask sensitive text)
- Support for more entity types (Aadhaar, PAN, IFSC)
