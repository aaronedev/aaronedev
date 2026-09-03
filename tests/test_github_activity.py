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
    CONTRIB_REPO_LIMIT,
    MAX_HISTORY_PAGES,
    MAX_PR_PAGES,
    PAGE_SIZE,
    PROFILE_TIMEZONE,
    PR_LIMIT,
    PROFILE_REPO,
)
from scripts.github_activity import (  # noqa: E402
    ActivityCollectionError,
    normalize,
    privacy_reduce,
    render,
    retrieve,
    default_http,
)
from scripts.http_json import HttpJsonTransportError  # noqa: E402

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
    owner_type: str | None = None,
) -> dict:
    name_with_owner = f"{owner}/{name}"
    repo_owner = {"login": owner}
    if owner_type is not None:
        repo_owner["__typename"] = owner_type
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
            "owner": repo_owner,
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
    owner_type: str | None = None,
) -> dict:
    name_with_owner = f"{owner}/{name}"
    repository = {
        "nameWithOwner": name_with_owner,
        "isPrivate": is_private,
        "url": repo_url or f"https://github.com/{name_with_owner}",
        "description": description,
    }
    if owner_login is not False:
        repository["owner"] = {
            "login": owner if owner_login is None else owner_login,
        }
        if owner_type is not None:
            repository["owner"]["__typename"] = owner_type
    return {"contributionCount": count, "repository": repository}


def _issue_contribution(
    *,
    owner: str,
    name: str,
    occurred_at: str = "2026-08-21T12:00:00Z",
    is_private: bool = False,
    is_restricted: bool = False,
    description: str | None = "A public repository",
    repo_url: str | None = None,
    issue_url: str | None = None,
    owner_type: str | None = None,
) -> dict:
    name_with_owner = f"{owner}/{name}"
    repo_owner = {"login": owner}
    if owner_type is not None:
        repo_owner["__typename"] = owner_type
    return {
        "occurredAt": occurred_at,
        "isRestricted": is_restricted,
        "issue": {
            "url": issue_url or f"https://github.com/{name_with_owner}/issues/1",
            "repository": {
                "nameWithOwner": name_with_owner,
                "isPrivate": is_private,
                "url": repo_url or f"https://github.com/{name_with_owner}",
                "description": description,
                "owner": repo_owner,
            },
        },
    }


def _raw(
    *,
    pull_requests=None,
    contributions=None,
    issue_contributions=None,
    commit_dates=None,
    commit_dates_by_repo=None,
    contribution_repos_bounded=None,
) -> dict:
    payload = {
        "pull_requests": list(pull_requests or []),
        "contributions": list(contributions or []),
        "issue_contributions": list(issue_contributions or []),
    }
    if commit_dates is not None:
        payload["commit_dates"] = list(commit_dates)
    if commit_dates_by_repo is not None:
        payload["commit_dates_by_repo"] = dict(commit_dates_by_repo)
    if contribution_repos_bounded is not None:
        payload["contribution_repos_bounded"] = contribution_repos_bounded
    return payload


def _rendered_from_raw(raw: dict) -> str:
    return render(privacy_reduce(normalize(raw)))


class ConfigContractTest(unittest.TestCase):
    def test_constants_come_from_single_module(self) -> None:
        self.assertEqual(AUTHOR_LOGIN, "aaronedev")
        self.assertEqual(PROFILE_REPO, "aaronedev/aaronedev")
        self.assertEqual(PR_LIMIT, 8)
        self.assertEqual(CONTRIB_LIMIT, 10)
        self.assertEqual(CONTRIB_REPO_LIMIT, 100)
        self.assertEqual(MAX_PR_PAGES, 100)
        self.assertEqual(MAX_HISTORY_PAGES, 100)
        self.assertEqual(PAGE_SIZE, 100)
        self.assertEqual(PROFILE_TIMEZONE, "Europe/Berlin")
        self.assertIn("aaronedev", ALLOWED_OWNERS)
        self.assertIn("Violet-Void", ALLOWED_OWNERS)
        self.assertIn("bauerstischfinder", ALLOWED_OWNERS)


class NormalizeTest(unittest.TestCase):
    def test_direct_graphql_contributions_prefer_user_and_support_legacy_viewer(
        self,
    ) -> None:
        contribution = {
            "contributions": {"totalCount": 3},
            "repository": _contrib(
                owner="aaronedev", name="public-dotfiles", count=0
            )["repository"],
        }
        legacy_contribution = {
            "contributions": {"totalCount": 99},
            "repository": _contrib(
                owner="aaronedev", name="public-dotfiles", count=0
            )["repository"],
        }
        user_raw = {
            "data": {
                "user": {
                    "contributionsCollection": {
                        "commitContributionsByRepository": [contribution],
                    }
                },
                "viewer": {
                    "contributionsCollection": {
                        "commitContributionsByRepository": [legacy_contribution],
                    }
                },
            }
        }
        legacy_viewer_raw = {
            "data": {
                "viewer": {
                    "contributionsCollection": {
                        "commitContributionsByRepository": [legacy_contribution],
                    }
                }
            }
        }

        self.assertEqual(
            normalize(user_raw)["contributions"],
            [_contrib(owner="aaronedev", name="public-dotfiles", count=3)],
        )
        self.assertEqual(
            normalize(legacy_viewer_raw)["contributions"],
            [_contrib(owner="aaronedev", name="public-dotfiles", count=99)],
        )

    def test_contribution_repo_bound_is_inferred_at_exact_api_limit(self) -> None:
        entries = [
            _contrib(owner="aaronedev", name=f"repo-{index}", count=1)
            for index in range(CONTRIB_REPO_LIMIT)
        ]
        bounded = normalize(_raw(contributions=entries))
        unbounded = normalize(_raw(contributions=entries[:-1]))

        self.assertTrue(bounded["contribution_repos_bounded"])
        self.assertFalse(unbounded["contribution_repos_bounded"])


