# Shopping Agent

Use `.agents/skills/shopping-agent/SKILL.md` for shopping and personal purchase planning. Respond in Thai by default. Keep financial calculation in Python, product evidence and interpretation in the agent, and presentation in reusable templates.

This repository contains source code and synthetic fixtures only. It has no real financial provider configured. Reuse a provider already selected by the workspace/user; otherwise request a local provider only when financial assessment requires it. Inspect its instructions, actual CSV header and confirmed profile before reading. Do not copy a ledger, receipt, private profile, account details, secrets or local goals into this repository or external search queries. Unknown values are never zero. Explicit price/spec-only requests must not read financial data.

No purchases or transaction writes. Product selection is not permission to save goals or watchlists. Goal writes require a reviewed plan, explicit consent, revision and operation ID. Potential savings are not cash. Protect existing commitments once; never use emergency funds automatically. Cross-month plans require complete confirmed future cashflows.

An optional local dashboard in `dashboard/` is authorized; bind only 127.0.0.1 and keep it in isolated Demo Mode. Its chat is a deterministic local router, not an LLM or live merchant search. Use Codex tools for sourced product research. Do not upload financial data or enable public hosting. Preserve existing chat/CLI workflows when changing the dashboard.

Private state lives in ignored `local/`. When installed outside this checkout, pass --store <workspace>/local/goals.sqlite3 or set SHOPPING_WORKSPACE to the intended project. Do not silently mix stores from unrelated projects. Tests must use temporary stores and synthetic fixtures.
