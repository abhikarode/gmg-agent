# Move the GMG Community Desk to Azure

Microsoft Billing case 2611200010002566 confirmed nonprofit coverage for all GPT-6 Luna US Data Zone Standard meters on GMG’s subscription. Deploy GPT-6 Luna in East US for the active Flex Desk. The workload must enforce a shared call allowance and stop hosted inference before the verified grant expiration. Directory search remains available when hosted inference is paused.

## Objective

Run the GMG Community Desk on Azure without a live dependency on the Mac, Ollama, or ngrok. Preserve LinkedIn sign-in, the approved-account restriction, the member and job directories, bilingual people matching, and the current interface. Use the lowest-cost combination that meets those requirements.

## Acceptance criteria

| Area | Required behavior |
| --- | --- |
| Access | An approved member completes real LinkedIn sign-in on the Azure hostname. Unapproved and unverified accounts are denied. Anonymous chat, stats, and recommendations return 401. FastAPI is inaccessible from the public Internet. Removing an account from the deployed allowlist revokes its access on the next server check after the change is live. |
| Directory | Exact search, job search, and statistics work without inference. With the current dataset, compare 5,133 people and 36 jobs, or record why an approved refresh changed those counts. Confirm Adit’s exact profile link and LinkedIn summary, Abhi’s Bay Area AI evidence, and the behavior of strict location filters. |
| Assistant | Both English and Marathi requests use recorded evidence. A failed or capped Azure model call leaves exact search, jobs, and the sourced community overview available. The UI identifies directory-only suggestions. |
| Privacy | Cloud storage holds only the approved application dataset. The raw export and workbooks stay in their existing protected workflow. The hosted model receives only the information needed for the question and approved professional evidence. |
| Operations | Measure cold-start latency and memory under realistic traffic. Restore the prior data version and serving revision in a rehearsal. Verify that Azure still serves the app when the Mac and tunnel are unavailable. |
| Cost | Compare current regional rates and eligible deployment types, validate a small real Azure charge against the correct grant billing profile, and record effective costs. Test that the inference limit survives restarts and concurrent requests. |

## Local deployment package

Compile the Bicep templates offline. Rehearse the shared-container topology and storage flow with Docker Compose and Azurite. Use a local HTTP test server for the hosted inference contract and exercise the call limits against Azurite Table Storage. Keep local Ollama as the default. The intended cloud model is Fireworks `FW-Nemotron-Lightning-3.5-30B-A3B` in East US, US Data Zone Standard. Confirm the exact input, cached input, and output meters with Microsoft before any Azure provisioning or hosted inference.

## Planning assumptions to confirm

- GMG wants the existing pilot and workflows moved first. New features such as broad LinkedIn profile synchronization, persistent chat, and cross-region disaster recovery are outside this migration.
- The lowest measured monthly cost is the default. Start with consumption hosting that can scale to zero and no continuously running GPU.
- US Data Zone inference is the proposed starting point. Confirm GMG’s data-handling expectations and Azure subscription quota before enabling live member traffic.
- GMG can use the Azure-generated HTTPS hostname for the pilot. If GMG controls and wants a subdomain, use a durable name such as `agent.garjemarathi.com` for final cutover.
- The grant had $2,000 available and an expiration date of November 20, 2027 when checked on November 20, 2026. Recheck the balance and the subscription’s billing-profile mapping before creating resources.

See the [architecture, cost model, and release plan](plan.md) and [implementation checklist](tasks.md).
