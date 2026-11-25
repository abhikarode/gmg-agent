# Nemotron and Bay Area member enrichment

## Constitution

AlmaShines determines GMG membership and remains the source of record for existing profile fields. The assistant answers directory lookups from verified records. Local imports must be repeatable, minimize contact data, and preserve the original data.

## User stories

1. A GMG user can ask a general community question and receive an answer from the installed Nemotron 3.5 Lightning model by default.
2. A GMG user can find existing members by employment or city when an authorized Bay Area source fills those gaps.
3. An operator can preview and apply the import locally. Ambiguous identities and conflicts are excluded. Names alone never establish identity, and spreadsheet emails never enter the runtime index.

## Clarifications

The three supplied workbooks are the new sources. The plain LinkedIn export provides job details. The raw list provides explicitly recorded cities. The enriched workbook is a cross-check, because its name-based email joins are not reliable enough to establish identity. Membership, jobs, and existing AlmaShines profile data stay authoritative. The public test uses the existing Vercel hostname and LinkedIn callback.

## Acceptance

- General chat selects and runs the installed Nemotron model. Existing explicit model choices still work.
- Import produces a separate, local overlay containing only approved field types, source labels, and stable member IDs. Duplicate keys and contradictory identifiers do not produce updates.
- The agent finds imported company, title, and city data without changing the member or job counts. Missing or malformed enrichment leaves the base directory usable.
- The public site starts LinkedIn federated login. Directory routes deny anonymous requests on both Vercel and the tunnel. A tester completes the callback and runs a real query.
