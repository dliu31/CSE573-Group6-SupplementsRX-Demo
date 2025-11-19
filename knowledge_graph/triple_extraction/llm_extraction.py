import os
import re
import json as _json
from typing import List, Dict
from openai import OpenAI
from dotenv import load_dotenv


load_dotenv()

LLM_MODEL = os.getenv("KG_LLM_MODEL", "gpt-4o-mini")

def parse_json(text: str):
    if not text or not text.strip():
        return None

    text = re.sub(r"^```json\s*|\s*```$", "", text.strip(), flags=re.IGNORECASE)

    try:
        return _json.loads(text)
    except Exception:
        pass

    match = re.search(r"(\[.*\])", text, flags=re.DOTALL)
    if match:
        try:
            return _json.loads(match.group(1))
        except Exception:
            pass

    match1 = re.search(r"(\{.*\})", text, flags=re.DOTALL)
    if match1:
        try:
            return _json.loads(match1.group(1))
        except Exception:
            pass

    return None


def llm_extract_triples(supplement_name: str, cleaned_text: str, url: str) -> List[Dict[str, str]]:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return []

    client = OpenAI()

    prompt = (
        "Extract supplement→relation→condition triples as JSON. "
        "Allowed relation values: {indicated_for,treats,prevents,helps_with,manages,relieves,deficiency,condition,symptom,procedure,cleanses,procedure_prep}. "
        "Each triple should include keys: condition, relation, confidence (0..1), evidence."
    )

    user_payload = _json.dumps({"supplement": supplement_name, "url": url, "text": cleaned_text})

    try:
        response = client.responses.create(
            model=LLM_MODEL,
            input=[{"role": "system", "content": prompt}, {"role": "user", "content": user_payload}],
            temperature=0,
        )
    except Exception:
        return []

    output_text = getattr(response, "output_text", None) or ""
    parsed = parse_json(output_text)
    if parsed is None:
        return []

    if isinstance(parsed, dict) and isinstance(parsed.get("triples"), list):
        return parsed["triples"]

    if isinstance(parsed, list):
        return parsed

    return []


def create_relation(rel_raw: str) -> str:
    relations = {
        "indicated_for": "INDICATED_FOR",
        "treats": "TREATS",
        "prevents": "PREVENTS",
        "helps_with": "HELPS_WITH",
        "manages": "MANAGES",
        "relieves": "RELIEVES",
        "deficiency": "TREATS_DEFICIENCY",
        "condition": "INDICATED_FOR",
        "symptom": "RELIEVES_SYMPTOM",
        "procedure": "USED_FOR_PROCEDURE",
        "cleanses": "CLEANSES",
        "procedure_prep": "USED_FOR_PROCEDURE",
    }

    key = (rel_raw or "").strip().lower()
    return relations.get(key, "RELATED_TO")
