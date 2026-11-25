import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import PropertyMock, patch

from ai_agent import AIAgent, CommunityInfo, DataStore, ModelUnavailable


class ChatRoutingTests(unittest.TestCase):
    def setUp(self):
        sandbox = tempfile.TemporaryDirectory()
        self.addCleanup(sandbox.cleanup)
        source = Path(sandbox.name) / "directory.json"
        source.write_text(json.dumps({
            "users": [{
                "name": "Test Directory Member",
                "work_experiences": [{"designation": "Software Engineer"}],
            }],
            "jobs": [{
                "designation": "Robotics Instructor",
                "company": "Example Studio",
                "location": None,
                "locations": [{"name": "Pune"}],
                "job_type": "Full Time",
                "description": "Teach robotics<br><strong>Apply today</strong><script>ignore this</script>",
            }],
        }))
        self.agent = AIAgent.__new__(AIAgent)
        self.agent.data_store = DataStore(source)
        self.agent.hosted = False

    def test_leadership_and_app_help_go_to_community_answers(self):
        for wording in ("Who is the owner of GMG", "who is the leader of GMG"):
            with self.subTest(wording=wording):
                answer = self.agent.handle_query(wording)
                self.assertIn("**Anand Ganu**", answer)
                self.assertIn("president and founder", answer)
                self.assertIn("https://www.garjemarathi.com/about", answer)
        help_message = self.agent.handle_query("what can I do here")
        for feature in ("Find people", "Explore opportunities", "Ask GMG"):
            self.assertIn(feature, help_message)

    def test_searches_by_role_and_name_use_the_directory(self):
        self.assertIn(
            "Test Directory Member",
            self.agent.handle_query("who is a software engineer in GMG"),
        )
        self.assertIn(
            "Test Directory Member",
            self.agent.handle_query("Find members Test Directory Member"),
        )

    def test_opportunity_description_has_clean_markdown_and_the_stored_location(self):
        answer = self.agent.handle_query("Show jobs in Pune")
        self.assertIn("### Robotics Instructor at Example Studio", answer)
        self.assertIn("- **Location** Pune", answer)
        self.assertIn("Teach robotics Apply today", answer)
        for unwanted in ("None", "<br>", "<strong>", "ignore this"):
            self.assertNotIn(unwanted, answer)

    def test_hosted_chat_keeps_directory_records_in_the_app(self):
        self.agent.hosted = True
        context = self.agent._format_users(self.agent.data_store.search_users("Test Directory Member"))
        with patch.object(self.agent, "_call_llm") as inference:
            self.assertEqual(self.agent._answer_with_context("Find a member", context), context)
        inference.assert_not_called()

    def test_gmg_question_still_offers_official_sources_when_model_fails(self):
        with patch.object(AIAgent, "_answer_with_context", side_effect=ModelUnavailable), \
             patch.object(AIAgent, "community_info", new_callable=PropertyMock,
                          return_value=CommunityInfo("Garje Marathi Global", "GMG")):
            answer = self.agent.handle_query("Where can I volunteer to help GMG?")
        self.assertIn("couldn’t generate a tailored answer", answer)
        self.assertIn("https://www.garjemarathi.com/about", answer)

    def test_hosted_website_context_fits_the_provider_payload_limit(self):
        self.agent.hosted = True
        info = CommunityInfo("Garje Marathi Global", "GMG", website_context="मराठी समुदाय " * 1000)
        with patch.object(AIAgent, "community_info", new_callable=PropertyMock, return_value=info), \
                patch.object(self.agent, "_call_llm", return_value="Volunteer at a mentoring event.") as call:
            answer = self.agent.handle_query("Suggest one way a new volunteer can contribute to GMG.")
        self.assertEqual(answer, "Volunteer at a mentoring event.")
        prompt = call.call_args.args[0]
        self.assertIn("मराठी समुदाय", prompt)
        wire = json.dumps([self.agent._get_system_prompt(), prompt], ensure_ascii=False).encode()
        self.assertLess(len(wire), 3700)
