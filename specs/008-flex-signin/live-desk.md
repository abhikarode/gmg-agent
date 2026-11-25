# Live Flex Desk rollout

The public sign-in entry opens a usable, membership-gated exact search on Flex. The Azure Function and Container App remain on demand. The existing full Desk stays available through a one-time session handoff for semantic matching, Ask GMG, opportunities, and expertise. The public pilot keeps its $10 monthly limit.

## Implementation

1. Expose an opt-in `/api/start?desk=flex` on the existing linked-in callback. After LinkedIn OIDC, validate the keyed roster and issue an encrypted first-party session. Recheck membership on every protected request. Keep the existing `/api/start` handoff as the rollback entry.
2. Read the private published snapshot with the Function's managed identity. Limit its grant to direct reads of the roster, manifest, and versioned snapshots. Build a cached exact-name index and render only directory-card fields. Keep the search input out of URLs and claim scope limited to member access.
3. Verify route tests, security checks, and the repository verifier. Deploy the backwards-compatible Flex code first, keeping the previous ZIP and static landing. Verify production member sign-in, a known exact search, denied anonymous access, and the existing full Desk handoff before publishing the public landing. Re-test the public path after the switch and record the time and Azure cost.

## Rollback

Republish the prior public landing, which points to `/api/start`. The existing Container Apps Desk remains the default for the legacy entry. If Flex code itself needs a rollback, redeploy the previous ZIP and restore the original roster-only condition on its directory role assignment.
