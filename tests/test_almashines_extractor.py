from unittest import TestCase
from unittest.mock import patch

from almashines_extractor import AlmaShinesExtractor


class MemberExportTests(TestCase):
    @patch("almashines_extractor.time.sleep")
    def test_failing_later_page_does_not_accept_partial_roster(self, _sleep):
        extractor = AlmaShinesExtractor("test-key", "test-secret")
        first_page = {"success": 1, "data": [{"unique_profile_id": str(i)} for i in range(200)]}
        with patch.object(extractor, "_make_request", side_effect=[first_page, {"success": 0}]):
            with self.assertRaisesRegex(ValueError, "page 2"):
                extractor.extract_all_users()
        self.assertNotIn("users", extractor.all_data)

    @patch("almashines_extractor.time.sleep")
    def test_duplicate_id_across_pages_rejects_export(self, _sleep):
        extractor = AlmaShinesExtractor("test-key", "test-secret")
        first_page = {"success": 1, "data": [{"unique_profile_id": str(i)} for i in range(200)]}
        duplicate = {"success": 1, "data": [{"unique_profile_id": "0"}]}
        with patch.object(extractor, "_make_request", side_effect=[first_page, duplicate]):
            with self.assertRaisesRegex(ValueError, "duplicate profile ID"):
                extractor.extract_all_users()
        self.assertNotIn("users", extractor.all_data)
