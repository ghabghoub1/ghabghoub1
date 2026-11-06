import os
import json
import html
import urllib.request
from pathlib import Path
from collections import Counter
from datetime import datetime, timezone, timedelta

USERNAME = "ghabghoub1"
TOKEN = os.environ["GITHUB_TOKEN"]

OUTPUT = Path("profile")
OUTPUT.mkdir(exist_ok=True)

API = "https://api.github.com"

HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
    "User-Agent": "github-profile-stats-generator",
}


def github_get(endpoint):
    request = urllib.request.Request(
        API + endpoint,
        headers=HEADERS,
    )

    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def github_graphql(query, variables):
    payload = json.dumps({
        "query": query,
        "variables": variables,
    }).encode("utf-8")

    request = urllib.request.Request(
        "https://api.github.com/graphql",
        data=payload,
        headers={
            **HEADERS,
            "Content-Type": "application/json",
        },
        method="POST",
    )

    with urllib.request.urlopen(request, timeout=30) as response:
        result = json.load(response)

    if result.get("errors"):
        raise RuntimeError(result["errors"])

    return result["data"]


def escape(value):
    return html.escape(str(value), quote=True)


def svg_document(width, height, content):
    return f"""<svg xmlns="http://www.w3.org/2000/svg"
        width="{width}" height="{height}"
        viewBox="0 0 {width} {height}">

        <rect width="100%" height="100%"
              rx="14" fill="#0D1117"/>

        <rect x="1" y="1"
              width="{width - 2}" height="{height - 2}"
              rx="13" fill="none"
              stroke="#30363D"/>

        <style>
          text {{
            font-family: Arial, Helvetica, sans-serif;
          }}
          .title {{
            fill: #38BDF8;
            font-size: 20px;
            font-weight: bold;
          }}
          .label {{
            fill: #8B949E;
            font-size: 14px;
          }}
          .value {{
            fill: #E6EDF3;
            font-size: 22px;
            font-weight: bold;
          }}
        </style>

        {content}
    </svg>"""


def save_svg(filename, content):
    path = OUTPUT / filename
    path.write_text(content, encoding="utf-8")
    print(f"Generated {path}")


def get_repositories():
    repositories = []
    page = 1

    while True:
        batch = github_get(
            f"/users/{USERNAME}/repos"
            f"?per_page=100&page={page}&type=owner"
        )

        repositories.extend(batch)

        if len(batch) < 100:
            break

        page += 1

    return [
        repo for repo in repositories
        if not repo["fork"]
    ]


def generate_stats(user, repositories, contributions):
    stars = sum(repo["stargazers_count"] for repo in repositories)

    metrics = [
        ("Public Repositories", len(repositories)),
        ("Total Stars", stars),
        ("Followers", user["followers"]),
        ("Contributions (12 months)", contributions),
    ]

    content = """
    <text x="25" y="38" class="title">
        GitHub Statistics
    </text>
    """

    for index, (label, value) in enumerate(metrics):
        y = 75 + index * 42

        content += f"""
        <text x="25" y="{y}" class="label">
            {escape(label)}
        </text>

        <text x="390" y="{y}" class="value"
              text-anchor="end">
            {escape(value)}
        </text>
        """

    save_svg(
        "stats.svg",
        svg_document(420, 245, content),
    )


def generate_languages(repositories):
    languages = Counter()

    for repo in repositories:
        data = github_get(
            f"/repos/{USERNAME}/{repo['name']}/languages"
        )

        languages.update(data)

    top = languages.most_common(6)
    total = sum(value for _, value in top)

    colors = [
        "#38BDF8",
        "#7C3AED",
        "#F59E0B",
        "#10B981",
        "#EF4444",
        "#EC4899",
    ]

    content = """
    <text x="25" y="38" class="title">
        Most Used Languages
    </text>
    """

    if not total:
        content += """
        <text x="25" y="90" class="label">
            No public repository language data
        </text>
        """
    else:
        for index, (language, value) in enumerate(top):
            percentage = value / total * 100
            y = 70 + index * 29
            bar_width = percentage * 2

            content += f"""
            <text x="25" y="{y}" class="label">
                {escape(language)}
            </text>

            <rect x="160" y="{y - 12}"
                  width="{bar_width:.1f}"
                  height="10" rx="5"
                  fill="{colors[index]}"/>

            <text x="390" y="{y}" class="label"
                  text-anchor="end">
                {percentage:.1f}%
            </text>
            """

    save_svg(
        "top-langs.svg",
        svg_document(420, 265, content),
    )


def get_contribution_calendar():
    query = """
    query($login: String!) {
      user(login: $login) {
        contributionsCollection {
          contributionCalendar {
            totalContributions
            weeks {
              contributionDays {
                date
                contributionCount
              }
            }
          }
        }
      }
    }
    """

    data = github_graphql(
        query,
        {"login": USERNAME},
    )

    return data["user"]["contributionsCollection"]["contributionCalendar"]


def generate_activity_graph(calendar):
    weeks = calendar["weeks"]

    colors = [
        "#161B22",
        "#0E4429",
        "#006D32",
        "#26A641",
        "#39D353",
    ]

    cell = 12
    gap = 4
    start_x = 35
    start_y = 65

    width = max(750, start_x + len(weeks) * (cell + gap) + 25)
    height = 220

    content = """
    <text x="25" y="35" class="title">
        Contribution Activity
    </text>
    """

    for week_index, week in enumerate(weeks):
        for day in week["contributionDays"]:
            date = datetime.strptime(
                day["date"], "%Y-%m-%d"
            )

            count = day["contributionCount"]

            if count == 0:
                level = 0
            elif count <= 2:
                level = 1
            elif count <= 5:
                level = 2
            elif count <= 9:
                level = 3
            else:
                level = 4

            x = start_x + week_index * (cell + gap)
            y = start_y + date.weekday() * (cell + gap)

            content += f"""
            <rect x="{x}" y="{y}"
                  width="{cell}" height="{cell}"
                  rx="2" fill="{colors[level]}">
              <title>{escape(day['date'])}: {count} contributions</title>
            </rect>
            """

    content += f"""
    <text x="25" y="195" class="label">
        Total contributions: {calendar['totalContributions']}
    </text>
    """

    save_svg(
        "activity-graph.svg",
        svg_document(width, height, content),
    )


def main():
    print(f"Generating GitHub statistics for {USERNAME}")

    user = github_get(f"/users/{USERNAME}")
    repositories = get_repositories()
    calendar = get_contribution_calendar()

    generate_stats(
        user,
        repositories,
        calendar["totalContributions"],
    )

    generate_languages(repositories)
    generate_activity_graph(calendar)

    print("All statistics generated successfully.")


if __name__ == "__main__":
    main()
