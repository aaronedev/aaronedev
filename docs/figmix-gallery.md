# figmix gallery

`bin/figmix-gallery` captures the real banner functions from the Bash dotfiles module; it does
not reimplement FIGlet, TOIlet, boxes, or their curated choices. The default source is
`${XDG_CONFIG_HOME:-$HOME/.config}/bash/source/toiletbox_figletbox.sh`. Set
`FIGMIX_BASH_SOURCE` to point at another checked-out copy for development or testing.

The sourced module owns the `figmix`, `toiletbox`, and `figletbox` functions and the curated
`__banner_toilet_fonts`, `__banner_figlet_fonts`, and `__banner_boxes` arrays. PNG conversion uses
`ansilove` on the captured terminal output, retaining the terminal artifact and TOIlet ANSI
filters exactly as emitted.

## Prerequisites

- The canonical `toiletbox_figletbox.sh` module and its normal local dependencies.
- `ansilove` when generating PNG output.

The generator has no network access and does not copy, download, or fork the dotfiles functions.

## Regenerate the profile banner

```bash
FIGMIX_BASH_SOURCE=/home/psy/dotfiles/bash/.config/bash/source/toiletbox_figletbox.sh \
  bin/figmix-gallery \
  --profile \
  --text 'AARON DEV' \
  --output-dir assets/generated \
  --format png
```

`--profile` always captures this exact composition and writes the fixed `profile-hero` base name:

```bash
figmix --word -H slant -T small 'AARON DEV'
```

The GitHub profile README displays the committed `assets/generated/profile-hero.png` at a fixed
path. GitHub does not execute shell functions or dynamic HTML in a profile README: choose a real
banner, regenerate the PNG, commit it, and GitHub will render the new static asset.

## Browse the curated collections

```bash
FIGMIX_BASH_SOURCE=/home/psy/dotfiles/bash/.config/bash/source/toiletbox_figletbox.sh \
  bin/figmix-gallery \
  --all \
  --text 'AARON DEV' \
  --output-dir /tmp/figmix-gallery \
  --format both
```

`--all` captures the three real `figmix` demos (auto, word-split `slant` + `small`, and TOIlet
`bigmono12` + `smblock`), every curated `toiletbox` font and box, and every curated `figletbox`
font. It also writes `figmix-gallery-manifest.md` with each exact command and its artifacts.

Keep broad galleries out of Git. Regenerate on demand, select the banner you want, then update the
single committed profile PNG.
