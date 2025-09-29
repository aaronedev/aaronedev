[![Header: aaronedev](./assets/aaronedev.png "Header image for aaronedev")](https://github.com/aaronedev)

# Oi, World! I'm Aaron

<!-- badges -->
![Profile views](https://komarev.com/ghpvc/?username=ahrwn&label=Profile%20views&color=7745bf&)
<a href="https://wakatime.com/@018cc02c-e893-42e6-b1c7-48cb3ef3ccfe">
  <img
    src="https://wakatime.com/badge/user/018cc02c-e893-42e6-b1c7-48cb3ef3ccfe.svg?style=flat"
    alt="Total time coded since Dec 31 2023"
    style="filter: hue-rotate(90deg);" />
</a>
[![Waka Readme](https://github.com/aaronedev/aaronedev/actions/workflows/readme.yaml/badge.svg)](https://github.com/aaronedev/aaronedev/actions/workflows/readme.yaml)

> Linux desktop engineering • rootless containers • Hyprland workflows •
> Neovim configs & Themes

## 🔧 What I do now
- Build secure, rootless **Podman** dev setups
- Engineer **Hyprland** desktop workflows and theming
- Ship **python-utility** apps: offline TTS tools powered by **Piper**
  - Example: clipboard-reader aka [read-that](https://github.com/aaronedev/read-that) 📢
 that auto-detects **EN/DE**, switches voices, and takes flags for speed, pitch, and voice
- Bash scripting: small, composable CLI tools
- Linux and network fundamentals for real deployments

<!-- shields -->
![Arch Linux](https://img.shields.io/badge/Arch_Linux-29adff?style=flat&logo=arch-linux&logoColor=ffffff)
![Hyprland](https://img.shields.io/badge/Hyprland-fd0098?style=flat&logo=hyprland&logoColor=ffffff)
![Neovim](https://img.shields.io/badge/Neovim-42ff97?style=flat&logo=neovim&logoColor=0b0b0b)
![Podman](https://img.shields.io/badge/Podman-7c60d1?style=flat&logo=podman&logoColor=ffffff)
![Linux](https://img.shields.io/badge/Linux-00fff9?style=flat&logo=linux&logoColor=0b0b0b)

## ⚡ I can help with
- Bash Scripting and automation
- Hardening dev containers and CI without Docker
- Modular **Hyprland** configs, rules, and automation
- **Neovim** UX: colors, LSP, performance
- Offline TTS pipelines with **Piper** and clean CLI ergonomics

---

## 🌟 Featured projects
- 🎨 **Violet Void Theme** — core color system powering matching themes across apps (ArchWiki, CopyQ, more)\
  [`aaronedev/violet-void-theme`](https://github.com/aaronedev/violet-void-theme)
  - ArchWiki: restyles the ArchWiki with a violet void palette\
    [`aaronedev/violet-void-theme_archwiki`](https://github.com/aaronedev/violet-void-theme_archwiki)
  - CopyQ: matching CopyQ theme for a cohesive desktop\
    [`aaronedev/violet-void-theme_copyq`](https://github.com/aaronedev/violet-void-theme_copyq)
- 🧩 **zen-mods** — modular ergonomics toolkit for Hyprland workspaces\
  [`aaronedev/zen-mods`](https://github.com/aaronedev/zen-mods)
  - zen-floating-bookmarks: lightweight floating bookmark UX\
    [`aaronedev/zen-floating-bookmarks`](https://github.com/aaronedev/zen-floating-bookmarks)
  - zen-spotlight *(in progress)* — rapid launcher overlays for Hyprland

---

## 📝 Docs workflow
All notes in Neovim via [obsidian.nvim](https://github.com/obsidian-nvim/obsidian.nvim) on plain Markdown.

---

## 📬 Contact
Matrix: <a href="https://matrix.to/#/@aaronedev:matrix.org" target="_blank">@aaronedev:matrix.org</a>

---

## ⭐ Recent activity

{{ $prs := recentPullRequests 5 }}
{{ if $prs }}
### 🔁 Fresh Pull Requests
{{ range $prs -}}
- {{- if eq .State "OPEN" -}}🟣{{- else if eq .State "MERGED" -}}🟢{{- else -}}⚫{{- end -}} [{{ .Title }}]({{ .URL }}) in [`{{ .Repo.Name }}`]({{ .Repo.URL }}) • {{ humanize .CreatedAt }}
  {{- if .Repo.Description }}\
  <sub>{{ .Repo.Description }}</sub>
  {{- end }}
{{ end }}
{{ else }}
_No pull request activity just yet — busy crafting something new._
{{ end }}

{{ $contribs := recentContributions 5 }}
{{ if $contribs }}
### 🛠️ Latest Contributions
{{ range $contribs -}}
- 🔗 [`{{ .Repo.Name }}`]({{ .Repo.URL }}) • {{ humanize .OccurredAt }}
  {{- if .Repo.Description }}\
  <sub>{{ .Repo.Description }}</sub>
  {{- end }}
{{ end }}
{{ else }}
_No public commits in the last few days — check back soon._
{{ end }}

### ✨ WakaTime stats ✨
<details>
  <summary>Click to expand the latest metrics</summary>

<!--START_SECTION:waka-->
<!--END_SECTION:waka-->

</details>

---
