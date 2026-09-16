/** @type {import('next').NextConfig} */
const nextConfig = {
  // Deployment target is an S3 bucket in static-website-hosting mode (CloudFront is blocked by
  // an AWS account verification hold — see docs/updates/harshita.md) — no Node server, so this
  // has to be a static export. trailingSlash makes every route emit <route>/index.html, which
  // is what lets S3's own IndexDocument resolution serve a folder-style request correctly.
  output: "export",
  trailingSlash: true,
};

export default nextConfig;
