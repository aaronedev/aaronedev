from __future__ import annotations

import io
import sys
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.readme_config import (  # noqa: E402
    ALLOWED_OWNERS,
    AUTHOR_LOGIN,
    CONTRIB_LIMIT,
    MAX_PR_PAGES,
    PAGE_SIZE,
    PR_LIMIT,
    PROFILE_REPO,
)
from scripts.github_activity import (  # noqa: E402
    ActivityCollectionError,
    normalize,
    privacy_reduce,
    render,
    retrieve,
)

CANARY_VV = "Violet-Void/private-client-project"
CANARY_BF = "bauerstischfinder/top-secret-acquisition"
UNRELATED_OWNER = "unrelated-org"
PUBLIC_REPOS = {
    "aaronedev": "aaronedev/public-dotfiles",
    "Violet-Void": "Violet-Void/public-theme",
    "bauerstischfinder": "bauerstischfinder/public-finder",
}


def _pr_node(
    *,
    owner: str,
    name: str,
    title: str,
    url: str,
    state: str = "OPEN",
    created_at: str = "2026-08-20T12:00:00Z",
    is_private: bool = False,
    description: str | None = "A public repository",
    repo_url: str | None = None,
) -> dict:
    name_with_owner = f"{owner}/{name}"
    return {
        "title": title,
        "url": url,
        "state": state,
        "createdAt": created_at,
        "repository": {
            "nameWithOwner": name_with_owner,
            "isPrivate": is_private,
            "url": repo_url or f"https://github.com/{name_with_owner}",
            "description": description,
            "owner": {"login": owner},
        },
    }


def _contrib(
    *,
    owner: str,
    name: str,
    count: int,
    is_private: bool = False,
    description: str | None = "A public repository",
    repo_url: str | None = None,
    owner_login: str | None = None,
) -> dict:
    name_with_owner = f"{owner}/{name}"
    repository = {
        "nameWithOwner": name_with_owner,
        "isPrivate": is_private,
        "url": repo_url or f"https://github.com/{name_with_owner}",
        "description": description,
    }
    if owner_login is not False:
        repository["owner"] = {"login": owner if owner_login is None else owner_login}
    return {"contributionCount": count, "repository": repository}


def _raw(*, pull_requests=None, contributions=None, commit_dates=None) -> dict:
    payload = {
        "pull_requests": list(pull_requests or []),
        "contributions": list(contributions or []),
    }
    if commit_dates is not None:
        payload["commit_dates"] = list(commit_dates)
    return payload


def _rendered_from_raw(raw: dict) -> str:
    return render(privacy_reduce(normalize(raw)))


class ConfigContractTest(unittest.TestCase):
    def test_constants_come_from_single_module(self) -> None:
        self.assertEqual(AUTHOR_LOGIN, "aaronedev")
        self.assertEqual(PROFILE_REPO, "aaronedev/aaronedev")
        self.assertEqual(PR_LIMIT, 8)
        self.assertEqual(CONTRIB_LIMIT, 10)
        self.assertEqual(MAX_PR_PAGES, 10)
        self.assertEqual(PAGE_SIZE, 100)
        self.assertIn("aaronedev", ALLOWED_OWNERS)
        self.assertIn("Violet-Void", ALLOWED_OWNERS)
        self.assertIn("bauerstischfinder", ALLOWED_OWNERS)


