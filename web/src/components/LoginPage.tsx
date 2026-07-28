import { useState, type FormEvent } from "react";
import { ArrowLeft, KeyRound, ShieldCheck } from "lucide-react";
import { MouvadahLockup } from "@/components/brand/mouvadah-brand";
import { TechnicalLabel } from "@/components/ui/technical-label";
import { useAuth } from "@/context/AuthContext";

export function LoginPage({
  onBackToLanding,
}: {
  onBackToLanding?: () => void;
}) {
  const { login, loginWithLocalApiKey, providers } = useAuth();
  const [apiKey, setApiKey] = useState("");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const hasProvider = providers.google || providers.local_api_key;

  const submitLocalLogin = async (event: FormEvent) => {
    event.preventDefault();
    setError("");
    setSubmitting(true);
    try {
      await loginWithLocalApiKey(apiKey.trim());
      setApiKey("");
    } catch {
      setError("That API key is invalid, expired, or revoked.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <main className="grid min-h-dvh w-full overflow-x-hidden bg-background text-foreground lg:grid-cols-[0.9fr_1.1fr]">
      <section className="relative hidden border-r border-border bg-surface px-10 py-12 lg:flex lg:flex-col lg:justify-between">
        <MouvadahLockup size="lg" />
        <div className="max-w-lg">
          <TechnicalLabel>Sign in</TechnicalLabel>
          <p className="mt-5 text-5xl font-semibold leading-[0.95] tracking-[-0.05em]">
            Return to your workspace.
          </p>
          <p className="mt-6 max-w-md text-lg leading-relaxed text-muted-foreground">
            Review current work, decisions, evidence, and the next action.
          </p>
        </div>
        <div className="border border-border bg-background">
          {providers.google && (
            <div className="grid grid-cols-[auto_1fr] gap-3 border-b border-border p-4 last:border-b-0">
              <ShieldCheck
                className="mt-0.5 h-4 w-4 text-brand-brass"
                aria-hidden
              />
              <div>
                <p className="text-sm font-semibold">Google sign-in</p>
                <p className="mt-1 text-xs text-muted-foreground">
                  Enabled for this environment.
                </p>
              </div>
            </div>
          )}
          {providers.local_api_key && (
            <div className="grid grid-cols-[auto_1fr] gap-3 border-b border-border p-4 last:border-b-0">
              <KeyRound
                className="mt-0.5 h-4 w-4 text-brand-brass"
                aria-hidden
              />
              <div>
                <p className="text-sm font-semibold">API-key sign-in</p>
                <p className="mt-1 text-xs text-muted-foreground">
                  Enabled for this environment.
                </p>
              </div>
            </div>
          )}
          {!hasProvider && (
            <p className="p-4 text-xs leading-relaxed text-muted-foreground">
              No sign-in method is configured for this environment.
            </p>
          )}
        </div>
      </section>

      <section className="flex min-w-0 items-center justify-center px-5 py-10 sm:px-8">
        <div className="w-full max-w-md">
          <div className="mb-10 lg:hidden">
            <MouvadahLockup size="lg" />
            <p className="mt-3 text-sm text-muted-foreground">
              Accountable human-agent software delivery.
            </p>
          </div>

          {onBackToLanding ? (
            <button
              type="button"
              onClick={onBackToLanding}
              className="focus-ring transition-fast mb-8 flex min-h-11 w-fit items-center gap-2 rounded-sm text-xs text-muted-foreground hover:text-foreground"
            >
              <ArrowLeft className="h-3.5 w-3.5" aria-hidden />
              Back to overview
            </button>
          ) : null}

          <h1 className="text-3xl font-semibold tracking-tight">
            Sign in to Mouvadah
          </h1>
          <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
            Use a sign-in method available in this environment.
          </p>

          <div className="mt-8 flex w-full flex-col gap-5">
            {providers.google && (
              <div className="rounded-sm border border-border bg-card p-4">
                <p className="technical-label mb-3">Google sign-in</p>
                <button
                  type="button"
                  onClick={login}
                  disabled={submitting}
                  className="focus-ring transition-fast flex min-h-11 w-full items-center justify-center gap-3 rounded-sm border border-border bg-background px-4 py-3 text-sm font-semibold hover:border-brand-brass hover:bg-accent disabled:cursor-not-allowed disabled:opacity-50"
                >
                  <svg
                    width="18"
                    height="18"
                    viewBox="0 0 24 24"
                    aria-hidden="true"
                  >
                    <path
                      fill="#4285F4"
                      d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
                    />
                    <path
                      fill="#34A853"
                      d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
                    />
                    <path
                      fill="#FBBC05"
                      d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"
                    />
                    <path
                      fill="#EA4335"
                      d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
                    />
                  </svg>
                  Continue with Google
                </button>
                <p className="mt-3 text-xs leading-relaxed text-muted-foreground">
                  Your configured provider returns you to this same workspace
                  entry. Pending invitations resume after authentication.
                </p>
              </div>
            )}

            {providers.local_api_key && (
              <form
                className="rounded-sm border border-border bg-card p-4"
                onSubmit={submitLocalLogin}
              >
                <p className="technical-label mb-3">API-key sign-in</p>
                <label
                  className="mb-2 block text-xs font-semibold"
                  htmlFor="local-api-key"
                >
                  Local API key
                </label>
                <input
                  id="local-api-key"
                  type="password"
                  autoComplete="off"
                  spellCheck={false}
                  value={apiKey}
                  onChange={(event) => setApiKey(event.target.value)}
                  aria-describedby="local-api-key-help"
                  aria-invalid={error ? true : undefined}
                  placeholder="mouvadah_…"
                  className="focus-ring min-h-11 w-full rounded-sm border border-input bg-background px-3 font-mono text-sm outline-none"
                />
                {error && (
                  <p
                    role="alert"
                    aria-live="assertive"
                    className="mt-2 text-xs text-destructive"
                  >
                    {error}
                  </p>
                )}
                <button
                  type="submit"
                  disabled={submitting || apiKey.trim().length === 0}
                  className="focus-ring transition-fast mt-3 min-h-11 w-full rounded-sm bg-primary px-4 py-3 text-sm font-semibold text-primary-foreground hover:bg-brand-brass hover:text-brand-brass-foreground disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {submitting ? "Exchanging key…" : "Continue with API key"}
                </button>
                <p
                  id="local-api-key-help"
                  className="mt-3 text-xs leading-relaxed text-muted-foreground"
                >
                  Created by <code>python3 bootstrap.py</code>. The secret stays
                  masked, is exchanged for an HttpOnly browser session, and is
                  never saved by this UI.
                </p>
              </form>
            )}

            {!hasProvider && (
              <div
                role="status"
                className="rounded-sm border border-warning/40 bg-warning/10 p-4"
              >
                <p className="text-sm font-semibold">
                  No sign-in method is configured
                </p>
                <p className="mt-2 text-xs leading-relaxed text-muted-foreground">
                  If you run Mouvadah locally, run{" "}
                  <code>python3 bootstrap.py</code>, then refresh. Otherwise,
                  ask the deployment operator to configure Google sign-in or
                  API-key access.
                </p>
              </div>
            )}
          </div>
        </div>
      </section>
    </main>
  );
}
