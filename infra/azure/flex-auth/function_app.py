"""LinkedIn OIDC, the keyed GMG roster, and a one-time Desk session handoff."""

import base64
import hashlib
import json
import os
import re
from datetime import timedelta
from functools import lru_cache
from hmac import compare_digest
from pathlib import Path
from secrets import token_urlsafe
from time import time

import azure.functions as func
from authlib.integrations.base_client import OAuthError
from authlib.integrations.base_client.errors import MismatchingStateError
from authlib.integrations.flask_client import OAuth
from authlib.integrations.requests_client import OAuth2Session
from azure.core import MatchConditions
from azure.core.exceptions import AzureError, ResourceModifiedError, ResourceNotFoundError
from azure.storage.blob import BlobServiceClient
from flask import Flask, jsonify, make_response, redirect, render_template, request, session, url_for
from joserfc.errors import JoseError
from requests.exceptions import RequestException

from azure_storage import runtime_identity, storage_endpoint
from member_desk import DESK_COOKIE, DESK_SESSION_AGE, desk_cipher, desk_identity, exact_members
from membership import expertise_key, lookup_member_key, normalize_email, roster_lookup_key

web = Flask(__name__)
web.config.update(
    SECRET_KEY=os.environ["GMG_FLEX_SESSION_SECRET"],
    SESSION_COOKIE_NAME="__Host-gmg-flex-oauth",
    SESSION_COOKIE_SECURE=True,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    PERMANENT_SESSION_LIFETIME=timedelta(minutes=12),
    MAX_CONTENT_LENGTH=1024,
)
origin = os.environ["GMG_FLEX_ORIGIN"].rstrip("/")
classic_enabled = os.getenv("GMG_FLEX_CLASSIC_ENABLED") == "1"
desk_origin = os.getenv("GMG_DESK_ORIGIN", "").rstrip("/")
if not re.fullmatch(r"https://[a-z0-9-]+\.azurewebsites\.net", origin):
    raise ValueError("Configure the Azure sign-in origin.")
if classic_enabled and not re.fullmatch(r"https://[a-z0-9.-]+\.azurecontainerapps\.io", desk_origin):
    raise ValueError("Configure the Azure sign-in and Desk origins.")
broker_secret = os.environ["GMG_FLEX_BROKER_SECRET"].encode()
roster_secret = os.environ["GMG_FLEX_ROSTER_SECRET"]
scope = "openid profile email"
relay_code = re.compile(r"[A-Za-z0-9_-]{43}")
roster_key = re.compile(r"[a-f0-9]{64}")
desk_start = "/api/start?desk=flex"
desk_route = "/api/desk"
linkedin_desk_route = f"{desk_route}?from=linkedin"
landing_origin = "https://green-river-01309971e.5.azurestaticapps.net"
cipher = desk_cipher(web.config["SECRET_KEY"])
desk_css = (Path(__file__).parent / "desk.css").read_text(encoding="utf-8")
desk_style_hash = base64.b64encode(hashlib.sha256(desk_css.encode()).digest()).decode()
tools_script = (Path(__file__).parent / "desk-tools.js").read_text(encoding="utf-8")
tools_script_hash = base64.b64encode(hashlib.sha256(tools_script.encode()).digest()).decode()
tool_labels = {"ask": "Ask GMG", "opportunities": "Opportunities", "expertise": "My expertise"}
people_route = "/api/desk/people"

oauth = OAuth(web)
linkedin_timeout = (2, 4)
oauth.register(
    "linkedin", client_id=os.environ["LINKEDIN_CLIENT_ID"], client_secret=os.environ["LINKEDIN_CLIENT_SECRET"],
    authorize_url="https://www.linkedin.com/oauth/v2/authorization",
    access_token_url="https://www.linkedin.com/oauth/v2/accessToken",
    issuer="https://www.linkedin.com/oauth",
    jwks_uri="https://www.linkedin.com/oauth/openid/jwks",
    userinfo_endpoint="https://api.linkedin.com/v2/userinfo",
    id_token_signing_alg_values_supported=["RS256"],
    client_kwargs={"scope": scope, "token_endpoint_auth_method": "client_secret_post", "default_timeout": linkedin_timeout},
)


@lru_cache(maxsize=1)
def relay_storage():
    client = BlobServiceClient(storage_endpoint(os.environ["GMG_FLEX_RELAY_STORAGE"], "blob"),
                               credential=runtime_identity(), api_version="2023-11-03",
                               connection_timeout=4, read_timeout=8, retry_total=0)
    return client.get_container_client("gmg-auth-relay")


def relay_blob(code):
    return relay_storage().get_blob_client("relay/" + hashlib.sha256(code.encode()).hexdigest())


