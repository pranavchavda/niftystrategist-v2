import { useState } from "react";
import { ArrowTrendingUpIcon } from "@heroicons/react/24/outline";

// For now, we'll use client-side auth check
export function clientLoader({ request }: { request: Request }) {
  const url = new URL(request.url);
  const tokenParam = url.searchParams.get("token");

  // If callback with token, store it and redirect
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
  const [isRegister, setIsRegister] = useState(false);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);

    try {
      const endpoint = isRegister ? "/api/auth/register" : "/api/auth/login";
      const body = isRegister
        ? { email, password, name }
        : { email, password };

      const response = await fetch(endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });

      if (!response.ok) {
        let message = "Authentication failed";
        try {
          const errData = await response.json();
          message = errData.detail || message;
        } catch {
          // Server returned non-JSON (e.g. "Internal Server Error")
          message = `Server error (${response.status}). Please try again later.`;
        }
        throw new Error(message);
      }

      const data = await response.json();

      // Store token and redirect
      localStorage.setItem("auth_token", data.access_token);
      window.location.href = "/";
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong");
    } finally {
      setLoading(false);
    }
  };

  const handleDevLogin = async () => {
    setLoading(true);
    try {
      const response = await fetch("/api/auth/dev-login");
      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || "Dev login failed");
      }

      localStorage.setItem("auth_token", data.access_token);
      window.location.href = "/";
    } catch (err) {
      // Fallback to old dev token method
      const devToken = "dev-token-" + Date.now();
      localStorage.setItem("auth_token", devToken);
      window.location.href = "/";
    }
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
          AI Trading Assistant
        </div>

        <div className="rounded-3xl border border-white/60 bg-white/80 p-8 shadow-2xl shadow-blue-500/10 backdrop-blur-xl dark:border-white/10 dark:bg-white/5 dark:shadow-black/40">
          <div className="flex justify-center">
            <div className="flex h-16 w-16 items-center justify-center rounded-2xl border border-white/70 bg-white/90 shadow-md dark:border-white/15 dark:bg-white/10">
              <ArrowTrendingUpIcon className="h-10 w-10 text-blue-600 dark:text-blue-400" />
            </div>
          </div>

          <h1 className="mt-6 text-center text-3xl font-bold tracking-tight text-zinc-900 dark:text-white">
            {isRegister ? "Create Account" : "Sign in"}
          </h1>
          <p className="mt-3 text-center text-sm leading-6 text-zinc-600 dark:text-zinc-400">
            AI-powered trading assistant for Indian stock markets
          </p>

          {error && (
            <div className="mt-4 rounded-lg bg-red-50 p-3 text-sm text-red-600 dark:bg-red-900/20 dark:text-red-400">
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit} className="mt-6 space-y-4">
            {isRegister && (
              <div>
                <label htmlFor="name" className="block text-sm font-medium text-zinc-700 dark:text-zinc-300">
                  Name
                </label>
                <input
                  id="name"
                  type="text"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  required={isRegister}
                  className="mt-1 block w-full rounded-xl border border-zinc-200 bg-white px-4 py-3 text-sm text-zinc-900 placeholder-zinc-400 focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/20 dark:border-white/10 dark:bg-white/5 dark:text-white dark:placeholder-zinc-500"
                  placeholder="Your name"
                />
              </div>
            )}

            <div>
              <label htmlFor="email" className="block text-sm font-medium text-zinc-700 dark:text-zinc-300">
                Email
              </label>
              <input
                id="email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                className="mt-1 block w-full rounded-xl border border-zinc-200 bg-white px-4 py-3 text-sm text-zinc-900 placeholder-zinc-400 focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/20 dark:border-white/10 dark:bg-white/5 dark:text-white dark:placeholder-zinc-500"
                placeholder="you@example.com"
              />
            </div>

            <div>
              <label htmlFor="password" className="block text-sm font-medium text-zinc-700 dark:text-zinc-300">
                Password
              </label>
              <input
                id="password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                minLength={6}
                className="mt-1 block w-full rounded-xl border border-zinc-200 bg-white px-4 py-3 text-sm text-zinc-900 placeholder-zinc-400 focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/20 dark:border-white/10 dark:bg-white/5 dark:text-white dark:placeholder-zinc-500"
                placeholder="Min 6 characters"
              />
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full rounded-full bg-blue-600 px-5 py-3 text-sm font-semibold text-white shadow-lg shadow-blue-500/25 transition-all duration-300 hover:-translate-y-0.5 hover:bg-blue-700 hover:shadow-xl disabled:opacity-50 disabled:hover:translate-y-0"
            >
              {loading ? "Please wait..." : isRegister ? "Create Account" : "Sign In"}
            </button>
          </form>

          <div className="mt-6 text-center">
            <button
              onClick={() => {
                setIsRegister(!isRegister);
                setError("");
              }}
              className="text-sm text-blue-600 hover:text-blue-700 dark:text-blue-400 dark:hover:text-blue-300"
            >
              {isRegister ? "Already have an account? Sign in" : "Don't have an account? Register"}
            </button>
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
                disabled={loading}
                className="inline-flex w-full items-center justify-center rounded-full border border-zinc-200/70 bg-zinc-100/80 px-5 py-3 text-sm font-semibold text-zinc-700 transition-all duration-300 hover:-translate-y-0.5 hover:bg-zinc-200 disabled:opacity-50 dark:border-white/10 dark:bg-white/10 dark:text-white dark:hover:bg-white/15"
              >
                Continue in Dev Mode
              </button>
            </div>
          )}

          <p className="mt-10 text-center text-xs text-zinc-500 dark:text-zinc-400">
            Paper trading mode enabled by default. Connect Upstox in Settings for live trading.
          </p>
        </div>
      </div>
    </div>
  );
}
