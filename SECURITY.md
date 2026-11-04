# Security Policy

## Reporting a vulnerability

**Please do not open a public issue for security problems.** Email
security@aiwave.live with:

- What you observed (redact all keys, tokens, and customer data)
- A minimal reproduction, if one exists
- The date you observed it

We aim to acknowledge within 2 business days and to give an initial
assessment within 5 business days. We'll keep you informed as we work on
a fix, and we'll credit you in the release notes if you'd like.

## Scope

- aiwave.live API and console
- SDKs in the [AIWaveAPI organization](https://github.com/AIWaveAPI)
- Public documentation and example code

## Please do not

- Run load tests or automated scans against production without asking first
- Attempt to access other users' data
- Publish details before a fix is available

## Credentials

Never commit API keys. Our examples use environment variables
(`AIWAVE_API_KEY`) and placeholders (`sk-REDACTED`). If you believe a real
key has been exposed, report it via the address above — do not paste the
key itself into a public issue.
