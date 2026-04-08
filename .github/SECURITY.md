# Security Policy

## Supported Versions

| Version | Supported          |
|---------|--------------------|
| 2.x     | Yes                |
| 1.x     | No (upstream, unmaintained) |

## Reporting a Vulnerability

If you discover a security vulnerability, please report it responsibly:

1. **Do NOT** open a public GitHub issue
2. Email **torkian@mac.com** with details
3. Include steps to reproduce if possible
4. You'll receive a response within 48 hours

## Security Measures

This project uses:
- **CodeQL** — automated static analysis on every push
- **pip-audit** — dependency vulnerability scanning in CI
- **Dependabot** — automated dependency updates
- **OAuth token redaction** — sensitive tokens are never logged

## Known Considerations

- Never commit `.env` files or credentials
- Use OAuth or API Key auth in production (not basic auth)
- ServiceNow instance URLs and credentials should be passed via environment variables
