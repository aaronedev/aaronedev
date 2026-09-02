from __future__ import annotations

import argparse
import html
import json
import os
import re
import stat
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts.readme_config import (
    ACTIVITY_END,
    ACTIVITY_START,
    PROFILE_END,
    PROFILE_START,
    WAKA_END,
    WAKA_START,
)

_GITHUB_LOGIN = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?$")
_RUNS_ON = re.compile(r"^([ \t]*)runs-on:[^\n]*$", re.MULTILINE)
_MARKER_TOKENS = ("<!--START_SECTION:", "<!--END_SECTION:", "PROFILE_START", "PROFILE_END")
_NEUTRAL_ACTIVITY = "\n_Activity will appear after you run the README workflow._\n"
_NEUTRAL_WAKA = "\n_WakaTime stats will appear after you run the README workflow._\n"


class ProfileSetupError(ValueError):
    """Raised when a profile setup request is unsafe or cannot be bounded."""


@dataclass(frozen=True)
class ProfilePaths:
    config: Path
    template: Path
    readme: Path
    workflow: Path | None = None


@dataclass(frozen=True)
class ProfileAnswers:
    display_name: str
    github_login: str
    what_i_build: str
    intro: str
    focus_items: tuple[str, ...]
    help_items: tuple[str, ...]
    timezone: str
    project_owners: tuple[str, ...]
    use_ubuntu_runner: bool = False


def validate_github_login(value: str) -> str:
    if (
        not isinstance(value, str)
        or not _GITHUB_LOGIN.fullmatch(value)
        or "--" in value
    ):
        raise ProfileSetupError("GitHub login must be 1-39 letters, digits, or hyphens")
    return value


def validate_one_line(value: str, field: str, *, required: bool = True) -> str:
    if not isinstance(value, str):
        raise ProfileSetupError(f"{field} must be text")
    cleaned = value.strip()
    if required and not cleaned:
        raise ProfileSetupError(f"{field} is required")
    if "\n" in value or "\r" in value:
        raise ProfileSetupError(f"{field} must be one line")
    if any(token in value for token in _MARKER_TOKENS):
        raise ProfileSetupError(f"{field} cannot contain profile marker tokens")
    return cleaned


def validate_timezone(value: str) -> str:
    timezone = validate_one_line(value, "timezone")
    try:
        ZoneInfo(timezone)
    except ZoneInfoNotFoundError as exc:
        raise ProfileSetupError(f"timezone must be a valid IANA timezone: {timezone}") from exc
    return timezone


def parse_semicolon_items(value: str, field: str) -> tuple[str, ...]:
    if not value.strip():
        return ()
    return tuple(
        validate_one_line(item, field)
        for item in value.split(";")
        if item.strip()
    )


def _three_items(items: Iterable[str], defaults: tuple[str, str, str]) -> tuple[str, str, str]:
    values = [validate_one_line(item, "list item") for item in items][:3]
    for default in defaults:
        if len(values) == 3:
            break
        values.append(default)
    return tuple(values)  # type: ignore[return-value]


def validate_answers(answers: ProfileAnswers) -> ProfileAnswers:
    display_name = validate_one_line(answers.display_name, "display name")
    github_login = validate_github_login(answers.github_login)
    what_i_build = validate_one_line(answers.what_i_build, "what you build")
    intro = validate_one_line(answers.intro, "intro", required=False)
    timezone = validate_timezone(answers.timezone)
    owners = answers.project_owners or (github_login,)
    validated_owners = tuple(validate_github_login(owner) for owner in owners)
    if github_login not in validated_owners:
        validated_owners = (github_login, *validated_owners)
    return ProfileAnswers(
        display_name=display_name,
        github_login=github_login,
        what_i_build=what_i_build,
        intro=intro,
        focus_items=_three_items(
            answers.focus_items,
            ("Build a small public project", "Write useful documentation", "Learn from feedback"),
        ),
        help_items=_three_items(
            answers.help_items,
            ("Software design", "Documentation", "Developer tooling"),
        ),
        timezone=timezone,
        project_owners=validated_owners,
        use_ubuntu_runner=answers.use_ubuntu_runner,
    )


