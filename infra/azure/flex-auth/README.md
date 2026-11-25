# Rebuild and restore the Azure Flex Community Desk

The production Desk is a Python 3.11 Azure Functions Flex Consumption application in West US 3. It runs with 512 MB, zero always-ready instances, a maximum of one instance, and HTTP concurrency of four. The public landing page is a separate [Azure Static Web Apps Free site](../README.md#public-news-events-and-sign-in). Keep infrastructure and Azure settings under the GMG subscription when restoring the service.

## Build the Flex package

From the repository root, build the source ZIP with Python 3.11:

```sh
gmg_build="$(mktemp -d)"
python3 infra/azure/flex-auth/package.py "$gmg_build/gmg-flex.zip"
unzip -l "$gmg_build/gmg-flex.zip"
```

The packager includes the Flex routes, templates and assets, the shared directory and inference modules, and the Python requirements. Azure resolves compatible dependencies during its remote build.

## Configure the Azure app

For a new environment, use the [Microsoft Flex Consumption setup instructions](https://learn.microsoft.com/en-us/azure/azure-functions/flex-consumption-how-to) with Standard LRS host and deployment storage. Enable the system-assigned managed identity. The current host and deployment storage use connection-string settings configured in Azure. Keep the private application directory, tables, and Foundry account access on managed identity.

| Azure app setting | Production configuration |
| --- | --- |
| `GMG_FLEX_ORIGIN`, `GMG_DESK_ORIGIN` | Exact HTTPS Flex origin. `GMG_DESK_ORIGIN` is the former Container App’s HTTPS origin for the optional Classic handoff. |
| `LINKEDIN_CLIENT_ID`, `LINKEDIN_CLIENT_SECRET` | OAuth credentials from the authorized LinkedIn developer app. Register `<Flex origin>/api/callback/linkedin` with the OpenID Connect sign-in product. |
| `GMG_FLEX_SESSION_SECRET`, `GMG_FLEX_BROKER_SECRET`, `GMG_FLEX_ROSTER_SECRET` | Separate protected values. The roster secret must match the key used to publish the membership index. Rotate it together with that index. |
| `GMG_BLOB_ACCOUNT_URL`, `GMG_FLEX_RELAY_STORAGE` | Private data and relay accounts’ HTTPS Blob service URLs. Grant the Flex identity Blob Data Reader on the directory container with the existing condition for individual reads of `membership.json`, `current.json`, and `snapshots/*.json`. The optional Classic relay uses Blob Data Contributor on `gmg-auth-relay`. |
| `GMG_EXPERTISE_TABLE_URL`, `GMG_QUOTA_TABLE_URL` | HTTPS Table service endpoints. Grant Storage Table Data Contributor on `gmgexpertise` and `gmginference`. |
| `GMG_INFERENCE_PROVIDER`, `GMG_FOUNDRY_ENDPOINT` | `azure-openai` and the Azure OpenAI or Foundry account endpoint. Grant the identity Cognitive Services OpenAI User and deploy `gpt-6-luna` version `2026-09-22`, US Data Zone Standard, in East US. |
| `GMG_INFERENCE_DAILY_CALLS`, `GMG_INFERENCE_MONTHLY_CALLS`, `GMG_INFERENCE_AUTHORIZED_UNTIL` | `500`, `4000`, and `2027-11-01T00:00:00Z` for the current pilot. Confirm grant eligibility and dates for another subscription. |
| `GMG_FLEX_TOOLS_ENABLED`, `GMG_FLEX_PEOPLE_ENABLED`, `GMG_FLEX_CLASSIC_ENABLED` | Set the first two settings to `1`. Leave the Classic switch unset so the retired Container App can stay stopped. |

The directory and roster live in private Blob Storage. For a fresh environment, an authorized publisher can set `GMG_BLOB_ACCOUNT_URL` and run the commands below with private files stored outside the checkout. Provide the Flex roster key to the publisher as `GMG_INTERNAL_TOKEN` through a protected environment. Member-authored expertise and the counters live in private Tables. Keep those tables when rebuilding the application.

```sh
python3 seed_local_directory.py seed --members /path/to/members.json --jobs /path/to/jobs.json
python3 seed_local_directory.py membership --members /path/to/members.json
```

Pass `--aliases /path/to/private-aliases.json` to the membership command when restoring verified alias mappings. See the [data source notes](../../../README.md#refresh-the-data) for export and enrichment options.

## Apply a reviewed build

Use the existing resource group and Flex app for an in-place restore, or the corresponding names in an approved replacement environment:

```sh
az functionapp deployment source config-zip \
  --resource-group "$GMG_RESOURCE_GROUP" --name "$GMG_FUNCTION_APP" \
  --src "$gmg_build/gmg-flex.zip" --build-remote true
```

Verify the active deployment in Azure and check LinkedIn sign-in for an approved member and a denied account. Check member search, expertise matching, Ask GMG, Opportunities, My expertise, anonymous denial, and sign-out. Check the directory fallback and the notice when no hosted inference allowance is available. Verify scale-to-zero, the grant scope, and the resource-group cost budget before pointing the public landing page to a replacement app.

For local verification, install the Flex requirements, run `python3 -m unittest discover -s infra/azure/flex-auth -p test_desk.py`, and install Playwright with `npm ci --prefix landing` and `npm exec --prefix landing -- playwright install chromium webkit`. Then run `node --test landing/tests/flex-sign-in.test.mjs` for the browser flow with synthetic LinkedIn and member accounts.