@web.after_request
def security_headers(response):
    response.headers.setdefault("Cache-Control", "no-store")
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    response.headers.setdefault("Content-Security-Policy", "default-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'none'")
    return response


def sign_in_error(status, use_desk, *, expired=False):
    destination = desk_start if use_desk else "/api/start"
    detail = "LinkedIn couldn’t finish signing you in. Try again in this browser tab."
    if expired:
        detail = "This sign-in attempt is no longer active. Start a new one to open the Community Desk."
    elif status == 503:
        detail = "The sign-in service is temporarily unavailable. Try again in a moment."
    response = desk_page(status=status, sign_in_error=detail, retry=destination)
    response.headers["Referrer-Policy"] = "no-referrer"
    return response


@web.get("/api/ready")
def ready():
    return "Ready"


@web.get("/api/handoff-v1.js")
def handoff_script():
    return (
        "setTimeout(() => { document.getElementById('opening').hidden = false }, 800);\n"
        "document.getElementById('desk').submit();\n",
        200,
        {"Content-Type": "text/javascript; charset=utf-8", "Cache-Control": "public, max-age=86400, immutable"},
    )


@web.get("/api/start")
def start():
    use_desk = not classic_enabled or request.args.get("desk") == "flex"
    session.clear()
    session.permanent = True
    session["starting"] = True
    session["desk"] = use_desk
    try:
        linkedin = oauth.linkedin
        callback_uri = f"{origin}/api/callback/linkedin"
        with OAuth2Session(linkedin.client_id, scope=scope, redirect_uri=callback_uri) as client:
            authorization, state = client.create_authorization_url(linkedin.authorize_url)
        linkedin.save_authorize_data(redirect_uri=callback_uri, state=state)
        return redirect(authorization)
    except (OAuthError, RequestException, KeyError, ValueError):
        session.clear()
        return sign_in_error(503, use_desk)


def verified_email(claims, token):
    if claims.get("email_verified") is True:
        if email := normalize_email(claims.get("email")):
            return email
    if token.get("access_token"):
        try:
            details = oauth.linkedin.userinfo(token=token)
            if details.get("sub") == claims["sub"] and details.get("email_verified") is True:
                return normalize_email(details.get("email")) or None
        except (OAuthError, ValueError):
            pass
    return None


@web.get("/api/callback/linkedin")
def callback():
    if not session.get("starting"):
        return sign_in_error(401, True, expired=True)
    use_desk = not classic_enabled or session.get("desk") is True
    try:
        token = oauth.linkedin.authorize_access_token()
        claims = oauth.linkedin.parse_id_token(token, nonce=None, leeway=60)
        sub = claims.get("sub") if claims else None
        if not isinstance(sub, str) or not 1 <= len(sub) <= 200 or claims.get("nonce") is not None:
            return sign_in_error(401, use_desk)
        name = claims.get("name")
        email = verified_email(claims, token)
        identity = {
            "sub": sub, "name": name[:200] if isinstance(name, str) else None,
            "rosterKey": roster_lookup_key(email, roster_secret),
        }
        if use_desk:
            if not member_key(identity):
                response = desk_page(status=403, denied=True, linkedin_denial=True, login_email=email)
                clear_desk_cookie(response)
                return response
            response = redirect(linkedin_desk_route, 303)
            response.set_cookie(DESK_COOKIE, cipher.encrypt(json.dumps(identity).encode()).decode(),
                                max_age=DESK_SESSION_AGE, secure=True, httponly=True, samesite="Lax", path="/")
            return response
        return handoff_page(identity)
    except MismatchingStateError:
        return sign_in_error(401, use_desk, expired=True)
    except (OAuthError, JoseError, ValueError):
        return sign_in_error(401, use_desk)
    except (AzureError, RequestException, OSError, TypeError):
        return sign_in_error(503, use_desk)
    finally:
        session.clear()


def handoff_page(identity):
    code = token_urlsafe(32)
    relay_blob(code).upload_blob(json.dumps({**identity, "expires": int(time()) + 120}, ensure_ascii=False).encode(), overwrite=False)
    response = make_response(f'''<!doctype html><html lang="en"><meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1"><title>Opening the GMG Community Desk</title>
    <main><p id="opening" role="status" hidden>Opening the Community Desk…</p>
    <form id="desk" method="post" action="{desk_origin}/api/gmg/flex-session">
    <input type="hidden" name="code" value="{code}"><noscript><button>Open the Community Desk</button></noscript></form></main>
    <script src="/api/handoff-v1.js" defer></script></html>''')
    response.headers["Content-Security-Policy"] = f"default-src 'none'; base-uri 'none'; frame-ancestors 'none'; script-src 'self'; form-action {desk_origin}"
    response.headers["Referrer-Policy"] = "origin"
    return response