class PrivacyReduceTest(unittest.TestCase):
    def test_public_repo_for_each_allowed_owner_is_included(self) -> None:
        pull_requests = []
        contributions = []
        for owner in ALLOWED_OWNERS:
            name = PUBLIC_REPOS[owner].split("/", 1)[1]
            pull_requests.append(
                _pr_node(
                    owner=owner,
                    name=name,
                    title=f"{owner} public pr",
                    url=f"https://github.com/{PUBLIC_REPOS[owner]}/pull/1",
                    created_at="2026-08-21T10:00:00Z",
                )
            )
            contributions.append(
                _contrib(
                    owner=owner, name=name, count=3, description=f"{owner} public desc"
                )
            )

        markdown = _rendered_from_raw(
            _raw(pull_requests=pull_requests, contributions=contributions)
        )

        for owner in ALLOWED_OWNERS:
            self.assertIn(PUBLIC_REPOS[owner], markdown)
            self.assertIn(f"{owner} public pr", markdown)

    def test_private_violet_void_canary_is_aggregate_only(self) -> None:
        owner, name = CANARY_VV.split("/", 1)
        raw = _raw(
            pull_requests=[
                _pr_node(
                    owner=owner,
                    name=name,
                    title="secret client work",
                    url=f"https://github.com/{CANARY_VV}/pull/9",
                    is_private=True,
                    description="do not leak",
                )
            ],
            contributions=[
                _contrib(
                    owner=owner,
                    name=name,
                    count=4,
                    is_private=True,
                    description="secret",
                )
            ],
        )
        buf = io.StringIO()
        with redirect_stdout(buf), redirect_stderr(buf):
            markdown = _rendered_from_raw(raw)
        self.assertNotIn(CANARY_VV, markdown)
        self.assertNotIn("private-client-project", markdown)
        self.assertNotIn("secret client work", markdown)
        self.assertNotIn(CANARY_VV, buf.getvalue())
        self.assertIn("🔒 Private activity:", markdown)
        self.assertRegex(markdown, r"🔒 Private activity: \d+ contributions")

    def test_private_bauerstischfinder_canary_is_aggregate_only(self) -> None:
        owner, name = CANARY_BF.split("/", 1)
        raw = _raw(
            pull_requests=[
                _pr_node(
                    owner=owner,
                    name=name,
                    title="acquisition notes",
                    url=f"https://github.com/{CANARY_BF}/pull/3",
                    is_private=True,
                )
            ],
            contributions=[_contrib(owner=owner, name=name, count=7, is_private=True)],
        )
        buf = io.StringIO()
        with redirect_stdout(buf), redirect_stderr(buf):
            markdown = _rendered_from_raw(raw)
        self.assertNotIn(CANARY_BF, markdown)
        self.assertNotIn("top-secret-acquisition", markdown)
        self.assertNotIn("acquisition notes", markdown)
        self.assertNotIn(CANARY_BF, buf.getvalue())
        self.assertIn("🔒 Private activity:", markdown)

    def test_unrelated_owner_is_excluded(self) -> None:
        raw = _raw(
            pull_requests=[
                _pr_node(
                    owner=UNRELATED_OWNER,
                    name="random-repo",
                    title="unrelated pr",
                    url=f"https://github.com/{UNRELATED_OWNER}/random-repo/pull/1",
                )
            ],
            contributions=[
                _contrib(owner=UNRELATED_OWNER, name="random-repo", count=99)
            ],
        )
        markdown = _rendered_from_raw(raw)
        self.assertNotIn(UNRELATED_OWNER, markdown)
        self.assertNotIn("unrelated pr", markdown)
        self.assertNotIn("random-repo", markdown)
        self.assertNotIn("🔒 Private activity:", markdown)

    def test_profile_meta_repo_excluded_from_public_contribs(self) -> None:
        owner, name = PROFILE_REPO.split("/", 1)
        raw = _raw(
            contributions=[
                _contrib(
                    owner=owner,
                    name=name,
                    count=50,
                    description="profile repo should not appear",
                ),
                _contrib(owner="aaronedev", name="public-dotfiles", count=2),
            ]
        )
        markdown = _rendered_from_raw(raw)
        self.assertNotIn(PROFILE_REPO, markdown)
        self.assertIn("aaronedev/public-dotfiles", markdown)

    def test_unproven_private_owner_omits_aggregate(self) -> None:
        contrib = _contrib(
            owner="Violet-Void",
            name="hidden",
            count=3,
            is_private=True,
        )
        contrib["repository"]["owner"] = None
        markdown = _rendered_from_raw(_raw(contributions=[contrib]))
        self.assertNotIn("🔒 Private activity:", markdown)
        self.assertNotIn("hidden", markdown)

    def test_successful_zero_results_use_empty_strings(self) -> None:
        markdown = _rendered_from_raw(_raw(pull_requests=[], contributions=[]))
        self.assertIn("_No public pull requests from allowed owners._", markdown)
        self.assertIn("_No public commits from allowed owners._", markdown)
        self.assertNotIn("_Activity temporarily unavailable._", markdown)
        self.assertNotIn("No activity", markdown)

    def test_duplicate_records_collapsed_and_stable(self) -> None:
        pr = _pr_node(
            owner="aaronedev",
            name="public-dotfiles",
            title="same pr",
            url="https://github.com/aaronedev/public-dotfiles/pull/4",
        )
        contrib = _contrib(owner="aaronedev", name="public-dotfiles", count=2)
        raw = _raw(
            pull_requests=[pr, dict(pr)],
            contributions=[
                contrib,
                _contrib(owner="aaronedev", name="public-dotfiles", count=3),
            ],
        )
        first = _rendered_from_raw(raw)
        second = _rendered_from_raw(raw)
        self.assertEqual(first, second)
        self.assertEqual(first.count("same pr"), 1)
        self.assertEqual(first.count("<code>aaronedev/public-dotfiles</code>"), 2)
        self.assertIn("<strong>5 commits</strong>", first)

    def test_malformed_remote_text_is_escaped(self) -> None:
        raw = _raw(
            pull_requests=[
                _pr_node(
                    owner="aaronedev",
                    name="public-dotfiles",
                    title="<script>alert(1)</script>",
                    url="https://github.com/aaronedev/public-dotfiles/pull/2",
                    description="<b>unclosed",
                )
            ],
            contributions=[
                _contrib(
                    owner="aaronedev",
                    name="public-dotfiles",
                    count=1,
                    description="<script>alert(1)</script>",
                )
            ],
        )
        markdown = _rendered_from_raw(raw)
        self.assertNotIn("<script>", markdown)
        self.assertNotIn("<b>", markdown)
        self.assertIn("alert(1)", markdown)

    def test_deterministic_ordering_and_tie_break(self) -> None:
        raw = _raw(
            pull_requests=[
                _pr_node(
                    owner="aaronedev",
                    name="zeta",
                    title="later z",
                    url="https://github.com/aaronedev/zeta/pull/2",
                    created_at="2026-08-20T12:00:00Z",
                    description=None,
                ),
                _pr_node(
                    owner="aaronedev",
                    name="alpha",
                    title="later a",
                    url="https://github.com/aaronedev/alpha/pull/1",
                    created_at="2026-08-20T12:00:00Z",
                    description=None,
                ),
                _pr_node(
                    owner="Violet-Void",
                    name="theme",
                    title="newest",
                    url="https://github.com/Violet-Void/theme/pull/1",
                    created_at="2026-08-22T12:00:00Z",
                    description=None,
                ),
            ],
            contributions=[
                _contrib(owner="aaronedev", name="zeta", count=5, description=None),
                _contrib(owner="aaronedev", name="alpha", count=5, description=None),
                _contrib(owner="Violet-Void", name="theme", count=9, description=None),
            ],
        )
        markdown = _rendered_from_raw(raw)
        self.assertLess(markdown.index("newest"), markdown.index("later a"))
        self.assertLess(markdown.index("later a"), markdown.index("later z"))
        self.assertLess(
            markdown.index("Violet-Void/theme"), markdown.index("aaronedev/alpha")
        )
        self.assertLess(
            markdown.index("aaronedev/alpha"), markdown.index("aaronedev/zeta")
        )

    def test_description_truncated_to_120(self) -> None:
        description = "x" * 200
        markdown = _rendered_from_raw(
            _raw(
                pull_requests=[
                    _pr_node(
                        owner="aaronedev",
                        name="public-dotfiles",
                        title="long desc",
                        url="https://github.com/aaronedev/public-dotfiles/pull/8",
                        description=description,
                    )
                ]
            )
        )
        self.assertNotIn("x" * 121, markdown)
        self.assertIn("x" * 120, markdown)


