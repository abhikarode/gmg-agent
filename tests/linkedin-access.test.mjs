import assert from "node:assert/strict";
import test from "node:test";
import { completeLinkedInClaims, verifiedLinkedInEmail } from "../linkedin-access.ts";
import { lookupGmgAccess } from "../gmg-backend.ts";

test("a verified LinkedIn account supplies a normalized email for membership", () => {
  const email = verifiedLinkedInEmail("linkedin", "member-1", {
    sub: "member-1", email: " Allowed@Example.test ", email_verified: true,
  });
  assert.equal(email, "allowed@example.test");
});

test("no access for unverified, unrelated, or missing LinkedIn claims", () => {
  const good = { sub: "member-1", email: "allowed@example.test", email_verified: true };
  assert.equal(verifiedLinkedInEmail("linkedin", "member-1", undefined), undefined);
  assert.equal(verifiedLinkedInEmail("other", "member-1", good), undefined);
  assert.equal(verifiedLinkedInEmail("linkedin", "member-2", good), undefined);
  assert.equal(verifiedLinkedInEmail("linkedin", "member-1", { ...good, email_verified: false }), undefined);
  assert.equal(verifiedLinkedInEmail("linkedin", "member-1", { ...good, email_verified: "true" }), undefined);
});

test("membership distinguishes a signed-in nonmember from an unavailable roster", async (t) => {
  const previous = process.env.GMG_INTERNAL_TOKEN;
  process.env.GMG_INTERNAL_TOKEN = "unit-test";
  t.after(() => {
    if (previous === undefined) delete process.env.GMG_INTERNAL_TOKEN;
    else process.env.GMG_INTERNAL_TOKEN = previous;
  });
  const fetch = t.mock.method(globalThis, "fetch", async () => Response.json({ key: null }));
  assert.deepEqual(await lookupGmgAccess(undefined), { status: "email-unverified" });
  assert.equal(fetch.mock.callCount(), 0);
  assert.deepEqual(await lookupGmgAccess("member@example.test"), { status: "unmatched" });
  fetch.mock.mockImplementation(async () => Response.json({ key: "a".repeat(64) }));
  assert.deepEqual(await lookupGmgAccess("member@example.test"), { status: "member", key: "a".repeat(64) });
  fetch.mock.mockImplementation(async () => new Response(null, { status: 503 }));
  assert.deepEqual(await lookupGmgAccess("member@example.test"), { status: "unavailable" });
});

test("userinfo can supply verification only for the validated LinkedIn subject", async () => {
  const claims = { sub: "member-1", email: "same@example.test" };
  const matching = { ...claims, email_verified: true };
  const completed = await completeLinkedInClaims(claims, async () => matching);
  assert.equal(verifiedLinkedInEmail("linkedin", "member-1", completed), claims.email);
  const wrongSubject = await completeLinkedInClaims(claims, async () => ({ ...matching, sub: "someone-else" }));
  assert.deepEqual(wrongSubject, claims);
  const unavailable = await completeLinkedInClaims(claims, async () => { throw new Error("offline"); });
  assert.deepEqual(unavailable, claims);
});

test("Flex rechecks new and existing sessions without falling back after an error", async (t) => {
  const settings = { GMG_FLEX_ACTIVE: "true", GMG_FLEX_AUTH_ORIGIN: "https://fixture.azurewebsites.net", GMG_FLEX_BROKER_SECRET: "fixture" };
  const before = Object.fromEntries(Object.keys(settings).map((key) => [key, process.env[key]]));
  Object.assign(process.env, settings);
  t.after(() => {
    for (const [key, value] of Object.entries(before)) {
      if (value === undefined) delete process.env[key];
      else process.env[key] = value;
    }
  });
  const requests = [];
  const fetch = t.mock.method(globalThis, "fetch", async (url, options) => {
    requests.push({ url, data: JSON.parse(options.body), authorization: options.headers.Authorization });
    return Response.json({ key: "a".repeat(64) });
  });
  const legacyEmail = "member@example.test";
  const rosterKey = "b".repeat(64);
  assert.equal((await lookupGmgAccess(legacyEmail)).status, "member");
  assert.equal((await lookupGmgAccess(undefined, rosterKey)).status, "member");
  assert.deepEqual(requests.map(({ data }) => data), [{ email: legacyEmail }, { rosterKey }]);
  assert.ok(requests.every(({ url, authorization }) => url === `${settings.GMG_FLEX_AUTH_ORIGIN}/api/membership` && authorization === "Bearer fixture"));
  fetch.mock.mockImplementation(async () => new Response(null, { status: 503 }));
  assert.deepEqual(await lookupGmgAccess(legacyEmail), { status: "unavailable" });
  assert.equal(fetch.mock.callCount(), 3);
});
