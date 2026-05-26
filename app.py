from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from transformers import pipeline
import os

app = Flask(__name__)
CORS(app)

print("Loading DLP model...")
MODEL_PATH = os.path.join(os.path.dirname(__file__), "dlp-model-final/checkpoint-985")

dlp_scanner = pipeline(
    "token-classification",
    model=MODEL_PATH,
    aggregation_strategy="first"
)
print("Model loaded and ready")

def merge_entities(results, original_text):
    if not results:
        return []
    merged = []
    current = {
        "entity_group": results[0]["entity_group"],
        "score": float(results[0]["score"]),
        "start": results[0]["start"],
        "end": results[0]["end"],
        "value": original_text[results[0]["start"]:results[0]["end"]]
    }
    for nxt in results[1:]:
        if nxt["entity_group"] == current["entity_group"] and \
           nxt["start"] <= current["end"] + 1:
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

@app.route('/')
def test_page():
    return send_from_directory('../extension', 'test.html')

@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "ok"})

@app.route('/scan', methods=['POST'])
def scan():
    data = request.get_json()
    text = data.get('text', '').strip()
    if not text:
        return jsonify([])
    results = dlp_scanner(text)
    merged = merge_entities(results, text)
    findings = [
        {
            "entity": r["entity_group"],
            "value": r["value"],
            "confidence": round(r["score"], 3),
            "start": int(r["start"]),
            "end": int(r["end"])
        }
        for r in merged
    ]
    return jsonify(findings)

if __name__ == '__main__':
    print("Starting DLP API on http://localhost:5000")
    app.run(port=5000, debug=False)
