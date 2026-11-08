#!/usr/bin/env python3
"""Generate profile stats SVGs from GitHub's GraphQL API."""

import html
import json
import os
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

LOGIN = os.environ.get("GITHUB_USERNAME", "Alan5598")
TOKEN = os.environ["PROFILE_STATS_TOKEN"]
OUTPUT = Path("assets")

QUERY = """
query($login: String!, $cursor: String) {
  user(login: $login) {
    contributionsCollection {
      contributionCalendar {
        totalContributions
        weeks { contributionDays { contributionCount date } }
      }
    }
    repositories(
      ownerAffiliations: OWNER
      privacy: PUBLIC
      first: 100
      after: $cursor
    ) {
      nodes {
        stargazerCount
        forkCount
        languages(first: 10, orderBy: {field: SIZE, direction: DESC}) {
          edges { size node { name color } }
        }
      }
      pageInfo { hasNextPage endCursor }
    }
  }
}
"""


def github_user(cursor=None):
    payload = json.dumps({
        "query": QUERY,
        "variables": {"login": LOGIN, "cursor": cursor},
    }).encode()

    request = urllib.request.Request(
        "https://api.github.com/graphql",
        data=payload,
        headers={
            "Authorization": f"Bearer {TOKEN}",
            "Content-Type": "application/json",
            "User-Agent": "profile-readme-stats",
        },
    )

    with urllib.request.urlopen(request, timeout=30) as response:
        result = json.load(response)

    if result.get("errors"):
        details = "; ".join(error["message"] for error in result["errors"])
        raise RuntimeError(f"GitHub GraphQL error: {details}")

    user = result["data"]["user"]
    if user is None:
        raise RuntimeError(f"GitHub user {LOGIN!r} was not found")
    return user


def start_svg(width, height, description):
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img" aria-label="{html.escape(description)}">'
        '<rect width="100%" height="100%" rx="16" fill="#0B1020"/>'
        f'<rect x="1" y="1" width="{width - 2}" height="{height - 2}" '
        'rx="15" fill="none" stroke="#26324B"/>'
    )


def text(x, y, value, size=13, color="#C4B5FD", weight=400):
    return (
        f'<text x="{x}" y="{y}" fill="{color}" '
        'font-family="Arial,sans-serif" '
        f'font-size="{size}" font-weight="{weight}">'
        f'{html.escape(str(value))}</text>'
    )


def save_svg(filename, content):
    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / filename).write_text(content + "</svg>\n", encoding="utf-8")


def make_stats(calendar, repos):
    metrics = [
        ("CONTRIBUTIONS · 1 YEAR", calendar["totalContributions"], "#22D3EE"),
        ("PUBLIC REPOSITORIES", len(repos), "#A855F7"),
        ("STARS EARNED", sum(repo["stargazerCount"] for repo in repos), "#22D3EE"),
        ("FORKS", sum(repo["forkCount"] for repo in repos), "#A855F7"),
    ]

    svg = [
        start_svg(920, 210, f"GitHub stats for {LOGIN}"),
        text(30, 38, f"{LOGIN} / GITHUB OVERVIEW", 15, "#22D3EE", 700),
        text(30, 62, "Public profile metrics", 12, "#94A3B8"),
    ]

    for index, (heading, value, accent) in enumerate(metrics):
        x = 30 + index * 220
        svg.extend([
            f'<rect x="{x}" y="82" width="200" height="82" rx="12" '
            'fill="#111A2E" stroke="#26324B"/>',
            text(x + 14, 108, heading, 10, "#94A3B8", 600),
            text(x + 14, 145, f"{value:,}", 27, accent, 700),
        ])

    updated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    svg.append(text(30, 192, f"Updated {updated} · GitHub API", 10, "#64748B"))
    save_svg("stats.svg", "".join(svg))


