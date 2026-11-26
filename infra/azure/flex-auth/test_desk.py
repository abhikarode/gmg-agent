import hashlib
import json
import os
import re
import unittest
from base64 import b64encode
from http.cookies import SimpleCookie
from time import time
from unittest.mock import patch
from urllib.parse import parse_qs, urlencode, urlsplit

import azure.functions as func
from joserfc import jwt
from joserfc.jwk import RSAKey
from requests import Response
from requests.exceptions import Timeout

ORIGIN = "https://gmg-flex-fixture.azurewebsites.net"
DESK_ORIGIN = "https://gmg-fixture.azurecontainerapps.io"
EMAIL = "member@example.test"
ENVIRONMENT = {
    "GMG_FLEX_ORIGIN": ORIGIN,
    "GMG_DESK_ORIGIN": DESK_ORIGIN,
    "GMG_FLEX_BROKER_SECRET": "fixture-broker",
    "GMG_FLEX_ROSTER_SECRET": "fixture-roster",
    "GMG_FLEX_SESSION_SECRET": "fixture-session",
    "LINKEDIN_CLIENT_ID": "fixture-client",
    "LINKEDIN_CLIENT_SECRET": "fixture-client-secret",
}
with patch.dict(os.environ, ENVIRONMENT):
    import function_app as flex
    import member_desk
from hosted_inference import MODEL_LABEL
from membership import roster_lookup_key
from relay_fixture import RelayFixture

KEY = roster_lookup_key(EMAIL, ENVIRONMENT["GMG_FLEX_ROSTER_SECRET"])


