import asyncio
import glob
import json
import os
from pathlib import Path
import pandas as pd

STANDARD_COLUMNS = [
    "supplement_name",
    "category",
    "uses",
    "dosage_range",
    "contraindications",
    "interactions",
    "evidence_rating",
    "clinical_refs",
    "source",
    "url",
]

def _read_any(path):
    if path.endswith(".jsonl"):
        return pd.read_json(path, lines=True)
    if path.endswith(".json"):
        return pd.read_json(path)
    if path.endswith(".csv"):
        return pd.read_csv(path)
    return pd.DataFrame()

async def load_and_standardize(outdir: str):
    files = glob.glob(os.path.join(outdir, "*.jsonl"))
    frames = []
    for f in files:
        try:
            df = _read_any(f)
            for col in STANDARD_COLUMNS:
                if col not in df.columns:
                    df[col] = None
            frames.append(df[STANDARD_COLUMNS])
        except Exception:
            continue

    if frames:
        merged = pd.concat(frames, ignore_index=True)
    else:
        merged = pd.DataFrame(columns=STANDARD_COLUMNS)


    merged["supplement_name"] = merged["supplement_name"].fillna("").str.strip().str.title()
    merged["category"] = merged["category"].fillna("").str.lower()
    merged["dosage_range"] = merged["dosage_range"].fillna("").str.replace("–", "-", regex=False)

    
    merged.drop_duplicates(subset=["supplement_name", "source", "url"], keep="first", inplace=True)

    parquet = Path(outdir) / "merged.clean.parquet"
    merged.to_parquet(parquet, index=False)  # columnar + compressed; handles millions
    return parquet

async def write_merged_outputs(merged_parquet: Path, outdir: str):
    df = pd.read_parquet(merged_parquet)

    
    jsonl_path = Path(outdir) / "final_supplements.jsonl"
    with open(jsonl_path, "w", encoding="utf-8") as f:
        for _, row in df.iterrows():
            f.write(json.dumps(row.to_dict(), ensure_ascii=False) + "\n")

    csv_path = Path(outdir) / "final_supplements.csv"
    df.to_csv(csv_path, index=False)

    return {"parquet": str(merged_parquet), "csv": str(csv_path), "jsonl": str(jsonl_path)}