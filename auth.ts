import NextAuth from "next-auth";
import GitHub from "next-auth/providers/github";

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

const providers = [
  GitHub({
    clientId: process.env.GITHUB_CLIENT_ID!,
    clientSecret: process.env.GITHUB_CLIENT_SECRET!,
  }),
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
