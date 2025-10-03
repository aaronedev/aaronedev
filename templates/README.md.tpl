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

## 📬 About me -- Contact
- Matrix: <a href="https://matrix.to/#/@aaronedev:matrix.org" target="_blank">@aaronedev:matrix.org</a>
- Brieftaube: <a href="https://de.wikipedia.org/wiki/Brieftaube" target="_blank">Homing Pigeon</a> send it to cologne 50.951811223028265, 6.986298711065432

> [!IMPORTANT]
> Don't take urself too seriously, we're all pretty dumbs here.

<div class="badges-githubstats">
  <img src="https://github-readme-stats.vercel.app/api?username=aaronedev&show_icons=true&hide_border=true&count_private=true&bg_color=111%2C082421%2C0D1117&title_color=7c60d1&text_color=f0f0f5&icon_color=319e8d&border_color=131313&border_radius=10" alt="aaronedev's github statistics" height="140" />
  <img src="https://github-readme-streak-stats.herokuapp.com/?user=aaronedev&hide_border=true&background=9%2C08242130%2C0D1117&border=131313&stroke=c7b8ff&ring=fd7cff&fire=fd0098&currStreakNum=c7b8ff&currStreakLabel=7c60d1&sideNums=c7b8ff&sideLabels=7c60d1&dates=f0f0f5&border_radius=10" alt="aaronedev's github commit streak" height="140" />
</div>

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

## ✨ I can help with
- Bash Scripting and automation
- Hardening dev containers and CI without Docker
- Modular **Hyprland** configs, rules, and automation
- **Neovim** UX: colors, LSP, performance
- Offline TTS pipelines with **Piper** and clean CLI ergonomics

## 🌟 Featured projects
- 🎨 **Violet Void Theme** — core color system powering matching themes across apps (ArchWiki, CopyQ, more)\
  [`aaronedev/violet-void-theme`](https://github.com/aaronedev/violet-void-theme)
  - ArchWiki: restyles the ArchWiki with a violet void palette\
    [`aaronedev/violet-void-theme_archwiki`](https://github.com/aaronedev/violet-void-theme_archwiki)
  - CopyQ: matching CopyQ theme for a cohesive desktop\
    [`aaronedev/violet-void-theme_copyq`](https://github.com/aaronedev/violet-void-theme_copyq)
  - Sublime tmTheme Syntax mappings which can be used for [Bat](https://github.com/sharkdp/bat) and such\
    [`aaronedev/violet-void-theme_subl`](https://github.com/aaronedev/violet-void-theme_subl)
- 🧩 **zen-mods** — modular ergonomics toolkit for Hyprland workspaces\
  [`aaronedev/zen-mods`](https://github.com/aaronedev/zen-mods)
  - zen-floating-bookmarks: lightweight floating bookmark UX\
    [`aaronedev/zen-floating-bookmarks`](https://github.com/aaronedev/zen-floating-bookmarks)
  - zen-spotlight *(in progress)* — rapid launcher overlays for Hyprland

## 📝 Docs workflow
All notes in Neovim via [obsidian.nvim](https://github.com/obsidian-nvim/obsidian.nvim) on plain Markdown.

---

## ⭐ Recent activity

{{ $prs := recentPullRequests 5 }}
{{ if $prs }}
### 🔁 Fresh Pull Requests
{{ range $prs }}
- {{ if eq .State "OPEN" }}🟣{{ else if eq .State "MERGED" }}🟢{{ else }}⚫{{ end }} [{{ .Title }}]({{ .URL }}) in [`{{ .Repo.Name }}`]({{ .Repo.URL }}) • {{ humanize .CreatedAt }}
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
{{ range $contribs }}
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