class FlexDeskTest(unittest.TestCase):
    def setUp(self):
        self.client = flex.web.test_client()
        relay_patch = patch.object(flex, "desk_relay_blob", RelayFixture().blob)
        relay_patch.start()
        self.addCleanup(relay_patch.stop)

    def get(self, path):
        return self.client.get(path, base_url=ORIGIN)

    def post(self, path, data=None, origin=ORIGIN):
        return self.client.post(path, data=data, base_url=ORIGIN, headers={"Origin": origin})

    def callback(self, mode=True, member="fixture-member", verified=True, complete=True):
        with self.client.session_transaction(base_url=ORIGIN) as auth:
            auth.update(starting=True, desk=mode)
        claims = {"sub": "fixture-sub", "name": "Fixture Name", "email": EMAIL, "email_verified": verified}
        with patch.object(flex.oauth.linkedin, "authorize_access_token", return_value={}), \
                patch.object(flex.oauth.linkedin, "parse_id_token", return_value=claims), \
                patch.object(flex, "lookup_member_key", return_value=member) as roster:
            response = self.get("/api/callback/linkedin")
            if verified and (mode or not flex.classic_enabled):
                roster.assert_called_once_with(KEY, ENVIRONMENT["GMG_FLEX_ROSTER_SECRET"])
            else:
                roster.assert_not_called()
            if complete and response.status_code == 200 and b'/api/desk/complete' in response.data:
                self.assertEqual(self.finish(response).status_code, 303)
        return response

    def finish(self, response, origin=ORIGIN):
        code = re.search(rb'name="code" value="([A-Za-z0-9_-]+)"', response.data)[1].decode()
        return self.post("/api/desk/complete", {"code": code}, origin=origin)

    def test_authenticated_search_and_logout(self):
        self.assertEqual(self.get("/api/desk").status_code, 401)
        self.assertEqual(self.get("/api/callback/linkedin").status_code, 401)
        with patch.object(flex, "relay_blob") as relay:
            response = self.callback(complete=False)
            relay.assert_not_called()
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'action="/api/desk/complete"', response.data)
        self.assertNotIn("Set-Cookie", response.headers)
        with patch.object(flex, "lookup_member_key", return_value="fixture-member"):
            self.assertEqual(self.finish(response, origin="https://elsewhere.example").status_code, 403)
            joined = self.finish(response)
            self.assertEqual((joined.status_code, joined.location), (303, "/api/desk?from=linkedin&session=v2"))
            self.assertEqual(self.finish(response).status_code, 401)
        cookie, = joined.headers.getlist("Set-Cookie")
        self.assertTrue(cookie.startswith(member_desk.DESK_COOKIE + "="))
        self.assertTrue(all(flag in cookie for flag in ("Secure", "HttpOnly", "SameSite=Lax")))
        self.assertNotIn("fixture-sub", cookie)
        with patch.object(flex, "lookup_member_key", return_value="fixture-member"), \
                patch.object(flex, "exact_members", return_value=[{"name": "Kavya Deshmukh"}]) as search:
            landing = self.get(joined.location)
            self.assertEqual(landing.status_code, 200)
            self.assertIn(b"Find member", landing.data)
            self.assertEqual(landing.headers["Cache-Control"], "no-store")
            style = re.search(b"<style>(.*?)</style>", landing.data, re.S)[1]
            self.assertIn("sha256-" + b64encode(hashlib.sha256(style).digest()).decode(), landing.headers["Content-Security-Policy"])
            self.assertEqual(self.post("/api/desk", {"name": "a"}, "https://external.example").status_code, 403)
            result = self.post("/api/desk", {"name": "Kavya Deshmukh"})
            self.assertIn(b"Kavya Deshmukh", result.data)
            search.assert_called_with("Kavya Deshmukh")
            self.assertEqual(self.post("/api/desk/logout", origin="https://external.example").status_code, 403)
            self.assertEqual(self.get("/api/desk/signed-out").location, "/api/desk")
            with self.client.session_transaction(base_url=ORIGIN) as auth:
                auth["starting"] = True
            logout = self.post("/api/desk/logout")
            self.assertEqual((logout.status_code, logout.location), (303, "/api/desk/signed-out"))
            self.assertEqual(logout.headers["Cache-Control"], "no-store")
            with self.client.session_transaction(base_url=ORIGIN) as auth:
                self.assertFalse(auth)
            signed_out = self.get(logout.location)
            self.assertEqual(signed_out.status_code, 200)
            self.assertIn("You’re signed out".encode(), signed_out.data)
            self.assertIn(b"Continue with LinkedIn", signed_out.data)
            self.assertEqual(self.get("/api/desk").status_code, 401)

    def test_membership_is_rechecked_and_no_results_leak(self):
        with patch.object(flex, "exact_members") as search:
            self.assertEqual(self.callback(member=None).status_code, 403)
            self.assertEqual(self.get("/api/desk").status_code, 401)
            self.assertEqual(self.callback().status_code, 200)
            with patch.object(flex, "lookup_member_key", return_value=None):
                self.assertEqual(self.get("/api/desk").status_code, 403)
                self.assertEqual(self.post("/api/desk/full").status_code, 403)
            search.assert_not_called()

    def test_post_linkedin_401_reports_missing_or_unreadable_session(self):
        url = "/api/desk?from=linkedin"
        missing = self.get(url)
        self.assertEqual(missing.status_code, 401)
        self.assertIn(b"GMG-S1", missing.data)
        domain = urlsplit(ORIGIN).hostname
        self.client.set_cookie(member_desk.DESK_COOKIE, "fixture-invalid-cookie", domain=domain)
        invalid = self.get(url)
        self.assertEqual(invalid.status_code, 401)
        self.assertIn(b"GMG-S2", invalid.data)
        self.assertNotIn(b"fixture-invalid-cookie", invalid.data)

    def test_handoff_binds_to_browser_and_preserves_existing_sessions(self):
        response = self.callback(complete=False)
        correct_browser = self.client
        self.client = flex.web.test_client()
        with self.client.session_transaction(base_url=ORIGIN) as auth:
            auth.update(starting=True, unrelated=True)
        self.assertEqual(self.finish(response).status_code, 401)
        self.client = correct_browser
        with patch.object(flex, "lookup_member_key", return_value="fixture-member"), \
                patch.object(flex, "exact_members", return_value=[]):
            old_cookie = flex.cipher.encrypt(json.dumps({"sub": "fixture", "rosterKey": KEY}).encode()).decode()
            domain = urlsplit(ORIGIN).hostname
            self.client.set_cookie(member_desk.PREVIOUS_DESK_COOKIE, old_cookie, domain=domain)
            self.assertEqual(self.get("/api/desk").status_code, 200)
            self.assertEqual(self.get("/api/desk?from=linkedin").status_code, 200)
            self.assertEqual(self.get("/api/desk?from=linkedin&session=v2").status_code, 401)
            self.assertEqual(self.finish(response).status_code, 303)
            self.assertEqual(self.get("/api/desk?from=linkedin&session=v2").status_code, 200)
            self.post("/api/desk/logout")
            self.assertEqual(self.get("/api/desk").status_code, 401)

    def test_expired_handoff_cannot_issue_a_session(self):
        response = self.callback(complete=False)
        with patch.object(flex, "time", return_value=time() + flex.relay_lifetime + 1):
            self.assertEqual(self.finish(response).status_code, 401)
        self.assertEqual(self.get("/api/desk").status_code, 401)

    def test_linkedin_denial_identifies_which_email_check_failed(self):
        unmatched = self.callback(member=None)
        self.assertEqual(unmatched.status_code, 403)
        self.assertIn(EMAIL.encode(), unmatched.data)
        self.assertIn(b"Try LinkedIn sign-in again", unmatched.data)
        self.assertEqual(unmatched.headers["Cache-Control"], "no-store")
        unverified = self.callback(verified=False)
        self.assertEqual(unverified.status_code, 403)
        self.assertIn(b"GMG requires a verified LinkedIn email", unverified.data)
        self.assertNotIn(EMAIL.encode(), unverified.data)
        self.assertEqual(self.get("/api/desk").status_code, 401)

    def test_userinfo_email_requires_matching_subject_and_verification(self):
        claims = {"sub": "fixture-sub"}
        token = {"access_token": "fixture-token"}
        for subject, verified, expected in (
            ("fixture-sub", True, EMAIL),
            ("another-sub", True, None),
            ("fixture-sub", False, None),
        ):
            with self.subTest(subject=subject, verified=verified):
                with patch.object(flex.oauth.linkedin, "userinfo", return_value={
                    "sub": subject, "email": EMAIL, "email_verified": verified,
                }):
                    self.assertEqual(flex.verified_email(claims, token), expected)

    def test_public_start_redirects_without_outbound_io(self):
        with patch("requests.sessions.Session.send", side_effect=AssertionError("Unexpected outbound request")):
            response = self.get("/api/start?desk=flex")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["Cache-Control"], "no-store")
        target = urlsplit(response.location)
        self.assertEqual((target.scheme, target.netloc, target.path), ("https", "www.linkedin.com", "/oauth/v2/authorization"))
        params = parse_qs(target.query)
        self.assertEqual(params["redirect_uri"], [f"{ORIGIN}/api/callback/linkedin"])
        with self.client.session_transaction(base_url=ORIGIN) as auth:
            self.assertIn(f"_state_linkedin_{params['state'][0]}", auth)

    def test_callback_outbound_timeouts_return_service_error(self):
        linkedin = flex.oauth.linkedin
        for operation in ("authorize_access_token", "userinfo"):
            with self.subTest(operation=operation):
                with self.client.session_transaction(base_url=ORIGIN) as auth:
                    auth.update(starting=True, desk=True)
                with patch.object(linkedin, "parse_id_token", return_value={"sub": "fixture-sub"}), \
                        patch.object(linkedin, "authorize_access_token", return_value={"access_token": "fixture"}), \
                        patch.object(linkedin, operation, side_effect=Timeout), \
                        patch.object(flex, "lookup_member_key") as roster:
                    response = self.get("/api/callback/linkedin")
                    roster.assert_not_called()
                self.assertEqual(response.status_code, 503)
                self.assertIn(b"Try LinkedIn sign-in again", response.data)
                self.assertEqual(response.headers["Cache-Control"], "no-store")
                self.assertIsNone(self.client.get_cookie(member_desk.DESK_COOKIE, domain=urlsplit(ORIGIN).hostname))

    def test_signed_callback_through_azure_wsgi_adapter(self):
        signed_key = RSAKey.generate_key(auto_kid=True)
        linkedin = flex.oauth.linkedin
        claims = {
            "iss": linkedin.server_metadata["issuer"], "aud": linkedin.client_id,
            "iat": int(time()), "exp": int(time()) + 60, "sub": "fixture-sub",
            "email": EMAIL, "email_verified": True,
        }
        middleware = func.WsgiMiddleware(flex.web.wsgi_app)

        def visit(path, cookie="", code=None):
            headers = {"Host": urlsplit(ORIGIN).netloc, "Cookie": cookie}
            if code:
                headers.update(Origin=ORIGIN, **{"Content-Type": "application/x-www-form-urlencoded"})
            request = func.HttpRequest("POST" if code else "GET", ORIGIN + path, headers=headers,
                                       body=urlencode({"code": code}).encode() if code else b"")
            return middleware.handle(request)

        def cookies(response):
            jar = SimpleCookie()
            for value in response.headers.get_all("Set-Cookie"):
                jar.load(value)
            return jar

        for audience, result in [(linkedin.client_id, 200), ("other-client", 401)]:
            with self.subTest(audience=audience):
                started = visit("/api/start?desk=flex")
                state = parse_qs(urlsplit(started.headers["Location"]).query)["state"][0]
                oauth_cookie = cookies(started)[flex.web.config["SESSION_COOKIE_NAME"]]
                token = jwt.encode({"alg": "RS256", "kid": signed_key.kid}, {**claims, "aud": audience}, signed_key)

                def provider_response(request, **options):
                    if request.url == linkedin.access_token_url:
                        payload = {"access_token": "fixture-access-token", "token_type": "Bearer", "id_token": token}
                    else:
                        self.assertEqual(request.url, linkedin.server_metadata["jwks_uri"])
                        payload = {"keys": [signed_key.as_dict()]}
                    self.assertEqual(options["timeout"], flex.linkedin_timeout)
                    response = Response()
                    response.status_code = 200
                    response._content = json.dumps(payload).encode()
                    response.headers["Content-Type"] = "application/json"
                    return response

                with patch("requests.sessions.Session.send", side_effect=provider_response), \
                        patch.dict(linkedin.server_metadata), \
                        patch.object(flex, "lookup_member_key", return_value="fixture-member"), \
                        patch.object(flex, "exact_members", return_value=[]):
                    callback = visit("/api/callback/linkedin?" + urlencode({"code": "fixture-code", "state": state}),
                                     f"{oauth_cookie.key}={oauth_cookie.value}")
                    self.assertEqual(callback.status_code, result)
                    response_cookies = cookies(callback)
                    if result == 200:
                        self.assertFalse(response_cookies)
                        code = re.search(rb'name="code" value="([A-Za-z0-9_-]+)"', callback.get_body())[1].decode()
                        joined = visit("/api/desk/complete", f"{oauth_cookie.key}={oauth_cookie.value}", code=code)
                        self.assertEqual(joined.status_code, 303)
                        desk_cookie = cookies(joined)[member_desk.DESK_COOKIE]
                        self.assertNotIn(oauth_cookie.key, response_cookies)
                        self.assertTrue(desk_cookie["secure"] and desk_cookie["httponly"])
                        header = f"{desk_cookie.key}={desk_cookie.value}; {oauth_cookie.key}={oauth_cookie.value}"
                        desk = visit(joined.headers["Location"], header)
                        self.assertEqual(desk.status_code, 200)
                        self.assertEqual(cookies(desk)[oauth_cookie.key].value, "")
                    else:
                        self.assertNotIn(member_desk.DESK_COOKIE, response_cookies)

    def test_inactive_callback_requires_new_flex_sign_in(self):
        with patch.object(flex.oauth.linkedin, "authorize_access_token") as exchange, \
                patch.object(flex, "relay_blob") as relay:
            response = self.get("/api/callback/linkedin")
            exchange.assert_not_called()
            relay.assert_not_called()
        self.assertEqual(response.status_code, 401)
        self.assertNotIn("Set-Cookie", response.headers)
        self.assertIn(b"sign-in attempt is no longer active", response.data)
        self.assertIn(b'href="/api/start?desk=flex"', response.data)
        self.assertNotIn(b'href="/api/start"', response.data)
        self.assertEqual(self.get("/api/desk").status_code, 401)

    def test_retired_classic_links_stay_on_flex(self):
        self.assertEqual(self.get("/api/start").status_code, 302)
        with self.client.session_transaction(base_url=ORIGIN) as auth:
            self.assertIs(auth["desk"], True)
        with patch.object(flex, "relay_blob") as relay, \
                patch.object(flex, "lookup_member_key", return_value="fixture-member"), \
                patch.object(flex, "exact_members", return_value=[]), \
                patch.dict(os.environ, {"GMG_FLEX_TOOLS_ENABLED": "1", "GMG_FLEX_PEOPLE_ENABLED": "1"}):
            callback = self.callback(mode=False)
            self.assertEqual(callback.status_code, 200)
            response = self.get("/api/desk")
            self.assertIn(b"Search by expertise", response.data)
            self.assertNotIn(b"/api/desk/full", response.data)
            former_handoff = self.post("/api/desk/full")
            self.assertEqual((former_handoff.status_code, former_handoff.location), (303, "/api/desk"))
            self.assertEqual(self.get("/api/desk").status_code, 200)
            relay.assert_not_called()

    @patch.object(flex, "classic_enabled", True)
    def test_full_desk_uses_the_existing_one_time_relay_when_reenabled(self):
        self.assertEqual(self.callback().status_code, 200)
        with patch.object(flex, "relay_blob") as relay, patch.object(flex, "lookup_member_key", return_value="fixture-member"):
            handoff = self.post("/api/desk/full")
            self.assertIn(f"{DESK_ORIGIN}/api/gmg/flex-session".encode(), handoff.data)
            arguments = relay.return_value.upload_blob.call_args
            identity = json.loads(arguments.args[0])
            self.assertEqual(identity["rosterKey"], KEY)
            self.assertTrue(identity["expires"] > 0)
            self.assertEqual(self.get("/api/desk").status_code, 401)
            self.assertEqual(self.callback(mode=False).status_code, 200)
            self.assertEqual(relay.return_value.upload_blob.call_count, 2)

    def test_index_exposes_only_directory_card_fields(self):
        version = "fixture-version"
        fixture = {"name": "Kavya Deshmukh", "current-city": "San Jose", "email": "private@example.test",
                   "profile_url_linkedin": "https://linkedin.com/in/kavya-test/?extra=one"}
        with patch.object(member_desk, "_manifest", return_value=version), \
                patch.object(member_desk, "snapshot_container", return_value=None), \
                patch.object(member_desk, "load_snapshot_version", return_value={"users": [fixture]}):
            self.assertEqual(member_desk.exact_members(" KAVYA  Deshmukh "), [{
                "name": "Kavya Deshmukh", "location": "San Jose", "role": "", "company": "", "summary": "",
                "linkedin": "https://www.linkedin.com/in/kavya-test/",
            }])
            self.assertEqual(member_desk.exact_members("Kavya"), [])

    def test_tools_require_current_membership_and_same_origin_writes(self):
        for name in ("ask", "opportunities", "expertise", "people"):
            path = f"/api/desk/{name}"
            self.assertEqual(self.get(path).status_code, 401)
            self.assertEqual(self.post(path, {}, "https://foreign.example").status_code, 403)
        self.assertEqual(self.callback().status_code, 200)
        with patch.object(flex, "lookup_member_key", return_value=None):
            self.assertEqual(self.get("/api/desk/expertise").status_code, 403)
            self.assertEqual(self.post("/api/desk/people", {"need": "Software engineering"}).status_code, 403)

    def test_tools_use_scoped_services_and_deployment_switch(self):
        import desk_tools

        self.assertEqual(self.callback().status_code, 200)
        with patch.object(flex, "lookup_member_key", return_value="fixture-member"), \
                patch.object(flex, "exact_members", return_value=[]), \
                patch.dict(os.environ, {"GMG_FLEX_TOOLS_ENABLED": "0"}):
            self.assertNotIn(b"Community Desk tools", self.get("/api/desk").data)
            self.assertIn(b"Community Desk tools", self.get("/api/desk?tools=preview").data)
            with patch.dict(os.environ, {"GMG_FLEX_TOOLS_ENABLED": "1"}):
                self.assertIn(b"Community Desk tools", self.get("/api/desk").data)
            with patch.object(desk_tools, "ask_gmg", return_value=("<strong>Fixture</strong>", MODEL_LABEL)) as ask:
                self.assertEqual(self.get("/api/desk/ask").status_code, 200)
                ask.assert_not_called()
                reply = self.post("/api/desk/ask", {"question": "Question"})
                ask.assert_called_once_with("Question")
                self.assertIn(b"<strong>Fixture</strong>", reply.data)
                self.assertIn(f"Answered with {MODEL_LABEL}".encode(), reply.data)
                ask.return_value = ("", "inference paused")
                paused = self.post("/api/desk/ask", {"question": "Question"})
                self.assertEqual(paused.status_code, 200)
                self.assertIn(b"AI answers are paused", paused.data)
                self.assertNotIn(b"allowance has been reached", paused.data)
            with patch.object(desk_tools, "opportunities", return_value="<p>Fixture role</p>") as jobs:
                self.assertIn(b"Fixture role", self.get("/api/desk/opportunities").data)
                jobs.assert_called_once_with("")
            fixture = {"catalog": {"Test group": {"one": "Test topic"}}, "max_topics": 8, "selected": ["one"], "saved": True}
            with patch.object(desk_tools, "expertise_form", return_value=fixture) as save:
                reply = self.post("/api/desk/expertise", {"topics": "one"})
                self.assertIn(b"Your expertise is saved.", reply.data)
                self.assertIn(b'value="one" checked', reply.data)
                save.assert_called_once_with("fixture-member", ["one"])

    def test_markdown_escapes_html_and_rejects_active_urls(self):
        from desk_tools import markdown

        rendered = markdown.render('<script>alert(1)</script>\n\n[link](javascript:alert)%20\n\n![photo](https://example.test/p.png)')
        self.assertNotIn("<script", rendered)
        self.assertNotIn('href="javascript:', rendered)
        self.assertNotIn("<img", rendered)

    def test_people_route_has_preview_switch_and_bounded_member_search(self):
        from desk_tools import find_people
        from people_match import MemberMatch, MatchResponse

        result = MatchResponse(place="Bay Area", ranking="directory", model="fixture", members=[
            MemberMatch(name="Fixture Person", evidence="Software engineer", source="GMG directory",
                        linkedin="https://www.linkedin.com/in/fixture-member"),
        ])
        self.assertEqual(self.callback().status_code, 200)
        with patch.object(flex, "lookup_member_key", return_value="fixture-member"), \
                patch.object(flex, "exact_members", return_value=[]), \
                patch.dict(os.environ, {"GMG_FLEX_TOOLS_ENABLED": "1", "GMG_FLEX_PEOPLE_ENABLED": "0"}), \
                patch("desk_tools.find_people", autospec=find_people,
                      return_value=(result, "pilot allowance reached")) as search:
            self.assertNotIn(b'href="/api/desk/people"', self.get("/api/desk").data)
            self.assertIn(b'href="/api/desk/people"', self.get("/api/desk?people=preview").data)
            with patch.dict(os.environ, {"GMG_FLEX_PEOPLE_ENABLED": "1"}):
                self.assertIn(b'href="/api/desk/people"', self.get("/api/desk").data)
            self.assertEqual(self.get("/api/desk/people").status_code, 200)
            self.assertEqual(self.post("/api/desk/people", {"need": "short"}).status_code, 400)
            self.assertEqual(self.post("/api/desk/people", {"need": "example need", "place": "x" * 91}).status_code, 400)
            self.assertEqual(self.post("/api/desk/people", {"need": "x" * 24_001}).status_code, 413)
            search.assert_not_called()
            reply = self.post("/api/desk/people", {"need": "Software engineering", "place": "Bay Area"})
            search.assert_called_once_with("Software engineering", "Bay Area")
            self.assertEqual(reply.status_code, 200)
            self.assertIn(b"Fixture Person", reply.data)
            self.assertIn(b"Matched using the GMG directory", reply.data)
            self.assertIn(b"AI allowance is used up", reply.data)
            self.assertIn(b"member profiles and saved expertise", reply.data)
            self.assertIn(b"https://www.linkedin.com/in/fixture-member", reply.data)
            self.assertNotIn(f"Matched with {MODEL_LABEL}".encode(), reply.data)
            self.assertEqual(reply.headers["Cache-Control"], "no-store")
            search.return_value = (result, "inference paused")
            paused = self.post("/api/desk/people", {"need": "Software engineering", "place": "Bay Area"})
            self.assertIn(b"AI matching is paused", paused.data)
            self.assertIn(b"Matched using the GMG directory", paused.data)
            self.assertNotIn(b"allowance is used up", paused.data)
            search.return_value = (result.model_copy(update={"ranking": "model"}), MODEL_LABEL)
            model_reply = self.post("/api/desk/people", {"need": "Software engineering", "place": "Anywhere"})
            self.assertEqual(search.call_args.args, ("Software engineering", ""))
            self.assertIn(f"Matched with {MODEL_LABEL}".encode(), model_reply.data)
            self.assertNotIn(b"allowance is used up", model_reply.data)


if __name__ == "__main__":
    unittest.main()
