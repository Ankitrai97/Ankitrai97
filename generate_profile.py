"""Generate animated profile SVGs from GitHub's public contribution calendar.

Uses only the Python standard library and the repository's GITHUB_TOKEN.
Calendar dates are UTC. An empty current day does not break yesterday's streak.
"""

import argparse
import json
import os
from datetime import date, datetime, timedelta, timezone
from html import escape
from pathlib import Path
from urllib.request import Request, urlopen


def graphql(query, variables):
    request = Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": query, "variables": variables}).encode(),
        headers={"Authorization": "Bearer " + os.environ["GITHUB_TOKEN"],
                 "Content-Type": "application/json", "User-Agent": "Rapple-AI-Profile"},
    )
    with urlopen(request, timeout=45) as response:
        result = json.load(response)
    if result.get("errors"):
        raise RuntimeError("GitHub contribution query failed: " + str(result["errors"]))
    return result["data"]


def calendar(username, today):
    info = graphql("query($login: String!) { user(login: $login) { createdAt } }",
                   {"login": username})
    if not info.get("user"):
        raise RuntimeError("GitHub user was not found")
    first = date.fromisoformat(info["user"]["createdAt"][:10])
    query = """query($login: String!, $from: DateTime!, $to: DateTime!) {
      user(login: $login) {
        contributionsCollection(from: $from, to: $to) {
          contributionCalendar { weeks {
            contributionDays { date contributionCount }
          } }
        }
      }
    }"""
    counts = {}
    for year in range(first.year, today.year + 1):
        start = max(first, date(year, 1, 1))
        end = min(today, date(year, 12, 31))
        data = graphql(query, {"login": username,
            "from": start.isoformat() + "T00:00:00Z",
            "to": end.isoformat() + "T23:59:59Z"})
        weeks = data["user"]["contributionsCollection"]["contributionCalendar"]["weeks"]
        for week in weeks:
            for day in week["contributionDays"]:
                key = date.fromisoformat(day["date"])
                if first <= key <= today:
                    counts[key] = day["contributionCount"]
    return counts, first


def statistics(counts, first, today):
    total = sum(counts.values())
    longest = running = 0
    cursor = first
    while cursor <= today:
        running = running + 1 if counts.get(cursor, 0) else 0
        longest = max(longest, running)
        cursor += timedelta(days=1)
    cursor = today if counts.get(today, 0) else today - timedelta(days=1)
    current = 0
    while cursor >= first and counts.get(cursor, 0):
        current += 1
        cursor -= timedelta(days=1)
    return total, current, longest


THEMES = {
    "dark": {"bg": "#0d1425", "text": "#f8fafc", "muted": "#94a3b8",
             "grid": "#243047", "mint": "#5eead4", "violet": "#c4b5fd"},
    "light": {"bg": "#f6f8fc", "text": "#0f172a", "muted": "#64748b",
              "grid": "#e2e8f0", "mint": "#0f766e", "violet": "#7c3aed"},
}


