# PNG visualization — Financial Fit POC

This layer renders engine output only. The financial engine and its calculations are unchanged. Scope is one Financial Fit card pending confirmation that the user sees it inline in Codex Desktop. Other seven card types are not implemented yet.

## Capability check, 2026-11-12

Running desktop: 26.1103.32239, build 25471, prod, read from check_app_update. No update was installed. Official documentation describes MCP tools for Codex/ChatGPT and optional iframe UI in ChatGPT, not a guarantee of native arbitrary inline widgets in this running session. The exposed tools do not provide a Shopping Agent native-card registration API. Do not claim global lack of MCP support, and do not claim a skill can register a native widget. The documented MCP UI path uses HTML/JS and a server; those are outside the user's scope.

Sources actually opened:
- https://developers.openai.com/plugins/build/app-quickstart
- https://developers.openai.com/plugins/build/chatgpt-ui

PNG is a visual image in chat, not an interactive native widget. Light/dark are explicit render options; there is no automatic detection of the app's theme. Do not generate a substitute website if inline image display fails.

## Dependencies and local execution

Optional PNG rendering needs Pillow in a local Python environment (`python -m pip install Pillow`). Core calculations and the dashboard use only the standard library. Supply appropriate Thai fonts for your platform.

Core shopping commands do not import Pillow and retain their existing dependency-free behavior. Windows font files: tahoma.ttf and tahomabd.ttf. The Windows wheel does not expose RAQM; renderer uses Unicode DrawTextW through local Windows GDI to shape Thai, then Pillow composites the glyph mask. No font uploads or downloads, no network during rendering. Platforms without Windows need RAQM and supplied matching Thai fonts; they fail clearly instead of silently rendering broken Thai.

Usage: call scripts/card_renderer.py with `--input <local engine result JSON> --output <new.png> --theme light|dark [--demo]` using the visual Python environment. It supports Financial Fit only. Input is the result object from engine.financial_fit or the financial field from an evaluated listing, not raw CSV or an invented summary. It reads status, months, monthly_surplus and savings_progress; money formatting and percentage-to-pixel scaling are visualization only. No fit/ETA/ratio calculation occurs in this renderer. Missing progress is shown as unknown; never create fake 0%.

Keep real financial artifacts inside the user's approved private local location, not outputs/examples/tests/commits. Ignore/remove those image artifacts as appropriate. Demo PNGs may be in the chat outputs because all figures are synthetic. PNGs contain financial numbers: do not upload to retailer sites or remote image services. All output files are exclusively created, never overwritten silently.

## Inline display and product layout

Render a generated image directly in the assistant response with `![Financial Fit](<absolute local path>)` (without angle brackets inside the actual image target), not a code path or download-only link. Review it with view_image first. Ask whether the user sees it if client visibility has not been observed. The review tool returning an image confirms a readable artifact; it does not prove that every client rendered the final message.

Product proposals use one section per product: product name -> immediately its verified image -> product details with identical headings ตัวเลือกสินค้า / ส่วนลดเพิ่มเติม / ค่าจัดส่ง. Do not collect all product photos into a gallery below the comparison table. Product image sources and exact variant verification remain mandatory.

## Verification

POC synthetic request: monthly surplus 3000, product 4500, allocated savings 0. Existing engine returns SAVE_FIRST, 2 months, 0.00% progress. Rendered light/dark PNGs at 1200x1400, visually inspected Thai characters, baht symbol, layout and unclipped text. Six renderer tests cover requested fixture, PNG validity/themes, no network/mutation, changed input changes image, missing data, and exclusive writes. Existing shopping regression suite is run separately; optional rendering tests reside in visual_tests/.

Next stage only after inline display is verified: Smart Budget, Upcoming Expenses, Opportunity Cost, Payment Comparison, Purchase Goal, What-if, Product Comparison. No changes to financial logic needed for that expansion.
