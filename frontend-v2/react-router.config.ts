import type { Config } from "@react-router/dev/config";

export default {
  // Build as SPA (no server-side rendering)
  ssr: false,

  // Build output directory
  buildDirectory: "./build",

  // App directory
  appDirectory: "./app",
} satisfies Config;
