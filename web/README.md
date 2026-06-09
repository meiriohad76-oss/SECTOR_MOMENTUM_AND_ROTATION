# Sector Momentum Dashboard Web Shell

This is the first Next.js migration shell for B-170. It consumes the optional
FastAPI backend while the production dashboard continues to run in Streamlit.

## Local Run

From this directory:

```bash
npm install
npm run dev
```

By default the shell reads the API from `http://127.0.0.1:8000`.
Override it with:

```bash
NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000 npm run dev
```

The current shell calls:

- `/api/v1/health`
- `/api/v1/data-health`

It does not fetch market providers directly and it does not replace the
Streamlit production route yet.

On this Windows host, npm registry access may need a one-command TLS workaround:

```bash
npm install --strict-ssl=false
```

The committed lockfile keeps the resolved dependency tree stable. The current
QA gate is:

```bash
npm audit --omit=dev --audit-level=moderate
npm run build
```
