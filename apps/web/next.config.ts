import type { NextConfig } from "next";

/**
 * Two outputs from one app.
 *
 * `standalone` is what the Docker image and `next start` have always
 * used, and it stays the default: a Node server that renders on demand.
 *
 * `export` is the desktop build. `PLANBENCH_DESKTOP=1` writes a folder
 * of plain files into `out/`, which the API process then serves from its
 * own origin (see `apps/api/planbench_api/static_site.py`). It is gated
 * on an env var rather than a separate config file because the two
 * builds have to stay the same app — a second config is a second app
 * that drifts.
 *
 * `images.unoptimized` is set unconditionally, not only for the export.
 * The optimiser needs a server, so `export` refuses to build without it;
 * setting it in both places keeps the two builds rendering images the
 * same way rather than only the one nobody looks at.
 */
const nextConfig: NextConfig = {
  output: process.env.PLANBENCH_DESKTOP === "1" ? "export" : "standalone",
  images: { unoptimized: true },
};

export default nextConfig;
