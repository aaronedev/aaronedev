# figmix gallery

`bin/figmix-gallery` captures the real banner functions from the Bash dotfiles module. It does
not reimplement FIGlet, TOIlet, boxes, filters, defaults, or curated choices. The default source is
`${XDG_CONFIG_HOME:-$HOME/.config}/bash/source/toiletbox_figletbox.sh`. Set
`FIGMIX_BASH_SOURCE` to use another checked-out copy for development or testing.

The sourced module remains the authority for `figmix`, `toiletbox`, `figletbox`, their rendering,
and the `__banner_toilet_fonts`, `__banner_figlet_fonts`, `__banner_boxes`, and
`__banner_toilet_filters` arrays. PNG conversion uses `ansilove` on captured terminal output, so
TOIlet ANSI filters are preserved as emitted.

## Prerequisites

- The canonical `toiletbox_figletbox.sh` module and its normal local dependencies.
- `ansilove` when generating PNG output.

The generator has no network access and never copies, downloads, or forks the dotfiles functions.
For `--profile` and a single `--capture`, the default output resolves to the repository's
`assets/generated` directory, regardless of the caller's current directory.

## Regenerate the profile banner

```bash
FIGMIX_BASH_SOURCE=/home/psy/dotfiles/bash/.config/bash/source/toiletbox_figletbox.sh \
  bin/figmix-gallery \
  --profile \
  --text 'AARON DEV' \
  --output-dir assets/generated \
  --format png
```

`--profile` always uses this exact source-backed composition and fixed `profile-hero` base name:

```bash
figmix --word -H slant -T small 'AARON DEV'
```

The GitHub profile README displays the committed `assets/generated/profile-hero.png` at a fixed
path. GitHub neither runs the Bash functions nor dynamically regenerates assets. A PNG is a static
capture of one terminal render: changing the profile means deliberately generating, reviewing, and
committing a replacement image. Live timer output is intentionally refused because it cannot become
a stable static asset.

## Capture any real style combination

Use `--capture`, name the artifact, and put the actual source-function arguments after `--`. They
are forwarded unchanged. `--text` becomes the positional text only when `figmix` does not use an
explicit `--head` or `--tail`; that lets the source function own either its split logic or explicit
two-sided content.

```bash
FIGMIX_BASH_SOURCE=/home/psy/dotfiles/bash/.config/bash/source/toiletbox_figletbox.sh \
  bin/figmix-gallery \
  --capture figmix \
  --text 'AARON DEV' \
  --output-name mixed-proof \
  --output-dir /tmp/figmix-gallery \
  --format png \
  -- --head-engine toilet --tail-engine figlet -H future -T slant \
    --head-filter metal --word --space 5 --align bottom --box ansi-rounded
```

For an explicit split, omit `--text`:

```bash
bin/figmix-gallery --capture figmix --output-name explicit --format png \
  -- --head 'AARON' --tail 'DEV' --head-engine figlet --tail-engine toilet \
    -H slant -T smblock --tail-filter rainbow --box ansi-heavy
```

`--capture toiletbox` and `--capture figletbox` forward their source-owned static options the same
way: font and box choices for both, plus TOIlet filters for `toiletbox`. Timer-related arguments
(`--timer`, headings, and alarms) are rejected rather than creating a misleading incomplete frame.

## Browse curated static axes

```bash
FIGMIX_BASH_SOURCE=/home/psy/dotfiles/bash/.config/bash/source/toiletbox_figletbox.sh \
  bin/figmix-gallery \
  --all \
  --text 'AARON DEV' \
  --output-dir /tmp/figmix-gallery \
  --format both
```

`--all` captures the three real figmix demos; every curated `toiletbox` font, box, and filter;
every curated `figletbox` font and box; and the four canonical figmix engine pairings:
figlet/figlet, figlet/toilet, toilet/figlet, and toilet/toilet. It writes
`figmix-gallery-manifest.md`, recording the exact command for every artifact.

`--all` requires `--output-dir` explicitly. This prevents a broad gallery from landing beside the
current shell directory when the command is run from a subdirectory.

## Exhaustive ordered font mixes

```bash
FIGMIX_BASH_SOURCE=/home/psy/dotfiles/bash/.config/bash/source/toiletbox_figletbox.sh \
  bin/figmix-gallery \
  --all-mixes \
  --text 'AARON DEV' \
  --output-dir /tmp/figmix-mixes \
  --format png
```

`--all-mixes` reads the source arrays at runtime and generates every ordered head/tail pair across
all four engine combinations. Each capture is a real `figmix --head-engine ... --tail-engine ...
-H ... -T ... --word` invocation. The output count grows roughly with the square of the curated
font count, so it is intentionally on-demand and must not be committed as a full gallery. Like
`--all`, it requires an explicit `--output-dir` before the source module is even loaded.

Keep broad galleries out of Git. Generate on demand, select the banner you want, then update only
the single committed profile PNG.
