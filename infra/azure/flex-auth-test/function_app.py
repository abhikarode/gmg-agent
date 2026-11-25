"""Temporary, isolated LinkedIn and membership test on Azure Functions Flex."""

import os
import re
import unicodedata
from datetime import timedelta
from functools import lru_cache
from threading import Lock
from time import time
from uuid import uuid4

import azure.functions as func
from azure.core.exceptions import AzureError
from authlib.integrations.flask_client import OAuth
from authlib.integrations.base_client import OAuthError
from authlib.integrations.requests_client import OAuth2Session
from flask import Flask, g, redirect, render_template, request, session
from joserfc.errors import JoseError
from requests.exceptions import RequestException

from directory_snapshot import load_snapshot
from membership import decode_roster, normalize_email, roster_lookup_key

web = Flask(__name__, static_url_path="/api/assets")
web.config.update(
    SECRET_KEY=os.environ["GMG_FLEX_SESSION_SECRET"],
    SESSION_COOKIE_NAME="__Host-gmg-flex-test",
    SESSION_COOKIE_SECURE=True,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    PERMANENT_SESSION_LIFETIME=timedelta(minutes=12),
    MAX_CONTENT_LENGTH=2048,
)

origin = os.environ["GMG_FLEX_ORIGIN"].rstrip("/")
landing = os.environ.get("GMG_FLEX_LANDING_ORIGIN", origin).rstrip("/")
if landing != origin and not re.fullmatch(r"https://[a-z0-9]+\.z[0-9]+\.web\.core\.windows\.net", landing):
    raise ValueError("Configure the isolated Azure static landing origin")
expires = int(os.environ["GMG_FLEX_EXPIRES"])
roster_secret = os.environ["GMG_FLEX_ROSTER_SECRET"]
rosters = {
    case: decode_roster(os.environ[f"GMG_FLEX_ROSTER_{case.upper()}"].encode(), roster_secret)
    for case in ("member", "unmatched")
}

oauth = OAuth(web)
linkedin_scope = "openid profile email"
oauth.register(
    "linkedin",
    client_id=os.environ["LINKEDIN_CLIENT_ID"],
    client_secret=os.environ["LINKEDIN_CLIENT_SECRET"],
    server_metadata_url="https://www.linkedin.com/oauth/.well-known/openid-configuration",
    client_kwargs={
        "scope": linkedin_scope,
        "token_endpoint_auth_method": "client_secret_post",
        "default_timeout": 8,
    },
)

worker_id = uuid4().hex
worker_lock = Lock()
first_request = True
known_oauth_errors = {
    "access_denied", "invalid_client", "invalid_grant", "invalid_request", "invalid_scope",
    "mismatching_state", "server_error", "unauthorized_client", "unsupported_grant_type",
}
known_oidc_claims = {"at_hash", "aud", "azp", "exp", "iat", "iss", "nbf", "nonce", "sub"}


def page(title, content, status=200):
    # Titles and markup are fixed by this harness. No upstream claims enter the response.
    return f"""<!doctype html><html lang="en"><meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1"><title>{title}</title>
    <main><h1>{title}</h1>{content}</main></html>""", status


@web.before_request
def prepare_request():
    global first_request
    with worker_lock:
        g.first_request = first_request
        first_request = False
    if time() >= expires:
        return page("GMG Flex test expired", "<p>The temporary test window has closed.</p>", 410)


@web.after_request
def response_headers(response):
    response.headers.update({
        "Cache-Control": "no-store",
        "Referrer-Policy": "origin",
        "Content-Security-Policy": "default-src 'none'; base-uri 'none'; frame-ancestors 'none'; style-src 'self'; img-src 'self'; "
        f"form-action 'self' https://www.linkedin.com {landing}",
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "X-GMG-Worker": worker_id,
        "X-GMG-First-Request": "yes" if g.first_request else "no",
    })
    return response


@web.get("/api/test")
def home():
    return page("GMG Flex sign-in test", """<p>Sign in with LinkedIn to check GMG membership in the isolated pilot.</p>
    <form method="post" action="/api/start">
      <button name="case" value="member">Test member access with LinkedIn</button>
      <button name="case" value="unmatched">Test unmatched access with LinkedIn</button>
    </form>""")


@web.post("/api/start")
def start():
    case = request.form.get("case")
    if case not in rosters or request.headers.get("Origin") not in (origin, landing):
        return page("Invalid test case", "<p>Choose a case from the test page.</p>", 400)
    session.clear()
    session.permanent = True
    session["case"] = case
    session["start_worker"] = worker_id
    session["cold_worker"] = g.first_request
    try:
        # Match the live desk's confidential code flow, which uses state and does not request a nonce.
        redirect_uri = f"{origin}/api/callback/linkedin"
        linkedin = oauth.linkedin
        endpoint = linkedin.load_server_metadata()["authorization_endpoint"]
        with OAuth2Session(linkedin.client_id, scope=linkedin_scope, redirect_uri=redirect_uri) as client:
            authorization, state = client.create_authorization_url(endpoint)
        linkedin.save_authorize_data(redirect_uri=redirect_uri, state=state)
        return redirect(authorization)
    except (OAuthError, RequestException, ValueError):
        session.clear()
        return page("LinkedIn is unavailable", '<p><a href="/api/test">Return to the test page</a></p>', 502)


