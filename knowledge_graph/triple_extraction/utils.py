import re, hashlib, json
import pandas as pd
from pathlib import Path
from typing import List, Dict
from data_structures import Triple

def create_id(text: str) -> str:
    cleaned = re.sub(r'[^a-zA-Z0-9\s]', '', str(text).lower())
    slug = re.sub(r'\s+', '-', cleaned).strip('-')

    if slug:
        return slug

    fallback = hashlib.md5(str(text).encode()).hexdigest()
    return fallback[:8]

def write_nodes(conditions: Dict[str, str], supplements: Dict[str, str], output_dir: Path):
    condition_records = []
    for cid, name in conditions.items():
        condition_records.append({
            "condition_id": cid,
            "condition_name": name,
            "entity_type": "condition",
        })

    conditions_df = pd.DataFrame(condition_records)
    conditions_df.to_csv(output_dir / 'nodes_conditions.csv', index=False)

    supplement_records = []
    for sid, name in supplements.items():
        supplement_records.append({
            "supplement_id": sid,
            "supplement_name": name,
            "entity_type": "supplement",
        })

    supplements_df = pd.DataFrame(supplement_records)
    supplements_df.to_csv(output_dir / 'nodes_supplements.csv', index=False)

    return {"conditions": len(conditions_df), "supplements": len(supplements_df)}

def write_edges(triples: List[Triple], output_dir: Path):
    records = []
    for t in triples:
        records.append(t.to_dict())

    edges_df = pd.DataFrame(records)
    edges_df.to_csv(output_dir / 'edges_detailed.csv', index=False)

    basic = edges_df[['relation_type', 'supplement_id', 'condition_id', 'source_url']].copy()
    basic.columns = ['type', 'supplement_id', 'condition_id', 'url']
    basic.to_csv(output_dir / 'edges_relationships.csv', index=False)

    high_conf_df = edges_df[edges_df['confidence'] > 0.8]
    high_conf_df.to_csv(output_dir / 'high_confidence_triples.csv', index=False)

    return {"basic": len(basic), "detailed": len(edges_df), "high_conf": len(high_conf_df)}

def write_stats(stats: dict, output_dir: Path):
    summary = stats.copy()

    summary['unique_supplements'] = len(summary.get('unique_supplements', []))
    summary['unique_conditions'] = len(summary.get('unique_conditions', []))

    out_path = output_dir / 'extraction_stats.json'
    with open(out_path, 'w') as f:
        json.dump(summary, f, indent=2)