#!/usr/bin/env python3
"""
Fetch the live numbers from GitHub, then render every theme.

    python today.py            # fetch and render (needs ACCESS_TOKEN)
    python today.py --demo     # render with placeholder numbers, no token
    python today.py --offline  # render from the last successful fetch
    python today.py --check    # validate layout without writing anything

Originally forked from Andrew6rant/Andrew6rant. The lines-of-code cache is the
same good idea - walking every commit of every repo daily would blow through
the API budget, so a repo is only re-walked when its commit count changes.
What is different here:

  * every theme is generated from one template rather than patched by element id
  * the API layer retries on the undocumented secondary rate limit instead of
    crashing the nightly build
  * nothing is written until every request has succeeded, so a partial failure
    can no longer leave a half-updated card on your profile
  * the last good result is cached, so a GitHub outage degrades to yesterday's
    numbers rather than a broken README

Token: a fine-grained PAT with All Repositories access.
  Account:    read:Followers, read:Starring
  Repository: read:Commit statuses, read:Contents, read:Metadata
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import sys
import time

import requests
from dateutil import relativedelta

import config
import render

API = "https://api.github.com/graphql"
STATS_CACHE = "cache/stats.json"

QUERY_COUNT: dict[str, int] = {}


class GitHubError(RuntimeError):
    pass


# --------------------------------------------------------------------------
# API plumbing
# --------------------------------------------------------------------------


class Client:
    """A thin GraphQL client that survives GitHub's rate limiters."""

    MAX_ATTEMPTS = 5

    def __init__(self, token: str, username: str):
        self.username = username
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Authorization": f"token {token}",
                "User-Agent": f"{username}-profile-card",
            }
        )

    def query(self, name: str, query: str, variables: dict, attempts=None) -> dict:
        QUERY_COUNT[name] = QUERY_COUNT.get(name, 0) + 1
        attempts = attempts or self.MAX_ATTEMPTS

        for attempt in range(1, attempts + 1):
            try:
                response = self.session.post(
                    API, json={"query": query, "variables": variables}, timeout=30
                )
            except requests.RequestException as exc:
                if attempt == self.MAX_ATTEMPTS:
                    raise GitHubError(f"{name}: network error: {exc}") from exc
                self._backoff(attempt, f"{name}: {exc}")
                continue

            if response.status_code == 200:
                payload = response.json()
                # A 200 can still carry errors; GraphQL is like that.
                if payload.get("errors"):
                    raise GitHubError(f"{name}: {payload['errors']}")
                return payload["data"]

            # 403/429 is the undocumented anti-abuse limit, 502 is GitHub
            # timing out on a large history query. Both are worth retrying.
            if response.status_code in (403, 429, 502, 503) and attempt < attempts:
                self._backoff(attempt, f"{name}: HTTP {response.status_code}")
                continue

            raise GitHubError(
                f"{name} failed with HTTP {response.status_code}: {response.text[:300]}"
            )

        raise GitHubError(f"{name}: exhausted {attempts} attempts")

    @staticmethod
    def _backoff(attempt: int, reason: str) -> None:
        delay = min(60, 2**attempt)
        print(f"  retrying in {delay}s ({reason})")
        time.sleep(delay)


# --------------------------------------------------------------------------
# Queries
# --------------------------------------------------------------------------

Q_USER = """
query($login: String!) {
  user(login: $login) { id createdAt }
}"""

Q_FOLLOWERS = """
query($login: String!) {
  user(login: $login) { followers { totalCount } }
}"""

Q_REPOS = """
query($owner_affiliation: [RepositoryAffiliation], $login: String!, $cursor: String) {
  user(login: $login) {
    repositories(first: 100, after: $cursor, ownerAffiliations: $owner_affiliation) {
      totalCount
      edges { node { ... on Repository { nameWithOwner stargazers { totalCount } } } }
      pageInfo { endCursor hasNextPage }
    }
  }
}"""

