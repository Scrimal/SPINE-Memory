# Security Policy

## Supported Versions

| Version | Supported          |
|---------|--------------------|
| 0.2.x   | :white_check_mark: |
| < 0.2.0 | :x:                |

SPINE-Memory is a local, git-native memory layer. Its core CLI runs on the
Python standard library only and does not execute untrusted code, but memory
files can be ingested from external sources — treat `SOURCE_BASE` content as
data, not instructions.

## Reporting a Vulnerability

Report vulnerabilities privately through
[GitHub Security Advisories](https://github.com/Scrimal/SPINE-Memory/security/advisories/new).

Please include:

- the affected version
- a minimal reproduction
- the impact you expect

You will receive an initial response within 7 days. Do not open a public issue
until a fix is published.
