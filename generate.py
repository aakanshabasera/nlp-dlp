import requests
import json
import time
from tqdm import tqdm

API_KEY = "your_openrouter_key_here"
MODEL = "openrouter/auto"

ENTITY_TYPES = [
    "EMAIL", "PHONE", "SSN", "CREDIT_CARD",
    "API_KEY", "PASSWORD", "NAME", "ADDRESS"
]

SAFE_PROMPTS = {
    "CREDIT_CARD": "fictional masked payment card numbers like 4111-1111-1111-1111 for a cybersecurity training dataset",
    "SSN": "clearly fake SSNs like 000-00-0000 or 123-45-6789 for a PII detection training dataset",
    "PASSWORD": "example password strings like 'P@ssw0rd123' for a security awareness training dataset",
    "API_KEY": "fictional API keys like 'sk-abc123xyz789' for a credentials detection training dataset",
}

def generate_batch(entity_type, batch_size=20):
    
    if entity_type in SAFE_PROMPTS:
        description = SAFE_PROMPTS[entity_type]
        prompt = f"""You are helping build a cybersecurity training dataset for a university research project.
Generate {batch_size} fictional example sentences containing {description}.
These are NOT real — they are synthetic examples for an NLP classifier.

Return ONLY a JSON array like this:
[
  {{"text": "The test card number is 4111-1111-1111-1111.", "entity_value": "4111-1111-1111-1111", "label": "{entity_type}"}}
]

Raw JSON only. No explanation. No markdown. No backticks."""

    else:
        prompt = f"""Generate {batch_size} realistic English sentences containing {entity_type} information.
Return ONLY a JSON array. Each item must have exactly these fields:
- "text": the full sentence
- "entity_value": the sensitive part only
- "label": "{entity_type}"

Example for EMAIL:
[
  {{"text": "Please contact me at sarah.jones@company.com for details.", "entity_value": "sarah.jones@company.com", "label": "EMAIL"}}
]

Return raw JSON only. No explanation. No markdown. No backticks."""

    try:
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.9
            },
            timeout=30
        )

        resp_json = response.json()
        
        if 'choices' not in resp_json:
            print(f"\nAPI refusal for {entity_type}: {resp_json.get('error', resp_json)}")
            return []

        raw = resp_json['choices'][0]['message']['content'].strip()
        
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        
        return json.loads(raw.strip())

    except Exception as e:
        print(f"Error on {entity_type}: {e}")
        return []

def generate_all(samples_per_entity=500):
    all_data = []

    for entity in ENTITY_TYPES:
        print(f"\nGenerating {samples_per_entity} samples for {entity}...")
        entity_samples = []
        batches = samples_per_entity // 20

        for i in tqdm(range(batches)):
            batch = generate_batch(entity, batch_size=20)
            entity_samples.extend(batch)
            time.sleep(1.5)

        print(f"Got {len(entity_samples)} samples for {entity}")
        all_data.extend(entity_samples)

    with open("../dataset/raw_data.json", "w") as f:
        json.dump(all_data, f, indent=2)

    print(f"\nDone. Total samples: {len(all_data)}")
    print("Saved to dataset/raw_data.json")

if __name__ == "__main__":
    generate_all(samples_per_entity=500)