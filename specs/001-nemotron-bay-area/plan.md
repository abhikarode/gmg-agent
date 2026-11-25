# Implementation plan

Use Ollama's installed model inventory to prefer Nemotron for automatic and fast chat. Retain explicit profile choices and provide a fallback for hosts that lack Nemotron. Keep directory lookups deterministic.

Import the workbooks offline, normalize LinkedIn URLs and email identifiers, and make only one-to-one matches against AlmaShines. Use enriched-email conflicts to veto updates, never to add new matches. Apply only missing company and title pairs, missing LinkedIn links from direct export-email matches, and missing cities with compatible state and country. Store no spreadsheet emails and avoid copying spreadsheet data into source control or containers.

Load the overlay before building the local index. Label imported values in search results, maintain a location-specific Bay Area filter, and verify the normal local API against the real snapshot and Ollama.

Keep Vercel and the Mac on the existing public URL and tunnel path. The Next.js server verifies the LinkedIn session before forwarding to FastAPI. FastAPI requires a shared server token on its directory routes when deployed. Stage and verify both components before switching traffic. Public test acceptance requires an anonymous request to receive 401 and an actual signed-in tester to complete the LinkedIn callback and run a directory or model query.
