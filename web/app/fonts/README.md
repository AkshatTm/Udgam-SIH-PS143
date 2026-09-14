# Fonts

`InterVariable.woff2` and `GeistMonoVF.woff` are committed and self-hosted — the app always has
a working face with no network.

The interface stack in `globals.css` (`--font-ui`) asks for **SF Pro Display / SF Pro Text
first**, so on any machine that has SF Pro installed (every Mac; a Windows box where you have
installed it) the app renders in SF Pro and falls back to Inter everywhere else. Nothing to
configure — install the font and it is used.

To self-host SF Pro instead (so it renders identically on a machine that does not have it
installed), drop the woff2 files into `web/public/fonts/` and paste this into `globals.css`
above the `:root` block:

```css
@font-face {
  font-family: "SF Pro Display";
  src: local("SF Pro Display"), url("/fonts/SFProDisplay-Variable.woff2") format("woff2");
  font-weight: 100 900;
  font-display: swap;
}
@font-face {
  font-family: "SF Pro Text";
  src: local("SF Pro Text"), url("/fonts/SFProText-Variable.woff2") format("woff2");
  font-weight: 100 900;
  font-display: swap;
}
```

Apple's licence covers SF Pro for use on Apple platforms — check it before shipping the binaries
in a public repo. The stack above is why the app does not depend on that decision.
