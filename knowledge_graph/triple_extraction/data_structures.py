from dataclasses import dataclass, asdict

@dataclass
class MedicalEntity:
    raw_text: str
    normalized: str
    entity_type: str
    confidence: float
    source_context: str
    def to_dict(self): return asdict(self)

@dataclass
class Triple:
    supplement_id: str
    supplement_name: str
    relation_type: str
    condition_id: str
    condition_name: str
    confidence: float
    extraction_method: str
    source_url: str
    evidence_text: str
    def to_dict(self): return asdict(self)