def render_profile(answers: ProfileAnswers) -> str:
    safe = lambda value: html.escape(value, quote=True)
    intro = answers.intro or f"I build {answers.what_i_build}."
    focus = "\n".join(f"- {safe(item)}" for item in answers.focus_items)
    help_areas = "\n".join(f"- {safe(item)}" for item in answers.help_items)
    return "\n".join(
        (
            PROFILE_START,
            f'<h1 align="center">{safe(answers.display_name)} / {safe(answers.github_login)}</h1>',
            "",
            '<p align="center">',
            f"  {safe(intro)}",
            "</p>",
            "",
            "## What I build",
            "",
            safe(answers.what_i_build),
            "",
            "## Current focus",
            focus,
            "",
            "## I can help with",
            help_areas,
            "",
            "## Featured projects",
            "",
            "- Add projects you are proud to share here.",
            "",
            "> [!TIP]",
            "> Personalise this starter profile, then let the README workflow update activity sections.",
            "",
            PROFILE_END,
        )
    )


def _read_regular_file(path: Path) -> str:
    if not path.is_file() or path.is_symlink():
        raise ProfileSetupError(f"expected a regular file: {path}")
    return path.read_text(encoding="utf-8")


def _replace_assignment(text: str, name: str, value: str) -> str:
    pattern = re.compile(rf"^{re.escape(name)}[ \t]*=[^\n]*$", re.MULTILINE)
    matches = list(pattern.finditer(text))
    if len(matches) != 1:
        raise ProfileSetupError(f"expected exactly one {name} assignment")
    replacement = f"{name} = {value}"
    match = matches[0]
    return text[: match.start()] + replacement + text[match.end() :]


def _validate_config_boundaries(text: str) -> None:
    for name in ("AUTHOR_LOGIN", "PROFILE_REPO", "ALLOWED_OWNERS", "PROFILE_TIMEZONE"):
        pattern = re.compile(rf"^{re.escape(name)}[ \t]*=[^\n]*$", re.MULTILINE)
        matches = list(pattern.finditer(text))
        if len(matches) != 1:
            raise ProfileSetupError(f"expected exactly one {name} assignment")
        value = matches[0].group().split("=", 1)[1].strip()
        if name == "ALLOWED_OWNERS":
            if not (value.startswith("(") and value.endswith(")")):
                raise ProfileSetupError("ALLOWED_OWNERS must be a single-line tuple")
        elif not (value.startswith('"') and value.endswith('"')):
            raise ProfileSetupError(f"{name} must be a single-line string assignment")


def _replace_profile_section(text: str, profile: str) -> str:
    start_count = text.count(PROFILE_START)
    end_count = text.count(PROFILE_END)
    if start_count != 1 or end_count != 1:
        raise ProfileSetupError("expected exactly one bounded profile marker pair")
    start_at = text.find(PROFILE_START)
    end_at = text.find(PROFILE_END)
    if end_at < start_at:
        raise ProfileSetupError("profile markers are inverted")
    return text[:start_at] + profile + text[end_at + len(PROFILE_END) :]


def _replace_bounded_section(text: str, start: str, end: str, inner: str) -> str:
    if text.count(start) != 1 or text.count(end) != 1:
        raise ProfileSetupError(f"expected exactly one bounded section: {start} / {end}")
    start_at = text.find(start)
    end_at = text.find(end)
    if end_at < start_at:
        raise ProfileSetupError(f"section markers are inverted: {start} / {end}")
    return text[: start_at + len(start)] + inner + text[end_at:]


def _neutralize_dynamic_sections(text: str) -> str:
    text = _replace_bounded_section(text, ACTIVITY_START, ACTIVITY_END, _NEUTRAL_ACTIVITY)
    return _replace_bounded_section(text, WAKA_START, WAKA_END, _NEUTRAL_WAKA)


def _replace_runner(text: str) -> str:
    matches = list(_RUNS_ON.finditer(text))
    if len(matches) != 1:
        raise ProfileSetupError("expected exactly one workflow runs-on assignment")
    match = matches[0]
    return text[: match.start()] + f"{match.group(1)}runs-on: ubuntu-latest" + text[match.end() :]


def _atomic_write(path: Path, text: str) -> None:
    mode = stat.S_IMODE(path.stat().st_mode)
    descriptor, temporary = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    try:
        os.fchmod(descriptor, mode)
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
        os.replace(temporary, path)
    except Exception:
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise


def _restore_file(path: Path, contents: bytes, mode: int) -> None:
    descriptor, temporary = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".restore", dir=path.parent
    )
    try:
        os.fchmod(descriptor, mode)
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(contents)
        os.replace(temporary, path)
    except Exception:
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise


