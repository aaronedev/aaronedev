from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "readme.yaml"


class ReadmeWorkflowContractTest(unittest.TestCase):
    def test_post_sync_rerender_has_renderer_credentials_and_precedes_push(self) -> None:
        workflow = WORKFLOW.read_text(encoding="utf-8")
        commit_step = workflow.split("    - name: Commit and push updates", 1)[1]

        self.assertIn("README_ACTIVITY_GITHUB_PAT: ${{ secrets.GH_TOKEN }}", commit_step)
        self.assertIn(
            "README_WAKATIME_API_KEY: ${{ secrets.WAKATIME_API_KEY }}", commit_step
        )
        self.assertNotIn('cp README.md "$rendered_readme"', commit_step)
        sync = commit_step.index("git pull --rebase --autostash --strategy-option=theirs origin main")
        recovery_reset = commit_step.index("git reset --hard origin/main")
        rerender = commit_step.index("python3 scripts/render_readme.py", sync)
        push = commit_step.index("git push origin HEAD:main")
        self.assertLess(sync, rerender)
        self.assertLess(recovery_reset, rerender)
        self.assertLess(rerender, push)
        self.assertIn("git add README.md", commit_step)
        self.assertIn('exit "$rerender_status"', commit_step)


if __name__ == "__main__":
    unittest.main()
