# GMG WhatsApp pilot

The pilot uses the existing Azure Container Apps revision and its existing Azure Storage account. It applies a separate WhatsApp quota in the `gmginference` table with the current managed identity. It uses reviewed replies and links to the current deployment’s `/login` page. Its messaging path never invokes hosted inference or the member directory.

## Activation

1. In GMG’s existing Meta business portfolio, create or select a Meta developer app with the WhatsApp use case. Start in development with Meta’s test WhatsApp number, a scoped test access token and a small group of consenting test recipients. Keep the test number separate from the existing Hackathon group.
2. Keep the unchanged Azure parameters for the current app and run a what-if using the current images and existing resource group. Build and push the verified web and API images and deploy the new digests together. Supply `whatsappEnabled=true`, `whatsappPhoneNumberId`, `whatsappAppSecret`, `whatsappAccessToken`, `whatsappTesters` (comma-separated international numbers), and a randomly generated `whatsappVerifyToken` through a private parameters file. The default `whatsappMonthlyLimit` is 100. Keep the parameter file outside the repository and enter identical values per environment.
3. Set the callback to `https://<existing-Azure-app-host>/api/whatsapp` in the app’s WhatsApp settings. Enter the verification token in Meta. Subscribe the app to the test WhatsApp Business Account and its `messages` events. Leave the app and test sender in Meta’s test setup during the pilot.
4. Send an inbound text from an enrolled tester to the Meta test number. Try “How do I sign in?”, “Find a mentor”, “How do I update my skills?” and “लॉगिन”. Check that each sends one useful reply and the Azure link, and that sign-in rules still apply on the desk. Review the service-message count. To pause, set `whatsappEnabled=false` and remove the webhook subscription in Meta when you are finished testing.

The ledger counts send attempts, including timeouts and rejections. It keeps hashed message IDs for the current and previous quota periods. Webhooks over 15 minutes old are skipped. A storage outage stops sends until the webhook can be acknowledged safely. If message delivery is unconfirmed after a Graph API call, the tester can send a fresh message.

## Costs

Meta bills its messaging platform separately from Azure. Check the current test-number rules and pricing before using a production sender. The pilot’s own limit applies to GMG pilot replies. If the same number runs another integration, Meta’s free allowance may include that traffic too. Azure pays for existing app activity and small Table transactions; the pilot adds no always-on resources, messaging provider subscription, or LLM calls.

- [Meta WhatsApp setup](https://developers.facebook.com/documentation/business-messaging/whatsapp/get-started)
- [Meta pricing FAQ](https://whatsappbusiness.com/resources/faq/)
- [Azure Container Apps pricing](https://azure.microsoft.com/en-us/pricing/details/container-apps/)
