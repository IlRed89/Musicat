"""
Harmonic Mixing Assistant & Camelot Wheel Engine for Musicat.

Implements circle of fifths calculations, Camelot Wheel conversions (1A-12B),
relative major/minor transitions, energy boost shifts (+2 and +7 semitone lifts),
and DJ harmonic compatibility verification.
"""

import re
from typing import Any, Dict, List, Optional, Set, Tuple


# Musical Key to Camelot Mapping (Minor = A, Major = B)
KEY_TO_CAMELOT: Dict[str, str] = {
    # Minor Keys (A)
    "Abm": "1A", "G#m": "1A", "G# min": "1A", "Ab min": "1A",
    "Ebm": "2A", "D#m": "2A", "D# min": "2A", "Eb min": "2A",
    "Bbm": "3A", "A#m": "3A", "A# min": "3A", "Bb min": "3A",
    "Fm": "4A",  "F min": "4A",
    "Cm": "5A",  "C min": "5A",
    "Gm": "6A",  "G min": "6A",
    "Dm": "7A",  "D min": "7A",
    "Am": "8A",  "A min": "8A",
    "Em": "9A",  "E min": "9A",
    "Bm": "10A", "B min": "10A",
    "F#m": "11A", "Gbm": "11A", "F# min": "11A", "Gb min": "11A",
    "C#m": "12A", "Dbm": "12A", "C# min": "12A", "Db min": "12A",

    # Major Keys (B)
    "B": "1B", "B maj": "1B", "Bmaj": "1B", "B major": "1B",
    "F#": "2B", "Gb": "2B", "F# maj": "2B", "Gb maj": "2B", "F#maj": "2B", "Gbmaj": "2B",
    "Db": "3B", "C#": "3B", "Db maj": "3B", "C# maj": "3B", "Dbmaj": "3B", "C#maj": "3B",
    "Ab": "4B", "G#": "4B", "Ab maj": "4B", "G# maj": "4B", "Abmaj": "4B", "G#maj": "4B",
    "Eb": "5B", "D#": "5B", "Eb maj": "5B", "D# maj": "5B", "Ebmaj": "5B", "D#maj": "5B",
    "Bb": "6B", "A#": "6B", "Bb maj": "6B", "A# maj": "6B", "Bbmaj": "6B", "A#maj": "6B",
    "F": "7B",  "F maj": "7B",  "Fmaj": "7B",  "F major": "7B",
    "C": "8B",  "C maj": "8B",  "Cmaj": "8B",  "C major": "8B",
    "G": "9B",  "G maj": "9B",  "Gmaj": "9B",  "G major": "9B",
    "D": "10B", "D maj": "10B", "Dmaj": "10B", "D major": "10B",
    "A": "11B", "A maj": "11B", "Amaj": "11B", "A major": "11B",
    "E": "12B", "E maj": "12B", "Emaj": "12B", "E major": "12B",
}

# Camelot Code to Primary Musical Key Name
CAMELOT_TO_KEY: Dict[str, str] = {
    "1A": "G#m", "1B": "B",
    "2A": "D#m", "2B": "F#",
    "3A": "A#m", "3B": "Db",
    "4A": "Fm",  "4B": "Ab",
    "5A": "Cm",  "5B": "Eb",
    "6A": "Gm",  "6B": "Bb",
    "7A": "Dm",  "7B": "F",
    "8A": "Am",  "8B": "C",
    "9A": "Em",  "9B": "G",
    "10A": "Bm", "10B": "D",
    "11A": "F#m", "11B": "A",
    "12A": "C#m", "12B": "E",
}

# Ordered list of all 24 Camelot codes
CAMELOT_KEYS_ORDERED: List[str] = [
    "1A", "1B", "2A", "2B", "3A", "3B", "4A", "4B",
    "5A", "5B", "6A", "6B", "7A", "7B", "8A", "8B",
    "9A", "9B", "10A", "10B", "11A", "11B", "12A", "12B",
]


