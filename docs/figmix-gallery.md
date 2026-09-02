# figmix gallery

`bin/figmix-gallery` is the profile-owned composition layer for locally installed FIGlet,
TOIlet, and ImageMagick. It renders one selected variant by default and can produce an
on-demand gallery across the installed fonts for either engine.

## Prerequisites

- `figlet`
- `toilet`
- ImageMagick 7 (`magick`)
- FIGlet and TOIlet fonts in `/usr/share/figlet`, or in `FIGMIX_FONT_DIR`

The generator does not download tools, fonts, or assets. It only uses local binaries and font
files.

## Generate a profile asset

```bash
bin/figmix-gallery \
  --text AARON \
  --output-dir assets/generated \
  --output-name profile-hero \
  --engine figlet \
  --font slant \
  --layout normal \
  --format png
```

The profile README embeds `assets/generated/profile-hero.png` at a fixed repository path.
GitHub profile READMEs render committed images; they do not run FIGlet, TOIlet, JavaScript, or
dynamic HTML. Choose a variant, rerun the command, commit the replacement PNG, and GitHub will
render the new static image.

## Explore installed fonts

```bash
FIGMIX_FONT_DIR=/usr/share/figlet bin/figmix-gallery \
  --text AARON \
  --output-dir /tmp/figmix-gallery \
  --output-name aaron \
  --engine figlet \
  --layout smushing \
  --format both \
  --all-fonts
```

`--all-fonts` selects `.flf` files for FIGlet or `.tlf` files for TOIlet. It writes one variant
per compatible font plus `<output-name>-manifest.md`, which links every generated plaintext and
PNG file. Keep broad galleries out of Git; only commit the selected profile asset.

## Layouts

`normal`, `kerning`, `full-width`, and `smushing` map to the engines' native layout flags.
`boxed` is TOIlet-only and uses its `border` filter. Run `bin/figmix-gallery --help` for the
complete CLI contract.
