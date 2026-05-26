import json
import random

def text_to_bio(text, entity_value, label):
    tokens = text.split()
    bio_tags = ["O"] * len(tokens)
    
    entity_tokens = entity_value.split()
    entity_len = len(entity_tokens)
    
    for i in range(len(tokens) - entity_len + 1):
        window = tokens[i:i+entity_len]
        clean_window = [t.strip(".,;:!?\"'()") for t in window]
        clean_entity = [t.strip(".,;:!?\"'()") for t in entity_tokens]
        
        if clean_window == clean_entity:
            bio_tags[i] = f"B-{label}"
            for j in range(1, entity_len):
                bio_tags[i+j] = f"I-{label}"
            break
    
    return tokens, bio_tags

def convert(input_path, output_path):
    with open(input_path) as f:
        data = json.load(f)
    
    converted = []
    skipped = 0
    
    for item in data:
        try:
            tokens, tags = text_to_bio(
                item["text"],
                item["entity_value"],
                item["label"]
            )
            
            if all(t == "O" for t in tags):
                skipped += 1
                continue
                
            converted.append({
                "tokens": tokens,
                "ner_tags": tags,
                "text": item["text"],
                "label": item["label"]
            })
        except Exception as e:
            skipped += 1
            continue
    
    random.shuffle(converted)
    total = len(converted)
    train_end = int(total * 0.8)
    val_end = int(total * 0.9)
    
    train = converted[:train_end]
    val = converted[train_end:val_end]
    test = converted[val_end:]
    
    with open(output_path + "/train.json", "w") as f:
        json.dump(train, f, indent=2)
    with open(output_path + "/val.json", "w") as f:
        json.dump(val, f, indent=2)
    with open(output_path + "/test.json", "w") as f:
        json.dump(test, f, indent=2)
    
    print(f"Total converted: {len(converted)}")
    print(f"Skipped (entity not found): {skipped}")
    print(f"Train: {len(train)} | Val: {len(val)} | Test: {len(test)}")
    print(f"Saved to {output_path}/")

if __name__ == "__main__":
    convert("dataset/raw_data.json", "dataset")
