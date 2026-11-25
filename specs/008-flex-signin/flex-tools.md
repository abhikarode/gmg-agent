# Flex Desk tools

Expose Ask GMG, Opportunities, My expertise, and expertise-based people search on the existing membership-gated Flex Desk. Keep Flex and the fallback Container App on demand. Preserve the $10 monthly pilot budget and the existing full Desk for rollback.

1. Reuse the published directory, Ask GMG agent, job formatter, expertise catalog, per-member expertise row, and shared transactional Nemotron allowance. Use managed identity on the two existing tables and Foundry account. Load tool dependencies on demand so clicking LinkedIn or opening the search form stays light.
2. Stage the tool tabs behind the preview entry. Deny absent and revoked membership, reject foreign-origin writes, render Markdown with HTML disabled, and keep choices within the existing catalog limits. Verify real job results, an actual Ask GMG reply, and an expertise save using the signed-in member before enabling the tabs for everyone.
3. Verify the public paths on Flex, budget, and instance settings. The prior package, prior permission shape, and full Desk link provide rollback.

Expertise search uses the published snapshot, member-selected expertise, and the existing evidence-constrained matching engine. Require a verified member and a same-origin POST for a search. Keep exact-name search available at the current entry point. Render only the recommendation card’s professional evidence, source, and approved profile link. Bound each model call’s read time on Flex and use the existing shared inference counter. If a model call is unavailable, return attributed directory matches when evidence is available.

Stage the new search from `/api/desk?people=preview`. Verify real language and location searches, result evidence and access controls before setting `GMG_FLEX_PEOPLE_ENABLED=1`. After switching, verify the normal Desk links route to Flex and the Container App remains at zero during the search. Reset the flag to `0` to restore the full Desk handoff.

Refresh the Flex workspace around the existing GMG wordmark and Marathi greeting. Keep all tool routes and forms, give expertise search examples that fill the form without sending a request, and make the search engine, location, and supporting evidence easy to scan in results. Use the existing server-rendered templates and inline assets. Verify keyboard and mobile interactions without adding inference calls to page navigation.

When the Desk starts a search, save, or data-loading navigation, lock duplicate submissions immediately and show a delayed, labeled loading mask while the browser waits. Keep the ordinary navigation and forms usable without JavaScript. Restore the controls on browser history return and respect reduced motion.
