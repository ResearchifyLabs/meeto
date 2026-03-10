# Security Policy

## Reporting a Vulnerability

If you discover a security vulnerability in meeto, please report it responsibly.

**Do NOT open a public GitHub issue for security vulnerabilities.**

Instead, please email **care@researchify.io** with:

- A description of the vulnerability
- Steps to reproduce (if applicable)
- The potential impact

We will acknowledge your report within 48 hours and aim to provide a fix within 7 days for critical issues.

## Scope

meeto handles browser sessions and authentication state files. Security concerns particularly relevant to this project include:

- Exposure of Google session credentials (`storage_state.json`)
- Unauthorized access to meeting audio or transcripts
- Injection via meeting URLs or configuration inputs

## Supported Versions

| Version | Supported |
|---------|-----------|
| 0.x.x   | Yes       |
