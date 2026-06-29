import os
import sys
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
from transformers import pipeline

app = Flask(__name__, template_folder="templates")
CORS(app)

# Resolve default model path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_MODEL_PATH = os.path.join(PROJECT_ROOT, "model", "dlp-model-final", "checkpoint-985")

print(f"Loading SOTA DLP NER model from: {DEFAULT_MODEL_PATH}")

try:
    dlp_scanner = pipeline(
        "token-classification",
        model=DEFAULT_MODEL_PATH,
        aggregation_strategy="first"
    )
    print("DLP Model loaded and initialized successfully.")
except Exception as e:
    print(f"Error loading model from {DEFAULT_MODEL_PATH}: {e}")
    print("Initializing fallback pipeline (zero-shot/HF default)...")
    try:
        # Fallback to local config check or a dummy model if it completely fails
        dlp_scanner = None
    except Exception as ex:
        dlp_scanner = None

# Taxonomy Adapter Map: baseline model output -> target project taxonomy
ADAPTER_MAP = {
    "EMAIL": "PII.Email",
    "PHONE": "PII.Mobile",
    "SSN": "PII.SSN",
    "CREDIT_CARD": "PFI.Credit_Card",
    "API_KEY": "Auth.API_KEY",
    "PASSWORD": "Auth.Password",
    "NAME": "PII.Name",
    "ADDRESS": "PII.Address"
}

def adapt_label(label):
    """
    Translates old model tags (e.g., 'EMAIL') to the new taxonomy format (e.g., 'PII.Email').
    If the tag is already in Category.Subtype format, returns it as-is.
    """
    clean_label = label
    # Strip B- or I- prefixes if the pipeline output contains them
    if clean_label.startswith("B-") or clean_label.startswith("I-"):
        clean_label = clean_label[2:]
        
    if clean_label in ADAPTER_MAP:
        return ADAPTER_MAP[clean_label]
    return clean_label

def merge_entities(results, original_text):
    """
    Helper to merge contiguous tokens of same type that are close to each other.
    """
    if not results:
        return []
    merged = []
    
    # Initialize with first detection
    first = results[0]
    current = {
        "entity_group": first["entity_group"],
        "score": float(first["score"]),
        "start": first["start"],
        "end": first["end"],
        "value": original_text[first["start"]:first["end"]]
    }
    
    for nxt in results[1:]:
        # If same entity group and adjacent (difference <= 2 characters for spaces/punctuation)
        if nxt["entity_group"] == current["entity_group"] and nxt["start"] <= current["end"] + 2:
            current["end"] = nxt["end"]
            current["value"] = original_text[current["start"]:current["end"]]
            current["score"] = min(current["score"], float(nxt["score"]))
        else:
            merged.append(current)
            current = {
                "entity_group": nxt["entity_group"],
                "score": float(nxt["score"]),
                "start": nxt["start"],
                "end": nxt["end"],
                "value": original_text[nxt["start"]:nxt["end"]]
            }
    merged.append(current)
    return merged

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "healthy", "model": "distilbert-ner"})

@app.route("/scan", methods=["POST"])
def scan():
    if not dlp_scanner:
        return jsonify({"error": "Model not loaded"}), 500
        
    data = request.get_json()
    if not data:
        return jsonify([])
        
    text = data.get("text", "").strip()
    if not text:
        return jsonify([])
        
    try:
        raw_results = dlp_scanner(text)
        merged = merge_entities(raw_results, text)
        
        findings = []
        for r in merged:
            entity_type = r["entity_group"]
            adapted_type = adapt_label(entity_type)
            
            findings.append({
                "entity": adapted_type,
                "value": r["value"],
                "confidence": round(r["score"], 4),
                "start": int(r["start"]),
                "end": int(r["end"])
            })
            
        return jsonify(findings)
    except Exception as e:
        print(f"Error during scan: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    # Binding ONLY to 127.0.0.1 (localhost) as per requirements
    print("Starting SOTA DLP Flask Server...")
    app.run(host="127.0.0.1", port=5000, debug=False)
