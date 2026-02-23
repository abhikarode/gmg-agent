import NextAuth from "next-auth";
import GitHub from "next-auth/providers/github";

const config = {
  providers: [
    GitHub({
      clientId: process.env.GITHUB_CLIENT_ID!,
      clientSecret: process.env.GITHUB_CLIENT_SECRET!,
    }),
  ],
  pages: {
    signIn: "/login",
  },
};

export const { auth, signIn, signOut } = NextAuth(config);