class PrivacyReduceTest(unittest.TestCase):
    def test_external_organization_pr_and_issue_without_commit_bucket_render_once(
        self,
    ) -> None:
        pull_request = _pr_node(
            owner="community-org",
            name="public-library",
            title="public contribution",
            url="https://github.com/community-org/public-library/pull/1",
            description="public <library>",
            owner_type="Organization",
        )
        issue_contribution = _issue_contribution(
            owner="community-org",
            name="public-library",
            issue_url="https://github.com/community-org/public-library/issues/1",
            owner_type="Organization",
        )
        markdown = _rendered_from_raw(
            _raw(
                pull_requests=[pull_request, dict(pull_request)],
                issue_contributions=[issue_contribution, dict(issue_contribution)],
            )
        )

        external_heading = "### 🤝 Contributions to Other Organizations"
        self.assertIn(external_heading, markdown)
        self.assertEqual(
            markdown.count("<code>community-org/public-library</code>"), 1
        )
        self.assertIn("1 pull request", markdown)
        self.assertIn("1 issue", markdown)
        self.assertIn("public &lt;library&gt;", markdown)

    def test_public_external_organization_contributions_have_a_separate_category(
        self,
    ) -> None:
        markdown = _rendered_from_raw(
            _raw(
                contributions=[
                    _contrib(
                        owner="aaronedev",
                        name="public-dotfiles",
                        count=2,
                    ),
                    _contrib(
                        owner="community-org",
                        name="public-library",
                        count=5,
                        owner_type="Organization",
                    ),
                ]
            )
        )

        owned_heading = "### 🛠️ Latest Contributions"
        external_heading = "### 🤝 Contributions to Other Organizations"
        self.assertIn(owned_heading, markdown)
        self.assertIn(external_heading, markdown)
        self.assertLess(markdown.index(owned_heading), markdown.index("aaronedev/public-dotfiles"))
        self.assertLess(markdown.index(external_heading), markdown.index("community-org/public-library"))
        self.assertNotIn(
            "community-org/public-library",
            markdown[markdown.index(owned_heading) : markdown.index(external_heading)],
        )

    def test_external_organization_activity_combines_commit_pr_and_issue_counts(
        self,
    ) -> None:
        markdown = _rendered_from_raw(
            _raw(
                pull_requests=[
                    _pr_node(
                        owner="community-org",
                        name="public-library",
                        title="public contribution",
                        url="https://github.com/community-org/public-library/pull/1",
                        owner_type="Organization",
                    )
                ],
                contributions=[
                    _contrib(
                        owner="community-org",
                        name="public-library",
                        count=1,
                        owner_type="Organization",
                    )
                ],
                issue_contributions=[
                    _issue_contribution(
                        owner="community-org",
                        name="public-library",
                        issue_url="https://github.com/community-org/public-library/issues/1",
                        owner_type="Organization",
                    )
                ],
            )
        )

        self.assertIn(
            "<strong>1 commit · 1 pull request · 1 issue</strong>", markdown
        )

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

    def test_case_variant_of_an_allowed_owner_is_included(self) -> None:
        owner = "VIOLET-VOID"
        name = "case-variant"
        markdown = _rendered_from_raw(
            _raw(
                pull_requests=[
                    _pr_node(
                        owner=owner,
                        name=name,
                        title="case variant public pr",
                        url=f"https://github.com/{owner}/{name}/pull/1",
                    )
                ],
                contributions=[_contrib(owner=owner, name=name, count=3)],
            )
        )

        self.assertIn(f"{owner}/{name}", markdown)
        self.assertIn("case variant public pr", markdown)

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
        self.assertIn("🔒 Private activity: 1 pull request · 4 commits", markdown)

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
        self.assertIn("🔒 Private activity: 1 pull request · 7 commits", markdown)

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

    def test_external_user_owned_contributions_are_excluded(self) -> None:
        markdown = _rendered_from_raw(
            _raw(
                contributions=[
                    _contrib(
                        owner="outside-user",
                        name="public-fork",
                        count=7,
                        owner_type="User",
                    )
                ]
            )
        )

        self.assertNotIn("outside-user/public-fork", markdown)
        self.assertNotIn("7 commits", markdown)

    def test_external_user_prs_and_issues_are_excluded(self) -> None:
        markdown = _rendered_from_raw(
            _raw(
                pull_requests=[
                    _pr_node(
                        owner="outside-user",
                        name="public-fork",
                        title="do not show",
                        url="https://github.com/outside-user/public-fork/pull/1",
                        owner_type="User",
                    )
                ],
                issue_contributions=[
                    _issue_contribution(
                        owner="outside-user",
                        name="public-fork",
                        issue_url="https://github.com/outside-user/public-fork/issues/1",
                        owner_type="User",
                    )
                ],
            )
        )

        self.assertNotIn("outside-user/public-fork", markdown)
        self.assertNotIn("do not show", markdown)
        self.assertNotIn("1 pull request", markdown)
        self.assertNotIn("1 issue", markdown)

    def test_external_private_organization_is_neither_rendered_nor_aggregated(
        self,
    ) -> None:
        markdown = _rendered_from_raw(
            _raw(
                contributions=[
                    _contrib(
                        owner="external-private-org",
                        name="confidential-work",
                        count=7,
                        is_private=True,
                        description="do not expose this",
                        owner_type="Organization",
                    )
                ]
            )
        )

        self.assertNotIn("external-private-org/confidential-work", markdown)
        self.assertNotIn("confidential-work", markdown)
        self.assertNotIn("do not expose this", markdown)
        self.assertNotIn("7 commits", markdown)
        self.assertNotIn("🔒 Private activity:", markdown)

    def test_external_private_and_restricted_issues_do_not_leak_metadata(self) -> None:
        markdown = _rendered_from_raw(
            _raw(
                pull_requests=[
                    _pr_node(
                        owner="private-org",
                        name="confidential-issue-tracker",
                        title="private pull request title",
                        url="https://github.com/private-org/confidential-issue-tracker/pull/1",
                        is_private=True,
                        owner_type="Organization",
                    )
                ],
                issue_contributions=[
                    _issue_contribution(
                        owner="private-org",
                        name="confidential-issue-tracker",
                        is_private=True,
                        description="private issue description",
                        issue_url="https://github.com/private-org/confidential-issue-tracker/issues/1",
                        owner_type="Organization",
                    ),
                    _issue_contribution(
                        owner="restricted-org",
                        name="restricted-issue-tracker",
                        is_restricted=True,
                        description="restricted issue description",
                        issue_url="https://github.com/restricted-org/restricted-issue-tracker/issues/1",
                        owner_type="Organization",
                    ),
                ]
            )
        )

        self.assertNotIn("private-org/confidential-issue-tracker", markdown)
        self.assertNotIn("private pull request title", markdown)
        self.assertNotIn("private issue description", markdown)
        self.assertNotIn("restricted-org/restricted-issue-tracker", markdown)
        self.assertNotIn("restricted issue description", markdown)
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

    def test_case_variant_profile_repo_is_excluded_from_public_contribs(self) -> None:
        owner, name = (part.upper() for part in PROFILE_REPO.split("/", 1))
        markdown = _rendered_from_raw(
            _raw(contributions=[_contrib(owner=owner, name=name, count=3)])
        )

        self.assertNotIn(f"{owner}/{name}", markdown)

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
                    title="Array<T>",
                    url='https://github.com/aaronedev/public-dotfiles/pull/2?x="quoted"',
                    repo_url='https://github.com/aaronedev/public-dotfiles?x="quoted"',
                    description="<b>unclosed",
                )
            ],
            contributions=[
                _contrib(
                    owner="aaronedev",
                    name="public-dotfiles",
                    count=1,
                    description="Array<T> <script>alert(1)</script>",
                )
            ],
        )
        markdown = _rendered_from_raw(raw)
        self.assertIn("Array&lt;T&gt;", markdown)
        self.assertIn("&lt;script&gt;", markdown)
        self.assertIn("&lt;b&gt;unclosed", markdown)
        self.assertIn("x=&quot;quoted&quot;", markdown)
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
            commit_dates_by_repo={
                "aaronedev/zeta": ["2026-08-19T12:00:00Z"],
                "aaronedev/alpha": ["2026-08-20T12:00:00Z"],
                "Violet-Void/theme": ["2026-08-22T12:00:00Z"],
            },
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
        self.assertIn("2026-08-22", markdown)

    def test_missing_contribution_timestamp_sorts_last(self) -> None:
        markdown = _rendered_from_raw(
            _raw(
                contributions=[
                    _contrib(owner="aaronedev", name="dated", count=1),
                    _contrib(owner="aaronedev", name="undated", count=100),
                ],
                commit_dates_by_repo={
                    "aaronedev/dated": ["2026-08-22T12:00:00Z"],
                },
            )
        )
        self.assertLess(markdown.index("aaronedev/dated"), markdown.index("aaronedev/undated"))

    def test_external_organization_ordering_and_limit_are_independent(self) -> None:
        raw = _raw(
            contributions=[
                _contrib(owner="aaronedev", name="owned-one", count=1),
                _contrib(owner="aaronedev", name="owned-two", count=2),
                _contrib(
                    owner="outside-org",
                    name="zeta",
                    count=3,
                    owner_type="Organization",
                ),
                _contrib(
                    owner="outside-org",
                    name="alpha",
                    count=4,
                    owner_type="Organization",
                ),
                _contrib(
                    owner="outside-org",
                    name="older",
                    count=5,
                    owner_type="Organization",
                ),
            ],
            commit_dates_by_repo={
                "aaronedev/owned-one": ["2026-08-22T12:00:00Z"],
                "aaronedev/owned-two": ["2026-08-21T12:00:00Z"],
                "outside-org/zeta": ["2026-08-22T12:00:00Z"],
                "outside-org/alpha": ["2026-08-22T12:00:00Z"],
                "outside-org/older": ["2026-08-21T12:00:00Z"],
            },
        )

        with mock.patch("scripts.github_activity.CONTRIB_LIMIT", 2):
            model = privacy_reduce(normalize(raw))

        self.assertEqual(
            [contrib.repo_name for contrib in model.public_contribs],
            ["aaronedev/owned-one", "aaronedev/owned-two"],
        )
        self.assertEqual(
            [activity.repo_name for activity in model.external_org_activities],
            ["outside-org/alpha", "outside-org/zeta"],
        )

    def test_timezone_buckets_use_profile_timezone(self) -> None:
        model = privacy_reduce(
            normalize(_raw(commit_dates=["2026-01-04T23:30:00Z"]))
        )
        self.assertEqual(model.commit_hours["night"], 1)
        self.assertEqual(model.commit_weekdays["Monday"], 1)

    def test_bounded_private_commits_are_conservative_and_private_dates_feed_timing(
        self,
    ) -> None:
        owner, name = CANARY_VV.split("/", 1)
        raw = _raw(
            contributions=[_contrib(owner=owner, name=name, count=4, is_private=True)],
            commit_dates=["2026-01-04T23:30:00Z"],
            commit_dates_by_repo={CANARY_VV: ["2026-01-04T23:30:00Z"]},
            contribution_repos_bounded=True,
        )
        model = privacy_reduce(normalize(raw))
        markdown = render(model)

        self.assertTrue(model.contribution_repos_bounded)
        self.assertEqual(model.commit_hours["night"], 1)
        self.assertEqual(model.commit_weekdays["Monday"], 1)
        self.assertIn(
            f"Commit contribution totals are based on the top {CONTRIB_REPO_LIMIT} "
            "contribution repositories.",
            markdown,
        )
        self.assertIn("at least 4 commits", markdown)
        self.assertNotIn(CANARY_VV, markdown)

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
    def setUp(self) -> None:
        self.issue_contribution_patcher = mock.patch(
            "scripts.github_activity._retrieve_issue_contributions",
            return_value=[],
        )
        self.issue_contribution_patcher.start()

    def tearDown(self) -> None:
        self.issue_contribution_patcher.stop()

    def test_pr_pagination_reaches_older_boundary_after_more_than_ten_pages(
        self,
    ) -> None:
        pr_calls = 0

        def http(url, *, method="GET", headers=None, json_body=None):
            nonlocal pr_calls
            query = (json_body or {}).get("query", "")
            if "commitContributionsByRepository" in query:
                return {
                    "status": 200,
                    "json": {
                        "data": {
                            "viewer": {"login": AUTHOR_LOGIN},
                            "user": {
                                "id": "UID",
                                "contributionsCollection": {
                                    "startedAt": "2026-08-01T00:00:00Z",
                                    "endedAt": "2026-08-31T00:00:00Z",
                                    "commitContributionsByRepository": [],
                                },
                            },
                        }
                    },
                }
            if "pullRequests" in query:
                pr_calls += 1
                if pr_calls <= 11:
                    node = _pr_node(
                        owner=UNRELATED_OWNER,
                        name=f"noise-{pr_calls}",
                        title=f"in-window {pr_calls}",
                        url=f"https://github.com/{UNRELATED_OWNER}/noise-{pr_calls}/pull/1",
                        created_at="2026-08-20T12:00:00Z",
                    )
                    cursor = f"page-{pr_calls}"
                else:
                    node = _pr_node(
                        owner=UNRELATED_OWNER,
                        name="older",
                        title="older boundary",
                        url=f"https://github.com/{UNRELATED_OWNER}/older/pull/1",
                        created_at="2026-07-31T23:59:59Z",
                    )
                    cursor = "unused"
                return {
                    "status": 200,
                    "json": {
                        "data": {
                            "user": {
                                "pullRequests": {
                                    "nodes": [node],
                                    "pageInfo": {
                                        "hasNextPage": True,
                                        "endCursor": cursor,
                                    },
                                }
                            }
                        }
                    },
                }
            raise AssertionError(f"unexpected query: {query}")

        raw = retrieve(http, token="token-value")

        self.assertEqual(pr_calls, 12)
        self.assertEqual(len(raw["pull_requests"]), 11)

    def test_prs_use_the_contribution_window_and_stop_after_an_older_page(self) -> None:
        in_window_public = _pr_node(
            owner="aaronedev",
            name="windowed-public",
            title="in window public",
            url="https://github.com/aaronedev/windowed-public/pull/1",
            created_at="2026-08-31T00:00:00Z",
        )
        in_window_private = _pr_node(
            owner="Violet-Void",
            name="windowed-private",
            title="in window private",
            url="https://github.com/Violet-Void/windowed-private/pull/2",
            created_at="2026-08-01T00:00:00Z",
            is_private=True,
        )
        newer = _pr_node(
            owner="aaronedev",
            name="newer",
            title="too new",
            url="https://github.com/aaronedev/newer/pull/3",
            created_at="2026-09-01T00:00:01Z",
        )
        malformed = _pr_node(
            owner="aaronedev",
            name="malformed",
            title="malformed date",
            url="https://github.com/aaronedev/malformed/pull/4",
            created_at="not-a-date",
        )
        older = _pr_node(
            owner="aaronedev",
            name="older",
            title="too old",
            url="https://github.com/aaronedev/older/pull/5",
            created_at="2026-07-31T23:59:59Z",
        )
        queries: list[str] = []
        pr_calls = 0

        def http(url, *, method="GET", headers=None, json_body=None):
            nonlocal pr_calls
            query = (json_body or {}).get("query", "")
            queries.append(query)
            if "commitContributionsByRepository" in query:
                return {
                    "status": 200,
                    "json": {
                        "data": {
                            "viewer": {"login": AUTHOR_LOGIN},
                            "user": {
                                "id": "UID",
                                "contributionsCollection": {
                                    "startedAt": "2026-08-01T00:00:00Z",
                                    "endedAt": "2026-08-31T00:00:00Z",
                                    "commitContributionsByRepository": [
                                        _contrib(
                                            owner="Violet-Void",
                                            name="windowed-private",
                                            count=5,
                                            is_private=True,
                                        )
                                    ],
                                },
                            },
                        }
                    },
                }
            if "pullRequests" in query:
                pr_calls += 1
                return {
                    "status": 200,
                    "json": {
                        "data": {
                            "user": {
                                "pullRequests": {
                                    "nodes": [
                                        newer,
                                        in_window_public,
                                        in_window_private,
                                        malformed,
                                        older,
                                    ],
                                    "pageInfo": {
                                        "hasNextPage": True,
                                        "endCursor": "should-not-be-used",
                                    },
                                }
                            }
                        }
                    },
                }
            raise AssertionError(f"unexpected query: {query}")

        with mock.patch("scripts.github_activity._collect_commit_dates", return_value={}):
            raw = retrieve(http, token="token-value")

        self.assertIn("commitContributionsByRepository", queries[0])
        self.assertEqual(pr_calls, 1)
        self.assertEqual(raw["pull_requests"], [in_window_public, in_window_private])
        model = privacy_reduce(normalize(raw))
        self.assertEqual(model.private_pr_count, 1)
        self.assertEqual(model.private_commit_count, 5)

    def test_retrieve_marks_exact_contribution_repository_limit_as_bounded(self) -> None:
        contributions = [
            _contrib(owner="aaronedev", name=f"repo-{index}", count=1)
            for index in range(CONTRIB_REPO_LIMIT)
        ]
        queries: list[str] = []

        def http(url, *, method="GET", headers=None, json_body=None):
            query = (json_body or {}).get("query", "")
            queries.append(query)
            if "pullRequests" in query:
                return {
                    "status": 200,
                    "json": {"data": {"user": {"pullRequests": {"nodes": [], "pageInfo": {"hasNextPage": False}}}}},
                }
            return {
                "status": 200,
                "json": {
                    "data": {
                        "viewer": {"login": AUTHOR_LOGIN},
                        "user": {
                            "id": "UID",
                            "contributionsCollection": {
                                "startedAt": "2026-08-01T00:00:00Z",
                                "endedAt": "2026-08-31T00:00:00Z",
                                "commitContributionsByRepository": contributions,
                            },
                        },
                    }
                },
            }

        with mock.patch("scripts.github_activity._collect_commit_dates", return_value={}):
            raw = retrieve(http, token="token-value")

        self.assertTrue(raw["contribution_repos_bounded"])
        self.assertTrue(any("maxRepositories: 100" in query for query in queries))
        self.assertTrue(
            any("owner { login __typename }" in query for query in queries)
        )

    def test_private_pr_after_public_limit_is_counted(self) -> None:
        public_prs = [
            _pr_node(
                owner="aaronedev",
                name="public-dotfiles",
                title=f"public {number}",
                url=f"https://github.com/aaronedev/public-dotfiles/pull/{number}",
            )
            for number in range(1, PR_LIMIT + 1)
        ]
        owner, name = CANARY_VV.split("/", 1)
        private_pr = _pr_node(
            owner=owner,
            name=name,
            title="private after public limit",
            url=f"https://github.com/{CANARY_VV}/pull/9",
            is_private=True,
        )
        pr_cursors: list[str | None] = []

        def http(url, *, method="GET", headers=None, json_body=None):
            query = (json_body or {}).get("query", "")
            variables = (json_body or {}).get("variables") or {}
            if "pullRequests" in query:
                after = variables.get("after")
                pr_cursors.append(after)
                if after is None:
                    nodes = public_prs
                    page_info = {"hasNextPage": True, "endCursor": "page-two"}
                elif after == "page-two":
                    nodes = [private_pr]
                    page_info = {"hasNextPage": False, "endCursor": None}
                else:
                    raise AssertionError(f"unexpected PR cursor: {after}")
                return {
                    "status": 200,
                    "json": {
                        "data": {
                            "user": {"pullRequests": {"nodes": nodes, "pageInfo": page_info}}
                        }
                    },
                }
            if "commitContributionsByRepository" in query:
                return {
                    "status": 200,
                    "json": {
                        "data": {
                            "viewer": {"login": AUTHOR_LOGIN},
                            "user": {
                                "id": "UID",
                                "contributionsCollection": {
                                    "startedAt": "2026-08-01T00:00:00Z",
                                    "endedAt": "2026-08-31T00:00:00Z",
                                    "commitContributionsByRepository": [],
                                },
                            },
                        }
                    },
                }
            if "history" in query:
                return {"status": 200, "json": {"data": {"repository": None}}}
            raise AssertionError(f"unexpected query: {query}")

        model = privacy_reduce(normalize(retrieve(http, token="token-value")))
        self.assertEqual(pr_cursors, [None, "page-two"])
        self.assertEqual(model.private_pr_count, 1)

    def test_pr_missing_continuation_cursor_fails_closed(self) -> None:
        def http(url, *, method="GET", headers=None, json_body=None):
            query = (json_body or {}).get("query", "")
            if "commitContributionsByRepository" in query:
                return {
                    "status": 200,
                    "json": {
                        "data": {
                            "viewer": {"login": AUTHOR_LOGIN},
                            "user": {
                                "id": "UID",
                                "contributionsCollection": {
                                    "startedAt": "2026-08-01T00:00:00Z",
                                    "endedAt": "2026-08-31T00:00:00Z",
                                    "commitContributionsByRepository": [],
                                },
                            },
                        }
                    },
                }
            return {
                "status": 200,
                "json": {
                    "data": {
                        "user": {
                            "pullRequests": {
                                "nodes": [],
                                "pageInfo": {"hasNextPage": True, "endCursor": None},
                            }
                        }
                    }
                },
            }

        with self.assertRaises(ActivityCollectionError):
            retrieve(http, token="token-value")

    def test_pr_repeated_continuation_cursor_fails_closed(self) -> None:
        calls = 0

        def http(url, *, method="GET", headers=None, json_body=None):
            nonlocal calls
            query = (json_body or {}).get("query", "")
            if "pullRequests" in query:
                calls += 1
                return {
                    "status": 200,
                    "json": {
                        "data": {
                            "user": {
                                "pullRequests": {
                                    "nodes": [],
                                    "pageInfo": {
                                        "hasNextPage": True,
                                        "endCursor": "repeat",
                                    },
                                }
                            }
                        }
                    },
                }
            return {
                "status": 200,
                "json": {
                    "data": {
                        "viewer": {"login": AUTHOR_LOGIN},
                        "user": {
                            "id": "UID",
                            "contributionsCollection": {
                                "startedAt": "2026-08-01T00:00:00Z",
                                "endedAt": "2026-08-31T00:00:00Z",
                                "commitContributionsByRepository": [],
                            },
                        },
                    }
                },
            }

        with self.assertRaises(ActivityCollectionError):
            retrieve(http, token="token-value")
        self.assertEqual(calls, 2)

    def test_pr_page_cap_fails_closed(self) -> None:
        def http(url, *, method="GET", headers=None, json_body=None):
            query = (json_body or {}).get("query", "")
            if "commitContributionsByRepository" in query:
                return {
                    "status": 200,
                    "json": {
                        "data": {
                            "viewer": {"login": AUTHOR_LOGIN},
                            "user": {
                                "id": "UID",
                                "contributionsCollection": {
                                    "startedAt": "2026-08-01T00:00:00Z",
                                    "endedAt": "2026-08-31T00:00:00Z",
                                    "commitContributionsByRepository": [],
                                },
                            },
                        }
                    },
                }
            variables = (json_body or {}).get("variables") or {}
            after = variables.get("after") or "first"
            return {
                "status": 200,
                "json": {
                    "data": {
                        "user": {
                            "pullRequests": {
                                "nodes": [],
                                "pageInfo": {
                                    "hasNextPage": True,
                                    "endCursor": f"next-{after}",
                                },
                            }
                        }
                    }
                },
            }

        with mock.patch("scripts.github_activity.MAX_PR_PAGES", 2), self.assertRaises(
            ActivityCollectionError
        ):
            retrieve(http, token="token-value")

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
                            "viewer": {"login": AUTHOR_LOGIN},
                            "user": {
                                "id": "UID",
                                "contributionsCollection": {
                                    "startedAt": "2026-08-01T00:00:00Z",
                                    "endedAt": "2026-08-31T00:00:00Z",
                                    "commitContributionsByRepository": []
                                },
                            },
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

    def test_author_mismatch_fails_closed(self) -> None:
        def http(url, *, method="GET", headers=None, json_body=None):
            query = (json_body or {}).get("query", "")
            if "pullRequests" in query:
                return {
                    "status": 200,
                    "json": {"data": {"user": {"pullRequests": {"nodes": [], "pageInfo": {"hasNextPage": False}}}}},
                }
            return {"status": 200, "json": {"data": {"viewer": {"login": "other"}, "user": {}}}}

        with self.assertRaises(ActivityCollectionError):
            retrieve(http, token="token-value")

    def test_history_repeated_cursor_fails_closed(self) -> None:
        calls = 0

        def http(url, *, method="GET", headers=None, json_body=None):
            nonlocal calls
            query = (json_body or {}).get("query", "")
            if "pullRequests" in query:
                return {
                    "status": 200,
                    "json": {"data": {"user": {"pullRequests": {"nodes": [], "pageInfo": {"hasNextPage": False}}}}},
                }
            if "commitContributionsByRepository" in query:
                return {
                    "status": 200,
                    "json": {"data": {"viewer": {"login": AUTHOR_LOGIN}, "user": {"id": "UID", "contributionsCollection": {"startedAt": "2026-08-01T00:00:00Z", "endedAt": "2026-08-31T00:00:00Z", "commitContributionsByRepository": [_contrib(owner="aaronedev", name="repo", count=1)]}}}},
                }
            calls += 1
            return {"status": 200, "json": {"data": {"repository": {"defaultBranchRef": {"target": {"history": {"nodes": [], "pageInfo": {"hasNextPage": True, "endCursor": "repeat"}}}}}}}}

        with self.assertRaises(ActivityCollectionError):
            retrieve(http, token="token-value")
        self.assertEqual(calls, 2)

    def test_history_page_cap_fails_closed(self) -> None:
        def http(url, *, method="GET", headers=None, json_body=None):
            query = (json_body or {}).get("query", "")
            if "pullRequests" in query:
                return {"status": 200, "json": {"data": {"user": {"pullRequests": {"nodes": [], "pageInfo": {"hasNextPage": False}}}}}}
            if "commitContributionsByRepository" in query:
                return {"status": 200, "json": {"data": {"viewer": {"login": AUTHOR_LOGIN}, "user": {"id": "UID", "contributionsCollection": {"startedAt": "2026-08-01T00:00:00Z", "endedAt": "2026-08-31T00:00:00Z", "commitContributionsByRepository": [_contrib(owner="aaronedev", name="repo", count=1)]}}}}}
            after = ((json_body or {}).get("variables") or {}).get("after") or "first"
            return {"status": 200, "json": {"data": {"repository": {"defaultBranchRef": {"target": {"history": {"nodes": [], "pageInfo": {"hasNextPage": True, "endCursor": f"next-{after}"}}}}}}}}

        with mock.patch("scripts.github_activity.MAX_HISTORY_PAGES", 2), self.assertRaises(ActivityCollectionError):
            retrieve(http, token="token-value")

    def test_default_http_translates_shared_transport_error(self) -> None:
        with mock.patch(
            "scripts.github_activity.request_json",
            side_effect=HttpJsonTransportError("transport"),
        ):
            with self.assertRaises(ActivityCollectionError):
                default_http("https://example.test")

    def test_commit_history_includes_only_public_external_organizations(self) -> None:
        queried_repos = []
        history_variables = []

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
                            "viewer": {"login": AUTHOR_LOGIN},
                            "user": {
                                "id": "UID",
                                "contributionsCollection": {
                                    "startedAt": "2026-08-01T00:00:00Z",
                                    "endedAt": "2026-08-31T00:00:00Z",
                                    "commitContributionsByRepository": [
                                        _contrib(
                                            owner=UNRELATED_OWNER,
                                            name="noise",
                                            count=4,
                                            owner_type="User",
                                        ),
                                        _contrib(
                                            owner="external-public-org",
                                            name="public-library",
                                            count=4,
                                            owner_type="Organization",
                                        ),
                                        _contrib(
                                            owner="external-private-org",
                                            name="private-library",
                                            count=4,
                                            is_private=True,
                                            owner_type="Organization",
                                        ),
                                        _contrib(
                                            owner="aaronedev",
                                            name="public-dotfiles",
                                            count=2,
                                        ),
                                        _contrib(
                                            owner="Violet-Void",
                                            name="private-timing-only",
                                            count=1,
                                            is_private=True,
                                        ),
                                    ]
                                },
                            },
                        }
                    },
                }
            if "history" in query:
                queried_repos.append(
                    f"{variables.get('owner')}/{variables.get('name')}"
                )
                history_variables.append(variables)
                after = variables.get("after")
                return {
                    "status": 200,
                    "json": {
                        "data": {
                            "repository": {
                                "defaultBranchRef": {
                                    "target": {
                                        "history": {
                                            "nodes": [
                                                {"committedDate": "2026-01-04T23:30:00Z"}
                                            ],
                                            "pageInfo": {
                                                "hasNextPage": after is None,
                                                "endCursor": "history-page-2" if after is None else None,
                                            },
                                        }
                                    }
                                }
                            }
                        }
                    },
                }
            raise AssertionError(query)

        raw = retrieve(http, token="token-value")
        self.assertIn("aaronedev/public-dotfiles", queried_repos)
        self.assertIn("Violet-Void/private-timing-only", queried_repos)
        self.assertIn("external-public-org/public-library", queried_repos)
        self.assertNotIn(f"{UNRELATED_OWNER}/noise", queried_repos)
        self.assertNotIn("external-private-org/private-library", queried_repos)
        self.assertNotIn(CANARY_VV, queried_repos)
        self.assertNotIn(CANARY_BF, queried_repos)
        self.assertEqual(history_variables[0]["authorId"], "UID")
        self.assertEqual(history_variables[0]["since"], "2026-08-01T00:00:00Z")
        self.assertEqual(history_variables[0]["until"], "2026-08-31T00:00:00Z")
        self.assertEqual(history_variables[1]["after"], "history-page-2")
        self.assertEqual(
            raw["commit_dates_by_repo"]["aaronedev/public-dotfiles"],
            ["2026-01-04T23:30:00Z", "2026-01-04T23:30:00Z"],
        )
        model = privacy_reduce(normalize(raw))
        self.assertEqual(model.commit_hours["night"], 6)
        self.assertEqual(model.commit_weekdays["Monday"], 6)
        self.assertNotIn("private-timing-only", render(model))
        self.assertNotIn("private-library", render(model))

    def test_pr_only_external_organization_does_not_query_commit_history(self) -> None:
        queried_repos: list[str] = []
        external_pr = _pr_node(
            owner="external-public-org",
            name="public-library",
            title="public contribution",
            url="https://github.com/external-public-org/public-library/pull/1",
            owner_type="Organization",
        )

        def http(url, *, method="GET", headers=None, json_body=None):
            query = (json_body or {}).get("query", "")
            variables = (json_body or {}).get("variables") or {}
            if "commitContributionsByRepository" in query:
                return {
                    "status": 200,
                    "json": {
                        "data": {
                            "viewer": {"login": AUTHOR_LOGIN},
                            "user": {
                                "id": "UID",
                                "contributionsCollection": {
                                    "startedAt": "2026-08-01T00:00:00Z",
                                    "endedAt": "2026-08-31T00:00:00Z",
                                    "commitContributionsByRepository": [],
                                },
                            },
                        }
                    },
                }
            if "pullRequests" in query:
                return {
                    "status": 200,
                    "json": {
                        "data": {
                            "user": {
                                "pullRequests": {
                                    "nodes": [external_pr],
                                    "pageInfo": {"hasNextPage": False, "endCursor": None},
                                }
                            }
                        }
                    },
                }
            if "history" in query:
                queried_repos.append(
                    f"{variables.get('owner')}/{variables.get('name')}"
                )
                return {"status": 200, "json": {"data": {"repository": None}}}
            raise AssertionError(f"unexpected query: {query}")

        raw = retrieve(http, token="token-value")

        self.assertEqual(queried_repos, [])
        model = privacy_reduce(normalize(raw))
        self.assertEqual(
            [(item.repo_name, item.pull_request_count) for item in model.external_org_activities],
            [("external-public-org/public-library", 1)],
        )


