import { BuildingStorefrontIcon, ShieldCheckIcon, SparklesIcon } from "@heroicons/react/24/outline";

const logo = new URL("../assets/eblogo.webp", import.meta.url).href;

// For now, we'll use client-side auth check
// In future, we can move to server-side session management
export function clientLoader({ request }: { request: Request }) {
  const url = new URL(request.url);
  const tokenParam = url.searchParams.get("token");

  // If OAuth callback with token, store it and redirect
  if (tokenParam) {
    localStorage.setItem("auth_token", tokenParam);
    throw new Response(null, {
      status: 302,
      headers: { Location: "/" },
    });
  }

  // Check if already authenticated
  const existingToken = localStorage.getItem("auth_token");
  if (existingToken) {
    // Already logged in, redirect to landing page
    throw new Response(null, {
      status: 302,
      headers: { Location: "/" },
    });
  }

  return null;
}



const isDevMode =
  (import.meta as unknown as { env?: { DEV?: boolean } }).env?.DEV ?? false;

export default function Login() {
  // OAuth callback is now handled by clientLoader
  // This component just renders the login UI

  const handleGoogleLogin = () => {
    // Redirect to backend OAuth endpoint
    window.location.href = "/api/auth/google?redirect_to=/login";
  };

  const handleDevLogin = () => {
    // Development mode - skip auth
    const devToken = "dev-token-" + Date.now();
    localStorage.setItem("auth_token", devToken);
    // Use window.location for full page navigation to ensure loader runs
    window.location.href = "/";
  };

  return (
    <div className="relative flex min-h-screen items-center justify-center overflow-hidden bg-gradient-to-br from-blue-50 via-white to-emerald-50 dark:from-zinc-950 dark:via-zinc-950/85 dark:to-zinc-900">
      <div className="pointer-events-none absolute inset-0">
        <div className="absolute -top-16 left-1/3 h-48 w-48 rounded-full bg-blue-200/40 blur-3xl dark:bg-blue-500/20" />
        <div className="absolute bottom-0 left-0 h-72 w-72 -translate-x-1/2 rounded-full bg-emerald-200/40 blur-3xl dark:bg-emerald-500/15" />
        <div className="absolute top-1/2 right-0 h-56 w-56 translate-x-1/3 -translate-y-1/2 rounded-full bg-purple-200/35 blur-3xl dark:bg-purple-500/20" />
      </div>

      <div className="relative z-10 w-full max-w-md px-4 py-12">
        <div className="mb-6 text-center text-xs font-semibold uppercase tracking-[0.45em] text-zinc-500 dark:text-zinc-500">
          iDrinkCoffee.com Internal
        </div>

        <div className="rounded-3xl border border-white/60 bg-white/80 p-8 shadow-2xl shadow-blue-500/10 backdrop-blur-xl dark:border-white/10 dark:bg-white/5 dark:shadow-black/40">
          <div className="flex justify-center">
            <div className="flex h-16 w-16 items-center justify-center rounded-2xl border border-white/70 bg-white/90 shadow-md dark:border-white/15 dark:bg-white/10">
              <img
                src={logo}
                alt="EspressoBot"
                className="h-12 w-12 object-contain"
                draggable="false"
              />
            </div>
          </div>

          <h1 className="mt-6 text-center text-3xl font-bold tracking-tight text-zinc-900 dark:text-white">
            Sign into EspressoBot
          </h1>
          <p className="mt-3 text-center text-sm leading-6 text-zinc-600 dark:text-zinc-400">
            Authenticate to orchestrate EspressoBot workflows
          </p>

          <div className="mt-8 space-y-3">
            <button
              onClick={handleGoogleLogin}
              className="group inline-flex w-full items-center justify-center gap-3 rounded-full border border-zinc-200/70 bg-white/90 px-5 py-3 text-sm font-semibold text-zinc-800 shadow-sm transition-all duration-300 hover:-translate-y-0.5 hover:shadow-lg dark:border-white/15 dark:bg-white/10 dark:text-white"
            >
              <svg className="h-5 w-5" viewBox="0 0 24 24">
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
              <span className="text-sm font-semibold">
                Continue with Google
              </span>
            </button>

            <div className="flex items-center justify-center gap-2 rounded-2xl border border-zinc-200/70 bg-white/80 px-4 py-3 text-xs font-medium uppercase tracking-[0.3em] text-zinc-500 backdrop-blur-sm dark:border-white/10 dark:bg-white/5 dark:text-zinc-400">
              <ShieldCheckIcon className="h-4 w-4" />
              <span>SSO restricted to @idrinkcoffee.com</span>
            </div>
          </div>

          

          {isDevMode && (
            <div className="mt-6 space-y-4">
              <div className="relative">
                <div className="absolute inset-0 flex items-center">
                  <div className="w-full border-t border-zinc-200/70 dark:border-white/10" />
                </div>
                <div className="relative flex justify-center text-[11px] uppercase tracking-[0.4em] text-zinc-400 dark:text-zinc-500">
                  <span className="bg-white/80 px-3 dark:bg-white/5">Dev tools</span>
                </div>
              </div>

              <button
                onClick={handleDevLogin}
                className="inline-flex w-full items-center justify-center rounded-full border border-zinc-200/70 bg-zinc-100/80 px-5 py-3 text-sm font-semibold text-zinc-700 transition-all duration-300 hover:-translate-y-0.5 hover:bg-zinc-200 dark:border-white/10 dark:bg-white/10 dark:text-white dark:hover:bg-white/15"
              >
                Continue in Dev Mode
              </button>
            </div>
          )}

          <p className="mt-10 text-center text-xs text-zinc-500 dark:text-zinc-400">
            Need access? Email <span className="font-medium text-zinc-700 dark:text-zinc-200">pranav@idrinkcoffee.com</span> or message Pranav in Flock to activate your account after you login via Google.
          </p>
        </div>
      </div>
    </div>
  );
}
