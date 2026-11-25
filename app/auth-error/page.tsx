import Link from "next/link";
import { Brand } from "../workspace-brand";

export default async function AuthErrorPage({
  searchParams,
}: {
  searchParams: Promise<{ error?: string | string[] }>;
}) {
  const error = (await searchParams).error;
  const denied = error === "AccessDenied" || error === "LinkedInVerifiedEmailUnavailable";
  return <main className="policy-page"><div className="policy-card">
    <Brand />
    <h1>{denied ? "GMG chat access required" : "Sign-in didn’t finish"}</h1>
    <p>{denied
      ? error === "LinkedInVerifiedEmailUnavailable"
        ? "LinkedIn didn’t provide a verified primary email for this sign-in. Check that your primary email is verified in LinkedIn, then try again."
        : "The email LinkedIn shared for this account doesn’t match the GMG access list. If you’re on the list, ask a GMG organizer to check your LinkedIn primary email."
      : "Please return to the login page and try again."}</p>
    <Link href="/login">Back to LinkedIn sign-in</Link>
  </div></main>;
}
