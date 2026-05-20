# Fonts

This design system **self-hosts** Inter (sans) and JetBrains Mono (mono for code). The `@font-face` declarations live at the top of `colors_and_type.css` and reference the files in this folder.

The source codebase (`niftystrategist-v2`) uses Google Fonts at runtime; this skill ships vendored copies so designs work offline and in sandboxed previewers.

## Files

| File | Family | Style | Weight | Source |
|---|---|---|---|---|
| `inter-variable.woff2` | Inter | normal | 100–900 (variable) | [rsms/inter](https://github.com/rsms/inter) |
| `inter-variable-italic.woff2` | Inter | italic | 100–900 (variable) | [rsms/inter](https://github.com/rsms/inter) |
| `jetbrains-mono-regular.woff2` | JetBrains Mono | normal | 400 | [JetBrains/JetBrainsMono](https://github.com/JetBrains/JetBrainsMono) |
| `jetbrains-mono-medium.woff2` | JetBrains Mono | normal | 500 | [JetBrains/JetBrainsMono](https://github.com/JetBrains/JetBrainsMono) |
| `jetbrains-mono-semibold.woff2` | JetBrains Mono | normal | 600 | [JetBrains/JetBrainsMono](https://github.com/JetBrains/JetBrainsMono) |

Both families are SIL OFL 1.1 licensed — free to redistribute with attribution to the upstream projects.

## Relative-path gotcha

The `src: url('fonts/…')` references in `colors_and_type.css` resolve **relative to the CSS file**, not the HTML that imports it. If you copy `colors_and_type.css` somewhere else, copy this `fonts/` folder next to it or rewrite the URLs.

## Fallback chain

If a woff2 fails to load, the `--font-sans` and `--font-mono` custom properties fall back to system fonts (Inter Variable if installed, then `system-ui`; Monaco / Menlo / Consolas for mono). No design will break — it will just look slightly less consistent.
