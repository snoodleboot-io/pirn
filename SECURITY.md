# Security Policy

## Supported Versions

| Version | Supported |
|---------|-----------|
| 0.x (current) | Yes |

pirn is pre-1.0 software. Security fixes are applied to the latest release on the `main` branch. There are no long-term support branches at this time. Users are encouraged to track the latest release.

## Reporting a Vulnerability

**Please do not open a public GitHub issue for security vulnerabilities.** Public disclosure before a fix is available puts all pirn users at risk.

### Option 1 — GitHub Security Advisory (preferred)

Use GitHub's private vulnerability reporting feature:

1. Navigate to the pirn repository on GitHub.
2. Click **Security** → **Advisories** → **Report a vulnerability**.
3. Fill in the advisory form. Your report is visible only to repository maintainers.

GitHub Security Advisories allow coordinated disclosure and, once resolved, automatically generate a CVE.

### Option 2 — Email

Send a report to: **security@\<placeholder — replace with your security contact email\>**

Please encrypt sensitive reports using the maintainer's PGP key (to be published at the above address).

### What to include in your report

- A clear description of the vulnerability and its impact.
- The affected pirn version(s) and component(s).
- Steps to reproduce or a proof-of-concept (even a conceptual one is helpful).
- Any suggested mitigations you have already considered.

### What to expect

| Milestone | Target timeline |
|-----------|----------------|
| Acknowledgement of receipt | Within 2 business days |
| Initial assessment and severity triage | Within 5 business days |
| Fix or mitigation plan communicated to reporter | Within 30 days |
| Public disclosure (coordinated with reporter) | After fix is released, or 90 days from report, whichever comes first |

We follow a coordinated disclosure model. We will keep you informed at each step and will credit you in the security advisory unless you request otherwise.

If you do not receive an acknowledgement within 2 business days, please follow up — your report may not have been received.

## Security Documentation

For a detailed description of pirn's security model, trust boundaries, known findings, and deployment hardening guidance, see [planning/security-analysis.md](planning/security-analysis.md).

## Scope

The following are in scope for vulnerability reports:

- Any pirn Python package code (`pirn/`)
- The YAML pipeline loader (`pirn/yaml_loader/`)
- All backends, emitters, and triggers shipped with pirn
- The `tapestry-check` CLI

The following are out of scope:

- Vulnerabilities in third-party dependencies (please report those to the upstream project; if you believe pirn's use of a vulnerable dependency creates a pirn-specific exploit path, that is in scope)
- Deployment misconfigurations not attributable to pirn's defaults or documentation

## Acknowledgements

We thank all security researchers who responsibly disclose vulnerabilities to us. Contributors will be acknowledged in the relevant GitHub Security Advisory unless they prefer to remain anonymous.
