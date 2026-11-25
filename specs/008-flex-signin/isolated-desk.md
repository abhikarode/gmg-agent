# Isolated Flex Desk benchmark

Measure one browser click from an isolated static page through LinkedIn, a test roster match, and an interactive exact-name search on the same Flex origin. Report the first moment the search form is usable and the elapsed time to the first actual result. Measure fresh worker and reused worker separately when those conditions can be observed.

- Use the previous temporary LinkedIn callback, with renewed approval. Preserve the public callback list after the trial. The test uses an authorized LinkedIn account and synthetic directory entries only.
- Reuse the Flex test harness, current OIDC flow, keyed roster checks, and Azure Blob snapshot reader. The Desk uses a short-lived first-party session, rechecks membership on each request, and reads only its own private test storage. Add a same-origin exact-name search and surface when Flex uses a new worker.
- Use one isolated resource group, one Functions Flex app, and a single Standard LRS storage account. Compare on-demand with a brief 512 MB always-ready trial where available. Exclude model requests and paid observability. Check pilot budget and retail run cost, then remove the temporary callback and resource group.
- Verify the actual result in Chrome, the denied anonymous and unmatched paths, and the live app deployment after the experiment. Use a valid result as the acceptance signal. Record sample count and any limitations on generalizing to production.
