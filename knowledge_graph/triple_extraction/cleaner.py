import re

class MedicalTextCleaner:
    JUNK_PATTERNS = [
        r'Sign up for free.*?email preview',
        r'Error Email field is required',
        r'Review/update the\s+information',
        r'Click here for an email',
        r'unsubscribe link in the email',
        r'Notice of Privacy Practices',
        r'This product is available in the following dosage forms',
        r'In deciding to use a medicine.*?should be considered',
        r'Mayo Clinic patient',
        r'©\s*\d{4}.*?Mayo',
    ]
    PRODUCT_PATTERNS = [
        r'^[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\s+\d+',
        r'^[A-Z]{2,}(?:\s+[A-Z]{2,})+$',
        r'^\w+\s+Kit\b', r'^\w+\s+Prep\b',
    ]
    @classmethod
    def clean_text(cls, text: str) -> str:
        if not text or not isinstance(text, str):
            return ""

        cleaned = re.sub(r'<[^>]+>', ' ', text)

        for pattern in cls.JUNK_PATTERNS:
            cleaned = re.sub(pattern, ' ', cleaned, flags=re.I | re.S)

        cleaned = re.sub(r'\s+', ' ', cleaned).strip()
        return cleaned

    @classmethod
    def is_valid_medical_text(cls, text: str) -> bool:
        if not text or len(text) < 40:
            return False

        first_100 = text[:100]
        for pattern in cls.PRODUCT_PATTERNS:
            if re.match(pattern, first_100):
                return False

        keywords = [
            'used to', 'treat', 'prevent', 'manage', 'relief', 'symptoms', 'condition', 'disease',
            'deficiency', 'indicated for', 'therapy', 'patient', 'clinical', 'medicine',
            'laxative', 'cleanse', 'preparation', 'colonoscopy', 'procedure', 'injection', 'supplement'
        ]

        text_lower = text.lower()
        found = sum(1 for kw in keywords if kw in text_lower)
        return found >= 1