def member_key(identity):
    key = identity.get("rosterKey") if identity else None
    return lookup_member_key(key, roster_secret) if isinstance(key, str) and roster_key.fullmatch(key) else None


def desk_page(status=200, **content):
    tools_enabled = os.environ.get("GMG_FLEX_TOOLS_ENABLED") == "1"
    show_tools = content.get("authorized") and (tools_enabled or request.args.get("tools") == "preview" or content.get("tool"))
    if show_tools:
        labels = tool_labels
        if (os.getenv("GMG_FLEX_PEOPLE_ENABLED") == "1" or request.args.get("people") == "preview"
                or content.get("tool") == "people"):
            labels = {"people": "By expertise", **tool_labels}
            content["people_route"] = people_route
        content.update(tool_labels=labels, tools_script=tools_script,
                       search_route=desk_route if tools_enabled else f"{desk_route}?tools=preview")
    response = make_response(render_template("desk.html", style=desk_css, landing=landing_origin,
                                             start=desk_start, classic_enabled=classic_enabled, **content), status)
    response.headers["Content-Security-Policy"] = (
        "default-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'; "
        f"style-src 'sha256-{desk_style_hash}'; img-src {landing_origin}; script-src 'sha256-{tools_script_hash}'"
    )
    response.headers["Referrer-Policy"] = "origin"
    return response


def clear_desk_cookie(response):
    response.delete_cookie(DESK_COOKIE, secure=True, httponly=True, samesite="Lax", path="/")


@web.route(desk_route, methods=["GET", "POST"])
def desk():
    if request.method == "POST" and request.headers.get("Origin") != origin:
        return "Forbidden", 403
    identity = desk_identity(cipher, request.cookies.get(DESK_COOKIE))
    if not identity:
        if request.method == "GET" and request.args.get("from") == "linkedin":
            return desk_page(status=401, sign_in_error="GMG couldn’t open your session after sign-in. Try again in this browser tab.",
                             retry=desk_start)
        return desk_page(status=401, sign_in=True)
    try:
        if not member_key(identity):
            return desk_page(status=403, denied=True)
        query = request.form.get("name", "").strip()
        if len(query) > 100:
            return desk_page(status=400, authorized=True, invalid_query=True)
        return desk_page(authorized=True, query=query, matches=exact_members(query))
    except (AzureError, OSError, TypeError, ValueError):
        return desk_page(status=503, authorized=True, unavailable=True)


@web.post("/api/desk/full")
def full_desk():
    if request.headers.get("Origin") != origin:
        return "Forbidden", 403
    identity = desk_identity(cipher, request.cookies.get(DESK_COOKIE))
    try:
        if not member_key(identity):
            return desk_page(status=403, denied=True)
        if not classic_enabled:
            return redirect(desk_route, 303)
        response = handoff_page(identity)
        clear_desk_cookie(response)
        return response
    except (AzureError, OSError, TypeError, ValueError):
        return desk_page(status=503, authorized=True, unavailable=True)


