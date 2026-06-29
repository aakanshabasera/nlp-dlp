#!/usr/bin/env python3
import os
import sys
import json
import time
import argparse
import requests
from dotenv import load_dotenv
from tqdm import tqdm

# Load environment variables
load_dotenv()

# Taxonomy Definition
TAXONOMY = {
    "PII": [
        "PII.SSN",
        "PII.Aadhar",
        "PII.PAN",
        "PII.Mobile",
        "PII.Address",
        "PII.Email"
    ],
    "PFI": [
        "PFI.Credit_Card",
        "PFI.CVV",
        "PFI.Expiration_Date",
        "PFI.Debit_Card",
        "PFI.Bank_Account",
        "PFI.IFSC"
    ],
    "PHI": [
        "PHI.Doctor",
        "PHI.MRN",
        "PHI.Medicine",
        "PHI.Diagnosis",
        "PHI.Hospital"
    ],
    "Auth": [
        "Auth.API_KEY",
        "Auth.Access_Token",
        "Auth.JWT_Token",
        "Auth.Username",
        "Auth.Password"
    ]
}

# Flattened list of all 22 subtypes
ALL_SUBTYPES = [subtype for category in TAXONOMY.values() for subtype in category]

# Helper to find a category from a subtype
def get_category(subtype):
    for cat, subtypes in TAXONOMY.items():
        if subtype in subtypes:
            return cat
    return None

def parse_args():
    parser = argparse.ArgumentParser(description="Generate synthetic training data for DLP NER model.")
    parser.add_argument(
        "--model", "-m",
        type=str,
        default=os.getenv("OPENROUTER_MODEL", "openrouter/free"),
        help="OpenRouter model name to use"
    )
    parser.add_argument(
        "--output", "-o",
        type=str,
        default="data/raw_data.json",
        help="Path to save the output JSON data"
    )
    parser.add_argument(
        "--samples-per-subtype", "-s",
        type=int,
        default=2500,
        help="Number of samples to generate per subtype"
    )
    parser.add_argument(
        "--api-key", "-k",
        type=str,
        default=os.getenv("OPENROUTER_API_KEY"),
        help="OpenRouter API Key (overrides env)"
    )
    parser.add_argument(
        "--batch-size", "-b",
        type=int,
        default=5,
        help="Batch size of samples per API call"
    )
    return parser.parse_args()

def call_openrouter(api_key, model, prompt, retries=5, backoff=2):
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    url = "https://openrouter.ai/api/v1/chat/completions"
    
    for attempt in range(retries):
        try:
            response = requests.post(
                url,
                headers=headers,
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.8
                },
                timeout=45
            )
            
            if response.status_code == 429:
                sleep_time = backoff * (2 ** attempt)
                print(f"\nRate limited (429). Sleeping for {sleep_time} seconds...")
                time.sleep(sleep_time)
                continue
                
            if response.status_code != 200:
                print(f"\nError: API returned status {response.status_code}. Response: {response.text}")
                time.sleep(2)
                continue
                
            resp_json = response.json()
            if 'choices' not in resp_json:
                print(f"\nError: 'choices' key missing in response: {resp_json}")
                time.sleep(2)
                continue
                
            return resp_json['choices'][0]['message']['content'].strip()
            
        except Exception as e:
            print(f"\nException during API call: {e}")
            time.sleep(2)
            
    return None

def process_generated_samples(raw_response_text):
    """
    Parses LLM response JSON and processes it to add character-level offsets.
    Discarding samples that do not match or are malformed.
    """
    try:
        raw = raw_response_text.strip()
        if raw.startswith("```"):
            parts = raw.split("```")
            if len(parts) >= 2:
                raw = parts[1].strip()
                if raw.startswith("json"):
                    raw = raw[4:].strip()
        data = json.loads(raw)
        samples = data.get("samples", [])
        processed_samples = []
        
        for item in samples:
            text = item.get("text", "").strip()
            raw_entities = item.get("entities", [])
            
            if not text:
                continue
                
            processed_entities = []
            valid = True
            
            for ent in raw_entities:
                val = ent.get("value", "").strip()
                lbl = ent.get("label", "").strip()
                
                if not val or not lbl:
                    continue
                
                # Check for redacted formats (should not be labeled)
                if any(x in val for x in ["****", "XXXX", "redacted", "REDACTED", "XXX-XX-XXXX"]):
                    continue
                    
                # Find occurrences in text
                start_idx = text.find(val)
                if start_idx == -1:
                    # Could be case mismatch, try case-insensitive
                    start_idx = text.lower().find(val.lower())
                    if start_idx == -1:
                        # Value not found in text, discard this entity
                        continue
                    # Align value case with the original text
                    val = text[start_idx:start_idx+len(val)]
                    
                end_idx = start_idx + len(val)
                processed_entities.append({
                    "start": start_idx,
                    "end": end_idx,
                    "label": lbl
                })
                
            # Deduplicate and sort entities by start index
            processed_entities = sorted(
                list({f"{e['start']}_{e['end']}_{e['label']}": e for e in processed_entities}.values()),
                key=lambda x: x["start"]
            )
            
            processed_samples.append({
                "text": text,
                "entities": processed_entities
            })
            
        return processed_samples
    except Exception as e:
        print(f"Error parsing response: {e}")
        return []

