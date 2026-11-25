# GMG Community Desk

The Community Desk helps Garje Marathi Global members find people, share expertise, and discover opportunities in the Marathi community.

[Open the Community Desk](https://green-river-01309971e.5.azurestaticapps.net/) · [Build and restore on Azure](infra/azure/flex-auth/README.md)

## For members

- **Find people** by name, or describe the help you need to find members with relevant experience.
- **Ask GMG** about the community and its programs.
- **Explore opportunities** and update **My expertise** so other members can find you.

Sign in with LinkedIn. Desk features require a verified LinkedIn email that matches an active GMG membership. The public landing page also shows GMG news and events.

## For maintainers

The live GMG Community Desk runs on **Azure Static Web Apps Free** and **Azure Functions Flex Consumption**. Flex handles LinkedIn sign-in, membership verification, people search, Ask GMG, Opportunities, and expertise updates. The member directory and membership index use private Azure Blob Storage. Azure Tables hold member expertise and inference counters, and Azure OpenAI GPT-6 Luna supports conversational answers and expertise matching.

Use the [Azure runbook](infra/azure/README.md) and [Flex build and restore instructions](infra/azure/flex-auth/README.md) to reproduce the current release from source. An authorized GMG administrator supplies LinkedIn credentials, application secrets, and the private data separately.

The Next.js and FastAPI stack below is available for local development with Ollama and for legacy deployments. Exact member and job searches use the directory directly. Search results can show recorded LinkedIn profile links and source-labeled summaries.

## Run locally

1. Install dependencies with `npm ci` and `python3 -m pip install -r requirements.txt` in your Python environment.
2. Copy `.env.example` to `.env.local` if there is no local configuration yet. Set the LinkedIn credentials, a unique `NEXTAUTH_SECRET`, and the matching LinkedIn callback URL (`http://localhost:3000/api/auth/callback/linkedin` for local development).
3. Start Ollama and check that `ollama list` shows `nemotron-3.5-lightning:latest`.
4. Start the backend with `python3 -m uvicorn api:app --host 127.0.0.1 --port 8000` and the frontend with `npm run dev`.

The `auto` and `fast` model profiles prefer Nemotron 3.5 Lightning, then installed fallback models including Qwen and Mistral. Set `OLLAMA_MODEL` to override `auto`, `OLLAMA_HOST` to change the Ollama server, or `OLLAMA_TIMEOUT_SECONDS` to change the backend's default 100-second deadline. Cold model loading can take a minute or more. The model is kept warm for ten minutes after inference. Exact member, job, and count lookups run directly against the local index.

## Refresh the data

Run `python3 refresh_data.py` with configured AlmaShines credentials to refresh `almashines_data.json`. Use `GMG_DATA_FILE` to select an alternate snapshot.

For a members-only export, run `python3 refresh_data.py --members-out "$HOME/Library/Application Support/GMG Agent/exports/members-$(date -u +%Y%m%dT%H%M%SZ).json"`. The export uses the existing AlmaShines `listUsers` integration. It writes a private file only after all pages and profile IDs pass validation. Keep raw exports outside the repository.

The app can include manually approved directory entries through `GMG_DIRECTORY_ADDITIONS_FILE`. Point it at a private JSON file with `{"version":1,"members":[{"name":"Example Member","linkedin":"https://www.linkedin.com/in/example/"}]}` and restart FastAPI after changes. An optional `linkedin_profile_summary` accepts a short, manually reviewed summary and is labeled as sourced from the LinkedIn profile. Records are matched by LinkedIn profile and persist across AlmaShines refreshes. LinkedIn sign-in access is configured separately.

For the Bay Area import, install `requirements-import.txt` in the same Python environment and run:

```sh
python3 import_bay_area.py \
  --contacts "/path/to/Bay Area 1700 connects (1).xlsx" \
  --linkedin "/path/to/Bay_Area_LinkedIn_Matches.xlsx" \
  --email-review "/path/to/Bay_Area_LinkedIn_Matches_with_Emails.xlsx"
```

The default is a preview with aggregate counts. Run the same command with `--apply` to save the local `bay_area_enrichment.json` sidecar. It is optional and ignored by Git. Use `--output` and `GMG_ENRICHMENT_FILE` for a different path. Re-run the import after refreshing the AlmaShines snapshot and restart the backend to reload it.

The LinkedIn export fills missing company, title, and profile links for one-to-one matches. The Bay Area contact sheet fills a missing city when its original email identifies one member and the directory location is compatible. The enriched email workbook can flag a conflicting identity but cannot establish a match. The app retains only allowed profile fields and source labels. Spreadsheet emails and unmatched people stay out of the runtime index. Directory results omit personal email addresses and phone numbers. The source doesn't verify that job titles and cities are current.

Try “Find members in the Bay Area”, “Find Bay Area members with marketing experience”, and “How many members are in the Bay Area?”

## Rehearse the Azure migration locally

The [Azure pilot package](infra/azure/README.md) contains the Bicep templates, offline validation steps, and the billing approval gate.

Docker Compose runs Next.js, FastAPI on the same loopback network namespace, and Azurite Blob Storage. Ollama runs on the Mac and must already have `nemotron-3.5-lightning:latest`. Only Next.js is published on the host at `http://localhost:13097`.

1. Put a member export in a private directory outside the repository. Prepare optional job, enrichment, and manual-additions JSON files there too. The job file uses a top-level `jobs` array.
2. Create a private Compose environment file such as `~/Library/Application Support/GMG Agent/local-compose.env`. Set `GMG_LOCAL_EXPORTS` to that absolute input directory and `GMG_LOCAL_UID` and `GMG_LOCAL_GID` to the output of `id -u` and `id -g`. Set independent values for `NEXTAUTH_SECRET` and `GMG_INTERNAL_TOKEN` with `openssl rand -hex 32` and for `GMG_LOCAL_STORAGE_KEY` with `openssl rand -base64 32`. Restrict the file to your user with `chmod 600`.
3. To sign in with LinkedIn, set `LINKEDIN_CLIENT_ID`, `LINKEDIN_CLIENT_SECRET`, and `NEXT_PUBLIC_LINKEDIN_ENABLED=true` before building, and register `http://localhost:13097/api/auth/callback/linkedin` in the corresponding LinkedIn application. If using a different `GMG_LOCAL_PORT`, update the registered callback to match.
4. Build, seed, and start the stack. Omit the optional flags for files you do not have.

```sh
gmg_env="$HOME/Library/Application Support/GMG Agent/local-compose.env"
docker compose --env-file "$gmg_env" -f compose.local.yml up -d --wait azurite
docker compose --env-file "$gmg_env" -f compose.local.yml build desk api
docker compose --env-file "$gmg_env" -f compose.local.yml run --rm snapshot seed \
  --members /input/members.json --jobs /input/jobs.json \
  --enrichment /input/enrichment.json --additions /input/additions.json
docker compose --env-file "$gmg_env" -f compose.local.yml up -d --wait desk api
```

After seeding, run `docker compose --env-file "$gmg_env" -f compose.local.yml run --rm snapshot membership --members /input/members.json`. This publishes the separate private membership roster and initializes the expertise table. Only the seeding container reads the input files. It publishes a field-limited snapshot to a named Azurite volume and verifies its checksum before switching the active manifest. To refresh, reseed and restart `api` to clear its in-memory snapshot. To roll back, run the snapshot container with `activate <sha256>` and restart `api` again. `docker compose ... down` stops the local stack and preserves its Azurite volume.

## Legacy deployment

Set `GMG_API_URL` on Vercel to the HTTPS tunnel URL ending in `/api`. Set a fresh, shared `GMG_INTERNAL_TOKEN` in the Vercel and backend environments. Start FastAPI with `GMG_REQUIRE_API_TOKEN=1` and bind it to loopback. The proxy checks the user's LinkedIn session; FastAPI checks the shared token on the chat and stats routes. Put `NEXTAUTH_URL`, `NEXTAUTH_SECRET`, and the LinkedIn credentials in Vercel's environment, and register the production LinkedIn callback URL. Upgrade these components together because the frontend now talks to its own server rather than making direct browser requests to the tunnel.

LinkedIn sign-in establishes identity. The Community Desk checks the verified LinkedIn email against the private membership roster derived from active AlmaShines records. Use the `membership` seed command with `--aliases /path/to/private-aliases.json` to add operator-confirmed email mappings. The alias file is a JSON object mapping email addresses to active AlmaShines member IDs. Keep it outside the repository. A refreshed roster takes effect within 30 seconds. The membership publisher and API share `GMG_INTERNAL_TOKEN` to derive email hashes, so publish a roster with the new key when rotating it.

Docker Compose mounts the local AlmaShines snapshot. If you use `docker run` directly, mount the snapshot read-only and set `GMG_DATA_FILE` to its container path. Set `OLLAMA_HOST` to an Ollama server reachable from the container. For enrichment, mount the overlay read-only and set `GMG_ENRICHMENT_FILE` to its container path. No snapshots, overlays, or workbooks are included in the image.

## Verify

Run `python3 -m unittest discover -s tests` and `~/.codex/bin/codex-verify`. Verify the new backend on loopback before changing the public tunnel or the Vercel deployment.