class IssueContributionRetrieveTest(unittest.TestCase):
    @staticmethod
    def _contribution_response() -> dict:
        return {
            "status": 200,
            "json": {
                "data": {
                    "viewer": {"login": AUTHOR_LOGIN},
                    "user": {
                        "id": "UID",
                        "contributionsCollection": {
                            "startedAt": "2026-08-01T00:00:00Z",
                            "endedAt": "2026-08-31T00:00:00Z",
                            "commitContributionsByRepository": [],
                        },
                    },
                }
            },
        }

    def test_retrieve_collects_paginated_issue_contributions_and_queries_typenames(
        self,
    ) -> None:
        first_issue = _issue_contribution(
            owner="community-org",
            name="public-library",
            occurred_at="2026-08-20T12:00:00Z",
            issue_url="https://github.com/community-org/public-library/issues/1",
            owner_type="Organization",
        )
        second_issue = _issue_contribution(
            owner="community-org",
            name="public-library",
            occurred_at="2026-08-19T12:00:00Z",
            issue_url="https://github.com/community-org/public-library/issues/2",
            owner_type="Organization",
        )
        queries: list[str] = []
        issue_cursors: list[str | None] = []

        def http(url, *, method="GET", headers=None, json_body=None):
            query = (json_body or {}).get("query", "")
            variables = (json_body or {}).get("variables") or {}
            queries.append(query)
            if "commitContributionsByRepository" in query:
                return self._contribution_response()
            if "issueContributions" in query:
                after = variables.get("after")
                issue_cursors.append(after)
                if after is None:
                    nodes = [first_issue]
                    page_info = {"hasNextPage": True, "endCursor": "issue-page-2"}
                elif after == "issue-page-2":
                    nodes = [second_issue]
                    page_info = {"hasNextPage": False, "endCursor": None}
                else:
                    raise AssertionError(f"unexpected issue cursor: {after}")
                return {
                    "status": 200,
                    "json": {
                        "data": {
                            "user": {
                                "contributionsCollection": {
                                    "issueContributions": {
                                        "nodes": nodes,
                                        "pageInfo": page_info,
                                    }
                                }
                            }
                        }
                    },
                }
            if "pullRequests" in query:
                return {
                    "status": 200,
                    "json": {
                        "data": {
                            "user": {
                                "pullRequests": {
                                    "nodes": [],
                                    "pageInfo": {"hasNextPage": False, "endCursor": None},
                                }
                            }
                        }
                    },
                }
            raise AssertionError(f"unexpected query: {query}")

        with mock.patch("scripts.github_activity._collect_commit_dates", return_value={}):
            raw = retrieve(http, token="token-value")

        self.assertEqual(issue_cursors, [None, "issue-page-2"])
        self.assertEqual(raw["issue_contributions"], [first_issue, second_issue])
        self.assertEqual(normalize(raw)["issue_contributions"], [first_issue, second_issue])
        pr_query = next(query for query in queries if "pullRequests" in query)
        issue_query = next(query for query in queries if "issueContributions" in query)
        self.assertIn("owner { login __typename }", pr_query)
        self.assertIn("owner { login __typename }", issue_query)
        self.assertIn(
            "issueContributions(first: $first, after: $after, orderBy: {direction: DESC})",
            issue_query,
        )

    def test_issue_contribution_collection_unavailable_fails_closed(self) -> None:
        def http(url, *, method="GET", headers=None, json_body=None):
            query = (json_body or {}).get("query", "")
            if "commitContributionsByRepository" in query:
                return self._contribution_response()
            if "issueContributions" in query:
                return {"status": 200, "json": {"data": {"user": {}}}}
            raise AssertionError(f"unexpected query: {query}")

        with self.assertRaises(ActivityCollectionError):
            retrieve(http, token="token-value")

    def test_issue_contribution_pagination_rejects_missing_cursor(self) -> None:
        def http(url, *, method="GET", headers=None, json_body=None):
            query = (json_body or {}).get("query", "")
            if "commitContributionsByRepository" in query:
                return self._contribution_response()
            if "issueContributions" in query:
                return {
                    "status": 200,
                    "json": {
                        "data": {
                            "user": {
                                "contributionsCollection": {
                                    "issueContributions": {
                                        "nodes": [],
                                        "pageInfo": {
                                            "hasNextPage": True,
                                            "endCursor": None,
                                        },
                                    }
                                }
                            }
                        }
                    },
                }
            raise AssertionError(f"unexpected query: {query}")

        with self.assertRaises(ActivityCollectionError):
            retrieve(http, token="token-value")

    def test_issue_contribution_pagination_rejects_repeated_cursor(self) -> None:
        calls = 0

        def http(url, *, method="GET", headers=None, json_body=None):
            nonlocal calls
            query = (json_body or {}).get("query", "")
            if "commitContributionsByRepository" in query:
                return self._contribution_response()
            if "issueContributions" in query:
                calls += 1
                return {
                    "status": 200,
                    "json": {
                        "data": {
                            "user": {
                                "contributionsCollection": {
                                    "issueContributions": {
                                        "nodes": [],
                                        "pageInfo": {
                                            "hasNextPage": True,
                                            "endCursor": "repeat",
                                        },
                                    }
                                }
                            }
                        }
                    },
                }
            raise AssertionError(f"unexpected query: {query}")

        with self.assertRaises(ActivityCollectionError):
            retrieve(http, token="token-value")
        self.assertEqual(calls, 2)


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
        self.assertEqual(model.private_pr_count, 1)
        self.assertEqual(model.private_commit_count, 2)


if __name__ == "__main__":
    unittest.main()