Q_REPO_HISTORY = """
query($owner_affiliation: [RepositoryAffiliation], $login: String!, $cursor: String) {
  user(login: $login) {
    repositories(first: 60, after: $cursor, ownerAffiliations: $owner_affiliation) {
      edges {
        node {
          ... on Repository {
            nameWithOwner
            defaultBranchRef { target { ... on Commit { history { totalCount } } } }
          }
        }
      }
      pageInfo { endCursor hasNextPage }
    }
  }
}"""

Q_COMMITS = """
query($repo_name: String!, $owner: String!, $cursor: String, $page: Int!) {
  repository(name: $repo_name, owner: $owner) {
    defaultBranchRef {
      target {
        ... on Commit {
          history(first: $page, after: $cursor) {
            totalCount
            edges {
              node {
                ... on Commit { committedDate }
                author { user { id } }
                deletions
                additions
              }
            }
            pageInfo { endCursor hasNextPage }
          }
        }
      }
    }
  }
}"""


# --------------------------------------------------------------------------
# Stats
# --------------------------------------------------------------------------


def human_age(birthday: datetime.datetime) -> str:
    diff = relativedelta.relativedelta(datetime.datetime.today(), birthday)
    cake = " *" if (diff.months == 0 and diff.days == 0) else ""
    return (
        f"{diff.years} year{plural(diff.years)}, "
        f"{diff.months} month{plural(diff.months)}, "
        f"{diff.days} day{plural(diff.days)}{cake}"
    )


def plural(n: int) -> str:
    return "" if n == 1 else "s"


def repo_totals(client: Client, count_type: str, affiliations: list[str]) -> int:
    """Total repository or star count, following pagination."""
    total, stars, cursor = 0, 0, None
    while True:
        data = client.query(
            "repo_totals", Q_REPOS, {
                "owner_affiliation": affiliations,
                "login": client.username,
                "cursor": cursor,
            }
        )
        repos = data["user"]["repositories"]
        total = repos["totalCount"]
        for edge in repos["edges"]:
            stars += edge["node"]["stargazers"]["totalCount"]
        if not repos["pageInfo"]["hasNextPage"]:
            break
        cursor = repos["pageInfo"]["endCursor"]
    return stars if count_type == "stars" else total


def cache_path(username: str) -> str:
    digest = hashlib.sha256(username.encode("utf-8")).hexdigest()
    return f"cache/{digest}.txt"


def repo_edges(client: Client, affiliations: list[str]) -> list[dict]:
    """Every repo plus its current commit count - the input to the LOC cache."""
    edges, cursor = [], None
    while True:
        data = client.query(
            "repo_edges", Q_REPO_HISTORY, {
                "owner_affiliation": affiliations,
                "login": client.username,
                "cursor": cursor,
            }
        )
        repos = data["user"]["repositories"]
        edges.extend(repos["edges"])
        if not repos["pageInfo"]["hasNextPage"]:
            break
        cursor = repos["pageInfo"]["endCursor"]
    return edges


