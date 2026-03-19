import json
import locale
from pathlib import Path


class I18N:
    def __init__(self, base_dir=None, lang=None):
        self.base_dir = Path(base_dir or Path(__file__).resolve().parent)
        self.lang_dir = self.base_dir / "lang"
        self.lang = self.normalize_lang(lang or self.detect_language())
        self.catalog = self._load_catalog(self.lang)

    def normalize_lang(self, lang):
        return (lang or "en").split("-")[0].split("_")[0].lower()

    def detect_language(self):
        lang, _ = locale.getdefaultlocale()
        return lang or "en"

    def available_languages(self):
        return sorted(p.stem for p in self.lang_dir.glob("*.json"))

    def _load_catalog(self, lang):
        path = self.lang_dir / f"{lang}.json"
        if not path.exists():
            path = self.lang_dir / "en.json"
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def set_language(self, lang):
        self.lang = self.normalize_lang(lang)
        self.catalog = self._load_catalog(self.lang)

    def t(self, key, **kwargs):
        text = self.catalog.get(key, key)
        if kwargs:
            return text.format(**kwargs)
        return text