class RetrievePaginationTest(unittest.TestCase):
    def test_allowlisted_pr_on_later_page_is_included(self) -> None:
        allowlisted = _pr_node(
            owner="aaronedev",
            name="public-dotfiles",
            title="from page two",
            url="https://github.com/aaronedev/public-dotfiles/pull/11",
        )
        unrelated = _pr_node(
            owner=UNRELATED_OWNER,
            name="noise",
            title="page one noise",
            url=f"https://github.com/{UNRELATED_OWNER}/noise/pull/1",
        )
        calls = []

        def http(url, *, method="GET", headers=None, json_body=None):
            calls.append(
                {
                    "url": url,
                    "method": method,
                    "headers": headers,
                    "json_body": json_body,
                }
            )
            self.assertEqual(url, "https://api.github.com/graphql")
            self.assertEqual(method, "POST")
            self.assertNotIn("token-value", url)
            query = (json_body or {}).get("query", "")
            variables = (json_body or {}).get("variables") or {}
            if "pullRequests" in query:
                after = variables.get("after")
                if after is None:
                    return {
                        "status": 200,
                        "json": {
                            "data": {
                                "user": {
                                    "pullRequests": {
                                        "pageInfo": {
                                            "hasNextPage": True,
                                            "endCursor": "cursor-1",
                                        },
                                        "nodes": [unrelated],
                                    }
                                }
                            }
                        },
                    }
                if after == "cursor-1":
                    return {
                        "status": 200,
                        "json": {
                            "data": {
                                "user": {
                                    "pullRequests": {
                                        "pageInfo": {
                                            "hasNextPage": False,
                                            "endCursor": None,
                                        },
                                        "nodes": [allowlisted],
                                    }
                                }
                            }
                        },
                    }
            if "commitContributionsByRepository" in query:
                return {
                    "status": 200,
                    "json": {
                        "data": {
                            "viewer": {
                                "id": "VID",
                                "contributionsCollection": {
                                    "commitContributionsByRepository": []
                                },
                            }
                        }
                    },
                }
            if "history" in query:
                return {
                    "status": 200,
                    "json": {"data": {"repository": None}},
                }
            raise AssertionError(f"unexpected query: {query}")

        raw = retrieve(http, token="token-value")
        markdown = _rendered_from_raw(raw)
        self.assertIn("from page two", markdown)
        self.assertNotIn("page one noise", markdown)
        self.assertTrue(
            any(
                call["headers"].get("Authorization") == "Bearer token-value"
                for call in calls
            )
        )
        self.assertGreaterEqual(
            sum(
                1
                for call in calls
                if "pullRequests" in (call["json_body"] or {}).get("query", "")
            ),
            2,
        )

    def test_http_error_raises_activity_collection_error(self) -> None:
        def http(url, *, method="GET", headers=None, json_body=None):
            return {"status": 502, "json": {"message": "nope"}}

        with self.assertRaises(ActivityCollectionError):
            retrieve(http, token="token-value")

    def test_graphql_errors_raise_activity_collection_error(self) -> None:
        def http(url, *, method="GET", headers=None, json_body=None):
            return {"status": 200, "json": {"errors": [{"message": "boom"}]}}

        with self.assertRaises(ActivityCollectionError):
            retrieve(http, token="token-value")

    def test_auth_uses_header_not_url(self) -> None:
        seen = {}

        def http(url, *, method="GET", headers=None, json_body=None):
            seen["url"] = url
            seen["headers"] = headers
            raise ActivityCollectionError("stop")

        with self.assertRaises(ActivityCollectionError):
            retrieve(http, token="super-secret")
        self.assertNotIn("super-secret", seen["url"])
        self.assertEqual(seen["headers"]["Authorization"], "Bearer super-secret")

    def test_commit_history_skips_non_allowlisted_repos(self) -> None:
        queried_repos = []

        def http(url, *, method="GET", headers=None, json_body=None):
            query = (json_body or {}).get("query", "")
            variables = (json_body or {}).get("variables") or {}
            if "pullRequests" in query:
                return {
                    "status": 200,
                    "json": {
                        "data": {
                            "user": {
                                "pullRequests": {
                                    "pageInfo": {
                                        "hasNextPage": False,
                                        "endCursor": None,
                                    },
                                    "nodes": [],
                                }
                            }
                        }
                    },
                }
            if "commitContributionsByRepository" in query:
                return {
                    "status": 200,
                    "json": {
                        "data": {
                            "viewer": {
                                "id": "VID",
                                "contributionsCollection": {
                                    "commitContributionsByRepository": [
                                        _contrib(
                                            owner=UNRELATED_OWNER,
                                            name="noise",
                                            count=4,
                                        ),
                                        _contrib(
                                            owner="aaronedev",
                                            name="public-dotfiles",
                                            count=2,
                                        ),
                                    ]
                                },
                            }
                        }
                    },
                }
            if "history" in query:
                queried_repos.append(
                    f"{variables.get('owner')}/{variables.get('name')}"
                )
                return {
                    "status": 200,
                    "json": {
                        "data": {
                            "repository": {
                                "defaultBranchRef": {
                                    "target": {
                                        "history": {
                                            "nodes": [
                                                {
                                                    "committedDate": "2026-08-20T08:00:00Z"
                                                }
                                            ]
                                        }
                                    }
                                }
                            }
                        }
                    },
                }
            raise AssertionError(query)

        retrieve(http, token="token-value")
        self.assertIn("aaronedev/public-dotfiles", queried_repos)
        self.assertNotIn(f"{UNRELATED_OWNER}/noise", queried_repos)
        self.assertNotIn(CANARY_VV, queried_repos)
        self.assertNotIn(CANARY_BF, queried_repos)


class RenderModelTest(unittest.TestCase):
    def test_render_model_has_no_private_metadata(self) -> None:
        owner, name = CANARY_VV.split("/", 1)
        model = privacy_reduce(
            normalize(
                _raw(
                    pull_requests=[
                        _pr_node(
                            owner=owner,
                            name=name,
                            title="secret",
                            url=f"https://github.com/{CANARY_VV}/pull/1",
                            is_private=True,
                        )
                    ],
                    contributions=[
                        _contrib(owner=owner, name=name, count=2, is_private=True)
                    ],
                )
            )
        )
        blob = repr(model)
        self.assertNotIn(CANARY_VV, blob)
        self.assertNotIn("private-client-project", blob)
        self.assertNotIn("secret", blob)
        self.assertGreater(model.private_count, 0)


if __name__ == "__main__":
    unittest.main()