def walk_repo(client: Client, owner_id: dict, owner: str, name: str):
    """
    Sum additions/deletions across every commit you authored in one repo.

    GitHub answers 502 when a `history(first: N)` page is too expensive to
    build - it is a server-side timeout, not a rate limit, so retrying the same
    query never works. The fix is to ask for less: on a 502 the page size is
    quartered and the same cursor retried, down to a floor of 5. Repositories
    with very large commits (lockfiles, vendored trees, generated assets) only
    come back at all this way.
    """
    additions = deletions = mine = 0
    cursor = None
    page = 100
    while True:
        try:
            data = client.query(
                "walk_repo", Q_COMMITS,
                {"repo_name": name, "owner": owner, "cursor": cursor,
                 "page": page},
                attempts=2,
            )
        except GitHubError as exc:
            if "502" in str(exc) and page > 5:
                page = max(5, page // 4)
                print(f"      page too heavy, retrying at {page}", flush=True)
                continue
            raise
        branch = data["repository"]["defaultBranchRef"]
        if branch is None:  # empty repository
            return 0, 0, 0
        history = branch["target"]["history"]
        for node in history["edges"]:
            if node["node"]["author"]["user"] == owner_id:
                mine += 1
                additions += node["node"]["additions"]
                deletions += node["node"]["deletions"]
        if not history["pageInfo"]["hasNextPage"]:
            return additions, deletions, mine
        cursor = history["pageInfo"]["endCursor"]


def build_loc_cache(client: Client, owner_id: dict, edges: list[dict]):
    """
    One line per repo: <hash> <total commits> <your commits> <added> <deleted>

    A repo is only re-walked when its total commit count has moved, which is
    what keeps this inside the API budget.
    """
    path = cache_path(client.username)
    comment_size = config.CACHE_COMMENT_SIZE
    os.makedirs("cache", exist_ok=True)

    header = [
        "# Lines-of-code cache. Generated, do not edit.\n",
        "# One line per repository:\n",
        "#   sha256(owner/name)  total_commits  your_commits  added  deleted\n",
        "# A repository is re-scanned only when total_commits changes.\n",
        "# Delete this file to force a full rebuild (slow, and API-expensive).\n",
        "#\n",
        "#\n",
    ]

    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = handle.readlines()
    except FileNotFoundError:
        data = list(header)

    if len(data) - comment_size != len(edges):
        # Repo count changed - rebuild the index, keeping the comment block.
        data = list(header) + [
            f"{hashlib.sha256(e['node']['nameWithOwner'].encode()).hexdigest()} 0 0 0 0\n"
            for e in edges
        ]

    comment, body = data[:comment_size], data[comment_size:]
    rescanned = 0
    excluded = {
        hashlib.sha256(name.encode()).hexdigest()
        for name in config.EXCLUDE_REPOS
    }

    def flush():
        with open(path, "w", encoding="utf-8") as handle:
            handle.writelines(comment)
            handle.writelines(body)

    try:
        for index, edge in enumerate(edges):
            node = edge["node"]
            repo_hash = hashlib.sha256(node["nameWithOwner"].encode()).hexdigest()
            cached_hash, cached_commits, *_ = body[index].split()

            if cached_hash != repo_hash:
                body[index] = f"{repo_hash} 0 0 0 0\n"
                cached_commits = "0"

            if node["nameWithOwner"] in config.EXCLUDE_REPOS:
                # Not walked and not counted. See EXCLUDE_REPOS in config.py.
                continue

            branch = node.get("defaultBranchRef")
            if branch is None:
                body[index] = f"{repo_hash} 0 0 0 0\n"
                continue

            total = branch["target"]["history"]["totalCount"]
            if int(cached_commits) == total:
                continue

            owner, name = node["nameWithOwner"].split("/")
            added, deleted, mine = walk_repo(client, owner_id, owner, name)
            body[index] = f"{repo_hash} {total} {mine} {added} {deleted}\n"
            rescanned += 1
            # Flush after every repository. A first run walks every commit you
            # have ever authored and can take many minutes; if it is killed
            # part-way, everything done so far still counts and the next run
            # picks up where this one stopped.
            flush()
            print(
                f"    {node['nameWithOwner']}: {mine} commits, "
                f"+{added}/-{deleted}",
                flush=True,
            )
    finally:
        flush()

    added = deleted = commits = 0
    for line in body:
        repo_hash, _, mine, plus, minus = line.split()
        if repo_hash in excluded:
            continue
        commits += int(mine)
        added += int(plus)
        deleted += int(minus)

    return {
        "loc_added": added,
        "loc_deleted": deleted,
        "loc_net": added - deleted,
        "commits": commits,
        "rescanned": rescanned,
    }


def fetch(client: Client) -> dict:
    print("fetching:")
    started = time.perf_counter()

    data = client.query("user", Q_USER, {"login": client.username})
    owner_id = {"id": data["user"]["id"]}
    print(f"  account            {data['user']['createdAt'][:10]}")

    edges = repo_edges(client, config.OWNER_AFFILIATIONS)
    print(f"  repositories       {len(edges)}")

    loc = build_loc_cache(client, owner_id, edges)
    print(
        f"  lines of code      {loc['loc_net']:,} "
        f"({loc['rescanned']} repo(s) rescanned)"
    )

    stars = repo_totals(client, "stars", config.OWNED_ONLY)
    repos = repo_totals(client, "repos", config.OWNED_ONLY)
    contributed = repo_totals(client, "repos", config.OWNER_AFFILIATIONS)
    followers = client.query(
        "followers", Q_FOLLOWERS, {"login": client.username}
    )["user"]["followers"]["totalCount"]
    print(f"  stars              {stars:,}")
    print(f"  followers          {followers:,}")

    live = {
        "age": human_age(config.BIRTHDAY),
        "repos": repos,
        "contributed": contributed,
        "stars": stars,
        "followers": followers,
        "commits": loc["commits"],
        "loc_added": loc["loc_added"],
        "loc_deleted": loc["loc_deleted"],
        "loc_net": loc["loc_net"],
    }
    live.update(levels(live["commits"]))

    calls = sum(QUERY_COUNT.values())
    print(f"  {calls} API call(s) in {time.perf_counter() - started:.1f}s")
    return live


def levels(commits: int) -> dict:
    return {
        "level": commits // config.XP_PER_LEVEL,
        "xp_current": commits % config.XP_PER_LEVEL,
        "xp_needed": config.XP_PER_LEVEL,
    }


# --------------------------------------------------------------------------
# Persistence and fallbacks
# --------------------------------------------------------------------------


def save_stats(live: dict) -> None:
    os.makedirs("cache", exist_ok=True)
    with open(STATS_CACHE, "w", encoding="utf-8") as handle:
        json.dump(live, handle, indent=2, sort_keys=True)


def load_stats() -> dict | None:
    try:
        with open(STATS_CACHE, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except (FileNotFoundError, json.JSONDecodeError):
        return None


DEMO = {
    "age": "22 years, 7 months, 13 days",
    "repos": 48,
    "contributed": 96,
    "stars": 1_204,
    "followers": 210,
    "commits": 3_182,
    "loc_added": 601_220,
    "loc_deleted": 88_777,
    "loc_net": 512_443,
    **levels(3_182),
}


# --------------------------------------------------------------------------
# Entry point
# --------------------------------------------------------------------------


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--demo", action="store_true", help="render fake numbers")
    parser.add_argument("--offline", action="store_true", help="reuse the last fetch")
    parser.add_argument("--check", action="store_true", help="validate, write nothing")
    args = parser.parse_args(argv)

    username = os.environ.get("USER_NAME") or config.GITHUB_USERNAME
    token = os.environ.get("ACCESS_TOKEN")

    if args.demo:
        live = dict(DEMO)
        live["age"] = human_age(config.BIRTHDAY)
    elif args.offline or args.check:
        live = load_stats() or dict(DEMO)
        live["age"] = human_age(config.BIRTHDAY)
    elif not token:
        print(
            "ACCESS_TOKEN is not set.\n"
            "  Locally, try:  python today.py --demo\n"
            "  In Actions, add a fine-grained PAT as the ACCESS_TOKEN secret.",
            file=sys.stderr,
        )
        return 2
    else:
        try:
            live = fetch(Client(token, username))
            save_stats(live)
        except GitHubError as exc:
            previous = load_stats()
            if previous is None:
                print(f"error: {exc}", file=sys.stderr)
                return 1
            # Yesterday's numbers beat a broken card.
            print(f"warning: {exc}\n         falling back to the cached numbers.")
            live = previous
            live["age"] = human_age(config.BIRTHDAY)

    issues = render.validate(live)
    if issues:
        print("layout warnings:")
        print("\n".join(issues))

    if args.check:
        print("check only, nothing written.")
        return 1 if issues else 0

    for path in render.write_all(live):
        print(f"wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
