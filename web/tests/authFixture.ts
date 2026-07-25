import { createHmac } from "node:crypto";

export const E2E_API_KEY = "taskable_e2e_fixture_key_not_a_secret";
export const E2E_JWT_SECRET = "e2e-jwt-secret-only-for-local-ci-0001";
export const E2E_USER_ID = 1;
export const E2E_EMAIL = "playwright@example.invalid";

function encode(value: object): string {
  return Buffer.from(JSON.stringify(value)).toString("base64url");
}

export function createSessionToken(): string {
  const now = Math.floor(Date.now() / 1000);
  const header = encode({ alg: "HS256", typ: "JWT" });
  const payload = encode({
    sub: String(E2E_USER_ID),
    email: E2E_EMAIL,
    iat: now,
    exp: now + 60 * 60,
  });
  const unsigned = `${header}.${payload}`;
  const signature = createHmac("sha256", E2E_JWT_SECRET)
    .update(unsigned)
    .digest("base64url");
  return `${unsigned}.${signature}`;
}
