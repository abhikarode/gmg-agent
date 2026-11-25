# Approved LinkedIn access and community desk

## Scope and principles

Give access to contacts from the supplied LinkedIn list whose export includes a unique original email, plus the three named profiles. Use the lowest amount of identity data needed. The enrichment workbook does not confer access. Public profiles identify which records to review, but LinkedIn OpenID Connect does not expose the public URL as a login claim.

Make the member finder the default signed-in page. Give people a place and expertise filter with browsable results and a shortlist for the current visit. Put opportunities and open-ended chat in separate destinations. Use the official logo served on the Garje Marathi Global website. Keep the production URL and the existing Mac backend.

## Acceptance

- An approved, verified LinkedIn email receives access. Anonymous visitors get 401, and authenticated sessions without an approved LinkedIn identity get 403 on chat and stats. An empty allowlist denies everyone.
- Recheck approval on every directory request. Pre-upgrade sessions must sign in again and cannot access data until then.
- The responsive browser workflow supports choosing a starting point, asking a question, reading and copying the response, starting a new question, and signing out. The login and denied states clearly explain access.
- The member finder returns real profiles, shows explainable match fields and source labels where available, and keeps a shortlist across searches during the current visit. The user can remove entries and copy the list without contacting anyone.
- The logo returns to the signed-in home screen and clears the conversation without losing the current visit’s shortlist.

## Verification plan

Run the repository's checks, inspect desktop and mobile screenshots, and exercise the local production build with signed test sessions and the real Mac directory. Stage the public Vercel deployment, verify anonymous access is denied, then have the owner complete an approved LinkedIn login.

November 18, 2026: Abhi confirmed he signed in with LinkedIn and reached the new public community desk after the verified-email fallback was deployed. Adit and Anand were configured, but their sign-ins have not been observed.
