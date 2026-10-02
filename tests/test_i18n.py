"""
Unit tests for Musicat Bilingual Localization Engine (i18n).

Verifies:
- Default language behavior (Italian default, English secondary)
- System language auto-detection with fallback
- Translation lookup with parameters, embedded fallbacks, and missing key resilience
- Signal emission on language change
- Parity between Italian and English translation key sets
"""

import os
import unittest
from unittest.mock import patch

from src.core.i18n import I18n, _t, tr, detect_system_language


class TestI18nEngine(unittest.TestCase):
    """Test suite for I18n class and translation helper functions."""

    def setUp(self) -> None:
        self.i18n = I18n.get_instance(default_lang="it")
        self.i18n.set_language("it")

    def tearDown(self) -> None:
        self.i18n.set_language("it")

    def test_singleton_instance(self) -> None:
        """Verifies that I18n.get_instance() returns a singleton instance."""
        inst1 = I18n.get_instance()
        inst2 = I18n.get_instance()
        self.assertIs(inst1, inst2)

    def test_default_language(self) -> None:
        """Verifies default language is Italian ('it')."""
        self.assertEqual(self.i18n.language, "it")

    def test_translation_italian(self) -> None:
        """Verifies correct Italian translation lookups."""
        self.i18n.set_language("it")
        self.assertEqual(_t("app_name"), "Musicat")
        self.assertIn("Libreria", _t("nav_library"))
        self.assertIn("Classifiche", _t("nav_trends"))
        self.assertEqual(_t("col_title"), "Titolo")
        self.assertEqual(_t("col_artist"), "Artista")
        self.assertEqual(_t("col_bpm"), "BPM")

    def test_translation_english(self) -> None:
        """Verifies correct English translation lookups."""
        self.i18n.set_language("en")
        self.assertEqual(_t("app_name"), "Musicat")
        self.assertIn("Library", _t("nav_library"))
        self.assertIn("Charts", _t("nav_trends"))
        self.assertEqual(_t("col_title"), "Title")
        self.assertEqual(_t("col_artist"), "Artist")
        self.assertEqual(_t("col_bpm"), "BPM")

    def test_translation_parameter_formatting(self) -> None:
        """Verifies string interpolation with named parameters."""
        self.i18n.set_language("it")
        formatted_it = _t("library_status", count=100, hours=5, mins=30, db="musicat.db")
        self.assertIn("100 tracce", formatted_it)
        self.assertIn("5h 30m", formatted_it)
        self.assertIn("musicat.db", formatted_it)

        self.i18n.set_language("en")
        formatted_en = _t("library_status", count=100, hours=5, mins=30, db="musicat.db")
        self.assertIn("100 tracks", formatted_en)
        self.assertIn("5h 30m", formatted_en)
        self.assertIn("musicat.db", formatted_en)

    def test_missing_key_fallback(self) -> None:
        """Verifies fallback to provided default or key name when translation is missing."""
        val = _t("non_existing_key_xyz", "Default Custom Fallback")
        self.assertEqual(val, "Default Custom Fallback")

        val2 = _t("another_missing_key_123")
        self.assertEqual(val2, "another_missing_key_123")

    def test_language_switch_signal(self) -> None:
        """Verifies language_changed signal is emitted on language switch."""
        emitted_langs = []
        self.i18n.language_changed.connect(lambda lang: emitted_langs.append(lang))

        self.i18n.set_language("en")
        self.assertEqual(emitted_langs, ["en"])

        self.i18n.set_language("it")
        self.assertEqual(emitted_langs, ["en", "it"])

    def test_invalid_language_fallback(self) -> None:
        """Verifies setting an unsupported language defaults to Italian."""
        self.i18n.set_language("fr_FR")
        self.assertEqual(self.i18n.language, "it")

    def test_detect_system_language(self) -> None:
        """Verifies system locale parsing detects it or en."""
        with patch("src.core.i18n.QLocale.system") as mock_ql:
            mock_loc = unittest.mock.MagicMock()
            mock_loc.name.return_value = "it_IT"
            mock_ql.return_value = mock_loc
            self.assertEqual(detect_system_language(), "it")

        with patch("src.core.i18n.QLocale.system") as mock_ql:
            mock_loc = unittest.mock.MagicMock()
            mock_loc.name.return_value = "en_US"
            mock_ql.return_value = mock_loc
            self.assertEqual(detect_system_language(), "en")

        with patch("src.core.i18n.QLocale.system") as mock_ql:
            mock_loc = unittest.mock.MagicMock()
            mock_loc.name.return_value = "de_DE"
            mock_ql.return_value = mock_loc
            # Non-English / non-Italian should fallback to default "it"
            self.assertEqual(detect_system_language(), "it")

    def test_translation_key_parity(self) -> None:
        """Ensures Italian and English dictionaries contain the exact same set of translation keys."""
        it_keys = set(self.i18n._translations.get("it", {}).keys())
        en_keys = set(self.i18n._translations.get("en", {}).keys())

        missing_in_en = it_keys - en_keys
        missing_in_it = en_keys - it_keys

        self.assertEqual(
            missing_in_en,
            set(),
            f"Keys present in Italian but missing in English: {missing_in_en}",
        )
        self.assertEqual(
            missing_in_it,
            set(),
            f"Keys present in English but missing in Italian: {missing_in_it}",
        )


if __name__ == "__main__":
    unittest.main()
