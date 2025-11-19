import re
from typing import List
from data_structures import MedicalEntity

class MedicalEntityExtractor:
    CONDITION_PATTERNS = [
        (r'\bindicated\s+for\s+(?:the\s+)?(?:treatment\s+of\s+)?([^.;,]+?)(?:\.|;|,|\s+in\s+patients)', 'indicated_for', 0.9),
        (r'\bused\s+to\s+treat\s+([^.;,]+?)(?:\.|;|,|\s+in\s+patients)', 'treats', 0.9),
        (r'\bfor\s+(?:the\s+)?treatment\s+of\s+([^.;,]+?)(?:\.|;|,|\s+in\s+patients)', 'treats', 0.85),
        (r'\bused\s+to\s+prevent\s+([^.;,]+?)(?:\.|;|,|\s+in\s+patients)', 'prevents', 0.85),
        (r'\bfor\s+(?:the\s+)?prevention\s+of\s+([^.;,]+?)(?:\.|;|,|\s+in\s+patients)', 'prevents', 0.85),
        (r'\bhelps\s+with\s+([^.;,]+?)(?:\.|;|,)', 'helps_with', 0.7),
        (r'\bmanagement\s+of\s+([^.;,]+?)(?:\.|;|,|\s+in\s+patients)', 'manages', 0.8),
        (r'\brelief\s+of\s+([^.;,]+?)(?:\.|;|,)', 'relieves', 0.75),
        (r'\bused\s+to\s+cleanse\s+the\s+([^.;,]+?)(?:\.|;|,)', 'cleanses', 0.85),
        (r'\bcleanse\s+the\s+([^.;,]+?)\s+(?:before|in\s+preparation)', 'cleanses', 0.85),
        (r'\b(?:before|preparation\s+for)\s+(?:a\s+)?([^.;,]+?)(?:\.|;|,)', 'procedure_prep', 0.8),
        (r'\bused\s+to\s+cleanse\s+[^.]*?(?:before|for)\s+(?:a\s+)?(\w+oscopy)', 'procedure_prep', 0.9),
        (r'preparation\s+for\s+(?:a\s+)?(?:procedure\s+called\s+)?(\w+oscopy)', 'procedure_prep', 0.9),
        (r'(\w+\s+deficiency)', 'deficiency', 0.95),
        (r'\btreat\s+(\w+\s+deficiency)', 'deficiency', 0.95),
        (r'\b(diabetes|hypertension|arthritis|osteoporosis|anemia|depression|anxiety)\b', 'condition', 0.9),
        (r'\b(cancer|tumor|carcinoma|lymphoma|leukemia)\b', 'condition', 0.9),
        (r'\b(infection|inflammation|allergy|asthma|bronchitis)\b', 'condition', 0.85),
        (r'\b(alzheimer|parkinson|dementia|epilepsy|migraine)\b', 'condition', 0.9),
        (r'\b(heart\s+disease|cardiovascular\s+disease|stroke|heart\s+failure)\b', 'condition', 0.9),
        (r'\b(narcolepsy|cataplexy|hypersomnia|sleepiness)\b', 'condition', 0.9),
        (r'\b(scurvy|rickets|beriberi|pellagra)\b', 'condition', 0.9),
        (r'\b(pain|fever|nausea|vomiting|diarrhea|constipation)\b', 'symptom', 0.7),
        (r'\b(fatigue|weakness|dizziness|headache|insomnia)\b', 'symptom', 0.7),
        (r'\b(sleepiness|drowsiness|muscle\s+weakness)\b', 'symptom', 0.7),
        (r'(\w+oscopy)\b', 'procedure', 0.85),
        (r'(?:before|prior\s+to)\s+(\w+\s+surgery)\b', 'procedure', 0.8),
    ]
    NEGATIVE_PATTERNS = [
        r'\bnot\s+(?:used|indicated|recommended)\b', r'\bshould\s+not\s+be\s+used\b',
        r'\bineffective\b', r'\bno\s+evidence\b', r'\binsufficient\s+evidence\b',
        r'\bdoes\s+not\s+(?:treat|prevent|help)\b', r'\bcontraindicated\b',
    ]
    NORMALIZATION_MAP = {
        'type 2 diabetes': 'Type 2 Diabetes',
        'type 1 diabetes': 'Type 1 Diabetes',
        'diabetes mellitus': 'Diabetes Mellitus',
        'high blood pressure': 'Hypertension',
        'low blood pressure': 'Hypotension',
        'heart attack': 'Myocardial Infarction',
        'stroke': 'Cerebrovascular Accident',
        'vitamin d deficiency': 'Vitamin D Deficiency',
        'iron deficiency': 'Iron Deficiency Anemia',
        'b12 deficiency': 'Vitamin B12 Deficiency',
        'vitamin c deficiency': 'Vitamin C Deficiency',
        'colonoscopy prep': 'Colonoscopy Preparation',
        'colonoscopy preparation': 'Colonoscopy Preparation',
        'colon': 'Colon Cleansing',
        'colon (bowel)': 'Colon Cleansing',
        'bowel': 'Bowel Preparation',
        'excessive daytime sleepiness': 'Excessive Daytime Sleepiness',
        'eds': 'Excessive Daytime Sleepiness (EDS)',
        'weak or paralyzed muscles': 'Muscle Weakness',
        'cataplexy (weak or paralyzed muscles)': 'Cataplexy',
    }

    @classmethod
    def extract_entities(cls, text: str) -> List[MedicalEntity]:
        entities: List[MedicalEntity] = []
        text_lower = text.lower()

        contains_negative = any(re.search(p, text_lower) for p in cls.NEGATIVE_PATTERNS)

        for pattern, r_type, conf in cls.CONDITION_PATTERNS:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                span = match.group(1) if match.groups() else match.group(0)

                cleaned = cls.clean_entity(span)
                if not cleaned or len(cleaned) < 3:
                    continue

                confidence = conf

                # If negative, check the surrounding words
                if contains_negative:
                    start, end = match.span()
                    context_window = text[max(0, start - 50): min(len(text), end + 50)]
                    if any(re.search(p, context_window.lower()) for p in cls.NEGATIVE_PATTERNS):
                        confidence *= 0.3

                normalized = cls.normalize_entity(cleaned)

                # Get the surrounding words to return for context
                ctx_start = max(0, match.start() - 100)
                ctx_end = min(len(text), match.end() + 100)
                context = text[ctx_start:ctx_end]

                entities.append(MedicalEntity(cleaned, normalized, r_type, confidence, context))

        return cls.deduplicate_entities(entities)

    @classmethod
    def clean_entity(cls, t: str) -> str:
        t = re.sub(r'\s+(in\s+patients|who\s+have|that\s+is|which\s+is).*$', '', t, flags=re.I)
        t = re.sub(r'\s+(caused\s+by|due\s+to|associated\s+with).*$', '', t, flags=re.I)

        t = re.sub(r'^(the|a|an)\s+', '', t, flags=re.I)

        cleaned = re.sub(r'\s+', ' ', t).strip()
        return cleaned

    # Normalize entity names, needs to be improved later
    @classmethod
    def normalize_entity(cls, t: str) -> str:
        key = t.lower()

        if key in cls.NORMALIZATION_MAP:
            return cls.NORMALIZATION_MAP[key]

        parts = []
        for word in t.split():
            if word.isupper() and len(word) <= 4:
                parts.append(word)
            else:
                parts.append(word.capitalize())

        return ' '.join(parts)

    @classmethod
    def deduplicate_entities(cls, ents: List[MedicalEntity]) -> List[MedicalEntity]:
        unique = {}
        for ent in ents:
            key = ent.normalized.lower()
            if key not in unique or ent.confidence > unique[key].confidence:
                unique[key] = ent

        return list(unique.values())
