# Dynamic goal planner / low usage contract

## Routing and data boundaries

Reuse the existing Shopping Agent. AI extracts intent and sourced fields; it does not calculate dates, money, forecasts, progress or calendars. Read this reference only for goal work. Do not reread unrelated skill resources on every click. Use the same renderer source and replace only the JSON data slot. No LLM, network, package dependency, server or scheduler in the goal modules.

Missing data: ask concise Thai questions, no obligatory UI while collecting facts. Extract fields already supplied, never ask twice. If a purchase has no price, research it with existing product-only search and effective-price tools. Never label an unverified offer as a confirmed purchase cost. No default product or historical demo balance. The old product-only `goal` snapshot command remains supported; it is not automatically imported into the new store. Explicitly reconcile any legacy goals before considering a portfolio complete.

## Commands

`python <skill-dir>/scripts/shopping.py goals --format json` accepts stdin JSON. No finance details in command arguments. Optional `--store <shopping-agent/local/goals.sqlite3>`; default is that workspace-local file. `goal_planner.py` also provides the same standalone stdin workflow. `--consent` is passed ONLY after the user approves the concrete fields and portfolio impact. Preview/view/list do not create the store.

- `action:list`: revision, saved goals and savings entries only, no profile reads.
- `action:preview`: goal fields plus current `profile`, `budget`, optional `forecast` and `coverage`. Replaces a matching goal ID for edit preview or uses temporary `preview` ID for creation. Includes every saved goal automatically; no caller-supplied list that omits competing goals.
- `action:view`: fresh portfolio calculation and active calendars from store.
- Mutations `create`, `edit`, `activate`, `pause`, `delete`, `record_savings`: `goal`, `expected_revision`, unique `operation_id`, full current financial inputs and explicit `--consent`. Return JSON then render a fresh view. `create` saves DRAFT; separately confirm activation before calendar appears. Pause/resume uses pause/activate. Edit permits name/category/target amount/date/image/priority/funding source. Savings totals change only via record_savings.
- `--format inline --output <new-fragment.html>` for preview/view writes a new fragment from the reusable template; show it with visualize directive, never a path alone. Read visualize skill before displaying a newly generated fragment. `--format markdown` is fallback when inline unavailable. Existing welcome and product workflows remain intact.

## Goal fields

Required: `goal_name`, `goal_category` (purchase/travel/general/education/future_expense), `target_amount`, `saved_amount` (explicit confirmed zero if none), `target_date`, `funding_source`. Optional: `goal_id`, `image_url` (HTTPS), `priority` (low/normal/high). Input dates ISO Gregorian, or สิ้นเดือน/end_of_month, สิ้นปี/end_of_year; pure functions resolve relative dates using current Asia/Bangkok date. No inferred year for other ambiguous dates. Fixed UTC+7 does not require Windows tzdata.

Funding source currently supported: `free_cash`, meaning the selected provider's money after essentials, debts, protected savings, emergency and buffer. Do not map emergency or an unapproved savings goal into it. A named alternative pool requires separate confirmation and reconciliation before adapting it; unsupported pools return an error. Priority is descriptive and never silently steals from a lower-priority goal. Horizon up to 10 years for bounded local computation; farther deadlines need refinement.

## Financial inputs and forecast

Use existing profile and cycle-aware budget contract in planning-contract.md; fresh source/confirmation rules remain unchanged. No new financial adapter or balance inference from transactions. Existing engine.budget determines current free spending cash. Goal planner protects ALL saved balances (even paused/deleted) plus remaining scheduled contributions.

`coverage` maps goal IDs to amounts already excluded in profile.reserved. Uncovered saved amounts are deducted once by goal planner; covered amounts are not deducted again. Sum coverage <=reserved and each entry <=that goal's saved balance. Confirm actual account/reserve mapping; never guess. Savings entries record allocation tracking, not additional income or a second expense. After an account/profile update reconcile coverage before recalculating.

Cash-flow forecast is required whenever a deadline extends past the protected current cycle. `forecast:{complete:true,through:<ISO>,events:[{date,income,outflow,confirmed:true}]}`. Events must be AFTER budget.next_income_date and on/before latest target; the current cycle and its income day are conservatively already protected and no receipt on that day is credited again. Include all future essentials, debts, protected savings and known future costs in the confirmed outflow exactly once; events describe changes in FREE CASH, not gross bank balances. Empty events with complete:true means explicitly confirmed no future net flows, not missing data. Variable income requires existing conservative complete-history validation and user-confirmed conservative future flows. Reject unconfirmed or incomplete forecasts. A future receipt cannot repair an earlier negative balance. Surface the forecast's assumptions; no promised future income.

Days remaining excludes today; savings-day denominator includes today. Daily contribution rounds UP to satang, final day caps to remaining target. Progress caps at 100%; saved amount remains actual even above target. Remaining spending budget reserves contributions through current cycle; daily spending rounds DOWN over days including today through next-income date. Separate these from the longer goal deadline. A forecast that cannot fund EVERY active goal returns NOT_FEASIBLE; incomplete inputs return INSUFFICIENT_DATA. Personality never changes either result.

## Storage, consent and buttons

SQLite transaction with BEGIN IMMEDIATE serializes updates. Revision checks prevent lost updates; operation IDs make retries idempotent. Unique (goal,date) rejects a second savings entry on the same day; show the original entry and ask about a correction rather than add blindly. Do not silently replace an entry. Recording future/pre-activation savings is rejected. Edits run full portfolio validation inside transaction. Delete is a tombstone: existing saved money stays protected until separately reconciled, not automatically released for spending.

After today's saving is recorded, today remains in the displayed inclusive day count but is excluded from remaining saving opportunities and daily contribution recalculation. Do not schedule a second saving on that day. A confirmed actual savings entry may still be recorded when the recalculated plan is infeasible/incomplete; return that status honestly instead of discarding the confirmed fact. Creation/edits/activation require a feasible complete plan. Correcting or releasing a historical saving entry is intentionally not automated in this MVP; inspect and reconcile it explicitly.

UI buttons send an in-chat follow-up REQUEST via host sendFollowUpMessage. They do not write to disk or claim success; Codex checks inputs/duplicates, presents the concrete change, obtains confirmation, invokes local CLI and renders updated results. If bridge unavailable show copyable request/native selection. No global experimental flags. Host click-to-follow-up worked for welcome; new goal buttons still need real user verification. No automatic ledger entry, payment, purchase, cancellation, saving or goal activation.

Image URL is optional; category Lucide icon is always available. The inline host CSP cannot load arbitrary merchant image origins; renderer offers an HTTPS source link instead of substituting an unrelated product photo. No image or financial data sent to external search for UI tests.

## Components and personality

assets/goal-planner-inline.html contains reusable creation form, compact goal cards, progress bars, daily spending, overview and month-selectable calendars. Calendar visible only after activation; its dates/recorded states come from Python and storage, not JS financial math. JS formats values and sends requests only. Calendar is a savings-day grid, not a bank statement. Initial empty form has no product, price, saved zero or deadline prefilled. After complete inputs use compact preview, not another forced questionnaire.

goal_renderer.py uses deterministic Thai “sassy but caring” status templates. FUNDED means the savings target is funded, never permission to purchase. No sarcasm or pressure changes financial outcomes.
