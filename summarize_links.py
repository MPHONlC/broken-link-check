import os
import re
import json
import sys
import argparse


CATEGORIES = [
    ('success_map', 'Successful'),
    ('error_map', 'Errors'),
    ('timeout_map', 'Timeouts'),
    ('excluded_map', 'Excluded'),
    ('unsupported_map', 'Unsupported'),
]


def status_code(entry):
    status = entry.get('status') or {}
    return status.get('code')


def status_text(entry):
    status = entry.get('status') or {}
    return status.get('text', 'Unknown')


def reclassify(stats):
    counts = {
        'Successful': 0, 'Errors': 0, 'Timeouts': 0, 'Excluded': 0,
        'Unsupported': 0, 'Auto-excluded (403)': 0,
    }
    per_file = {}
    auto_excluded_total = 0

    for map_key, label in CATEGORIES:
        for source, entries in (stats.get(map_key) or {}).items():
            for e in entries:
                url = e.get('url', '')
                text = status_text(e)
                target_label = label
                if label == 'Errors' and status_code(e) == 403:
                    target_label = 'Auto-excluded (403)'
                    auto_excluded_total += 1
                counts[target_label] += 1
                per_file.setdefault(source, {}).setdefault(target_label, []).append((url, text))

    return counts, per_file, auto_excluded_total


def redirected_urls(stats):
    urls = set()
    for _, entries in (stats.get('redirect_map') or {}).items():
        for e in entries:
            origin = e.get('origin')
            if origin:
                urls.add(origin)
    return urls


def all_urls(stats):
    urls = []
    for map_key, _ in CATEGORIES:
        for _, entries in (stats.get(map_key) or {}).items():
            for e in entries:
                url = e.get('url')
                if url:
                    urls.append(url)
    return urls


def extract_domain(url):
    m = re.match(r'^[a-zA-Z][a-zA-Z0-9+.-]*://([^/]+)', url)
    if not m:
        return None
    host = m.group(1).split('@')[-1].split(':')[0].lower()
    parts = host.split('.')
    if len(parts) >= 2:
        return '.'.join(parts[-2:])
    return host


def edit_distance(a, b):
    if a == b:
        return 0
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        curr = [i] + [0] * len(b)
        for j, cb in enumerate(b, 1):
            cost = 0 if ca == cb else 1
            curr[j] = min(prev[j] + 1, curr[j - 1] + 1, prev[j - 1] + cost)
        prev = curr
    return prev[-1]


def find_domain_typos(urls, max_distance=2):
    domains = {}
    for url in urls:
        d = extract_domain(url)
        if d:
            domains.setdefault(d, set()).add(url)

    unique_domains = sorted(domains.keys())
    flagged = []
    seen_pairs = set()
    for i in range(len(unique_domains)):
        for j in range(i + 1, len(unique_domains)):
            a, b = unique_domains[i], unique_domains[j]
            if abs(len(a) - len(b)) > max_distance:
                continue
            dist = edit_distance(a, b)
            if 0 < dist <= max_distance:
                pair = tuple(sorted((a, b)))
                if pair not in seen_pairs:
                    seen_pairs.add(pair)
                    flagged.append((a, len(domains[a]), b, len(domains[b]), dist))
    return flagged


def build_summary(stats, files_checked):
    out = ["## Broken Link Check", ""]

    counts, per_file, auto_excluded_total = reclassify(stats)
    redirected = redirected_urls(stats)

    out.append("| Status | Count |")
    out.append("|---|---|")
    out.append(f"| Total | {stats.get('total', 0)} |")
    out.append(f"| Unique | {stats.get('unique', 0)} |")
    out.append(f"| Successful | {counts['Successful']} |")
    out.append(f"| Redirected | {stats.get('redirects', 0)} |")
    out.append(f"| Excluded | {counts['Excluded']} |")
    out.append(f"| Auto-excluded (403) | {counts['Auto-excluded (403)']} |")
    out.append(f"| Timeouts | {counts['Timeouts']} |")
    out.append(f"| Unsupported | {counts['Unsupported']} |")
    out.append(f"| Unknown | {stats.get('unknown', 0)} |")
    out.append(f"| Errors | {counts['Errors']} |")
    out.append("")

    if auto_excluded_total:
        out.append(f"{auto_excluded_total} link(s) returned HTTP 403 and were treated as excluded rather than broken - a 403 usually means the site blocks automated requests, not that the link is dead.")
        out.append("")

    out.append("### Per-file breakdown")
    out.append("")
    label_order = ['Successful', 'Errors', 'Timeouts', 'Excluded', 'Auto-excluded (403)', 'Unsupported']
    for f in files_checked:
        out.append(f"**{f}**")
        out.append("")
        categories = per_file.get(f, {})
        if not categories:
            out.append("No links found in this file.")
            out.append("")
            continue
        for label in label_order:
            entries = categories.get(label)
            if not entries:
                continue
            out.append(f"- {label}:")
            for url, text in entries:
                mark = " (redirected)" if url in redirected else ""
                out.append(f"  - `{url}` - {text}{mark}")
        out.append("")

    typos = find_domain_typos(all_urls(stats))
    out.append("### Domain consistency check")
    out.append("")
    if typos:
        out.append("These domains look similar enough that one might be a typo - verify they're meant to be different:")
        out.append("")
        for a, count_a, b, count_b, dist in typos:
            out.append(f"- `{a}` ({count_a} link(s)) vs `{b}` ({count_b} link(s)) - {dist} character(s) different")
    else:
        out.append("No near-duplicate domains found.")
    out.append("")

    return out, counts, typos


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--report', required=True)
    parser.add_argument('--files', required=True, nargs='+')
    parser.add_argument('--fail-on-error', default='true')
    args = parser.parse_args()

    annotations = []

    try:
        with open(args.report) as f:
            stats = json.load(f)
    except FileNotFoundError:
        annotations.append(f"::error::Link check report not found at {args.report} - lychee may have failed to run.")
        emit(["## Broken Link Check", "", "Could not run - see annotations."], annotations)
        sys.exit(1)

    report, counts, typos = build_summary(stats, args.files)

    errors = counts['Errors']
    timeouts = counts['Timeouts']

    if errors or timeouts:
        annotations.append(f"::error::Broken link check found {errors} error(s) and {timeouts} timeout(s) - see the summary above.")
    if typos:
        annotations.append(f"::warning::Found {len(typos)} pair(s) of suspiciously similar domains - see the Domain consistency check section.")

    emit(report, annotations)

    if (errors or timeouts) and args.fail_on_error.lower() == 'true':
        sys.exit(1)


def emit(report_lines, annotations):
    summary_path = os.environ.get('GITHUB_STEP_SUMMARY')
    if summary_path:
        with open(summary_path, 'a') as f:
            f.write('\n'.join(report_lines) + '\n')
    else:
        print('\n'.join(report_lines))
    for a in annotations:
        print(a)


if __name__ == '__main__':
    main()
