# Security Policy

## Supported Versions

This repository tracks upstream releases. The latest commit on the default branch is the only supported version.

## Reporting a Vulnerability

Please report security vulnerabilities privately via GitHub Security Advisories:

1. Go to the repository's **Security** tab.
2. Click **Report a vulnerability**.
3. Provide:
   - A description of the issue
   - Steps to reproduce
   - Potential impact
   - Any suggested mitigations

You will receive an initial response within 7 days. If the report is confirmed, a fix will be prepared privately and released with an advisory.

Please do **not** open public issues for security problems.

## Scope

This repository is a NixOS rEFInd bootloader module with theme packaging. Security scope covers:

- **Theme validation** — PE binary injection, LogoFAIL-class oversized images, path traversal, symlinks
- **ESP write safety** — atomic writes, orphan cleanup, crash resilience
- **Build-time supply-chain** — unpinned inputs, missing hash verification
- **Installer privilege** — runs as root via boot.loader.external; must not expose escalation paths
- **Misconfigured CI secrets or tokens**

Upstream rEFInd vulnerabilities should be reported to the rEFInd project directly.
