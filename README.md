# Broken Link Check

Checks every link in a set of files with [lychee](https://github.com/lycheeverse/lychee) and reports a full breakdown by status (successful, redirected, excluded, timed out, unsupported, errored) and by file - not just the failures. Excludes `esoui.com` and `uesp.net` by default, since both reject automated requests with a 403.

Any other link that comes back `403 Forbidden` is automatically treated as excluded rather than broken - a 403 almost always means the site blocks bots, not that the link is dead - and reported separately as "Auto-excluded (403)" so it's still visible, just not counted as a failure.

Also runs a domain consistency check across every link in the run: flags pairs of domains that are suspiciously close to each other (a couple of characters apart) as a possible typo, e.g. `facebook.com` vs `faecbook.com`.

## Usage

```yaml
name: Broken Link Check

on:
  push:
    branches: [main]
    paths:
      - 'README.md'
      - 'README_BBCODE.txt'
      - 'README_COMMONMARK.txt'
      - 'CHANGELOG_GFM.txt'
  schedule:
    - cron: '0 12 * * 1'
  workflow_dispatch:

jobs:
  check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v7
      - uses: MPHONlC/broken-link-check@Version-0.0.1
```

## Inputs

| Input | Required | Default | Description |
|---|---|---|---|
| `files` | No | `README.md README_BBCODE.txt README_COMMONMARK.txt CHANGELOG_GFM.txt` | Space-separated list of files to check. |
| `exclude` | No | `https://(www\.esoui\.com\|([a-z0-9-]+\.)?uesp\.net)` | Regex of URLs to skip before they're even requested. |
| `github_token` | No | *(none)* | GitHub token to raise the rate limit on `github.com` links. Pass `${{ secrets.GITHUB_TOKEN }}`. |
| `fail` | No | `true` | Whether a real error or timeout fails the run. Excluded, auto-excluded (403), and redirected links never fail the run. |

## What counts as a mismatch

An input file listed in `files` that doesn't exist in the checkout fails the run immediately with a clear list of which file(s) are missing, instead of an upstream parser error.

A real error (a broken link, a 404, an unreachable host) or a timeout fails the run when `fail` is `true`. An excluded link, an auto-excluded 403, a redirect, or an unsupported URL scheme never does. A domain-typo pairing never fails the run either - it's reported as a warning annotation only.

<details>
<summary>Example step summary output</summary>

````
## Broken Link Check

| Status | Count |
|---|---|
| Total | 6 |
| Unique | 6 |
| Successful | 2 |
| Redirected | 0 |
| Excluded | 1 |
| Auto-excluded (403) | 1 |
| Timeouts | 0 |
| Unsupported | 0 |
| Unknown | 0 |
| Errors | 2 |

1 link(s) returned HTTP 403 and were treated as excluded rather than broken - a 403 usually means the site blocks automated requests, not that the link is dead.

### Per-file breakdown

**README.md**

- Successful:
  - `https://facebook.com/mypage` - 200
  - `https://github.com/MPHONlC/LibAPH` - 200
- Excluded:
  - `https://www.esoui.com/` - Excluded
- Auto-excluded (403):
  - `https://en.uesp.net/wiki/Online:Something` - Rejected status code: 403 Forbidden

**README_BBCODE.txt**

- Errors:
  - `https://example.com/broken` - Rejected status code: 404 Not Found
  - `https://faecbook.com/mypage` - Rejected status code: 404 Not Found

### Domain consistency check

These domains look similar enough that one might be a typo - verify they're meant to be different:

- `facebook.com` (1 link(s)) vs `faecbook.com` (1 link(s)) - 2 character(s) different
````

</details>

## License

MIT - see [LICENSE](LICENSE).