@web.get("/api/callback/linkedin")
def callback():
    case = session.get("case")
    if case not in rosters:
        return page("LinkedIn session rejected", '<p><a href="/api/test">Start a new test</a></p>', 401)

    try:
        token = oauth.linkedin.authorize_access_token(timeout=8)
        claims = oauth.linkedin.parse_id_token(token, nonce=None, leeway=60)
        if not claims or claims.get("nonce") is not None or not isinstance(claims.get("sub"), str) or not claims["sub"]:
            raise ValueError("Missing validated LinkedIn identity")
        email = verified_email(claims)
        if not email and token.get("access_token"):
            try:
                details = oauth.linkedin.userinfo(token=token, timeout=5)
                if details.get("sub") == claims["sub"]:
                    email = verified_email(details)
            except (OAuthError, RequestException, ValueError):
                pass
    except (OAuthError, JoseError, RequestException, ValueError) as error:
        session.clear()
        reason = rejection_reason(error)
        return page("LinkedIn sign-in could not be verified",
                    f'<p>{reason}</p><p><a href="/api/test">Start a new test</a></p>', 401)

    first_worker = session.get("start_worker")
    cold_worker = session.get("cold_worker") or g.first_request or first_worker != worker_id
    key = roster_lookup_key(email, roster_secret)
    matched = key is not None and key in rosters[case]
    session.clear()
    session.permanent = True
    if matched:
        session.update(access="member", roster_key=key, auth_worker=worker_id, cold_worker=cold_worker)
        return redirect("/api/desk", 303)
    session["access"] = "unmatched" if email else "email-unverified"
    return redirect("/api/result", 303)


def verified_email(claims):
    return normalize_email(claims.get("email")) if claims.get("email_verified") is True else ""


def rejection_reason(error):
    # Report only fixed failure categories and standard names, never raw provider errors.
    if isinstance(error, OAuthError) and error.error in known_oauth_errors:
        return f"OAuth rejected the request ({error.error})."
    if isinstance(error, JoseError):
        claim = getattr(error, "claim", None)
        return f"LinkedIn token claim validation failed ({claim})." if claim in known_oidc_claims else "LinkedIn token validation failed."
    if isinstance(error, RequestException):
        return "The LinkedIn token service could not be reached."
    return "The LinkedIn response could not be validated."


@web.get("/api/result")
def result():
    match session.get("access"):
        case "member":
            return page("LinkedIn verified · GMG membership matched",
                        '<p><a href="/api/desk">Open the test Community Desk</a></p>')
        case "unmatched":
            return page("LinkedIn verified · GMG membership not matched",
                        '<p><a href="/api/desk">Check that the test desk denies access</a></p>')
        case "email-unverified":
            return page("LinkedIn email could not be verified", '<p><a href="/api/test">Start a new test</a></p>', 403)
        case _:
            return page("No completed LinkedIn sign-in", '<p><a href="/api/test">Start a test</a></p>', 401)


def search_key(value):
    return " ".join(unicodedata.normalize("NFC", value).casefold().split())


@lru_cache(maxsize=1)
def exact_name_index():
    by_name = {}
    for member in load_snapshot(os.getenv("GMG_BLOB_CONNECTION_STRING"))["users"]:
        name = member.get("name")
        if isinstance(name, str) and (key := search_key(name)):
            by_name.setdefault(key, []).append(member)
    return by_name


@web.route("/api/desk", methods=["GET", "POST"])
def desk():
    if session.get("access") != "member" or session.get("roster_key") not in rosters["member"]:
        return page("GMG member access denied", '<p><a href="/api/test">Return to the test page</a></p>', 403)
    if request.method == "POST" and request.headers.get("Origin") != origin:
        return page("Search request denied", '<p><a href="/api/desk">Return to the Desk</a></p>', 403)
    query = request.form.get("name", "").strip()
    if len(query) > 100:
        return page("Member name is too long", '<p><a href="/api/desk">Return to the Desk</a></p>', 400)
    try:
        directory = exact_name_index()
    except (AzureError, OSError, ValueError):
        return page("Member search is unavailable", '<p><a href="/api/desk">Try the Desk again</a></p>', 503)
    session["cold_worker"] = bool(session.get("cold_worker") or g.first_request or session.get("auth_worker") != worker_id)
    matches = directory.get(search_key(query), [])[:10] if query else []
    return render_template("desk.html", query=query, matches=matches, cold_worker=session["cold_worker"])


app = func.WsgiFunctionApp(app=web.wsgi_app, http_auth_level=func.AuthLevel.ANONYMOUS)
