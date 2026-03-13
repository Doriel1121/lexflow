import spacy
import re
import dateparser
from typing import List, Dict, Any, Optional
from datetime import datetime
from app.db.models.deadline import DeadlineType

class NERService:
    def __init__(self):
        try:
            # Load English spaCy model
            self.nlp_en = spacy.load("en_core_web_sm")
        except:
            # Fallback if model not downloaded
            self.nlp_en = None
            print("Warning: en_core_web_sm not found. English NER will be limited.")

        # Keywords for classification
        self.classification_keywords = {
            DeadlineType.HEARING: ["hearing", "court", "trial", "appearance", "דיון", "משפט", "ישיבה", "קדם משפט"],
            DeadlineType.FILING: ["filing", "submit", "file", "submission", "הגשה", "להגיש", "יוגש", "יוגשו"],
            DeadlineType.RESPONSE: ["response", "answer", "reply", "כתב הגנה", "תגובה", "תשובה"],
            DeadlineType.APPEAL: ["appeal", "reconsideration", "ערעור", "בקשת רשות"],
            DeadlineType.STATUTE_OF_LIMITATIONS: ["statute of limitations", "expiration", "prescription", "התיישנות"],
        }

        # Hebrew months for pattern matching
        self.hebrew_months = [
            "ינואר", "פברואר", "מרץ", "אפריל", "מאי", "יוני",
            "יולי", "אוגוסט", "ספטמבר", "אוקטובר", "נובמבר", "דצמבר",
            "במרץ", "בינואר", "בפברואר" # Common prefix
        ]

    def extract_deadlines(self, text: str, language: str = "en") -> List[Dict[str, Any]]:
        """
        Extract deadlines from text with dates and types.
        """
        if language == "he" or self._is_mostly_hebrew(text):
            return self._extract_hebrew_deadlines(text)
        else:
            return self._extract_english_deadlines(text)

    def _is_mostly_hebrew(self, text: str) -> bool:
        hebrew_chars = len(re.findall(r'[\u0590-\u05FF]', text))
        return hebrew_chars > len(text) * 0.2

    def _extract_english_deadlines(self, text: str) -> List[Dict[str, Any]]:
        deadlines = []
        if not self.nlp_en:
            return self._extract_dates_regex(text)

        doc = self.nlp_en(text)
        
        # Look for DATE entities
        for ent in doc.ents:
            if ent.label_ == "DATE":
                # Attempt to parse date
                parsed_date = dateparser.parse(ent.text, settings={'PREFER_DATES_FROM': 'future'})
                if parsed_date:
                    # Get the sentence containing the date for description
                    sentence = ent.sent.text.strip()
                    
                    # Context before and after for classification
                    context_before = text[max(0, ent.start_char - 60):ent.start_char].lower()
                    context_after = text[ent.end_char:min(len(text), ent.end_char + 30)].lower()
                    
                    deadline_type = self._classify_deadline(context_before, context_after)
                    
                    # Clean up description
                    description = sentence
                    if description.strip() == ent.text.strip():
                        # If description is JUST the date, expand it
                        start_idx = max(0, ent.start_char - 60)
                        end_idx = min(len(text), ent.end_char + 40)
                        description = text[start_idx:end_idx].strip()
                    
                    if len(description) > 150:
                        start_idx = max(0, ent.start_char - 70)
                        end_idx = min(len(text), ent.end_char + 50)
                        description = "..." + text[start_idx:end_idx].strip() + "..."

                    deadlines.append({
                        "date": parsed_date,
                        "text": ent.text,
                        "description": description,
                        "type": deadline_type,
                        "confidence": 0.85 if deadline_type != DeadlineType.OTHER else 0.6
                    })
        
        return deadlines

    def _extract_hebrew_deadlines(self, text: str) -> List[Dict[str, Any]]:
        deadlines = []
        # Custom Hebrew NER for dates
        patterns = [
            r'\d{1,2}\s+(?:ב?[' + '|'.join(self.hebrew_months) + r']+)\s+\d{4}', # 15 במרץ 2025
            r'\d{1,2}[./]\d{1,2}[./]\d{2,4}', # 15.3.25
        ]
        
        for pattern in patterns:
            for match in re.finditer(pattern, text):
                date_str = match.group()
                parsed_date = dateparser.parse(date_str, languages=['he'], settings={'PREFER_DATES_FROM': 'future'})
                
                if parsed_date:
                    context_before = text[max(0, match.start() - 80):match.start()]
                    context_after = text[match.end():min(len(text), match.end() + 40)]
                    
                    deadline_type = self._classify_deadline(context_before.lower(), context_after.lower())
                    
                    # Try to find a logical start of the description (newline or period)
                    desc_start = context_before.rfind('\n')
                    if desc_start == -1: desc_start = context_before.rfind('.')
                    if desc_start == -1: desc_start = 0
                    else: desc_start += 1 # Skip the delimiter
                    
                    description = context_before[desc_start:].strip() + " " + date_str + " " + context_after.split('\n')[0].strip()

                    deadlines.append({
                        "date": parsed_date,
                        "text": date_str,
                        "description": description.strip(),
                        "type": deadline_type,
                        "confidence": 0.8 if deadline_type != DeadlineType.OTHER else 0.5
                    })
                    
        return deadlines

    def _extract_dates_regex(self, text: str) -> List[Dict[str, Any]]:
        # Basic regex fallback for English
        deadlines = []
        pattern = r'\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]* \d{1,2},? \d{4}\b|\b\d{1,2}/\d{1,2}/\d{2,4}\b'
        for match in re.finditer(pattern, text, re.IGNORECASE):
            date_str = match.group()
            parsed_date = dateparser.parse(date_str)
            if parsed_date:
                context_before = text[max(0, match.start() - 60):match.start()]
                context_after = text[match.end():min(len(text), match.end() + 30)]
                
                description = context_before.strip() + " " + date_str + " " + context_after.strip()

                deadlines.append({
                    "date": parsed_date,
                    "text": date_str,
                    "description": description.strip(),
                    "type": self._classify_deadline(context_before.lower(), context_after.lower()),
                    "confidence": 0.5
                })
        return deadlines

    def _classify_deadline(self, context_before: str, context_after: str) -> DeadlineType:
        # Prioritize keywords in context_before (closer to the end of context_before is better)
        best_type = DeadlineType.OTHER
        min_score = 999
        
        # Priority weights for types (lower is higher priority)
        type_priority = {
            DeadlineType.STATUTE_OF_LIMITATIONS: 1,
            DeadlineType.APPEAL: 2,
            DeadlineType.HEARING: 3,
            DeadlineType.RESPONSE: 4,
            DeadlineType.FILING: 5,
            DeadlineType.OTHER: 10
        }
        
        for d_type, keywords in self.classification_keywords.items():
            for kw in keywords:
                # Check context_before
                idx = context_before.rfind(kw.lower())
                if idx != -1:
                    dist = len(context_before) - idx
                    # Score is a combination of distance and type priority (multiplier 20)
                    score = dist + (type_priority.get(d_type, 10) * 20)
                    if score < min_score:
                        min_score = score
                        best_type = d_type
                
                # Check context_after with a penalty
                idx = context_after.find(kw.lower())
                if idx != -1:
                    dist = idx + 40 # Penalty for being after the date
                    score = dist + (type_priority.get(d_type, 10) * 20)
                    if score < min_score:
                        min_score = score
                        best_type = d_type
                        
        return best_type

ner_service = NERService()
