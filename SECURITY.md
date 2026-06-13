# Security Policy

Thanks for helping keep Ticketly and its users safe.

## Supported versions

Only the **latest release** of Ticketly (on [PyPI](https://pypi.org/project/ticketly/))
receives security fixes. Please upgrade before reporting:

```bash
pipx upgrade ticketly        # or: pip install -U ticketly
```

| Version        | Supported          |
| -------------- | ------------------ |
| Latest release | :white_check_mark: |
| Older releases | :x:                |

## Reporting a vulnerability

**Please do not open a public issue for security problems** — a public report
tips off attackers before a fix is out.

Instead, report it privately through GitHub:

1. Go to the [**Security** tab](https://github.com/Shreyas0786/ticketly/security)
   of the repository.
2. Click **"Report a vulnerability"** to open a private security advisory.

This keeps the report confidential between you and the maintainer until a fix is
released. No email address is needed.

When reporting, please include:

- A clear description of the issue and its impact.
- Steps to reproduce, or a proof of concept.
- The Ticketly version (`ticketly --version`) and your environment.

You can expect an initial response within a few days. Once a fix is ready, the
advisory is published with credit to you, unless you prefer to remain anonymous.

## Scope and design notes

Ticketly is **local by design** — it makes no network calls, uses no API key,
stores no secrets, and only reads and writes the folder you run it in (see
[README — Safe by design](README.md#safe-by-design)). This deliberately keeps
the attack surface small. Reports most relevant to Ticketly include, for example:

- A path-handling flaw that lets it read or write **outside** the current folder.
- A way `ticketly install` could alter files beyond the agent config it documents.
- Unsafe handling of a malicious profile or backlog file.

Vulnerabilities in third-party dependencies should be reported upstream, though
you're welcome to flag them here too if they affect Ticketly directly.
