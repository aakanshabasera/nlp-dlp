#!/usr/bin/env python3
import os
import re
import json
import random
import argparse

def tokenize_with_spans(text):
    """
    Tokenizes text by splitting on words and keeping punctuation separate,
    returning list of tokens and their start/end character offsets.
    """
    pattern = re.compile(r'\w+|[^\w\s]')
    tokens = []
    spans = []
    for match in pattern.finditer(text):
        tokens.append(match.group())
        spans.append((match.start(), match.end()))
    return tokens, spans

def align_entities_to_tokens(text, entities, tokens, spans):
    """
    Maps character-level entity offsets to token-level BIO tags.
    """
    bio_tags = ["O"] * len(tokens)
    
    for ent in entities:
        ent_start = ent["start"]
        ent_end = ent["end"]
        label = ent["label"]
        
        first_token_idx = None
        for idx, (t_start, t_end) in enumerate(spans):
            # Check if token falls inside entity boundaries
            if t_start >= ent_start and t_end <= ent_end:
                if first_token_idx is None:
                    bio_tags[idx] = f"B-{label}"
                    first_token_idx = idx
                else:
                    bio_tags[idx] = f"I-{label}"
                    
    return bio_tags

def parse_args():
    parser = argparse.ArgumentParser(description="Convert synthetic offset-based data to BIO-tagged token data.")
    parser.add_argument(
        "--input", "-i",
        type=str,
        default="data/raw_data.json",
        help="Path to raw synthetic JSON file"
    )
    parser.add_argument(
        "--output-dir", "-o",
        type=str,
        default="data",
        help="Directory to save train.json, val.json, test.json"
    )
    parser.add_argument(
        "--train-split",
        type=float,
        default=0.8,
        help="Proportion of training data"
    )
    parser.add_argument(
        "--val-split",
        type=float,
        default=0.1,
        help="Proportion of validation data"
    )
    return parser.parse_args()

def main():
    args = parse_args()
    
    if not os.path.exists(args.input):
        print(f"Error: Input file {args.input} does not exist.")
        return
        
    with open(args.input, "r") as f:
        raw_data = json.load(f)
        
    print(f"Loaded {len(raw_data)} samples from {args.input}")
    
    processed_samples = []
    skipped = 0
    
    for idx, item in enumerate(raw_data):
        text = item.get("text", "")
        entities = item.get("entities", [])
        
        try:
            tokens, spans = tokenize_with_spans(text)
            tags = align_entities_to_tokens(text, entities, tokens, spans)
            
            # Sanity check: verify tags match entities
            # For non-empty entities, we should have at least one B- tag
            active_ents = [e for e in entities if e["start"] != e["end"]]
            if active_ents and all(t == "O" for t in tags):
                skipped += 1
                continue
                
            processed_samples.append({
                "tokens": tokens,
                "ner_tags": tags,
                "text": text,
                "entities": entities
            })
        except Exception as e:
            print(f"Error processing sample {idx}: {e}")
            skipped += 1
            
    print(f"Successfully processed {len(processed_samples)} samples. Skipped {skipped} due to alignment failures.")
    
    # Shuffle and split
    random.seed(42)
    random.shuffle(processed_samples)
    
    total = len(processed_samples)
    train_end = int(total * args.train_split)
    val_end = int(total * (args.train_split + args.val_split))
    
    train_data = processed_samples[:train_end]
    val_data = processed_samples[train_end:val_end]
    test_data = processed_samples[val_end:]
    
    os.makedirs(args.output_dir, exist_ok=True)
    
    with open(os.path.join(args.output_dir, "train.json"), "w") as f:
        json.dump(train_data, f, indent=2)
    with open(os.path.join(args.output_dir, "val.json"), "w") as f:
        json.dump(val_data, f, indent=2)
    with open(os.path.join(args.output_dir, "test.json"), "w") as f:
        json.dump(test_data, f, indent=2)
        
    print(f"\nSaved datasets to {args.output_dir}:")
    print(f" - train.json: {len(train_data)} samples")
    print(f" - val.json:   {len(val_data)} samples")
    print(f" - test.json:  {len(test_data)} samples")

if __name__ == "__main__":
    main()
