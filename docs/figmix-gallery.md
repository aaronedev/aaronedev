# figmix gallery

`bin/figmix-gallery` captures real output from the Bash dotfiles module. It does not reimplement
FIGlet, TOIlet, boxes, filters, defaults, or curated choices. The default source is
`${XDG_CONFIG_HOME:-$HOME/.config}/bash/source/toiletbox_figletbox.sh`; set
`FIGMIX_BASH_SOURCE` to point at a checked-out module for development or testing.

The sourced module remains authoritative for `figmix`, `toiletbox`, `figletbox`, their rendering,
and the `__banner_toilet_fonts`, `__banner_figlet_fonts`, `__banner_boxes`, and
`__banner_toilet_filters` arrays. PNG conversion passes the captured terminal output through
`ansilove`, preserving ANSI emitted by TOIlet filters.

## Prerequisites

- The canonical `toiletbox_figletbox.sh` module and its ordinary local dependencies.
- `ansilove` when generating PNG output.

The generator has no network access and never copies, downloads, or forks the dotfiles functions.
For `--profile` and a single `--capture`, the default output is the repository's
`assets/generated` directory, regardless of the caller's current directory.

## Modes and options

| Mode | What it captures | Output guard |
| --- | --- | --- |
| `--profile` | The fixed profile banner. | Default or explicit output directory. |
| `--capture KIND` | One source-owned `figmix`, `toiletbox`, or `figletbox` invocation. | Name required; default or explicit output directory. |
| `--all` | Existing curated fonts, boxes, filters, engine pairs, and demos. | Explicit `--output-dir`. |
| `--all-layouts` | One real example of each remaining split, box, align, and spacing axis. | Explicit `--output-dir`. |
| `--all-filters` | Filter position examples plus an unfiltered control. | Explicit `--output-dir`. |
| `--all-mixes` | Every ordered curated head/tail font pair across the four engine pairs. | Explicit `--output-dir`. |
| `--all-mixes --combine-layouts` | Every ordered font pair crossed with the finite layout matrix. | Explicit output and `--max-variants N`. |

`--format text`, `--format png`, and `--format both` choose which artifact types are retained;
`both` is the default. Every non-profile invocation writes `figmix-gallery-manifest.md`, which
records the exact command used for each artifact.

`--text TEXT` supplies the normal positional input. `--capture figmix` may omit it when the
forwarded source options provide `--head` or `--tail`. `--output-name NAME` is required for a
single capture. All source-function style arguments belong after `--` and are forwarded unchanged.

Live timer, heading, and alarm options are refused for `--capture`: they produce dynamic output
and cannot truthfully be represented by a stable image.

## Regenerate the profile banner

```bash
FIGMIX_BASH_SOURCE=/home/psy/dotfiles/bash/.config/bash/source/toiletbox_figletbox.sh \
  bin/figmix-gallery \
  --profile \
  --text 'AARON DEV' \
  --output-dir assets/generated \
  --format png
```

`--profile` always uses this fixed source-backed composition and `profile-hero` base name:

```text
figmix --word -H slant -T small 'AARON DEV'
```

GitHub displays the committed `assets/generated/profile-hero.png`; it does not run Bash or
dynamically regenerate profile assets. To change it, intentionally create, inspect, and commit a
replacement at that fixed path.

## Capture any real composition

`--capture` is the complete escape hatch. It forwards real static options untouched, so it covers
independent engines and fonts, separate TOIlet filters, split choices, spacing, alignment, and
boxing. This capture derives its sides from the supplied text:

```bash
FIGMIX_BASH_SOURCE=/home/psy/dotfiles/bash/.config/bash/source/toiletbox_figletbox.sh \
  bin/figmix-gallery \
  --capture figmix \
  --text 'AARON DEV' \
  --output-name derived-mix \
  --output-dir /tmp/figmix-gallery \
  --format png \
  -- --head-engine toilet --tail-engine figlet -H future -T slant \
    --head-filter metal --chars 5 --space 6 --align bottom --box ansi-rounded
```

