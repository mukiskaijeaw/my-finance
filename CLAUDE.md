# Claude Code

This folder was written for Codex. Claude Code uses the same rules and skills:

@AGENTS.md

## Differences in Claude Code

- Skills are in `.agents/skills/`. The files in `.claude/skills/` only point to them, so there is one copy to edit.
- Where `AGENTS.md` or a skill says "ask-with-options tool" or `request_user_input`, use the `AskUserQuestion` tool. It allows up to 4 options per question, so the น้องเป๋าวีน welcome uses two questions: first 📸 ส่งสลิป / 🧾 ส่ง statement / 📊 ขอดูสรุป / 🔔 บิลใกล้ถึง; the user can type for anything else, then offer ✏️ จดเอง/พูดเลย and 💸 ภาษี ลงทุน ช้อป only if they ask for something not on the first list. If the tool is not available, use a numbered list.
- On Windows the Python command is usually `python` (or `py`), not `python3`. If `python3` is not found, run the same command with `python`.
- Run commands from this folder (the one holding `AGENTS.md`).