class CamelotWheel:
    """Provides Camelot Wheel math, harmonic compatibility and BPM calculations for DJs."""

    @staticmethod
    def get_musical_name(camelot_key: str) -> str:
        """Returns primary musical key name for a Camelot key (e.g. '8A' -> 'Am', '8B' -> 'C')."""
        norm = CamelotWheel.normalize_key(camelot_key)
        return CAMELOT_TO_KEY.get(norm, "")

    @staticmethod
    def normalize_key(key_str: Optional[str]) -> str:
        """Normalizes any musical or Camelot key string into canonical Camelot format (e.g. '8A').

        Args:
            key_str (Optional[str]): Input key string (e.g. '8A', '8a', 'Am', 'A minor', 'C Major').

        Returns:
            str: Canonical Camelot key (e.g. '8A') or empty string if invalid.
        """
        if not key_str:
            return ""

        clean = key_str.strip()

        # Check if already Camelot format: e.g. "8A", "12B", "08A"
        match = re.match(r"^0?([1-9]|1[0-2])\s*([a-bA-B])$", clean)
        if match:
            num = int(match.group(1))
            letter = match.group(2).upper()
            return f"{num}{letter}"

        # Standardize musical key naming
        # Strip trailing 'm', 'min', 'minor', 'maj', 'major'
        musical_clean = clean.replace("minor", "min").replace("major", "maj")
        return KEY_TO_CAMELOT.get(musical_clean, KEY_TO_CAMELOT.get(clean, ""))

    @staticmethod
    def parse_camelot(camelot_key: str) -> Optional[Tuple[int, str]]:
        """Parses a Camelot string into number (1-12) and letter ('A' or 'B').

        Args:
            camelot_key (str): Camelot key string (e.g. '8A', '11B').

        Returns:
            Optional[Tuple[int, str]]: (number, letter) or None if invalid.
        """
        norm = CamelotWheel.normalize_key(camelot_key)
        if not norm:
            return None
        return int(norm[:-1]), norm[-1]

    @staticmethod
    def get_relative_key(camelot_key: str) -> str:
        """Gets relative Major/Minor key on the same number (e.g. '8A' <-> '8B').

        Args:
            camelot_key (str): Canonical Camelot key.

        Returns:
            str: Opposite letter key on the same number.
        """
        parsed = CamelotWheel.parse_camelot(camelot_key)
        if not parsed:
            return ""
        num, letter = parsed
        opp = "B" if letter == "A" else "A"
        return f"{num}{opp}"

    @staticmethod
    def get_adjacent_keys(camelot_key: str) -> Tuple[str, str]:
        """Gets adjacent keys on the wheel (-1 hour counter-clockwise, +1 hour clockwise).

        Args:
            camelot_key (str): Canonical Camelot key.

        Returns:
            Tuple[str, str]: (minus_one_key, plus_one_key) e.g. for '8A' -> ('7A', '9A').
        """
        parsed = CamelotWheel.parse_camelot(camelot_key)
        if not parsed:
            return ("", "")
        num, letter = parsed

        # 1-12 wrap around
        prev_num = 12 if num == 1 else num - 1
        next_num = 1 if num == 12 else num + 1

        return f"{prev_num}{letter}", f"{next_num}{letter}"

    @staticmethod
    def get_energy_boost_keys(camelot_key: str) -> Dict[str, str]:
        """Calculates energy boosting transition keys for high-energy DJ mixes.

        Transitions:
        - Whole Step Boost (+2 on wheel): Increases energy by two fifths (e.g. 8A -> 10A).
        - Semitone Energy Lift (+7 on wheel): Chromatic +1 semitone modulation, classic festival lift.

        Args:
            camelot_key (str): Canonical Camelot key.

        Returns:
            Dict[str, str]: Mapping with keys 'plus_two_boost' and 'semitone_lift'.
        """
        parsed = CamelotWheel.parse_camelot(camelot_key)
        if not parsed:
            return {}
        num, letter = parsed

        # +2 boost
        plus_two_num = (num + 1) % 12 + 1
        # +7 semitone boost (+1 semitone = +7 hours on Circle of Fifths)
        semitone_num = (num + 6) % 12 + 1

        return {
            "plus_two_boost": f"{plus_two_num}{letter}",
            "semitone_lift": f"{semitone_num}{letter}",
        }

    @classmethod
    def get_harmonic_matches(
        cls,
        current_key: str,
        include_exact: bool = True,
        include_adjacent: bool = True,
        include_relative: bool = True,
        include_energy_boost: bool = True,
        include_semitone: bool = False,
    ) -> List[str]:
        """Calculates all harmonically compatible Camelot keys for a given track.

        Args:
            current_key (str): Starting Camelot or musical key (e.g. '8A' or 'Am').
            include_exact (bool): Include same key (e.g. 8A). Default True.
            include_adjacent (bool): Include +1 and -1 (e.g. 7A, 9A). Default True.
            include_relative (bool): Include relative major/minor (e.g. 8B). Default True.
            include_energy_boost (bool): Include +2 energy boost (e.g. 10A). Default True.
            include_semitone (bool): Include +7 semitone lift (e.g. 3A). Default False.

        Returns:
            List[str]: List of compatible Camelot key codes in logical mixing order.
        """
        norm = cls.normalize_key(current_key)
        if not norm:
            return []

        matches: List[str] = []

        if include_exact:
            matches.append(norm)

        if include_adjacent:
            prev_k, next_k = cls.get_adjacent_keys(norm)
            if prev_k and prev_k not in matches:
                matches.append(prev_k)
            if next_k and next_k not in matches:
                matches.append(next_k)

        if include_relative:
            rel_k = cls.get_relative_key(norm)
            if rel_k and rel_k not in matches:
                matches.append(rel_k)

        boosts = cls.get_energy_boost_keys(norm)
        if include_energy_boost and "plus_two_boost" in boosts:
            b_k = boosts["plus_two_boost"]
            if b_k and b_k not in matches:
                matches.append(b_k)

        if include_semitone and "semitone_lift" in boosts:
            s_k = boosts["semitone_lift"]
            if s_k and s_k not in matches:
                matches.append(s_k)

        return matches

    @classmethod
    def get_relationship_description(cls, source_key: str, target_key: str) -> str:
        """Describes the harmonic relationship between two keys for live DJ display.

        Args:
            source_key (str): Playing track's key.
            target_key (str): Candidate track's key.

        Returns:
            str: Human readable relationship description (e.g. 'Exact Match', 'Clockwise +1', etc.).
        """
        src = cls.normalize_key(source_key)
        tgt = cls.normalize_key(target_key)
        if not src or not tgt:
            return "Unknown"

        if src == tgt:
            return "Exact Match (Same Key)"

        rel = cls.get_relative_key(src)
        if tgt == rel:
            return "Relative Scale (Major ⇄ Minor Mood Shift)"

        prev_k, next_k = cls.get_adjacent_keys(src)
        if tgt == next_k:
            return "Clockwise (+1 Step / Energy Rise)"
        if tgt == prev_k:
            return "Counter-Clockwise (-1 Step / Energy Drop)"

        boosts = cls.get_energy_boost_keys(src)
        if tgt == boosts.get("plus_two_boost"):
            return "Energy Boost (+2 Steps / Whole Tone)"
        if tgt == boosts.get("semitone_lift"):
            return "Peak Energy Lift (+1 Semitone)"

        return "Harmonically Clash / Key Change"

    @staticmethod
    def calculate_bpm_tolerance_range(target_bpm: float, tolerance_pct: float) -> Tuple[float, float]:
        """Calculates minimum and maximum BPM boundaries for a given target BPM and tolerance %.

        Args:
            target_bpm (float): Baseline tempo in BPM (e.g. 126.0).
            tolerance_pct (float): Pitch tolerance percentage (e.g. 2.0 or 4.0).

        Returns:
            Tuple[float, float]: (min_bpm, max_bpm) rounded to 1 decimal place.
        """
        if target_bpm <= 0:
            return (0.0, 250.0)

        factor = max(0.0, tolerance_pct) / 100.0
        min_bpm = round(target_bpm * (1.0 - factor), 1)
        max_bpm = round(target_bpm * (1.0 + factor), 1)
        return (min_bpm, max_bpm)

    @staticmethod
    def calculate_pitch_pct(original_bpm: float, current_bpm: float) -> float:
        """Calculates DJ pitch slider percentage needed to match tempos.

        Args:
            original_bpm (float): Original track native tempo.
            current_bpm (float): Master/Target deck tempo.

        Returns:
            float: Pitch deviation percentage (e.g. +3.2%).
        """
        if original_bpm <= 0:
            return 0.0
        return round(((current_bpm - original_bpm) / original_bpm) * 100.0, 2)
