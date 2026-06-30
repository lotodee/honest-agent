# Dashboard (React + Vite)

The owner-facing dashboard, minimal and product-only: upload, status, results, and
a trace link. Red-to-green is shown via the real GitHub Actions run, never a custom
eval-visualization UI.

> Deferred placeholder. The full buildable scaffold lands with the Day-9 dashboard
> work; it is stubbed here so the priming task stays backend-focused and does not
> ship a half-configured frontend toolchain.

## Chosen tooling (locked)

- **Build**: React + Vite, TypeScript.
- **Language**: TypeScript, `strict` plus `noUncheckedIndexedAccess`, via extending [`@tsconfig/strictest`](https://www.npmjs.com/package/@tsconfig/strictest).
- **Lint + format**: Biome for the baseline, plus a thin ESLint flat config carrying only `eslint-plugin-react-hooks` on top of Biome. Biome cannot yet do the React-hooks rules, so ESLint covers exactly that gap and nothing else.
- **Package manager**: npm with a committed `package-lock.json`.
- **Node**: pinned via `.nvmrc` and the `engines` field in `package.json`.

## What goes here

- `src/`: the React app shell (upload, status, results, trace link), no scope creep.
- `vite.config.ts`, `index.html`.
- `tsconfig.json` extending `@tsconfig/strictest`, `biome.json`, `eslint.config.js` (react-hooks only), `package.json`, `.nvmrc`.