def generate_subtype_batch(api_key, model, subtype, count, batch_size):
    prompt = f"""You are building a high-quality Named Entity Recognition (NER) training dataset for Data Loss Prevention (DLP).
Generate exactly {batch_size} unique, diverse sentences where each sentence contains at least one sensitive entity of type '{subtype}'.
The sentence should look natural, like real email content, chat messages, support tickets, code comments, or configuration files.

Category subtype: '{subtype}'
Description: A sensitive value corresponding to '{subtype}'.

Return your output in JSON format with a root "samples" key holding an array.
Each sample must contain:
1. "text": The complete sentence/text.
2. "entities": An array of objects, each containing:
   - "value": The exact substring value of the sensitive entity.
   - "label": "{subtype}"

Ensure the text contains the EXACT entity value string you specify.
Avoid using markdown tags, markdown boxes, or explanations. Return ONLY the JSON object.

Example JSON output format:
{{
  "samples": [
    {{
      "text": "Please send the report to admin@company.com immediately.",
      "entities": [
        {{"value": "admin@company.com", "label": "PII.Email"}}
      ]
    }}
  ]
}}
"""
    raw = call_openrouter(api_key, model, prompt)
    if not raw:
        return []
    return process_generated_samples(raw)

def generate_multi_entity_batch(api_key, model, subtypes_pair, count, batch_size):
    sub1, sub2 = subtypes_pair
    prompt = f"""You are building a high-quality Named Entity Recognition (NER) training dataset for Data Loss Prevention (DLP).
Generate exactly {batch_size} unique, diverse sentences where each sentence contains BOTH a '{sub1}' entity AND a '{sub2}' entity.
The sentence should look natural, like real messages, transaction logs, database dumps, or emails.

Entities to include:
- '{sub1}'
- '{sub2}'

Return your output in JSON format with a root "samples" key holding an array.
Each sample must contain:
1. "text": The complete text.
2. "entities": An array of objects, each containing:
   - "value": The exact substring value of the entity.
   - "label": The respective label (e.g. "{sub1}" or "{sub2}").

Example JSON output format:
{{
  "samples": [
    {{
      "text": "User admin logged in from IP with username admin_user and password P@ssword123.",
      "entities": [
        {{"value": "admin_user", "label": "Auth.Username"}},
        {{"value": "P@ssword123", "label": "Auth.Password"}}
      ]
    }}
  ]
}}
"""
    raw = call_openrouter(api_key, model, prompt)
    if not raw:
        return []
    return process_generated_samples(raw)

def generate_clean_batch(api_key, model, batch_size):
    prompt = f"""You are building a high-quality training dataset for Data Loss Prevention (DLP).
Generate exactly {batch_size} unique, diverse sentences that contain NO sensitive data, OR contain REDACTED/MASKED sensitive information.
Examples of redacted information include: "SSN: XXX-XX-XXXX", "my email is redacted for privacy", "the password was ****", etc.
These redacted values must NOT be labeled as sensitive.

Return your output in JSON format with a root "samples" key holding an array.
Each sample must contain:
1. "text": The complete sentence/text.
2. "entities": An empty array [] (since there is no active sensitive data).

Example JSON output format:
{{
  "samples": [
    {{
      "text": "The transaction was approved. Credit card details were masked: **** **** **** 4321.",
      "entities": []
    }}
  ]
}}
"""
    raw = call_openrouter(api_key, model, prompt)
    if not raw:
        return []
    return process_generated_samples(raw)

