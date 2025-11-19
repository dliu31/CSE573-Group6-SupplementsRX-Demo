import json
from pathlib import Path
import pandas as pd
import re


def clean_text(text):
    if not isinstance(text, str):
        return ""
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    prompts = [
        "Sign up for free",
        "stay up to date",
        "email field is required",
        "valid email address",
        "unsubscribe link",
        "privacy practices",
    ]
    for b in prompts:
        text = text.replace(b, "")
    return text.strip()


def normalize_name(s):
    if not isinstance(s, str):
        return ""
    s = s.replace("®", "").replace("™", "").strip()
    s = " ".join(s.split())
    if not s:
        return ""
    if s.isupper():
        return s.title()
    return s[:1].upper() + s[1:]


def is_http(series):
    return series.astype(str).str.startswith(("http://", "https://"))


def parse_dosage(text):
    if not isinstance(text, str) or not text.strip():
        return None, None
    text = text.lower()
    m = re.search(r"(\d+(?:\.\d+)?)\s*-\s*(\d+(?:\.\d+)?)(?:\s*(mg|mcg))", text)
    if m:
        a = float(m.group(1))
        b = float(m.group(2))
        unit = m.group(3)
        if unit == "mcg":
            a /= 1000.0
            b /= 1000.0
        return round(a, 3), round(b, 3)
    m2 = re.search(r"(\d+(?:\.\d+)?)\s*(mg|mcg)", text)
    if m2:
        v = float(m2.group(1))
        unit = m2.group(2)
        if unit == "mcg":
            v /= 1000.0
        v = round(v, 3)
        return v, v
    return None, None


def map_evidence(s):
    if not isinstance(s, str) or not s.strip():
        return "Unspecified"
    t = s.strip().lower()
    if "strong" in t or "grade a" in t or "level i" in t:
        return "High"
    if "moderate" in t or "grade b" in t or "level ii" in t or "good" in t:
        return "Moderate"
    if "limited" in t or "weak" in t or "grade c" in t or "level iii" in t:
        return "Low"
    if "anecdotal" in t or "insufficient" in t or "traditional" in t:
        return "Anecdotal"
    return "Unspecified"


def split_simple(val):
    if not isinstance(val, str):
        return []
    parts = re.split(r"[;,|\n]+", val)
    clean = [p.strip() for p in parts if p.strip()]
    return clean


def load_file(path):
    p = Path(path)
    suf = p.suffix.lower()
    if suf == ".csv":
        return pd.read_csv(p)
    if suf == ".jsonl":
        rows = []
        with open(p, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    rows.append(json.loads(line))
        return pd.DataFrame(rows)
    if suf == ".json":
        with open(p, "r", encoding="utf-8") as f:
            obj = json.load(f)
        if isinstance(obj, list):
            return pd.DataFrame(obj)
        if isinstance(obj, dict) and "data" in obj:
            return pd.DataFrame(obj["data"])
        raise ValueError("Unsupported JSON structure")
    raise ValueError(f"Unsupported file type: {suf}")


def standardize_minimal(df):
    if "query" in df.columns and "mechanism_of_action" in df.columns:
        out = pd.DataFrame()
        out["supplement_name"] = df["query"].apply(normalize_name)
        out["url"] = ""
        out["source_name"] = "natural_medicines"
        uses = df["mechanism_of_action"].fillna("").astype(str)
        out["uses_text"] = uses.apply(clean_text)
        out["evidence_rating"] = "Unspecified"
        out["dosage_min_mg"] = None
        out["dosage_max_mg"] = None
        has_name = out["supplement_name"] != ""
        filtered = out[has_name].copy()
        filtered.reset_index(drop=True, inplace=True)
        return filtered

    out = pd.DataFrame()
    out["supplement_name"] = df.get("supplement_name", "").apply(normalize_name)
    out["url"] = df.get("url", "").fillna("").astype(str).str.strip()
    out["source_name"] = df.get("source", "").fillna("").astype(str).str.strip()
    uses = df.get("uses", "").fillna("").astype(str)
    out["uses_text"] = uses.apply(clean_text)
    ev = df.get("evidence_rating", "")
    out["evidence_rating"] = ev.apply(map_evidence) if hasattr(ev, "apply") else map_evidence(ev)
    mins = []
    maxs = []
    if "dosage_range" in df.columns:
        for val in df["dosage_range"].fillna("").astype(str):
            mn, mx = parse_dosage(val)
            mins.append(mn)
            maxs.append(mx)
    else:
        mins = [None] * len(out)
        maxs = [None] * len(out)
    out["dosage_min_mg"] = mins
    out["dosage_max_mg"] = maxs
    has_name = out["supplement_name"] != ""
    has_http_url = is_http(out["url"])
    filtered = out[has_name & has_http_url].copy()
    filtered.reset_index(drop=True, inplace=True)
    return filtered


def extend_optional_columns(df_std, df_raw):
    out = df_std.copy()
    if "category" in df_raw.columns:
        out["category"] = df_raw["category"].fillna("").astype(str).str.strip()
    else:
        out["category"] = ""
    if "interactions" in df_raw.columns:
        out["interactions_drugs"] = df_raw["interactions"].apply(split_simple)
    else:
        out["interactions_drugs"] = [[] for _ in range(len(out))]
    if "contraindications" in df_raw.columns:
        out["contraindications"] = df_raw["contraindications"].apply(split_simple)
    else:
        out["contraindications"] = [[] for _ in range(len(out))]
    return out


def remove_junk(df):
    junk_list = [
        "Sign up for free",
        "valid email address",
        "unsubscribe",
        "There is a problem with information submitted for this request",
    ]
    junk_strs = "|".join(junk_list)
    junk = df["uses_text"].str.contains(junk_strs, case=False, regex=True)
    df = df[~junk]
    return df


def remove_dupes(df):
    no_dupes = df.drop_duplicates(subset=["supplement_name", "url"], keep="first").reset_index(drop=True)
    return no_dupes


def save_csv(df, out_path):
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_path, index=False)


if __name__ == "__main__":
    df_raw = load_file("output/final_supplements.jsonl")
    df_std = standardize_minimal(df_raw)
    df_std = extend_optional_columns(df_std, df_raw)
    df_std = remove_junk(df_std)
    df_std = remove_dupes(df_std)
    save_csv(df_std, "knowledge_graph/data/standardized_rows_mayo.csv")

    df_raw = load_file("output/combined.json")
    df_std = standardize_minimal(df_raw)
    df_std = extend_optional_columns(df_std, df_raw)
    df_std = remove_junk(df_std)
    df_std = remove_dupes(df_std)
    save_csv(df_std, "knowledge_graph/data/standardized_rows.csv")
