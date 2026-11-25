# GMG Community Desk

The Community Desk helps Garje Marathi Global members find people, share expertise, and discover opportunities in the Marathi community.

[Open the Community Desk](https://green-river-01309971e.5.azurestaticapps.net/) · [Browse the Azure source](https://github.com/abhikarode/gmg-agent/tree/codex/azure-release) · [Build and restore on Azure](https://github.com/abhikarode/gmg-agent/blob/codex/azure-release/infra/azure/flex-auth/README.md)

## For members

- **Find people** by name, or describe the help you need to find members with relevant experience.
- **Ask GMG** about the community and its programs.
- **Explore opportunities** and update **My expertise** so other members can find you.

Sign in with LinkedIn. Desk features require a verified LinkedIn email that matches an active GMG membership. The public landing page also shows GMG news and events.

## For maintainers

The live app uses Azure Static Web Apps Free for the landing page and Azure Functions Flex Consumption for LinkedIn sign-in and the Desk. Private Azure Blob Storage holds the directory and membership index. Azure Tables store member expertise and inference counters. Azure OpenAI GPT-6 Luna supports Ask GMG and expertise matching. Exact directory search runs without an AI call.

Use the `codex/azure-release` branch to rebuild the version running on Azure. It contains the Flex package builder, the landing-page build, Bicep templates, and tests.

```sh
git clone --single-branch --branch codex/azure-release https://github.com/abhikarode/gmg-agent.git
cd gmg-agent
python3 infra/azure/flex-auth/package.py gmg-flex.zip
```

The Azure runbook covers restoring the landing site, configuring the Flex app, and publishing private data. Keep credentials, membership exports, and personal data outside Git. [Azure runbook](https://github.com/abhikarode/gmg-agent/blob/codex/azure-release/infra/azure/README.md)