def make_languages(repos):
    sizes = Counter()
    colors = {}

    for repo in repos:
        for edge in repo["languages"]["edges"]:
            language = edge["node"]["name"]
            sizes[language] += edge["size"]
            colors[language] = edge["node"].get("color") or "#22D3EE"

    top_languages = sizes.most_common(6)
    total_bytes = sum(sizes.values())
    svg = [
        start_svg(460, 250, "Most-used languages in public repositories"),
        text(22, 32, "MOST-USED LANGUAGES", 14, "#22D3EE", 700),
    ]

    if not top_languages:
        svg.append(text(22, 75, "No public language data available.", 13, "#94A3B8"))

    for index, (language, byte_count) in enumerate(top_languages):
        y = 70 + index * 27
        percentage = byte_count * 100 / total_bytes if total_bytes else 0
        color = html.escape(colors[language])
        bar_width = 190 * percentage / 100

        svg.extend([
            f'<circle cx="28" cy="{y - 4}" r="5" fill="{color}"/>',
            text(42, y, language, 12, "#E2E8F0", 600),
            f'<rect x="170" y="{y - 12}" width="190" height="8" '
            'rx="4" fill="#1E293B"/>',
            f'<rect x="170" y="{y - 12}" width="{bar_width:.1f}" '
            f'height="8" rx="4" fill="{color}"/>',
            text(375, y, f"{percentage:.1f}%", 11, "#C4B5FD", 600),
        ])

    svg.append(text(22, 228, "Language share by bytes in public repositories", 10, "#64748B"))
    save_svg("languages.svg", "".join(svg))


def make_contributions(calendar):
    weeks = calendar["weeks"][-53:]
    cell_size, gap = 10, 4
    left, top = 42, 48
    colors = ["#151D30", "#164E63", "#0E7490", "#22D3EE", "#A855F7"]

    svg = [
        start_svg(820, 160, f"{LOGIN} contribution heatmap"),
        text(22, 27, "CONTRIBUTION ACTIVITY · PAST YEAR", 13, "#22D3EE", 700),
    ]

    for day_index, day_name in [(0, "Mon"), (2, "Wed"), (4, "Fri")]:
        svg.append(text(7, top + day_index * (cell_size + gap) + 9,
                        day_name, 8, "#94A3B8"))

    for week_index, week in enumerate(weeks):
        for day in week["contributionDays"]:
            weekday = datetime.strptime(day["date"], "%Y-%m-%d").weekday()
            count = day["contributionCount"]
            level = 0 if count == 0 else 1 if count < 3 else 2 if count < 6 else 3 if count < 10 else 4
            x = left + week_index * (cell_size + gap)
            y = top + weekday * (cell_size + gap)
            title = html.escape(f"{day['date']}: {count} contributions")
            svg.append(
                f'<rect x="{x}" y="{y}" width="{cell_size}" height="{cell_size}" '
                f'rx="2" fill="{colors[level]}"><title>{title}</title></rect>'
            )

    total = calendar["totalContributions"]
    svg.append(text(22, 146, f"{total:,} contributions in the past year", 11, "#C4B5FD", 600))
    for index, color in enumerate(colors):
        svg.append(
            f'<rect x="{650 + index * 13}" y="137" width="9" height="9" '
            f'rx="2" fill="{color}"/>'
        )

    save_svg("contributions.svg", "".join(svg))


def main():
    first_page = github_user()
    calendar = first_page["contributionsCollection"]["contributionCalendar"]
    repos = first_page["repositories"]["nodes"]
    page_info = first_page["repositories"]["pageInfo"]

    while page_info["hasNextPage"]:
        next_page = github_user(page_info["endCursor"])
        repos.extend(next_page["repositories"]["nodes"])
        page_info = next_page["repositories"]["pageInfo"]

    make_stats(calendar, repos)
    make_languages(repos)
    make_contributions(calendar)
    print(f"Generated stats for {LOGIN} from {len(repos)} public repositories.")


if __name__ == "__main__":
    main()
