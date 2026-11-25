# GMG membership and expertise

1. Any successful LinkedIn OpenID Connect sign-in can establish a session. A verified email must map to one current GMG membership before the session can use the directory, opportunities, chat or expertise editor. Unmatched and ambiguous emails receive the same access screen and API denial. A membership service outage fails closed.
2. The private membership index comes from authenticated AlmaShines records that have no recorded departure. The publisher excludes ambiguous email-to-member mappings and supports operator-confirmed email aliases for eligible records. Only keyed email hashes and stable directory IDs go to the membership Blob. Source emails and the index do not enter client responses or model prompts.
3. Members choose up to eight expertise topics from a versioned catalog. They can replace or clear their own choices. Input outside the catalog is rejected server-side. Choices persist in Table Storage and enter search as member-reported expertise. The write target derives from the session.
4. Azure keeps existing inference limits and uses existing storage and managed identity. The Hackathon test covers a matched member, a signed-in unmatched account, save and reload, and discovery of a selected skill. Check email mismatches privately and resolve ambiguous records before granting access.

## Implementation and acceptance

Publish the membership index and configure the expertise table before cutting traffic to a revision. Verify the identity and membership matrix, catalog validation and bounded storage writes, persistence across process restart, and current English and Marathi search behavior. Preserve the previous healthy revision for rollback.
