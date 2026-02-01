import json
import os
from typing import List, Set

class FieldHistory:
    """Manages history of field values (company names, document titles, etc.)"""

    def __init__(self, history_file: str = "field_history.json"):
        self.history_file = history_file
        self.history = {
            "companies": [],
            "titles": []
        }
        self._load_history()

    def _load_history(self):
        """Load history from JSON file"""
        if os.path.exists(self.history_file):
            try:
                with open(self.history_file, 'r', encoding='utf-8') as f:
                    self.history = json.load(f)
                # Ensure keys exist
                if "companies" not in self.history:
                    self.history["companies"] = []
                if "titles" not in self.history:
                    self.history["titles"] = []
            except Exception as e:
                print(f"Error loading field history: {e}")
                self.history = {"companies": [], "titles": []}

    def _save_history(self):
        """Save history to JSON file"""
        try:
            with open(self.history_file, 'w', encoding='utf-8') as f:
                json.dump(self.history, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Error saving field history: {e}")

    def add_company(self, company: str):
        """Add a company to history (if not already present)"""
        if company and company.strip():
            company = company.strip()
            if company not in self.history["companies"]:
                self.history["companies"].append(company)
                self.history["companies"].sort()  # Keep sorted alphabetically
                self._save_history()

    def add_title(self, title: str):
        """Add a title to history (if not already present)"""
        if title and title.strip():
            title = title.strip()
            if title not in self.history["titles"]:
                self.history["titles"].append(title)
                self.history["titles"].sort()  # Keep sorted alphabetically
                self._save_history()

    def get_companies(self) -> List[str]:
        """Get list of all company names"""
        return self.history.get("companies", [])

    def get_titles(self) -> List[str]:
        """Get list of all document titles"""
        return self.history.get("titles", [])

    def clear_companies(self):
        """Clear all company history"""
        self.history["companies"] = []
        self._save_history()

    def clear_titles(self):
        """Clear all title history"""
        self.history["titles"] = []
        self._save_history()
