# docassert-action

Run [docassert](https://github.com/c4g-john/docassert) — unit testing for
business documents — in GitHub Actions with one `uses:` line. Validates
documents against their audit criteria, checks cross-document traceability, and
builds the derived status site.

Part of [PMO as Code](https://c4g-john.github.io/pmo-as-code/). New repo?
Start from the [template](https://github.com/c4g-john/pmo-as-code-template)
instead — it wires all of this up for you.

## Usage

```yaml
name: docassert audit
on: [pull_request]
permissions:
  contents: read
  pull-requests: write        # lets the action post results as a PR comment

jobs:
  audit:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0       # needed for changed-only
      - uses: c4g-john/docassert-action@v1
        with:
          command: validate
          changed-only: 'true'
          anthropic-api-key: ${{ secrets.ANTHROPIC_API_KEY }}   # optional

  consistency:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: c4g-john/docassert-action@v1
        with:
          command: consistency
          anthropic-api-key: ${{ secrets.ANTHROPIC_API_KEY }}   # optional
```

Make the gate binding with branch protection requiring the `audit` and
`consistency` checks.

## Inputs

| Input | Default | What it does |
|---|---|---|
| `command` | `validate` | `validate` · `consistency` (registry check + graph + RTM) · `pages` (build `_site/`) · `projects-check` |
| `paths` | `documents/**/*.md` | Globs for `validate`. |
| `changed-only` | `false` | On a PR, validate only the changed documents (checkout needs `fetch-depth: 0`). |
| `version` | *(latest)* | Pin a docassert version, e.g. `1.0.0`. |
| `extras` | `ai` | pip extras; empty string installs the bare package. |
| `comment` | `true` | Post the result as a PR comment (needs `pull-requests: write`). |
| `anthropic-api-key` | *(empty)* | Enables AI advisory checks; structural checks gate without it. |

## Publishing the status site

```yaml
name: status dashboard
on:
  push:
    branches: [main]
permissions:
  contents: read
  pages: write
  id-token: write

jobs:
  build-deploy:
    runs-on: ubuntu-latest
    environment:
      name: github-pages
    steps:
      - uses: actions/checkout@v4
      - uses: c4g-john/docassert-action@v1
        with:
          command: pages
      - uses: actions/configure-pages@v5
      - uses: actions/upload-pages-artifact@v3
        with:
          path: _site
      - uses: actions/deploy-pages@v4
```

One-time: Settings → Pages → Source: **GitHub Actions**.

## License

Apache-2.0 — © 2026 C4G Enterprises Inc.
