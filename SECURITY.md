# Security and privacy

This project has no real-order execution or wallet support. Do not add private keys, seed phrases, real wallet examples, names, email addresses, analytics IDs, personal URLs, or machine-specific paths to public source, fixtures, reports, commits, or logs.

The dashboard has no third-party scripts, trackers, external fonts, or automatic wallet discovery. Its automatic startup reads are same-origin static assets. A separately configured worker receives a built-in scenario name or a request to start/stop the fixed-token observer; the browser never uploads imported reports. Worker tokens stay in memory and are never included in exports or browser storage. The browser rejects credential-bearing URLs, insecure remote HTTP, and redirects when sending a token.

The local CLI serves loopback only. A remote worker requires `WORM_WORKER_TOKEN`, exact `WORM_ALLOWED_ORIGINS`, TLS, and a host-level rate limit. Never allow anonymous public simulation jobs. CORS is not authentication; authorization is checked independently. The Docker command disables proxy-header trust. If a reverse proxy is added, it must not turn unauthenticated external clients into trusted loopback clients.

The worker allows one job at a time and retains at most eight job results in memory. The JVM is memory- and time-bounded. Schema errors and simulator failures return generic client messages without local paths or dependency logs. Local runtime data and diagnostic files are ignored by Git.

Live observation uses one fixed public Pons HTTPS endpoint and performs GET requests only. Redirects are rejected. There is no arbitrary URL input, wallet lookup, wallet signature, order request or private blockchain credential. The parser discards account addresses and hashes event identifiers before they enter report state. It retains at most 10,000 deduplication entries and 240 neural frames. Normal dashboard polling returns one frame; full history is fetched only for export. A session lasts one hour by default, and the neural process is terminated when it ends. Indexer data is untrusted and is not presented as independently receipt-verified.

Upstream c302 can include donor labels in generated cell metadata. The adapter removes those optional labels before executing and hashing its output; equations and connectivity are unchanged. Generated raw model files are temporary and are not published.

`npm run check` scans source for common secrets, email addresses, and local paths. This is not a comprehensive privacy guarantee: perform manual staged-diff review before publishing. Hosting providers and GitHub may independently record account/transport metadata; source code cannot anonymize the hosting platform itself. Use non-personal Git author/committer metadata for public commits.

For security reports, use GitHub's private vulnerability reporting when enabled. Do not post credentials or personal information in a public issue.