def build_updates(paths: ProfilePaths, answers: ProfileAnswers) -> dict[Path, str]:
    answers = validate_answers(answers)
    config = _read_regular_file(paths.config)
    _validate_config_boundaries(config)
    template = _read_regular_file(paths.template)
    readme = _read_regular_file(paths.readme)
    profile = render_profile(answers)
    owner_values = ", ".join(json.dumps(owner) for owner in answers.project_owners)
    owners = f"({owner_values}{',' if len(answers.project_owners) == 1 else ''})"
    template = _neutralize_dynamic_sections(_replace_profile_section(template, profile))
    readme = _neutralize_dynamic_sections(_replace_profile_section(readme, profile))
    updates = {
        paths.config: _replace_assignment(
            _replace_assignment(
                _replace_assignment(
                    _replace_assignment(config, "AUTHOR_LOGIN", json.dumps(answers.github_login)),
                    "PROFILE_REPO",
                    json.dumps(f"{answers.github_login}/{answers.github_login}"),
                ),
                "ALLOWED_OWNERS",
                owners,
            ),
            "PROFILE_TIMEZONE",
            json.dumps(answers.timezone),
        ),
        paths.template: template,
        paths.readme: readme,
    }
    if answers.use_ubuntu_runner:
        if paths.workflow is None:
            raise ProfileSetupError("workflow path is required for the ubuntu runner option")
        updates[paths.workflow] = _replace_runner(_read_regular_file(paths.workflow))
    return updates


def apply_profile_setup(paths: ProfilePaths, answers: ProfileAnswers) -> dict[Path, str]:
    updates = build_updates(paths, answers)
    originals = {
        path: (path.read_bytes(), stat.S_IMODE(path.stat().st_mode)) for path in updates
    }
    try:
        for path, text in updates.items():
            _atomic_write(path, text)
    except Exception:
        for path, (contents, mode) in originals.items():
            try:
                _restore_file(path, contents, mode)
            except OSError:
                pass
        raise
    return updates


def _paths_for_root(root: Path) -> ProfilePaths:
    return ProfilePaths(
        config=root / "scripts" / "readme_config.py",
        template=root / "templates" / "README.md.tpl",
        readme=root / "README.md",
        workflow=root / ".github" / "workflows" / "readme.yaml",
    )


def _answers_from_args(args: argparse.Namespace) -> ProfileAnswers:
    required = ("display_name", "github_login", "what_i_build", "timezone")
    missing = [name.replace("_", "-") for name in required if not getattr(args, name)]
    if missing:
        raise ProfileSetupError(f"--apply requires: {', '.join(missing)}")
    return ProfileAnswers(
        display_name=args.display_name,
        github_login=args.github_login,
        what_i_build=args.what_i_build,
        intro=args.intro or "",
        focus_items=parse_semicolon_items(args.focus or "", "focus item"),
        help_items=parse_semicolon_items(args.help or "", "help item"),
        timezone=args.timezone,
        project_owners=tuple(
            validate_github_login(owner)
            for owner in parse_semicolon_items(args.owners or "", "project owner")
        ),
        use_ubuntu_runner=args.ubuntu_runner,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Safely prepare a fork profile starter.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true", help="validate boundaries without writing")
    mode.add_argument("--apply", action="store_true", help="write the validated starter profile")
    parser.add_argument("--repo-root", type=Path, default=_ROOT)
    parser.add_argument("--display-name")
    parser.add_argument("--github-login")
    parser.add_argument("--what-i-build")
    parser.add_argument("--intro")
    parser.add_argument("--focus", help="semicolon-separated current-focus items")
    parser.add_argument("--help-areas", dest="help", help="semicolon-separated help areas")
    parser.add_argument("--timezone")
    parser.add_argument("--owners", help="semicolon-separated project owners")
    parser.add_argument("--ubuntu-runner", action="store_true")
    args = parser.parse_args(argv)
    paths = _paths_for_root(args.repo_root)
    try:
        if args.apply:
            apply_profile_setup(paths, _answers_from_args(args))
        else:
            config = _read_regular_file(paths.config)
            _validate_config_boundaries(config)
            _replace_profile_section(_read_regular_file(paths.template), "")
            _replace_profile_section(_read_regular_file(paths.readme), "")
            if args.ubuntu_runner:
                _replace_runner(_read_regular_file(paths.workflow))
            if any(
                getattr(args, name) is not None
                for name in ("display_name", "github_login", "what_i_build", "timezone")
            ):
                validate_answers(_answers_from_args(args))
    except ProfileSetupError as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    sys.exit(main())
