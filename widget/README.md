# Widget (Lit + Vite library bundle)

The embeddable visitor-facing widget: a Lit + Shadow-DOM custom element, built as
a Vite library bundle and served from a CDN. It holds only the public widget key,
streams answers via fetch-based streaming with a Bearer header (not native
EventSource), and must work on a host page without breaking it.

> Deferred placeholder. The full buildable scaffold lands with the Day-10 widget
> work; it is stubbed here so the priming task stays backend-focused and does not
> ship a half-configured frontend toolchain.

## Chosen tooling (locked)

- **Build**: Vite library mode, single custom element entry, ES bundle for the CDN.
- **Language**: TypeScript, `strict` plus `noUncheckedIndexedAccess`, via extending [`@tsconfig/strictest`](https://www.npmjs.com/package/@tsconfig/strictest).
- **Lint + format**: Biome alone. No ESLint here: there is no React, so the `eslint-plugin-react-hooks` caveat that the dashboard carries does not apply.
- **Package manager**: npm with a committed `package-lock.json`.
- **Node**: pinned via `.nvmrc` and the `engines` field in `package.json`.

## What goes here

- `src/honest-agent-widget.ts`: the Lit `@customElement` with Shadow DOM styling.
- `vite.config.ts`: library build (`build.lib`) producing the CDN bundle.
- `tsconfig.json` extending `@tsconfig/strictest`, `biome.json`, `package.json`, `.nvmrc`.