@web.route("/api/desk/<any(ask,opportunities,expertise,people):tool>", methods=["GET", "POST"])
def desk_tool(tool):
    if request.method == "POST" and request.headers.get("Origin") != origin:
        return "Forbidden", 403
    identity = desk_identity(cipher, request.cookies.get(DESK_COOKIE))
    if not identity:
        return desk_page(status=401, sign_in=True)
    title = "Find people by expertise" if tool == "people" else tool_labels[tool]
    details = {"tool": tool, "tool_title": title}
    try:
        member = member_key(identity)
        if not member:
            return desk_page(status=403, denied=True)
        from hosted_inference import MODEL_LABEL

        details["authorized"] = True
        posting = request.method == "POST"
        request.max_content_length = 24_000
        if tool == "people":
            if posting:
                need = request.form.get("need", "").strip()
                place = request.form.get("place", "").strip()
                if not 8 <= len(need) <= 600 or len(place) > 90:
                    return desk_page(status=400, **details, tool_error="Describe your need in 8 to 600 characters and use a location of up to 90 characters.")
                if place.casefold() in ("anywhere", "कुठेही"):
                    place = ""
                from desk_tools import find_people

                details.update(tool_query=need, people_place=place)
                matches, engine = find_people(need, place)
                details["people_matches"] = matches
                if matches.ranking == "model" and engine == MODEL_LABEL:
                    details["tool_model"] = engine
                if engine == "pilot allowance reached":
                    details["tool_notice"] = ("The pilot’s AI allowance is used up. This search uses "
                                              "member profiles and saved expertise from the GMG directory.")
                elif engine == "inference paused":
                    details["tool_notice"] = ("AI matching is paused. These results use GMG member profiles "
                                              "and saved expertise.")
        elif tool == "ask":
            if posting:
                question = request.form.get("question", "").strip()
                if not 1 <= len(question) <= 2000:
                    return desk_page(status=400, **details, tool_error="Enter a question of up to 2,000 characters.")
                from desk_tools import ask_gmg

                details["tool_query"] = question
                answer, engine = ask_gmg(question)
                if engine == MODEL_LABEL:
                    details["tool_model"] = engine
                elif os.environ.get("GMG_FLEX_TOOLS_ENABLED") != "1" and engine != "directory":
                    details["tool_engine"] = engine
                if engine == "pilot allowance reached":
                    details["tool_notice"] = "The pilot’s AI allowance has been reached."
                elif engine == "inference paused":
                    details["tool_notice"] = "AI answers are paused."
                if not answer:
                    if engine == "inference paused":
                        return desk_page(**details)
                    return desk_page(status=503, **details, tool_error="Ask GMG is temporarily unavailable. Try again shortly.")
                details["tool_result"] = answer
        elif tool == "opportunities":
            query = request.form.get("query", "").strip() if posting else ""
            if len(query) > 120:
                return desk_page(status=400, **details, tool_error="Enter up to 120 characters.")
            from desk_tools import opportunities

            details["tool_query"] = query
            details["tool_result"] = opportunities(query)
        else:
            from desk_tools import expertise_form

            expertise = expertise_form(member, request.form.getlist("topics") if posting else None)
            return desk_page(status=422 if expertise.get("error") else 200, **details, expertise=expertise)
        return desk_page(**details)
    except (AzureError, OSError, TypeError, ValueError, KeyError) as error:
        web.logger.warning("GMG Flex %s unavailable (%s)", tool, type(error).__name__)
        if not details.get("authorized"):
            return desk_page(status=503, unavailable=True)
        return desk_page(status=503, **details, tool_error=f"{title} is temporarily unavailable. Try again shortly.")


@web.post("/api/desk/logout")
def desk_logout():
    if request.headers.get("Origin") != origin:
        return "Forbidden", 403
    session.clear()
    response = redirect(url_for("desk_signed_out"), 303)
    clear_desk_cookie(response)
    return response


@web.get("/api/desk/signed-out")
def desk_signed_out():
    if desk_identity(cipher, request.cookies.get(DESK_COOKIE)):
        return redirect(desk_route, 303)
    return desk_page(signed_out=True)


def broker_request():
    supplied = request.headers.get("Authorization", "").encode()
    return compare_digest(supplied, b"Bearer " + broker_secret)


@web.post("/api/exchange")
def exchange():
    if not broker_request():
        return "Unauthorized", 401
    body = request.get_json(silent=True)
    code = body.get("code") if isinstance(body, dict) else None
    if not isinstance(code, str) or not relay_code.fullmatch(code):
        return "Unauthorized", 401
    try:
        blob = relay_blob(code)
        data = blob.download_blob(offset=0, length=4097)
        value = data.readall()
        blob.delete_blob(etag=data.properties.etag, match_condition=MatchConditions.IfNotModified)
        if len(value) > 4096:
            return "Unauthorized", 401
        identity = json.loads(value)
        if identity.pop("expires") <= time():
            return "Unauthorized", 401
        return jsonify(identity)
    except (ResourceNotFoundError, ResourceModifiedError, KeyError, TypeError, ValueError):
        return "Unauthorized", 401
    except AzureError:
        return "Unavailable", 503


@web.post("/api/membership")
def membership():
    if not broker_request():
        return "Unauthorized", 401
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        return "Invalid membership request", 400
    key = body.get("rosterKey") or roster_lookup_key(body.get("email"), roster_secret)
    if not isinstance(key, str) or not roster_key.fullmatch(key):
        return "Invalid membership request", 400
    try:
        member_id = lookup_member_key(key, roster_secret)
        return jsonify(key=expertise_key(member_id) if member_id else None)
    except (AzureError, OSError, TypeError, ValueError):
        return "Membership unavailable", 503


app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)


@app.function_name("http_app_func")
@app.http_type(http_type="wsgi")
@app.route(route="/{*route}", methods=list(func.HttpMethod))
def http_app_func(req: func.HttpRequest, context: func.Context) -> func.HttpResponse:
    unavailable = False

    def forward(environ, start_response):
        def forward_status(status, headers):
            nonlocal unavailable
            # Azure's WSGI adapter throws on 5xx. Preserve explicit retry responses.
            unavailable = status.startswith("503 ")
            return start_response("200 OK" if unavailable else status, headers)

        return web.wsgi_app(environ, forward_status)

    result = func.WsgiMiddleware(forward).handle(req, context)
    if unavailable:
        return func.HttpResponse(result.get_body(), status_code=503, headers=result.headers,
                                 mimetype=result.mimetype, charset=result.charset)
    return result
