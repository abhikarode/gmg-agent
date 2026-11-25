import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Privacy Policy | Garje Marathi AI",
  description: "Privacy policy for the Garje Marathi AI community assistant.",
};

export default function PrivacyPolicyPage() {
  return (
    <main className="policy-page">
      <div className="policy-card">
        <p className="eyebrow">Garje Marathi Global</p>
        <h1>Privacy Policy</h1>
        <p className="policy-updated">Updated November 23, 2026</p>

        <p>
          Garje Marathi AI is a community assistant for Garje Marathi Global. This policy
          explains what information the service uses when you sign in and interact with it.
        </p>

        <h2>Information we receive</h2>
        <p>
          When you sign in, LinkedIn shares your name, email address, profile image, and account
          identifier. We match the verified email from LinkedIn to the private GMG membership
          roster. We also process the messages you send so the assistant can respond. The
          backend records request timing, status, model selection, and message length.
        </p>

        <h2>How we use information</h2>
        <p>
          We use this information to authenticate members, provide community search and
          assistance, maintain service security, and improve reliability. We do not sell personal
          information or use social-network data for advertising.
        </p>
        <p>Your selected expertise topics are visible to other GMG members in directory search. You can update or clear them at any time.</p>

        <h2>Sharing and retention</h2>
        <p>
          Authentication data is processed by the sign-in provider and service infrastructure
          providers required to operate the application. We retain information only as long as
          needed to provide and secure the service, or as required by law.
        </p>

        <h2>Your choices</h2>
        <p>
          You may stop using the service at any time. For privacy questions or requests, contact
          Garje Marathi Global through the official website:
          {" "}
          <a href="https://www.garjemarathi.com/">garjemarathi.com</a>.
        </p>

        <p className="policy-footer">
          This temporary policy is published for the Garje Marathi AI sign-in integration and
          should be reviewed and replaced with the organization&apos;s final legal policy.
        </p>
      </div>
    </main>
  );
}
