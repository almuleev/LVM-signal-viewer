# Security Policy

## Supported Versions

Only the latest release receives fixes. Please reproduce issues on the most
recent [release](https://github.com/almuleev/LVM-signal-viewer/releases/latest)
or the current `main` branch before reporting.

## Reporting a Vulnerability

LVM Signal Viewer is an offline desktop application that reads local data files.
The most likely security-relevant issues are crashes or unexpected behavior when
parsing malformed `.lvm` / `.txt` input.

If you find a vulnerability:

1. Open a [private security advisory](https://github.com/almuleev/LVM-signal-viewer/security/advisories/new),
   or email the maintainer if you prefer.
2. Include OS, Python version, app version/commit, and steps to reproduce.
3. Attach a minimal sample file when the issue is parser-related (remove any
   sensitive measurement data first).

Please do not open a public issue for sensitive reports until a fix is available.
We aim to acknowledge reports within a few days.
