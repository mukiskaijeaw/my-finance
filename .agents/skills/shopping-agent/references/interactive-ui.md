# Native Welcome + Purchase Simulator (MVP)

## Latest welcome update

The user approved host visualize inline rendering and requested the 2-column, 6-card welcome (tax and investment removed at the user's request). Use assets/welcome-inline.html and the current SKILL.md routing instructions before the older native-only guidance below. No financial data is read or embedded by the welcome. Host sendFollowUpMessage is guarded with a visible failure fallback; actual click-to-chat remains awaiting user verification. This is separate from the unconnected MCP Apps POC and does not establish MCP Apps support.

## Verified runtime, 2026-11-12

- Desktop 26.1103.32239, build 25471, prod, read with check_app_update.
- Bundled CLI features: apps stable true; enable_mcp_apps under development false. This CLI/config evidence does not independently prove all host UI capability flags. No custom UI renderer or tool hot-registration API is exposed in this chat.
- Native question/selection tool accepted one question with all 8 options. Actual user clicked “💰 เดือนนี้เหลือเงินใช้ได้อีกเท่าไหร่”; its answer arrived as a new user reply in the same chat. This is a real PASS for native selection and context continuation, not an automated fake click.
- Local browser automation rejected file:// with a URL-policy denial. Do not try a different browser, indirect launch, local HTTP server or headless browser to bypass that denial. Pointer drag, keyboard/touch, image load, responsive visual parity and rendered dark mode remain NOT TESTED in a real browser. JS view-model tests are not evidence of actual dragging.
- No global feature flags, MCP config or app settings were changed. No external server/tunnel/plugin upload; no restart was forced. Financial Decision Engine and Pillar 1 data unchanged.

References opened: https://developers.openai.com/plugins/build/chatgpt-ui and https://developers.openai.com/plugins/build/app-quickstart. MCP Apps resource MIME is text/html;profile=mcp-app; tool `_meta.ui.resourceUri`; bridge `ui/initialize`, tools/call and ui/message. Local MCP configuration requires connection/restart per https://learn.chatgpt.com/docs/extend/mcp?surface=app. Do not claim an unconnected server renders inline.

## Native Welcome behavior

When the entire user message is `/shopping-agent`, `/shopping`, `shopping agent`, or `เริ่ม shopping agent`, or an explicit bare skill activation, show the native selection once. This is a text/skill trigger, not registration of a new app command. If the composer handles a slash command itself, use the installed skill's supported invocation or text trigger instead. Do not show the menu on ordinary product questions or follow-ups.

Run `python <skill-dir>/scripts/shopping.py welcome` to obtain the host tool payload without reading any finance source or searching products. Pass its questions to the available request_user_input_async native tool. It is not an MCP tool or JSON for the user to type. The host tool itself renders the controls; do not replace them with a PNG or Markdown imitation. The title contains the exact heading and description on two lines; font/layout are host-controlled, not a custom 2x4 grid.

The tool accepts all eight options in this environment; no splitting was required. If a different runtime rejects the count, split into short native questions: purchase/promotion/tradeoff; balance/expenses; saving/installment/travel, then show that category's choices. Never hide a category. Users can always provide free text; do not append an Other option yourself. scripts/welcome.py contains exact options and routes; limited-option category output requires a second native question, not a financial calculation before selection.

On a real reply, use route_answer to choose existing tools. Monthly overview uses selected Pillar 1 plus budget when confirmed; transactions alone are not balances. Expense analysis routes through finance summary. Product or purpose missing -> ask only a necessary follow-up. No transaction/goals saved from a menu click. Preserve the existing conversation; no new thread or message-to-another-thread tool. Do not repeat the menu automatically.

## Simulator architecture and financial mapping

scripts/simulator.py calls existing engine.financial_fit for each of the 111 slider steps (1000..12000 by 100). assets/simulator.html only formats/selects those precomputed results on native input events. No financial formulas or LLM calls on slider movement; bar/slider pixel geometry is presentation only. No submit, reload or chat message required for a price change. A product can be passed by name, initial price and verified image URL/source; placeholder if absent or image fails. Snapshot must be rebuilt if the profile, slider range or product changes.

The user-provided profile is an explicitly synthetic demo, not a discovered existing Pillar 1 profile. Use the existing confirmed profile contract without editing the real provider. Map cash=12000 spending+5000 already-transferred savings+60000 separate emergency=77000; emergency=60000; reserved=5500 unpaid+5000 protected transferred savings=10500. Available=6500. The 17000 monthly expenses and 5000 target are monthly flows, not additional cash deductions. Demo assumes debt=0 beyond stated expenses, explicitly as an assumption. Never infer that for actual users.

Demo safety buffer 1500 defines `demoFinancialStatus` only. Preserve engineFinancialFit separately; e.g. price5500 is engine AFFORDABLE but demo BUY_WITH_CAUTION. This visual status is neither full necessity/value assessment nor the Personal Decision policy's Final Recommendation. Buffer is not subtracted twice; available remains6500. Price8000 yields remaining -1500, shortfall1500 and spending123.1%; visual bar clamps to100%. Price5000 exact buffer is AFFORDABLE; price6500 exact zero is BUY_WITH_CAUTION. Unknown denominator gives unknown ratio and hidden bar, not fake 0%.

build_payload returns productName,productImageUrl,productPrice,availableMoney,safetyBuffer,currency,demoMode,slider,states,assumptions. Engine results are decimal strings. State includes remainingMoney,spendingPercentage,shortfall,progressBarWidth, price/remaining display strings and labels. Renderer accepts demo only in this MVP; real mode is rejected. No financial adapter imports network or touches CSV. `demoMode:true` must not be applied to real user data to bypass this restriction.

Preview command: `python <skill-dir>/scripts/simulator.py --output <new-preview.html> [--product-name <name>] [--price <grid-price>]`. Only synthetic data are used. The local single component is user-authorized; no full website/dashboard or server. New file creation is exclusive. A generated preview is not proof of Codex inline rendering. The latest request contained textual design specs but no screenshot; exact screenshot fidelity cannot be assessed.

## MCP POC preparation

scripts/mcp_ui_poc.py is a local stdio MCP demo, not installed in desktop config. No HTTP listener or external server. It exposes one-button resource assets/mcp-button-poc.html, simulator resource and three demo tools. Tool parameters are empty and reject arbitrary financial fields/file reads. Context/click count is synthetic in-memory state only, not access to the real conversation or profile.

Resource/protocol tests pass; the actual Codex widget-render, host click, follow-up and context retention tests are NOT TESTED while disconnected and disabled. Native menu is the working fallback. Do not expand the custom welcome into 8 HTML cards until its real host POC passes. The server/tool bridge can be connected later on a supported host, but do not enable experimental features, register it globally or restart the user's app implicitly. Simulator resource already embeds the engine-computed demo payload and uses the same HTML component.

## Testing

- `python -B -m unittest discover -s tests -q`: core, welcome routes, simulator A–E, financial mapping, no mutation/network, MCP stdio protocol.
- Existing visual_tests still test PNG policy cards separately.
- `python scripts/test_simulator_view.py --node <node executable>`: JS DOM-stub/input-event tests, all111 states, colors/progress/explanation updates, second product, no fetch. These tests do NOT test mouse, touch, keyboard or visual layout in a browser.

No purchase action, transaction writing, goal saving, analytics or localStorage exists in this component. Image request may go to static.nike.com, with no-referrer and no financial information. connect-src none blocks outgoing fetch. Product screenshot/reference still requires separate visual QA after the user can open the local preview.
