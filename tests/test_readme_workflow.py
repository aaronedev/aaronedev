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
        self.assertIn("git add README.md", commit_step)
        self.assertIn('exit "$rerender_status"', commit_step)


if __name__ == "__main__":
    unittest.main()
