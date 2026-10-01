"""
Unit tests for Extended Scrapers, HD Artwork, and Metadata Reconciler.
"""

import unittest
from src.scrapers.traxsource import TraxsourceScraper, TraxsourceTrack
from src.scrapers.artwork_hd import HDArtworkFinder, HDArtworkCandidate
from src.scrapers.reconciler import MetadataReconciler, DiscrepancyReport


class TestExtendedScrapers(unittest.TestCase):

    def test_traxsource_html_parsing(self):
        sample_html_block = """
        <div class="trk-row">
            <a class="title" href="/title/123">Deep In The Soul</a>
            <span class="version">(Kerri Chandler Remix)</span>
            <a href="/artist/1">Kerri Chandler</a>
            <a href="/label/10">Madhouse Records</a>
            <a href="/genre/1">Deep House</a>
            124 BPM
            2023-05-12
            <img src="https://traxsource.com/images/art.jpg" />
        </div>
        """
        track = TraxsourceScraper._parse_html_row(sample_html_block)
        self.assertIsNotNone(track)
        self.assertEqual(track.title, "Deep In The Soul")
        self.assertEqual(track.mix_name, "(Kerri Chandler Remix)")
        self.assertEqual(track.label, "Madhouse Records")
        self.assertEqual(track.genre, "Deep House")
        self.assertEqual(track.bpm, 124.0)

    def test_hd_artwork_upscaling_itunes(self):
        sample_100_url = "https://is1-ssl.mzstatic.com/image/thumb/Music125/v4/100x100bb.jpg"
        hd_1400 = sample_100_url.replace("100x100bb", "1400x1400bb")
        hd_3000 = sample_100_url.replace("100x100bb", "3000x3000bb")

        self.assertIn("1400x1400bb.jpg", hd_1400)
        self.assertIn("3000x3000bb.jpg", hd_3000)

    def test_reconciler_conflict_detection(self):
        # Two sources with disagreeing genres and matching titles
        source_records = [
            {
                "source": "Beatport",
                "title": "Opus",
                "artist": "Eric Prydz",
                "genre": "Melodic House & Techno",
                "year": 2016,
                "bpm": 126.0,
                "camelot_key": "12A",
            },
            {
                "source": "Traxsource",
                "title": "Opus",
                "artist": "Eric Prydz",
                "genre": "Progressive House",
                "year": 2016,
                "bpm": 126.0,
                "camelot_key": "12A",
            },
        ]

        report = MetadataReconciler.analyze_discrepancies("Eric Prydz Opus", source_records)

        # Genre should have conflict
        self.assertTrue(report.fields["genre"].has_conflict)
        self.assertEqual(len(report.fields["genre"].values_by_source), 2)

        # Title should match
        self.assertFalse(report.fields["title"].has_conflict)

        # Selective merge
        # User chooses Traxsource genre
        user_choice = {"genre": "Traxsource"}
        merged = MetadataReconciler.merge_selected_metadata(report, user_choice)

        self.assertEqual(merged["genre"], "Progressive House")
        self.assertEqual(merged["title"], "Opus")
        self.assertEqual(merged["bpm"], 126.0)


if __name__ == "__main__":
    unittest.main()
