# SwiftLaTeX POC Assets

These files are vendored only for the isolated browser LaTeX proof of concept.

Source release:

- Repository: https://github.com/SwiftLaTeX/SwiftLaTeX
- Release: `v20022022`
- Asset: `20-02-2022.zip`

Included files:

- `PdfTeXEngine.js`
- `swiftlatexpdftex.js`
- `swiftlatexpdftex.wasm`
- `swiftlatexpdftex.fmt`
- `LICENSE`

Local patch:

- `PdfTeXEngine.js` reads `self.SWIFTLATEX_ENGINE_PATH` so the engine worker can be loaded from Vite's static asset path.
- `PdfTeXEngine.js` returns bytes from `compileFormat()` for debugging, although the POC now prefers the prebuilt `swiftlatexpdftex.fmt`.

Additional source:

- `swiftlatexpdftex.fmt` is from https://github.com/SwiftLaTeX/Texlive-Ondemand.

Important:

- SwiftLaTeX fetches TeX package files from a TeXLive endpoint when they are missing.
- The production app must not depend on the public SwiftLaTeX endpoint unless explicitly approved.
- Do not wire this POC into the main report button until the static TeX asset strategy and AGPL-3.0 licensing are accepted.
