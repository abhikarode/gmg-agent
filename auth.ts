import NextAuth from "next-auth";
import GitHub, { type GithubProfile } from "next-auth/providers/github";
import type { OAuthConfig } from "next-auth/providers/oauth";

const LinkedInOIDC = (options: { clientId: string; clientSecret: string }) => ({
  id: "linkedin",
  name: "LinkedIn",
  type: "oauth" as const,
  wellKnown: "https://www.linkedin.com/oauth/.well-known/openid-configuration",
  authorization: { params: { scope: "openid profile email" } },
  idToken: true,
  client: { token_endpoint_auth_method: "client_secret_post" as const },
  profile(profile: { sub: string; name?: string; email?: string; picture?: string }) {
    return { id: profile.sub, name: profile.name, email: profile.email, image: profile.picture };
  },
  options,
});

const githubProvider: OAuthConfig<GithubProfile> = {
  ...GitHub({
    clientId: process.env.GITHUB_CLIENT_ID!,
    clientSecret: process.env.GITHUB_CLIENT_SECRET!,
  }),
  // next-auth 4.x builds an openid-client Issuer for every OAuth provider.
  // GitHub's built-in definition omits this metadata, which causes the
  // callback to fail with "issuer must be configured on the issuer".
  issuer: "https://github.com/login/oauth",
  token: {
    async request({ params, provider }) {
      const response = await fetch("https://github.com/login/oauth/access_token", {
        method: "POST",
        headers: {
          Accept: "application/json",
          "Content-Type": "application/x-www-form-urlencoded",
        },
        body: new URLSearchParams({
          client_id: process.env.GITHUB_CLIENT_ID!,
          client_secret: process.env.GITHUB_CLIENT_SECRET!,
          code: String(params.code),
          redirect_uri: provider.callbackUrl,
        }),
      });

      const tokens = await response.json();
      if (!response.ok || !tokens.access_token) {
        throw new Error(`GitHub token exchange failed: ${tokens.error ?? response.status}`);
      }
      return { tokens };
    },
  },
};

const providers = [
  githubProvider,
  ...(process.env.LINKEDIN_CLIENT_ID && process.env.LINKEDIN_CLIENT_SECRET
    ? [
        LinkedInOIDC({
          clientId: process.env.LINKEDIN_CLIENT_ID,
          clientSecret: process.env.LINKEDIN_CLIENT_SECRET,
        }),
      ]
    : []),
];

export const config = {
  providers,
  pages: {
    signIn: "/login",
  },
};

export const { auth, signIn, signOut } = NextAuth(config);
