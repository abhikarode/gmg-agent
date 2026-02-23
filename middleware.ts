import { auth } from "./auth";

export default auth((req: { auth: { user?: { id: string } } | null; nextUrl: URL }) => {
  const isLoggedIn = !!req.auth?.user;
  const isOnChat = req.nextUrl.pathname.startsWith("/");

  if (isOnChat && !isLoggedIn) {
    const newUrl = new URL("/login", req.nextUrl.origin);
    return Response.redirect(newUrl);
  }
});

export const config = {
  matcher: ["/((?!api|_next/static|_next/image|favicon.ico|logo.png).*)"],
};
