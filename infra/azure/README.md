# GMG Azure pilot package

The live release uses Azure Static Web Apps Free, Azure Functions Flex Consumption and GPT-6 Luna through Azure OpenAI. Start with the [Flex build and restore runbook](flex-auth/README.md). Use `foundation.bicep`, `foundry.bicep`, and `budget.bicep` as supporting infrastructure templates. `app.bicep` and `registry.bicep` cover the legacy Container Apps stack.

The GMG nonprofit billing confirmation covers GPT-6 Luna US Data Zone Standard. Verify the target subscription’s billing eligibility, balance, and expiration before a rollout. The current Flex pilot pauses inference on November 1, 2027 UTC and caps hosted inference calls. The Azure cost budget sends alerts. The inference cutoff applies only to calls initiated by the app.

## Compile locally

Use Python 3.11, the Docker Compose setup in the [project README](../../README.md#rehearse-the-azure-migration-locally), and the standalone [Bicep CLI](https://learn.microsoft.com/azure/azure-resource-manager/bicep/install). The following commands run locally without an Azure account.

```sh
gmg_arm_dir="$(mktemp -d)"
for template in infra/azure/*.bicep; do
  bicep build "$template" --outdir "$gmg_arm_dir" || break
done
python -m unittest discover -s tests -p test_hosted_inference.py -v
```

Set `GMG_TEST_TABLE_CONNECTION_STRING` to a **local Azurite Table** connection string to include the concurrency, restart, and UTC rollover test. The test creates and removes a uniquely named table. The inference tests use a local HTTP server. The regular Compose stack uses Ollama on the Mac.

The Next.js image needs `--build-arg NEXT_PUBLIC_LINKEDIN_ENABLED=true` for the pilot. Build both images for `linux/amd64`. Use `docker build --platform linux/amd64 --target azure -t gmg-agent-api .` for the slim API runtime. Publish only reviewed source revisions and supply private registry image digests. Use `registry.bicep` and pass its `loginServer` as `registryServer` for Azure Container Registry Basic with managed-identity pulls. For GHCR, use the default registry and a narrowly scoped read-only credential. Pass secrets as secure parameters from a protected local file outside the repo and keep the values out of command lines, images, templates, and deployment outputs.

## Supporting infrastructure and legacy Container Apps

1. Use a dedicated resource group in the verified grant-bearing subscription. Review an Azure what-if for each template in the order below. Resolve unexpected billing meters and verify cloud model quota before deploying.
2. Use `budget.bicep` to set a group-level cost alert at 50%, 80%, and 100% of up to $10 per month. Set `startDate` to the first day of the current UTC month and `notificationEmail` to the pilot owner’s address.
3. Use `foundation.bicep` for the [private directory and counter](foundation.bicep). Supply the Entra **object ID** of the approved snapshot publisher. The runtime identity can read the directory container and update the inference table. It has no directory write grant. Shared-key and anonymous Blob access are disabled. Azure Storage service URLs use TLS and require Entra authorization.
4. Publish the approved, minimized snapshot before launching the app. With Azure CLI authenticated as the publisher, set `GMG_BLOB_ACCOUNT_URL` to the foundation output and run `python seed_local_directory.py seed --members /path/to/members.json --jobs /path/to/jobs.json` with the approved enrichment and additions arguments as needed. Also run `python seed_local_directory.py membership --members /path/to/members.json` with the same `GMG_INTERNAL_TOKEN` configured for the app and a private `--aliases` file when needed. Keep the source and aliases local. The membership Blob contains keyed email hashes and member IDs. Review free-text fields before publishing.
5. Use `foundry.bicep` for GPT-6 Luna (OpenAI, version 2026-09-22), East US, Data Zone Standard. Use managed identity with Cognitive Services OpenAI User on the Foundry account and API-key authentication disabled. Follow the [Flex runbook](flex-auth/README.md) for the live Desk.
6. Use `app.bicep` with the foundation's storage and identity names, the image digests, and the configuration above. Only web port 3000 is routed. Its readiness endpoint checks the loopback FastAPI sidecar and the validated directory without invoking a model. Register the template’s `linkedinCallback` output with LinkedIn. Start with a small pilot allowlist and use fresh session and internal API secrets.
7. Verify approved and denied LinkedIn sign-in, anonymous API denial, exact search and jobs during inference outages, the shared allowance, cold start, and release and snapshot rollback. Reconcile an authorized small metered request with the nonprofit balance before admitting wider traffic.

## Public news, events, and sign-in

The public landing page runs on Azure Static Web Apps Free. It serves a snapshot of [GMG NewsCorner](https://www.garjemarathi.com/feed?cat=34556), the event listing, and the logo while the services are idle. **Continue with LinkedIn** opens the Flex sign-in endpoint. The LinkedIn callback verifies membership and establishes the Desk session on the Flex origin. See the [Flex runbook](flex-auth/README.md).

Set the Flex origin in `landing/index.html` for the target environment. Verify each event against a public organizer page before updating the page. Use `data-until` with the event’s local time zone so the listing disappears when the date passes. The build reads the public feed in a signed-out browser context and places the latest three dated headlines in the HTML. A fetch or parse failure aborts the refresh and leaves the last deployed snapshot online.

```sh
gmg_landing="$(mktemp -d)"
npm ci --prefix landing --ignore-scripts
npm exec --prefix landing -- playwright install --with-deps --only-shell chromium
node landing/build.mjs "$gmg_landing"
```

`.github/workflows/refresh-public-landing.yml` refreshes the snapshot daily once the workflow is on the default branch and the `GMG_PUBLIC_LANDING_DEPLOYMENT_TOKEN` Actions secret is configured. The deployment token belongs to the separate `gmg-community-landing` static app.

## Inference allowance

The app template defaults both hosted call limits to zero. A zero limit or a missing or elapsed authorization deadline pauses hosted inference. For the grant-approved deployment, set daily and monthly limits together with an explicit UTC deadline before the sponsorship expires. Both periods are reserved atomically in one Azure Table entity using its ETag.

Every hosted request bounds the UTF-8 wire body and requests at most 500 completion tokens. An ambiguous storage write or a full counter prevents the provider call. A reservation still counts if the provider times out, returns an error, or delivers malformed content. The adapter does not automatically retry. Any separate planner, ranker, or chat correction call needs its own reservation. The Azure cost budget sends alerts. Actual charges follow the Azure meters.

Use `seed_local_directory.py activate <sha256>` with the publisher identity to restore a verified snapshot. Restart the serving revision so its in-memory directory reloads. Keep the last approved image digests available to restore the app separately.

The pilot uses locally redundant storage and authenticated public service endpoints for Storage and Foundry. This supports the Mac publisher and the Consumption app without private networking charges. Checkov flags these design choices and cannot resolve the generated storage name offline. Validate the resulting access rules and accept the pilot’s network and resiliency posture before rollout.
