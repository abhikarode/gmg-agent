import { auth } from "./auth";

export default auth((req: { auth: { user?: { id: string } } | null; nextUrl: { pathname: string } }) => {
  const isLoggedIn = !!req.auth?.user;
  const isOnChat = req.nextUrl.pathname.startsWith("/");

  if (isOnChat && !isLoggedIn) {
    const newUrl = new URL("/login", "http://localhost:3000");
    return Response.redirect(newUrl);
  }
});

export const config = {
  matcher: ["/((?!api|_next/static|_next/image|favicon.ico|logo.png).*)"],
};
