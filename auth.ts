import type { DefaultSession, NextAuthOptions } from "next-auth";
import type { OAuthConfig } from "next-auth/providers/oauth";
import { completeLinkedInClaims, verifiedLinkedInEmail } from "./linkedin-access";
import { lookupGmgAccess, type GmgAccess } from "./gmg-backend";
import { gmgSessionMaxAge } from "./flex-auth";

declare module "next-auth" {
  interface Session extends DefaultSession {
    gmgAccess: GmgAccess["status"];
  }
}

type Profile = { sub: string; name?: string; email?: string; email_verified?: boolean; picture?: string };

const LinkedInOIDC = (options: { clientId: string; clientSecret: string }): OAuthConfig<Profile> => ({
  id: "linkedin",
  name: "LinkedIn",
  type: "oauth" as const,
  wellKnown: "https://www.linkedin.com/oauth/.well-known/openid-configuration",
  authorization: { params: { scope: "openid profile email" } },
  idToken: true,
  client: { token_endpoint_auth_method: "client_secret_post" as const },
  userinfo: {
    async request({ tokens, client }) {
      if (typeof tokens.claims !== "function") throw new Error("Missing LinkedIn ID token claims");
      const claims = tokens.claims() as Profile;
      return completeLinkedInClaims(claims, async () => {
        if (!tokens.access_token) return {};
        return client.userinfo(tokens.access_token);
      });
    },
  },
  profile(profile) {
    return { id: profile.sub, name: profile.name, email: profile.email, image: profile.picture };
  },
  options,
});

const providers = [
  ...(process.env.LINKEDIN_CLIENT_ID && process.env.LINKEDIN_CLIENT_SECRET
    ? [
        LinkedInOIDC({
          clientId: process.env.LINKEDIN_CLIENT_ID,
          clientSecret: process.env.LINKEDIN_CLIENT_SECRET,
        }),
      ]
    : []),
];

export const config: NextAuthOptions = {
  providers,
  session: { strategy: "jwt", maxAge: gmgSessionMaxAge },
  pages: {
    signIn: "/login",
    error: "/auth-error",
  },
  callbacks: {
    jwt({ token, account, profile }) {
      if (account) {
        token.gmgVerifiedLinkedInEmail = verifiedLinkedInEmail(
          account.provider, account.providerAccountId, profile,
        );
      }
      return token;
    },
    async session({ session, token }) {
      session.gmgAccess = (await lookupGmgAccess(token.gmgVerifiedLinkedInEmail, token.gmgFlexRosterKey)).status;
      return session;
    },
  },
};
