from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "readme.yaml"


class ReadmeWorkflowContractTest(unittest.TestCase):
    def _find_fragment(self, workflow: str, fragment: str, start: int = 0) -> int:
        position = workflow.find(fragment, start)
        self.assertGreaterEqual(
            position, 0, f"workflow is missing required fragment: {fragment!r}"
        )
        return position

    def test_post_sync_rerender_has_renderer_credentials_and_precedes_push(self) -> None:
        workflow = WORKFLOW.read_text(encoding="utf-8")
        commit_step = workflow[
            self._find_fragment(workflow, "- name: Commit and push updates") :
        ]

        self.assertIn("README_ACTIVITY_GITHUB_PAT: ${{ secrets.GH_TOKEN }}", commit_step)
        self.assertIn(
            "README_WAKATIME_API_KEY: ${{ secrets.WAKATIME_API_KEY }}", commit_step
        )
        self.assertNotIn('cp README.md "$rendered_readme"', commit_step)
        sync = self._find_fragment(
            commit_step,
            "git pull --rebase --autostash --strategy-option=theirs origin main",
        )
        recovery_reset = self._find_fragment(commit_step, "git reset --hard origin/main")
        rerender = self._find_fragment(commit_step, "python3 scripts/render_readme.py", sync)
        push = self._find_fragment(commit_step, "git push origin HEAD:main")
        self.assertLess(sync, rerender)
        self.assertLess(recovery_reset, rerender)
        self.assertLess(rerender, push)
        self.assertIn(
            "git add -- README.md assets/generated/violet-void-org-stats.svg "
            "assets/generated/violet-void-org-languages.svg",
            commit_step,
        )
        self.assertIn('exit "$rerender_status"', commit_step)

    def test_organization_stats_fail_closed_and_are_committed(self) -> None:
        workflow = WORKFLOW.read_text(encoding="utf-8")
        self.assertEqual(workflow.count("README_ORG_STATS_TOKEN: ${{ secrets.GH_TOKEN }}"), 2)
        self.assertEqual(workflow.count("python3 scripts/org_stats.py"), 2)
        self.assertEqual(workflow.count("git add -- README.md assets/generated/violet-void-org-stats.svg assets/generated/violet-void-org-languages.svg"), 2)
        self.assertIn('exit "$org_status"', workflow)
        self.assertLess(workflow.index("python3 scripts/org_stats.py"), workflow.index("python3 scripts/render_readme.py"))

        commit_step = workflow[
            self._find_fragment(workflow, "- name: Commit and push updates") :
        ]
        fail_closed = self._find_fragment(
            commit_step,
            'if (( org_status != 0 )); then\n'
            '          echo "Organization stats failed; refusing to publish partial data" >&2\n'
            '          exit "$org_status"\n'
            '        fi',
        )
        self.assertLess(fail_closed, self._find_fragment(commit_step, "git push origin HEAD:main"))


if __name__ == "__main__":
    unittest.main()
