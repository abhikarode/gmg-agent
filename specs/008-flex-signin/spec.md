# Move GMG authentication to Flex Consumption

## Requirements and decisions

- Azure Functions Flex owns LinkedIn OIDC and membership decisions using the existing private keyed roster. Authenticated unmatched accounts retain the existing access screen. Membership failures deny protected access.
- The public landing page starts sign-in on Flex. Container Apps owns the Desk, its browser session, and the existing Python API for directory, expertise, and inference.
- Establish a Desk session only after a trusted-origin form POST delivers a short-lived, single-use code exchanged through a private server-to-server endpoint. The form and its redirect never put the code in a URL. Preserve existing sessions and recheck current membership for protected requests.
- Run both components on demand. Use one 512 MB Flex worker at most if the region permits it, the existing $10 pilot budget, and the existing Container Apps 0–1 scale configuration.

## Rollout and acceptance

1. Provision Flex with private relay storage. Grant its managed identity read access to the membership blob and scoped access to the relay container. Verify expiry, replay denial, anonymous denial, and roster read access.
2. Stage the Desk integration with its current entry point serving users. Verify a real LinkedIn account can redeem a code, reach the Desk, read directory and expertise data, and use Ask GMG.
3. Enable Flex at both sign-in entry points once the live check passes. Verify the browser flow from the public page, access controls, deployed scaling limits, and the posted budget.
4. Keep the preceding Desk revision and LinkedIn callback available for rollback. The public landing target and the Desk feature flag can be reverted independently.
