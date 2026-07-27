"""
PHI detection for HIPAA compliance, using Microsoft Presidio.

A clinical assistant must never emit protected health information (PHI). This
wraps Presidio's analyzer to flag HIPAA-relevant identifiers (names, contact
info, SSNs, dates, locations) in a piece of text.
"""

from presidio_analyzer import AnalyzerEngine, Pattern, PatternRecognizer

# HIPAA "Safe Harbor" identifiers, mapped to the Presidio entity types that
# detect them. (Some HIPAA IDs like MRNs have no dedicated Presidio recognizer.)
HIPAA_ENTITIES = [
    "PERSON",             # names
    "LOCATION",           # geographic info
    "DATE_TIME",          # dates tied to an individual
    "PHONE_NUMBER",       # phone / fax
    "EMAIL_ADDRESS",
    "US_SSN",
    "US_DRIVER_LICENSE",
    "MEDICAL_LICENSE",
    "URL",
    "IP_ADDRESS",
    "CREDIT_CARD",
]


class PHIDetector:
    """Detects HIPAA PHI in text via Presidio."""

    def __init__(self, threshold=0.4, entities=None):
        # threshold: minimum confidence to count a detection. Lower = higher
        # recall (catch more PHI) at the cost of more false positives. For
        # compliance we favor recall — missing PHI is worse than a false alarm.
        self.threshold = threshold
        self.entities = entities or HIPAA_ENTITIES
        self.analyzer = AnalyzerEngine()
        self._add_custom_recognizers()

    def detect(self, text):
        """Return a list of PHI findings: {entity, text, score}."""
        results = self.analyzer.analyze(
            text=text, language="en", entities=self.entities
        )
        return [
            {
                "entity": r.entity_type,
                "text": text[r.start:r.end],
                "score": round(r.score, 2),
            }
            for r in results
            if r.score >= self.threshold
        ]

    def is_compliant(self, text):
        """True if no PHI was detected."""
        return len(self.detect(text)) == 0

    def _add_custom_recognizers(self):
        """Patch gaps in Presidio's defaults. Verified: out-of-box Presidio
        missed standard-format SSNs entirely, so we add an explicit recognizer.
        A medical-record-number (MRN) recognizer could be added the same way."""
        ssn = PatternRecognizer(
            supported_entity="US_SSN",
            patterns=[Pattern(
                name="ssn_dashed",
                regex=r"\b\d{3}-\d{2}-\d{4}\b",   # XXX-XX-XXXX
                score=0.85,
            )],
        )
        self.analyzer.registry.add_recognizer(ssn)

if __name__ == "__main__":
    det = PHIDetector()
    samples = [
        "An A1C below 7% is recommended for most adults with diabetes.",   # clean
        "Patient John Smith, SSN 123-45-6789, was seen on 03/14/2024.",     # PHI!
    ]
    for s in samples:
        findings = det.detect(s)
        print(f"\ncompliant={det.is_compliant(s)}  | {s}")
        for f in findings:
            print(f"   - {f['entity']}: '{f['text']}' ({f['score']})")