def main():
    args = parse_args()
    
    if not args.api_key:
        print("Error: OpenRouter API key is missing. Set OPENROUTER_API_KEY in .env or pass --api-key / -k")
        sys.exit(1)
        
    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    
    # Load existing data (Resume Capability)
    existing_samples = []
    if os.path.exists(args.output):
        try:
            with open(args.output, "r") as f:
                existing_samples = json.load(f)
            print(f"Loaded {len(existing_samples)} existing samples from {args.output}")
        except Exception as e:
            print(f"Warning: Could not load existing file: {e}. Starting fresh.")
            
    # Count samples by entity label to see what is already covered
    counts = {subtype: 0 for subtype in ALL_SUBTYPES}
    counts["clean"] = 0
    counts["multi"] = 0
    
    for sample in existing_samples:
        ents = sample.get("entities", [])
        if not ents:
            counts["clean"] += 1
        elif len(ents) > 1:
            counts["multi"] += 1
            # Still count the subtypes inside
            for e in ents:
                lbl = e.get("label")
                if lbl in counts:
                    counts[lbl] += 1
        else:
            lbl = ents[0].get("label")
            if lbl in counts:
                counts[lbl] += 1
                
    print("\nCurrent subtype counts in existing dataset:")
    for sub, count in counts.items():
        if count > 0:
            print(f" - {sub}: {count}")
            
    # Target calculations
    # 2500 entries per subtype.
    target_per_subtype = args.samples_per_subtype
    
    # We want to distribute this across single, multi, and clean.
    # Let's say:
    # - 70% single-entity samples
    # - 15% multi-entity samples
    # - 15% clean samples
    # If the user requested e.g. 2500 samples per subtype, we'll try to reach that total.
    # For a dry run (small number), we will scale accordingly.
    
    all_generated_samples = list(existing_samples)
    
    # 1. Single Entity Generation
    print("\n--- Generating Single-Entity Samples ---")
    for subtype in ALL_SUBTYPES:
        needed = target_per_subtype - counts[subtype]
        if needed <= 0:
            print(f"Subtype {subtype} already fully generated.")
            continue
            
        print(f"Generating {needed} samples for {subtype}...")
        pbar = tqdm(total=needed)
        
        while needed > 0:
            current_batch = min(needed, args.batch_size)
            samples = generate_subtype_batch(args.api_key, args.model, subtype, needed, current_batch)
            
            if not samples:
                print("\nFailed to generate batch, sleeping and retrying...")
                time.sleep(5)
                continue
                
            all_generated_samples.extend(samples)
            needed -= len(samples)
            pbar.update(len(samples))
            
            # Save incrementally
            with open(args.output, "w") as f:
                json.dump(all_generated_samples, f, indent=2)
                
            time.sleep(1.0) # Rate limit protection
            
        pbar.close()
        
    # 2. Multi-Entity Generation
    # We generate multi-entity samples containing pairs from different categories
    print("\n--- Generating Multi-Entity Samples ---")
    target_multi = int(len(ALL_SUBTYPES) * target_per_subtype * 0.15)
    current_multi = counts["multi"]
    needed_multi = target_multi - current_multi
    
    if needed_multi > 0:
        print(f"Generating {needed_multi} multi-entity samples...")
        pbar = tqdm(total=needed_multi)
        
        # Create pairs from different categories
        categories = list(TAXONOMY.keys())
        pair_index = 0
        
        while needed_multi > 0:
            # Pick two subtypes from different categories
            cat1 = categories[pair_index % len(categories)]
            cat2 = categories[(pair_index + 1) % len(categories)]
            sub1 = TAXONOMY[cat1][(pair_index // len(categories)) % len(TAXONOMY[cat1])]
            sub2 = TAXONOMY[cat2][(pair_index // len(categories)) % len(TAXONOMY[cat2])]
            pair_index += 1
            
            current_batch = min(needed_multi, args.batch_size)
            samples = generate_multi_entity_batch(args.api_key, args.model, (sub1, sub2), needed_multi, current_batch)
            
            if not samples:
                print("\nFailed to generate multi-entity batch, sleeping and retrying...")
                time.sleep(5)
                continue
                
            all_generated_samples.extend(samples)
            needed_multi -= len(samples)
            pbar.update(len(samples))
            
            # Save incrementally
            with open(args.output, "w") as f:
                json.dump(all_generated_samples, f, indent=2)
                
            time.sleep(1.0)
            
        pbar.close()
        
    # 3. Clean Samples Generation
    # Must be at least 15% of total samples
    print("\n--- Generating Clean & Redacted Samples ---")
    total_samples = len(all_generated_samples)
    target_clean = int(total_samples * 0.18) # Aim slightly higher than 15%
    current_clean = counts["clean"]
    needed_clean = target_clean - current_clean
    
    if needed_clean > 0:
        print(f"Generating {needed_clean} clean samples...")
        pbar = tqdm(total=needed_clean)
        
        while needed_clean > 0:
            current_batch = min(needed_clean, args.batch_size)
            samples = generate_clean_batch(args.api_key, args.model, current_batch)
            
            if not samples:
                print("\nFailed to generate clean batch, sleeping and retrying...")
                time.sleep(5)
                continue
                
            all_generated_samples.extend(samples)
            needed_clean -= len(samples)
            pbar.update(len(samples))
            
            # Save incrementally
            with open(args.output, "w") as f:
                json.dump(all_generated_samples, f, indent=2)
                
            time.sleep(1.0)
            
        pbar.close()
        
    print(f"\nGeneration complete! Total samples: {len(all_generated_samples)}")
    print(f"Saved to {args.output}")

if __name__ == "__main__":
    main()
