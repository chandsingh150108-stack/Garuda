/** Light/dark theme plumbing (D16.5). No dependencies: the choice lives
 * on <html data-theme> so pure-CSS variables do the work, persisted in
 * localStorage, announced via a window event for Monaco/Mermaid refresh. */

export type Theme = "light" | "dark";

const KEY = "cm-theme";
export const THEME_EVENT = "cm:theme";

export function getTheme(): Theme {
  try {
    const saved = window.localStorage.getItem(KEY);
    if (saved === "light" || saved === "dark") return saved;
  } catch {
    /* storage unavailable: fall through to OS preference */
  }
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

export function applyTheme(t: Theme): void {
  document.documentElement.dataset.theme = t;
  try {
    window.localStorage.setItem(KEY, t);
  } catch {
    /* ignore */
  }
  window.dispatchEvent(new CustomEvent<Theme>(THEME_EVENT, { detail: t }));
}

/** Least-opinionated mermaid preset + explicit variables. Two channels carry
 * theming, and BOTH are set deliberately:
 * 1. These variables: mermaid bakes them into attributes/inline styles at
 *    render time (attributes survive CSP; this is how fonts, actor boxes,
 *    and note colors actually take effect).
 * 2. Our own CSS (styles.css): backstop for everything mermaid only emits
 *    via its injected stylesheet (CSP-blocked here), e.g. flowchart edge
 *    strokes. CSS `!important` always beats the attributes from (1).
 */
export function mermaidBaseConfig(t: Theme): Record<string, unknown> {
  const dark = t === "dark";
  const ink = dark ? "#f0f3fa" : "#1c2333";
  const soft = dark ? "#c2c9dd" : "#5d6579";
  const card = dark ? "#161d33" : "#ffffff";
  const line = dark ? "#2a3452" : "#e3e7f2";
  const brand = dark ? "#22d3ee" : "#7c3aed";
  return {
    theme: "base",
    fontFamily: "'Segoe UI', system-ui, sans-serif",
    themeVariables: {
      darkMode: dark,
      background: "transparent",
      primaryTextColor: ink,
      lineColor: brand,
      secondaryColor: dark ? "#1c2547" : "#e9efff",
      tertiaryColor: "transparent",
      edgeLabelBackground: card,
      // Sequence actors: dark card + bright text in dark mode (the exact
      // white-on-grey failure was actorTextColor following page ink while
      // actorBkg stayed hardcoded light).
      actorBkg: card,
      actorBorder: dark ? "#a78bfa" : "#7c3aed",
      actorTextColor: ink,
      actorLineColor: soft,
      // Messages and lifelines.
      signalColor: soft,
      signalTextColor: ink,
      // Activation boxes, notes, loop labels.
      activationBkgColor: dark ? "#1c2547" : "#e9efff",
      activationBorderColor: dark ? "#a78bfa" : "#7c3aed",
      noteBkgColor: "#fdf3d7",
      noteBorderColor: "#b45309",
      noteTextColor: "#3a2c10",
      labelBoxBkgColor: dark ? "#3a2c10" : "#fdf0dc",
      labelBoxBorderColor: "#f59e0b",
      labelTextColor: dark ? "#fbbf24" : "#b45309",
      sequenceNumberColor: "#ffffff",
    },
  };
}