Use `--head` and `--tail` when the start and end strings themselves should be explicit. This makes
the source's `--word`/`--chars` split selection irrelevant, so choose either explicit sides or a
text-derived split—not both as meaningful presentation controls:

```bash
bin/figmix-gallery \
  --capture figmix \
  --output-name explicit-mix \
  --output-dir /tmp/figmix-gallery \
  --format png \
  -- --head 'AARON' --tail 'DEV' --head-engine toilet --tail-engine toilet \
    -H future -T smblock --head-filter metal --tail-filter rainbow \
    --space 3 --align top --no-box
```

`--capture toiletbox` and `--capture figletbox` forward their static source-owned options in the
same manner: both support fonts and box/no-box presentation; `toiletbox` also supports filters.

## Layout-axis gallery

`--all-layouts` uses one documented stable base mix:

```text
figmix --head-engine toilet --tail-engine figlet -H future -T slant --chars 1 TEXT
```

It captures the control plus each finite axis independently: `--chars 1` through the last boundary
with a non-empty tail, `--word` when the text has multiple words, every source-owned box plus
`--no-box`, `--align top|middle|bottom`, and spacing `0`, `1`, `3` (the source default), and `6`.
This is an axis showcase, deliberately not a large Cartesian product.

```bash
FIGMIX_BASH_SOURCE=/home/psy/dotfiles/bash/.config/bash/source/toiletbox_figletbox.sh \
  bin/figmix-gallery \
  --all-layouts \
  --text 'AARON DEV' \
  --output-dir /tmp/figmix-layouts \
  --format png
```

## Filter-position gallery

`--all-filters` captures one unfiltered TOIlet/TOIlet control, then every source-owned TOIlet
filter in each meaningful `figmix` position: head-only (TOIlet/FIGlet), tail-only (FIGlet/TOIlet),
and shared (TOIlet/TOIlet). The resulting commands use real `--head-filter`, `--tail-filter`, and
`--filter` source options; ANSI is never imitated or synthesized.

```bash
FIGMIX_BASH_SOURCE=/home/psy/dotfiles/bash/.config/bash/source/toiletbox_figletbox.sh \
  bin/figmix-gallery \
  --all-filters \
  --text 'AARON DEV' \
  --output-dir /tmp/figmix-filters \
  --format png
```

## Ordered font matrix

`--all-mixes` creates every ordered head/tail font pair across FIGlet/FIGlet, FIGlet/TOIlet,
TOIlet/FIGlet, and TOIlet/TOIlet. It is intentionally on-demand and must not be committed as a
full gallery.

```bash
FIGMIX_BASH_SOURCE=/home/psy/dotfiles/bash/.config/bash/source/toiletbox_figletbox.sh \
  bin/figmix-gallery \
  --all-mixes \
  --text 'AARON DEV' \
  --output-dir /tmp/figmix-font-matrix \
  --format png
```

## Controlled multi-axis combinations

The number of possible static combinations is not bounded in general: spacing accepts arbitrary
non-negative integers, and fonts, filters, split choices, engines, boxes, and layout axes multiply.
There is intentionally no unsafe “everything” mode.

For a finite real cross-product, `--combine-layouts` adds every valid character split and optional
word split, every source box plus no-box, all three alignments, and the four documented spacing
values to each ordered font mix. It requires `--max-variants N`. Before the module is sourced or an
artifact is rendered, the generator reads the static curated array declarations, calculates the
exact planned count, and refuses a request above that cap. Every generated invocation appears in the
manifest.

```bash
FIGMIX_BASH_SOURCE=/home/psy/dotfiles/bash/.config/bash/source/toiletbox_figletbox.sh \
  bin/figmix-gallery \
  --all-mixes \
  --combine-layouts \
  --max-variants 100000 \
  --text 'AB' \
  --output-dir /tmp/figmix-combinations \
  --format png
```

With the current source arrays, even the short `AB` example is broad: its cap is deliberately high
enough to permit the real matrix. First run with a knowingly low cap to read the exact refused count,
then choose a justified cap and explicit temporary directory. Keep broad galleries out of Git;
select a banner afterward and commit only the intended profile PNG.
