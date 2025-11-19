from pathlib import Path
from typing import Dict, List
import pandas as pd
from collections import defaultdict
from data_structures import Triple
from cleaner import MedicalTextCleaner
from re_extractor import MedicalEntityExtractor
from llm_extraction import llm_extract_triples, create_relation
from utils import create_id, write_nodes, write_edges, write_stats

class SupplementTripleExtractor:
    def __init__(self, input_path: str, output_dir: str):
        self.input_path = Path(input_path)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.cleaner = MedicalTextCleaner()
        self.extractor = MedicalEntityExtractor()
        self.stats = {
            'total_rows': 0,
            'valid_rows': 0,
            'invalid_rows': 0,
            'total_triples': 0,
            'unique_supplements': set(),
            'unique_conditions': set(),
            'extraction_methods': defaultdict(int)
        }

    def process(self) -> Dict[str, any]:
        df = self.load_data()
        self.stats['total_rows'] = len(df)

        all_triples: List[Triple] = []
        all_conditions: Dict[str, str] = {}
        all_supplements: Dict[str, str] = {}

        for _, row in df.iterrows():
            triples = self.extract_from_row(row)

            all_triples.extend(triples)
            for t in triples:
                all_supplements[t.supplement_id] = t.supplement_name
                all_conditions[t.condition_id] = t.condition_name
                self.stats['unique_supplements'].add(t.supplement_id)
                self.stats['unique_conditions'].add(t.condition_id)
                self.stats['extraction_methods'][t.extraction_method] += 1

        self.stats['total_triples'] = len(all_triples)
        write_nodes(all_conditions, all_supplements, self.output_dir)
        write_edges(all_triples, self.output_dir)
        write_stats(self.stats, self.output_dir)

        return self.stats

    def load_data(self) -> pd.DataFrame:
        df = pd.read_csv(self.input_path)

        if 'uses_text' not in df.columns and 'uses' in df.columns:
            df['uses_text'] = df['uses']
            print("'uses_text' column not found, using 'uses' instead")

        df = df.fillna("")
        df['is_valid'] = df.apply(self.validate_row, axis=1)
        invalid = len(df[~df['is_valid']])

        if invalid > 0:
            print(f"Found {invalid} invalid rows (will be skipped)")
            self.stats['invalid_rows'] = invalid

        valid_df = df[df['is_valid']].copy()
        self.stats['valid_rows'] = len(valid_df)

        return valid_df

    def validate_row(self, row) -> bool:
        if not row.get('supplement_name'):
            return False

        uses_text = str(row.get('uses_text', ''))
        if not uses_text:
            return False

        cleaned = self.cleaner.clean_text(uses_text)
        return self.cleaner.is_valid_medical_text(cleaned)

    def extract_from_row(self, row) -> List[Triple]:
        result: List[Triple] = []

        sup_name = str(row.get('supplement_name', '')).strip()
        sup_id = create_id(sup_name)
        url = str(row.get('url', '')).strip()

        raw_uses = str(row.get('uses_text', '')).strip()
        cleaned_text = self.cleaner.clean_text(raw_uses)
        if not cleaned_text:
            return result

        entities = self.extractor.extract_entities(cleaned_text)
        for ent in entities:
            if ent.confidence < 0.5:
                continue

            condition_id = create_id(ent.normalized)
            relation = self.get_relation_type(ent.entity_type)

            result.append(Triple(
                supplement_id=sup_id,
                supplement_name=sup_name,
                relation_type=relation,
                condition_id=condition_id,
                condition_name=ent.normalized,
                confidence=ent.confidence,
                extraction_method=ent.entity_type,
                source_url=url,
                evidence_text=ent.source_context[:500]
            ))

        llm_results = self.llm_triples(sup_name, sup_id, url, cleaned_text)
        result.extend(llm_results)

        return self.dedup(result)

    def llm_triples(self, sup_name: str, sup_id: str, url: str, cleaned: str) -> List[Triple]:
        triples: List[Triple] = []
        items = llm_extract_triples(sup_name, cleaned, url)

        for item in items:
            raw_condition = str(item.get("condition", "")).strip()
            if not raw_condition:
                continue

            relation = create_relation(item.get("relation", ""))

            try:
                confidence = float(item.get("confidence", 0.7))
            except Exception:
                confidence = 0.7

            normalized = self.extractor.normalize_entity(raw_condition)
            condition_id = create_id(normalized)

            context = str(item.get("evidence", "")).strip() or cleaned[:500]

            triples.append(Triple(
                supplement_id=sup_id,
                supplement_name=sup_name,
                relation_type=relation,
                condition_id=condition_id,
                condition_name=normalized,
                confidence=confidence,
                extraction_method="llm",
                source_url=url,
                evidence_text=context[:500]
            ))

        return triples

    def get_relation_type(self, entity_type: str) -> str:
        m = {
            'indicated_for': 'INDICATED_FOR',
            'treats': 'TREATS',
            'prevents': 'PREVENTS',
            'helps_with': 'HELPS_WITH',
            'manages': 'MANAGES',
            'relieves': 'RELIEVES',
            'deficiency': 'TREATS_DEFICIENCY',
            'condition': 'INDICATED_FOR',
            'symptom': 'RELIEVES_SYMPTOM',
            'procedure': 'USED_FOR_PROCEDURE',
            'cleanses': 'CLEANSES',
            'procedure_prep': 'USED_FOR_PROCEDURE'
        }
        return m.get(entity_type, 'RELATED_TO')

    def dedup(self, triples: List[Triple]) -> List[Triple]:
        u = {}
        for t in triples:
            k = (t.supplement_id, t.condition_id, t.relation_type)
            if k not in u or t.confidence > u[k].confidence:
                u[k] = t
        return list(u.values())
