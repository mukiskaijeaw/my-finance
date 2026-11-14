# Personal Financial Decision Agent

Help users make better financial decisions, not just better purchases. The skill remains `shopping-agent`, with the workspace name `shopping`; no duplicate agent or renamed installation is created.

## Conversation routing

Codex extracts intent and relevant sourced context; Python calculates and applies the policy. A product search is optional, never the default answer to every financial concern.

| User intent | Local tools / behavior |
|---|---|
| Price/specification only | Product search, images only if requested; no financial source read |
| Bare product / purchase desire | Follow workspace-authorized local provider connection; clarify meaningful variant/purpose, then financial assessment |
| Should I buy / replace broken item / promotion | Cycle-aware fit + decision policy; offer relevant alternatives |
| Overspending / biggest category this month | Finance workflow in selected Pillar 1; deterministic observed totals, not a shopping search; incomplete transaction history does not prove a complete monthly budget |
| Remaining cash / travel / saving for next year | Existing budget, future obligations, goals or what-if as appropriate; never suggest a product merely to spend remaining cash |
| Installment / BNPL | Existing complete-term installment analysis before recommending; missing terms means NEED_MORE_INFO |
| Goal trade-off | Existing opportunity-cost tool with actual proposed funding source; no automatic diversion of goal/emergency money |
| New information | Fresh local data + recalculation and recommendation; do not mutate actual financial facts from a simulation |

Ask only questions that can materially change the decision. Do not judge necessity from product type or invent necessity/value scores. Purpose, repairability, urgency, borrowing availability, desire for used items, and willingness to skip come from user/evidence. A sale countdown is not evidence of user urgency. A purchase that is affordable may be discretionary and valid; do not moralize or automatically reject it.

The selected provider is already recorded in workspace AGENTS.md. Do not ask for its location again. Read only the data required for the chosen financial intent. No usable Pillar 5 due-date feed or confirmed legacy profile has been established; never imply they exist. Pillar 2 investment cash flows/3 tax due dates/5 subscriptions are included only when real, current, confirmed data are available. Preparation estimates and historical recurring patterns are not confirmed bills.

## Decision request contract

`shopping.py decision --format json|markdown --finance-dir <selected provider>` accepts:

```json
{
  "profile": {},
  "decision": {
    "price": "4500",
    "price_confirmed": true,
    "price_source": "user-confirmed final checkout or fresh effective_price evidence",
    "budget": {},
    "context": {
      "purpose": {"value":"meetings for work", "source":"user statement"},
      "necessity": {"value":"required", "source":"user statement"},
      "timing": {"value":"flexible", "source":"user statement"},
      "value_suitable": {"value":true, "source":"verified requirements and specifications"},
      "planned": {"value":true, "source":"user statement"},
      "offer_ready": {"value":true, "source":"confirmed exact variant, size, stock and checkout terms"}
    },
    "alternatives": []
  }
}
```

This is an input shape, not a financial example; profile/budget require confirmed fields from the existing planning contract. A price must be a verified effective price (with eligible discounts and shipping) or user-confirmed final total. A partial estimate cannot be marked confirmed. Codex prepares the request; users do not fill JSON. JSON stdout is the default. Markdown is the accessibility fallback. Primary chosen presentation is PNG via decision_renderer.py.

Facts use `{value,source}`. Unknown or unsourced facts remain unknown. necessity: required/wanted/not_needed; timing: urgent/flexible. Booleans: value_suitable, planned, promotion, prefer_skip, current_usable, repair_possible, borrow_possible, secondhand_acceptable, offer_ready. Do not fill absent facts with false to manufacture confidence. No percentage score is used. `offer_ready` includes variant match and stock, not just a positive engine balance.

Alternatives are `{id,action,price,price_confirmed,price_source,suitable:{value:true,source}}`. Actions: repair/use_current/borrow/rent/buy_used/cheaper. Confirm costs including fees; zero cost is explicit, not unknown. Each is calculated by the same cycle-aware fit before being labeled affordable. Unknown repair cost can generate a quote request only; it is not claimed cheaper. No alternative action is actually performed.

`evaluate_decision` returns `{financial,decision,price}`. `financial` is the existing fit result without changed calculations. `decision` has policy_version, financial_fit, recommendation, label, reasons, alternative_actions, verified_alternatives, follow_up_questions (at most one), missing, and assessment across affordability/necessity/value/timing/financial_impact. `assessment.financial_impact` is the existing protection classification; use the opportunity-cost tool for actual goal delays rather than inventing them here.

## Policy v1 priority

1. Explicit preference to skip -> SKIP_PURCHASE, without suggesting products to spend the money.
2. Missing financial fit/verified total -> NEED_MORE_INFO, never a buy verdict.
3. Missing sourced purpose/necessity -> NEED_MORE_INFO, targeted question.
4. Known unsuitable item -> CHOOSE_ALTERNATIVE only if a suitable affordable alternative exists, otherwise NEED_MORE_INFO.
5. SAVE_FIRST / NOT_AFFORDABLE -> CHOOSE_ALTERNATIVE when user urgency and verified feasible alternative exist; otherwise WAIT_AND_SAVE. No ETA if engine cannot establish one; in that case review obligations first.
6. AFFORDABLE with missing suitability/offer readiness -> NEED_MORE_INFO.
7. AFFORDABLE + confirmed required purpose + planned + suitable ready offer, without promotion pressure -> BUY_NOW. This is advice, not authorization to transact.
8. Other complete affordable contexts -> BUY_WITH_CAUTION; discretionary spending is not automatically disapproved.

Promotion adds a reminder about actual cash outlay, never an urgency prompt. The six recommendations are separate from the four fit statuses. No new money formula is defined. A better cash balance alone cannot bypass missing purpose/value/offer evidence.

## Visual response and privacy

The user selected option A, graphic PNG cards, without product photographs. Use local Pillow renderer decision_renderer.py after evaluating. Place recommendation first, separate Financial Fit line, then price/available/gap/monthly surplus, timeline/progress, reasons, relevant next action. Mark DEMO or hypothetical data visibly. Use a concise accompanying sentence for questions/alternatives not visible in the card. Large lists of product offers are secondary and appear only when needed. Product options, additional discounts and shipping stay consistent; links are in accompanying chat text because PNG is not clickable. No HTML/CSS/JavaScript/frontend/server.

The original financial-fit renderer remains available. This upgrade adds a personal decision card; it does not pretend that all seven other planned visual renderers are implemented. The application theme is not detected; choose light/dark explicitly. Rendering failures do not trigger website creation; use the textual accessibility fallback and state the limitation.

Real output images are sensitive local financial artifacts: store only in the approved private local directory, never public examples, reports or commits. Only synthetic demos may be placed in this chat's outputs. No raw finance, purpose, balances or profile enters a product query. Core helper imports no Pillow; optional visual environment remains isolated. No actual financial records/goals/wishlist/purchases are written by decision evaluation.
