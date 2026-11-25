import assert from "node:assert/strict";
import test from "node:test";
import { directoryQuery, memberKey, parseDirectoryResults } from "../directory-results.ts";

test("a directory response yields browseable members and clean profile links", () => {
  const people = parseDirectoryResults(`Found 2 member(s):

**Example Member**
- 🔗 https://www.linkedin.com/in/example/?utm_source=app
- 💼 Software Engineer at Example
- 📍 San Jose, California
- Source: Company and title from LinkedIn export

**Another Member**
- 🔗 https://notlinkedin.com/in/another/
`);
  assert.deepEqual(people, [
    { name: "Example Member", linkedin: "https://www.linkedin.com/in/example/",
      location: "San Jose, California", source: "Company and title from LinkedIn export",
      work: "Software Engineer at Example" },
    { name: "Another Member" },
  ]);
  assert.notEqual(memberKey(people[0]), memberKey(people[1]));
});

test("search uses the existing directory API without assuming that chat prose is a profile", () => {
  assert.equal(directoryQuery("Bay Area", " Design "), "Find members Bay Area Design");
  assert.equal(directoryQuery("", "Example Member"), "Find members Example Member");
  assert.deepEqual(parseDirectoryResults("No members found matching your search."), []);
  assert.deepEqual(parseDirectoryResults("**Example Member**\n- An AI-generated suggestion"), []);
});

test("a reviewed LinkedIn profile summary has its own source label", () => {
  const [member] = parseDirectoryResults(`Found 1 member(s):

**Example Member**
- 🔗 https://www.linkedin.com/in/example/
- LinkedIn profile summary: Builds tools for designers.
`);
  assert.equal(member.summary, "Builds tools for designers.");
  assert.equal(member.summarySource, "LinkedIn profile");
});
