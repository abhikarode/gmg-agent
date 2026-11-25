function normalizeEmail(email: unknown): string | undefined {
  if (typeof email !== "string") return;
  const normalized = email.trim().toLowerCase();
  if (normalized.length <= 254 && /^[^\s@,;]+@[^\s@,;]+\.[a-z]{2,}$/.test(normalized)) return normalized;
}

type LinkedInClaims = {
  sub?: unknown;
  email?: unknown;
  email_verified?: unknown;
};

export async function completeLinkedInClaims<T extends LinkedInClaims>(
  claims: T,
  userinfo: () => Promise<LinkedInClaims>,
): Promise<T> {
  if (verifiedLinkedInEmail("linkedin", typeof claims.sub === "string" ? claims.sub : undefined, claims)) {
    return claims;
  }
  try {
    const details = await userinfo();
    if (typeof claims.sub === "string" && claims.sub && details.sub === claims.sub &&
        details.email_verified === true && normalizeEmail(details.email)) {
      return { ...claims, email: details.email, email_verified: true };
    }
  } catch {
    // The original claims remain authoritative if LinkedIn's userinfo service is unavailable.
  }
  return claims;
}

export function verifiedLinkedInEmail(
  provider: string | undefined,
  accountId: string | undefined,
  profile: LinkedInClaims | undefined,
): string | undefined {
  if (provider !== "linkedin" || !accountId || profile?.sub !== accountId ||
      profile.email_verified !== true) return;
  return normalizeEmail(profile.email);
}

