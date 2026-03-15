import { useState } from "react";
import { ArrowTrendingUpIcon } from "@heroicons/react/24/outline";
import { useSearchParams, Link } from "react-router";

export function clientLoader({ request }: { request: Request }) {
  return null;
}

export default function ResetPassword() {
  const [searchParams] = useSearchParams();
  const token = searchParams.get("token") || "";
  const email = searchParams.get("email") || "";

  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState("");
  const [success, setSuccess] = useState(false);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");

    if (password !== confirmPassword) {
      setError("Passwords do not match");
      return;
    }

    setLoading(true);
    try {
      const response = await fetch("/api/auth/reset-password", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, token, new_password: password }),
      });

      if (!response.ok) {
        const data = await response.json();
        throw new Error(data.detail || "Failed to reset password");
      }

      setSuccess(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong");
    } finally {
      setLoading(false);
    }
  };

  if (!token || !email) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-gradient-to-br from-blue-50 via-white to-emerald-50 dark:from-zinc-950 dark:via-zinc-950/85 dark:to-zinc-900">
        <div className="w-full max-w-md px-4">
          <div className="rounded-3xl border border-white/60 bg-white/80 p-8 shadow-2xl backdrop-blur-xl dark:border-white/10 dark:bg-white/5">
            <p className="text-center text-red-600 dark:text-red-400">Invalid reset link. Please request a new one.</p>
            <div className="mt-4 text-center">
              <Link to="/login" className="text-sm text-blue-600 hover:text-blue-700 dark:text-blue-400">Back to Sign In</Link>
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="relative flex min-h-screen items-center justify-center overflow-hidden bg-gradient-to-br from-blue-50 via-white to-emerald-50 dark:from-zinc-950 dark:via-zinc-950/85 dark:to-zinc-900">
      <div className="pointer-events-none absolute inset-0">
        <div className="absolute -top-16 left-1/3 h-48 w-48 rounded-full bg-blue-200/40 blur-3xl dark:bg-blue-500/20" />
        <div className="absolute bottom-0 left-0 h-72 w-72 -translate-x-1/2 rounded-full bg-emerald-200/40 blur-3xl dark:bg-emerald-500/15" />
      </div>

      <div className="relative z-10 w-full max-w-md px-4 py-12">
        <div className="rounded-3xl border border-white/60 bg-white/80 p-8 shadow-2xl shadow-blue-500/10 backdrop-blur-xl dark:border-white/10 dark:bg-white/5 dark:shadow-black/40">
          <div className="flex justify-center">
            <div className="flex h-16 w-16 items-center justify-center rounded-2xl border border-white/70 bg-white/90 shadow-md dark:border-white/15 dark:bg-white/10">
              <ArrowTrendingUpIcon className="h-10 w-10 text-blue-600 dark:text-blue-400" />
            </div>
          </div>

          <h1 className="mt-6 text-center text-3xl font-bold tracking-tight text-zinc-900 dark:text-white">
            Reset Password
          </h1>
          <p className="mt-3 text-center text-sm text-zinc-600 dark:text-zinc-400">
            Enter your new password for <strong>{email}</strong>
          </p>

          {success ? (
            <div className="mt-6">
              <div className="rounded-lg bg-emerald-50 p-4 text-sm text-emerald-700 dark:bg-emerald-900/20 dark:text-emerald-400">
                Password reset successfully!
              </div>
              <div className="mt-4 text-center">
                <Link
                  to="/login"
                  className="inline-block rounded-full bg-blue-600 px-6 py-3 text-sm font-semibold text-white shadow-lg hover:bg-blue-700"
                >
                  Sign In
                </Link>
              </div>
            </div>
          ) : (
            <>
              {error && (
                <div className="mt-4 rounded-lg bg-red-50 p-3 text-sm text-red-600 dark:bg-red-900/20 dark:text-red-400">
                  {error}
                </div>
              )}

              <form onSubmit={handleSubmit} className="mt-6 space-y-4">
                <div>
                  <label htmlFor="password" className="block text-sm font-medium text-zinc-700 dark:text-zinc-300">
                    New Password
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

                <div>
                  <label htmlFor="confirm-password" className="block text-sm font-medium text-zinc-700 dark:text-zinc-300">
                    Confirm Password
                  </label>
                  <input
                    id="confirm-password"
                    type="password"
                    value={confirmPassword}
                    onChange={(e) => setConfirmPassword(e.target.value)}
                    required
                    minLength={6}
                    className="mt-1 block w-full rounded-xl border border-zinc-200 bg-white px-4 py-3 text-sm text-zinc-900 placeholder-zinc-400 focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/20 dark:border-white/10 dark:bg-white/5 dark:text-white dark:placeholder-zinc-500"
                    placeholder="Re-enter password"
                  />
                </div>

                <button
                  type="submit"
                  disabled={loading}
                  className="w-full rounded-full bg-blue-600 px-5 py-3 text-sm font-semibold text-white shadow-lg shadow-blue-500/25 transition-all duration-300 hover:-translate-y-0.5 hover:bg-blue-700 hover:shadow-xl disabled:opacity-50"
                >
                  {loading ? "Resetting..." : "Reset Password"}
                </button>
              </form>
            </>
          )}

          <div className="mt-6 text-center">
            <Link to="/login" className="text-sm text-blue-600 hover:text-blue-700 dark:text-blue-400 dark:hover:text-blue-300">
              Back to Sign In
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}
