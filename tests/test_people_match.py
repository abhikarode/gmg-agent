import json
import unittest

from people_match import MatchUnavailable, PeopleIndex, recommend


def member(name, title, city, **fields):
    return {
        "name": name, "current-city": city, "current-state": "California",
        "current-country": "United States", "work_experiences": [{"designation": title}],
        **fields,
    }


class PeopleMatchTests(unittest.TestCase):
    def setUp(self):
        self.index = PeopleIndex([
            member("GMG Member One", "Tax Accountant", "San Jose",
                   primary_email="private@example.test",
                   profile_url_linkedin="https://www.linkedin.com/in/test/?utm_source=search",
                   _gmg_linkedin_work={"designation": "Tax Accountant", "company": "Example"}),
            member("GMG Member Two", "Tax Accountant", "Los Angeles"),
            member("GMG Member Three", "Engineering Manager", "San Jose"),
        ])

    def test_model_is_constrained_to_real_evidence_and_selected_location(self):
        def complete(_system, request, _schema, _timeout):
            payload = json.loads(request)
            if "candidates" not in payload:
                return json.dumps({"intent": "Help with taxes", "terms": ["tax accountant", "accounting manager"]})
            self.assertEqual(len(payload["candidates"]), 1)
            self.assertNotIn("GMG Member", request)
            self.assertNotIn("private@", request)
            self.assertNotIn("linkedin.com", request)
            return json.dumps({"matches": [{"id": 91, "evidence": 1}, {"id": 1, "evidence": 1}]})

        result = recommend(self.index, "मला करासाठी मदत हवी आहे", "Bay Area", "test-model", complete)
        self.assertEqual(result.ranking, "model")
        self.assertEqual([card.name for card in result.members], ["GMG Member One"])
        self.assertEqual(result.members[0].summary, "Tax Accountant at Example")
        self.assertEqual(result.members[0].summarySource, "LinkedIn export")
        self.assertEqual(result.members[0].linkedin, "https://www.linkedin.com/in/test")

    def test_generic_partial_overlaps_do_not_create_candidate_and_place_must_be_explicit(self):
        self.assertEqual(self.index.retrieve(["Accounting Manager"], "San Jose"), [])
        self.assertEqual(self.index.resolve_place("", "San Jose", "Need an accountant"), "")
        self.assertEqual(self.index.resolve_place("", "San Jose", "Need an accountant in San Jose"), "San Jose")

    def test_ranking_failure_is_labeled_and_planning_failure_does_not_guess(self):
        def complete(_system, request, _schema, _timeout):
            if "candidates" in json.loads(request):
                raise MatchUnavailable("offline")
            return '{"terms":["accountant"]}'

        matches = recommend(self.index, "Help with my finances", "", "test-model", complete)
        self.assertEqual(matches.ranking, "directory")
        self.assertEqual(len(matches.members), 2)
        with self.assertRaises(MatchUnavailable):
            recommend(self.index, "Help with my finances", "", "test-model", lambda *_: "invalid")

    def test_bay_area_topic_keeps_direct_evidence_with_incomplete_model_ranking(self):
        index = PeopleIndex([
            member("Local Mentor", "", "San Ramon", _gmg_professional_evidence={
                "text": "Artificial intelligence hackathon mentor and judge",
                "source": "GMG activity", "url": "https://www.garjemarathi.com/",
            }),
            member("Remote Mentor", "Artificial intelligence mentor", "Los Angeles"),
        ])

        def complete(_system, request, _schema, _timeout):
            if "candidates" in json.loads(request):
                return '{"matches":[]}'
            return '{"terms":["AI systems architect"]}'

        result = recommend(index, "Artificial Intelligence in Bay Area", "", "test-model", complete)
        self.assertEqual(result.place, "Bay Area")
        self.assertEqual([match.name for match in result.members], ["Local Mentor"])
        self.assertEqual(result.members[0].sourceUrl, "https://www.garjemarathi.com/")

    def test_directory_fallback_interprets_common_marathi_terms_and_keeps_place(self):
        def unavailable(*_):
            raise MatchUnavailable("allowance")

        result = recommend(self.index, "मला हिशेब आणि करासाठी मदत हवी आहे", "Bay Area",
                           "test-model", unavailable, fallback_on_plan_failure=True)
        self.assertEqual(result.ranking, "directory")
        self.assertEqual(result.place, "Bay Area")
        self.assertEqual([match.name for match in result.members], ["GMG Member One"])

    def test_start_up_funding_fallback_requires_funding_evidence_and_location(self):
        index = PeopleIndex([
            member("Local Investor", "Venture Capital Partner", "San Jose"),
            member("Local Operator", "Startup Operations", "San Jose"),
            member("Remote Investor", "Angel Investor", "Los Angeles"),
        ])
        result = index.suggest("Start up funding", "Bay Area", "test-model")
        self.assertEqual(result.place, "Bay Area")
        self.assertEqual(result.ranking, "directory")
        self.assertEqual([match.name for match in result.members], ["Local Investor"])

        def complete(_system, request, _schema, _timeout):
            payload = json.loads(request)
            if "candidates" not in payload:
                return '{"terms":["startup operations","investor"]}'
            self.assertEqual(payload["candidates"][0]["evidence"], ["Venture Capital Partner"])
            self.assertEqual(len(payload["candidates"]), 1)
            return '{"matches":[]}'

        ranked = recommend(index, "Start up funding", "Bay Area", "test-model", complete)
        self.assertEqual(ranked.ranking, "directory")
        self.assertEqual([match.name for match in ranked.members], ["Local Investor"])
