import Link from "next/link";
import { Brand, MissionArt } from "../workspace-brand";

export default function LoginPage() {
  const linkedinEnabled = process.env.NEXT_PUBLIC_LINKEDIN_ENABLED === "true";

  return <main className="auth-shell">
    <section className="auth-content" aria-labelledby="login-heading">
      <Brand priority />
      <h1 id="login-heading">The GMG<br />community desk.</h1>
      <p>Sign in with LinkedIn. GMG members can find people and opportunities and ask the community desk a question.</p>
      {linkedinEnabled
        ? <form action="/api/gmg/sign-in" method="get">
            <button className="solid-action">Continue with LinkedIn <span aria-hidden="true">↗</span></button>
          </form>
        : <button className="solid-action" disabled>Continue with LinkedIn <span aria-hidden="true">↗</span></button>}
      {!linkedinEnabled && <p>LinkedIn sign-in is temporarily unavailable.</p>}
      <p className="privacy-caption"><Link href="/privacy-policy">Privacy policy</Link></p>
    </section>
    <MissionArt />
  </main>;
}
