import NextAuth, { type NextAuthConfig } from "next-auth";
import GitHub from "next-auth/providers/github";

const config: NextAuthConfig = {
  providers: [
    GitHub({
      clientId: process.env.GITHUB_CLIENT_ID!,
      clientSecret: process.env.GITHUB_CLIENT_SECRET!,
    }),
  ],
  callbacks: {
    authorized({ auth, request: { nextUrl } }) {
      const isLoggedIn = !!auth?.user;
      const isOnChat = nextUrl.pathname.startsWith("/");

      if (isOnChat && !isLoggedIn) {
        return false;
      }

      return true;
    },
  },
  pages: {
    signIn: "/login",
  },
};

export const { auth, signIn, signOut } = NextAuth(config);
