import os
import re
import requests
import datetime
from dateutil import relativedelta

TOKEN = os.environ["ACCESS_TOKEN"]
USER = os.environ["USER_NAME"]

GQL = "https://api.github.com/graphql"
HEAD = {"Authorization": f"Bearer {TOKEN}"}


# ---------- GraphQL helper ----------
def gql(query, variables=None):
    r = requests.post(GQL, json={"query": query, "variables": variables or {}}, headers=HEAD, timeout=30)
    r.raise_for_status()
    j = r.json()
    if "errors" in j:
        raise RuntimeError(j["errors"])
    return j["data"]


# ---------- Uptime from DOB ----------
# def get_age_from_dob(dob):
#     delta = relativedelta.relativedelta(datetime.date.today(), dob)
#     def unit(n, w): return f"{n} {w}{'' if n == 1 else 's'}"
#     return f"{unit(delta.years, 'year')}, {unit(delta.months, 'month')}, {unit(delta.days, 'day')}"

# DOB = datetime.date(2002, 12, 12)


# ---------- GitHub Stats ----------
def get_stats(login: str):
    query = """
    query($login:String!){
      user(login:$login){
        followers { totalCount }
        repositories(ownerAffiliations: OWNER, first: 100){
          totalCount
          nodes { stargazers { totalCount } }
        }
        contributionsCollection {
          totalCommitContributions
          totalRepositoriesWithContributedCommits
        }
      }
    }
    """
    d = gql(query, {"login": login})["user"]
    repos = d["repositories"]["totalCount"]
    stars = sum(n["stargazers"]["totalCount"] for n in d["repositories"]["nodes"])
    followers = d["followers"]["totalCount"]
    commits12m = d["contributionsCollection"]["totalCommitContributions"]
    contrib_repos = d["contributionsCollection"]["totalRepositoriesWithContributedCommits"]

    # fetch extra pages if >100 repos
    end_cursor, has_more = None, repos > len(d["repositories"]["nodes"])
    while has_more:
        q2 = """
        query($login:String!,$cursor:String){
          user(login:$login){
            repositories(ownerAffiliations: OWNER, first: 100, after:$cursor){
              nodes { stargazers { totalCount } }
              pageInfo { endCursor hasNextPage }
            }
          }
        }
        """
        r = gql(q2, {"login": login, "cursor": end_cursor})["user"]["repositories"]
        stars += sum(n["stargazers"]["totalCount"] for n in r["nodes"])
        end_cursor = r["pageInfo"]["endCursor"]
        has_more = r["pageInfo"]["hasNextPage"]

    return {
        "REPOS": repos,
        "STARS": stars,
        "FOLLOWERS": followers,
        "COMMITS_12M": commits12m,
        "CONTRIBS": contrib_repos,
        # "AGE": get_age_from_dob(DOB),
    }


# ---------- Replace placeholders ----------
def replace_in_readme(content: str, stats: dict) -> str:
    for k, v in stats.items():
        val = f"{v:,}" if isinstance(v, int) else str(v)
        content = content.replace(f"{{{{{k}}}}}", val)
    return content


# ---------- Main ----------
def main():
    stats = get_stats(USER)
    with open("README.md", "r", encoding="utf-8") as f:
        content = f.read()

    updated = replace_in_readme(content, stats)

    if updated != content:
        with open("README.md", "w", encoding="utf-8") as f:
            f.write(updated)
        print("README updated successfully.")
    else:
        print("No changes detected.")


if __name__ == "__main__":
    main()