def svg_start(width, height, title, description, theme):
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-labelledby="title description">
<title id="title">{escape(title)}</title><desc id="description">{escape(description)}</desc>
<style>
text{{font-family:Segoe UI,Arial,sans-serif}}
.reveal{{animation:reveal .9s ease-out both}}
.orbit{{transform-box:fill-box;transform-origin:center;animation:orbit 14s linear infinite}}
.pulse{{transform-box:fill-box;transform-origin:center;animation:pulse 3s ease-in-out infinite}}
.trace{{stroke-dasharray:1;stroke-dashoffset:0;animation:trace 9s ease-in-out infinite}}
.bar{{transform-box:fill-box;transform-origin:center bottom;animation:grow 1.2s ease-out both}}
@keyframes reveal{{from{{opacity:0;transform:translateY(8px)}}to{{opacity:1;transform:translateY(0)}}}}
@keyframes orbit{{to{{transform:rotate(360deg)}}}}
@keyframes pulse{{0%,100%{{opacity:.45;transform:scale(1)}}50%{{opacity:1;transform:scale(1.35)}}}}
@keyframes trace{{0%{{stroke-dashoffset:1;opacity:.5}}30%,90%{{stroke-dashoffset:0;opacity:1}}100%{{stroke-dashoffset:0;opacity:1}}}}
@keyframes grow{{from{{transform:scaleY(0)}}to{{transform:scaleY(1)}}}}
@media(prefers-reduced-motion:reduce){{.reveal,.orbit,.pulse,.trace,.bar{{animation:none;transform:none;opacity:1;stroke-dashoffset:0}}}}
</style>
<rect width="{width}" height="{height}" rx="18" fill="{theme['bg']}"/>
'''


def streak_svg(counts, first, today, theme):
    total, current, longest = statistics(counts, first, today)
    desc = f"Public contribution totals since {first}: {total} contributions, current streak {current} days, longest streak {longest} days. Updated {today} UTC."
    parts = [svg_start(1000, 270, "Contribution streaks", desc, theme)]
    parts += [f'<text x="32" y="40" font-size="17" font-weight="600" fill="{theme["text"]}">CONSISTENCY / CONTRIBUTION STREAKS</text>',
              f'<text x="32" y="63" font-size="12" fill="{theme["muted"]}">Public GitHub calendar · refreshed daily · UTC</text>']
    for x in (333, 667):
        parts.append(f'<path d="M{x} 90V224" stroke="{theme["grid"]}"/>')
    parts.append(f'<circle cx="500" cy="144" r="44" fill="none" stroke="{theme["grid"]}" stroke-width="3"/>')
    parts.append(f'<circle class="orbit" cx="500" cy="144" r="44" fill="none" stroke="{theme["mint"]}" stroke-width="3" stroke-dasharray="75 18 35 148" stroke-linecap="round"/>')
    for x, number, label, subtitle in (
        (166, total, "TOTAL CONTRIBUTIONS", "Since " + first.strftime("%b %Y")),
        (500, current, "CURRENT STREAK", "Consecutive days"),
        (834, longest, "LONGEST STREAK", "Personal best · days"),
    ):
        parts.append(f'<text class="reveal" x="{x}" y="156" text-anchor="middle" font-size="40" font-weight="700" fill="{theme["text"]}">{number:,}</text>')
        parts.append(f'<text x="{x}" y="211" text-anchor="middle" font-size="13" font-weight="600" letter-spacing="1" fill="{theme["mint"] if x == 500 else theme["violet"]}">{label}</text>')
        parts.append(f'<text x="{x}" y="232" text-anchor="middle" font-size="12" fill="{theme["muted"]}">{subtitle}</text>')
    parts.append(f'<text x="968" y="255" text-anchor="end" font-size="10" fill="{theme["muted"]}">Updated {today.isoformat()}</text></svg>')
    return "\n".join(parts)


def activity_svg(counts, today, theme):
    days = [today - timedelta(days=30-i) for i in range(31)]
    values = [counts.get(day, 0) for day in days]
    maximum = max(4, max(values))
    x0, x1, y0, y1 = 65, 960, 100, 286
    points = [(x0 + i * (x1-x0)/30, y1-value*(y1-y0)/maximum) for i, value in enumerate(values)]
    path = "M" + " L".join(f"{x:.2f},{y:.2f}" for x, y in points)
    desc = f"Daily public GitHub contributions from {days[0]} to {today}. Total {sum(values)} contributions on {sum(v > 0 for v in values)} active days."
    parts = [svg_start(1000, 360, "Contribution activity — last 31 days", desc, theme)]
    parts += [f'<text x="32" y="40" font-size="17" font-weight="600" fill="{theme["text"]}">ACTIVITY / LAST 31 DAYS</text>',
              f'<text x="32" y="65" font-size="12" fill="{theme["muted"]}">{sum(values):,} contributions · {sum(v > 0 for v in values)} active days · daily totals</text>',
              f'<defs><linearGradient id="area" x1="0" y1="0" x2="0" y2="1"><stop stop-color="{theme["mint"]}" stop-opacity=".25"/><stop offset="1" stop-color="{theme["mint"]}" stop-opacity=".015"/></linearGradient></defs>']
    for ratio in (0, .25, .5, .75, 1):
        y = y1-ratio*(y1-y0)
        parts += [f'<path d="M{x0} {y}H{x1}" stroke="{theme["grid"]}" stroke-dasharray="3 7"/>',
                  f'<text x="50" y="{y+4}" text-anchor="end" font-size="11" fill="{theme["muted"]}">{maximum*ratio:g}</text>']
    parts.append(f'<path d="{path} L{x1},{y1} L{x0},{y1} Z" fill="url(#area)"/>')
    for i, ((x, y), value) in enumerate(zip(points, values)):
        if value:
            parts.append(f'<rect class="bar" x="{x-4}" y="{y}" width="8" height="{y1-y}" rx="3" fill="{theme["mint"]}" opacity=".17" style="animation-delay:{i*.025:.3f}s"/>')
    parts.append(f'<path class="trace" d="{path}" pathLength="1" fill="none" stroke="{theme["mint"]}" stroke-width="3" stroke-linejoin="round" stroke-linecap="round"/>')
    for i, ((x, y), day, value) in enumerate(zip(points, days, values)):
        if value:
            parts.append(f'<circle class="pulse" cx="{x:.2f}" cy="{y:.2f}" r="4" fill="{theme["violet"]}" style="animation-delay:{i*.12:.2f}s"><title>{day.isoformat()}: {value} contributions</title></circle>')
        if i in (0, 5, 10, 15, 20, 25, 30):
            parts.append(f'<text x="{x:.2f}" y="312" text-anchor="middle" font-size="11" fill="{theme["muted"]}">{day.strftime("%b %d")}</text>')
    parts.append(f'<text x="32" y="342" font-size="10" fill="{theme["muted"]}">Source: GitHub public contribution calendar · updated {today.isoformat()} UTC</text></svg>')
    return "\n".join(parts)


def self_test():
    today = date(2026, 10, 2)
    first = today-timedelta(days=7)
    counts = {first: 1, first+timedelta(days=1): 2,
              today-timedelta(days=3): 1, today-timedelta(days=2): 3,
              today-timedelta(days=1): 1}
    assert statistics(counts, first, today) == (8, 3, 3)
    counts[today] = 2
    assert statistics(counts, first, today) == (10, 4, 4)
    assert statistics({}, first, today) == (0, 0, 0)
    gap = {first: 1, first+timedelta(days=1): 1, today: 1}
    assert statistics(gap, first, today) == (3, 1, 2)
    from xml.etree import ElementTree
    for theme in THEMES.values():
        for sample in ({}, counts):
            ElementTree.fromstring(streak_svg(sample, first, today, theme))
            ElementTree.fromstring(activity_svg(sample, today, theme))
    print("Profile generator checks passed.")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    self_test()
    if args.self_test:
        return
    today = datetime.now(timezone.utc).date()
    counts, first = calendar(os.environ["GITHUB_REPOSITORY_OWNER"], today)
    output = Path("dist")
    output.mkdir(exist_ok=True)
    for name, theme in THEMES.items():
        suffix = "-dark" if name == "dark" else ""
        (output / f"streak-stats{suffix}.svg").write_text(streak_svg(counts, first, today, theme), encoding="utf-8")
        (output / f"activity-chart{suffix}.svg").write_text(activity_svg(counts, today, theme), encoding="utf-8")
    print("Generated streak table and activity chart from GitHub calendar data.")


if __name__ == "__main__":
    main()
