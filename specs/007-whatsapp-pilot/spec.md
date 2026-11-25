# GMG WhatsApp Business pilot

Use Meta's test business number on GMG's existing Meta portfolio. Pilot with explicitly enrolled testers and inbound one-to-one text only. Reply to GMG FAQs, LinkedIn sign-in questions, and navigation requests using reviewed English and Marathi text. Send members to the Azure desk to search or edit expertise.

Reuse the existing Azure app, managed identity and inference-counter table. Reserve each reply against a separate monthly WhatsApp limit, with at most 200 send attempts and a default of 100. Deduplicate provider message IDs before sending, fail closed when the ledger is unavailable and never resend an ambiguously delivered reply. Persist only hashed message IDs and the quota month. Validate Meta's challenge, request signature, phone number identity, sender and message age. Keep the webhook disabled unless explicitly configured. The pilot has no template sends or model calls.

Verify the public-to-private webhook path, good and bad signatures, FAQ routing, rejection of unapproved and stale senders and group events, durable retry deduplication and the cost cap. Activate the public callback with GMG credentials only after a Meta test number and testers are available. Require an actual WhatsApp reply from the test number for a live pilot claim.
