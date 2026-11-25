"""Serve the real Flex WSGI routes and a synthetic OAuth provider on separate sites."""

import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from time import time
from unittest.mock import patch
from urllib.parse import parse_qs, urlencode

import azure.functions as func
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
from joserfc import jwt
from joserfc.jwk import RSAKey
from requests import Response
from requests.exceptions import Timeout
from werkzeug import Request, Response as WsgiResponse
from werkzeug.serving import WSGIRequestHandler, make_server

project = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(project / "infra/azure/flex-auth"), str(project)]
os.environ.update(
    GMG_FLEX_ORIGIN="https://gmg-fixture.azurewebsites.net",
    GMG_FLEX_CLASSIC_ENABLED="0",
    GMG_FLEX_SESSION_SECRET="synthetic-desk-secret",
    GMG_FLEX_BROKER_SECRET="synthetic-broker",
    GMG_FLEX_ROSTER_SECRET="synthetic-roster",
    LINKEDIN_CLIENT_ID="synthetic-client",
    LINKEDIN_CLIENT_SECRET="synthetic-client-secret",
)

import function_app as flex
from membership import roster_lookup_key

handler = flex.app.get_functions()[0].get_user_function()
linkedin = flex.oauth.linkedin
signing_key = RSAKey.generate_key(auto_kid=True)
member_email = "member@example.test"
roster_key = roster_lookup_key(member_email, flex.roster_secret)
landing = project / "landing"
landing_html = (landing / "index.html").read_text(encoding="utf-8")
landing_assets = {
    "/landing.css": (landing / "landing.css", "text/css"),
    "/landing-flex-desk.js": (landing / "landing.js", "text/javascript"),
    "/garje-marathi-logo.png": (project / "public/garje-marathi-logo.png", "image/png"),
    "/gmg-favicon.jpg": (project / "app/icon.jpg", "image/jpeg"),
}


def provider_response(request, **kwargs):
    if request.url == linkedin.server_metadata["jwks_uri"]:
        payload = {"keys": [signing_key.as_dict()]}
    else:
        assert request.url == linkedin.access_token_url
        code = parse_qs(request.body)["code"][0]
        if code == "timeout":
            raise Timeout
        email = "unmatched@example.test" if code == "unmatched" else member_email
        token = jwt.encode({"alg": "RS256", "kid": signing_key.kid}, {
            "iss": linkedin.server_metadata["issuer"], "aud": linkedin.client_id,
            "sub": "synthetic-subject", "iat": int(time()), "exp": int(time()) + 120,
            "email": email, "email_verified": True,
        }, signing_key)
        payload = {"access_token": "synthetic", "token_type": "Bearer", "id_token": token}
    response = Response()
    response.status_code = 200
    response.headers["Content-Type"] = "application/json"
    response._content = json.dumps(payload).encode()
    return response


@Request.application
def route(request):
    if request.path == "/":
        return WsgiResponse(landing_html.replace("https://gmg-agent-auth-flex-4dbcc4d1.azurewebsites.net", flex.origin),
                            mimetype="text/html")
    if asset := landing_assets.get(request.path):
        file, mimetype = asset
        return WsgiResponse(file.read_bytes(), mimetype=mimetype)
    if request.path == "/oidc/authorize":
        assert request.host.startswith("localhost:")
        assert flex.web.config["SESSION_COOKIE_NAME"] not in request.cookies
        scenario = request.cookies.get("fixture-scenario", "approved")
        state = "wrong-state" if scenario == "expired" else request.args["state"]
        target = request.args["redirect_uri"]
        assert target == f"{flex.origin}/api/callback/linkedin"
        return WsgiResponse(status=302, headers={"Location": f"{target}?{urlencode({'state': state, 'code': scenario})}"})
    azure_request = func.HttpRequest(request.method, request.url, headers=dict(request.headers), body=request.get_data())
    response = handler(azure_request, None)
    return WsgiResponse(response.get_body(), response.status_code, headers=response.headers.items())


class QuietHandler(WSGIRequestHandler):
    def log_request(self, code="-", size="-"):
        pass


def fixture_tls(directory):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "localhost")])
    now = datetime.now(timezone.utc)
    cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key())
            .serial_number(x509.random_serial_number()).not_valid_before(now - timedelta(minutes=1))
            .not_valid_after(now + timedelta(minutes=10)).sign(key, hashes.SHA256()))
    cert_path, key_path = directory / "fixture.pem", directory / "fixture-key.pem"
    cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    key_path.write_bytes(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                          serialization.NoEncryption()))
    return str(cert_path), str(key_path)


if __name__ == "__main__":
    with TemporaryDirectory() as directory:
        server = make_server("127.0.0.1", 0, route, threaded=True,
                             ssl_context=fixture_tls(Path(directory)), request_handler=QuietHandler)
        # Hostnames differ so browsers apply the normal cross-site cookie rules.
        flex.origin = f"https://127.0.0.1:{server.server_port}"
        flex.landing_origin = f"https://localhost:{server.server_port}"
        linkedin.authorize_url = f"https://localhost:{server.server_port}/oidc/authorize"
        print(server.server_port, flush=True)
        with patch("requests.sessions.Session.send", side_effect=provider_response), \
                patch.object(flex, "lookup_member_key", side_effect=lambda key, _: "fixture-member" if key == roster_key else None), \
                patch.object(flex, "exact_members", return_value=[]):
            server.serve_forever()
