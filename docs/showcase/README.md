# Showcase materials (September 2026)

Built from scratch on 2026-09-15 for the ReliaQuest Innovation Challenge showcase (five-minute slot, mixed audience). FSU visual style (garnet #782F40, gold #CEB888, Arial as the approved Open Sans substitute); FSU and ReliaQuest marks top-left on every slide.

| File | What it is |
|---|---|
| `Ariadne_Showcase.pptx` | 13-slide deck; speaker notes on every slide carry the timed script (4:55 total) |
| `Ariadne_Showcase_preview.pdf` | LibreOffice render of the deck for quick viewing |
| `Ariadne_Technical_Brief.docx` / `.pdf` | One-page technical brief: what it is, what it does, how it does it, structural facts, limits |
| `build/build_deck.js`, `build/build_report.js` | Generators (pptxgenjs, docx). `cd build && npm i pptxgenjs docx && node build_deck.js` |
| `build/capture.js` | Headless-Chromium capture of the workbench answer used on slide 8 (`npm i puppeteer-core`; needs the app on :16500) |
| `build/assets/` | Logos, recoloured figures (from olmozavala.com/presentations/ariadne, backgrounds swapped to FSU garnet), workbench captures, closing illustration |

Numbers policy: structural figures only (3·2·1, 0 vs 1,083, 240/240, card-to-graph size, ReliaQuest catalogue counts). No correctness scores on any slide. Experiment ids live in the speaker notes, never on the slide; check `docs/research/CURRENT.md` before changing one.

Open items: re-record a 30-second clip of slide 8's run on the current workbench and embed it; the still is a placeholder.
