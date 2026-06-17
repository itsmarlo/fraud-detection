# Docker CA certificates

If HTTPS traffic is inspected by an organization proxy, export its root CA as a
PEM-encoded certificate and save it in this directory with a `.crt` extension:

```text
certs/company-root-ca.crt
```

Docker installs certificates from this directory before `pip` downloads Python
dependencies. The Dockerfile points `pip`, Python SSL, and Requests at the
updated Debian certificate bundle. Certificate files are ignored by Git.
