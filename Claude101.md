# Claude101.md — Using Claude as your “coding LLM” in VS Code (baby guide)

This guide explains how to use **Claude Code** inside **VS Code** (“VSStudio” as you call it) to help you program: planning, editing files, running commands, and reviewing changes.

> The **recommended** way to use Claude Code in VS Code is the **Claude Code VS Code extension** (GUI in the IDE). citeturn2view1

---

## 1) What you’re using (simple mental model)

### Claude UI (claude.ai)
- Best for: brainstorming, writing, asking questions without touching your repo.
- Not ideal for: editing many files, running tests, working with git directly.

### Claude Code (developer tool)
Claude Code is an agentic coding tool that can understand your codebase, edit files, run commands, and integrate with tools. citeturn0search5

You can use Claude Code in:
- Terminal CLI (`claude`) citeturn1view1
- VS Code extension (recommended) citeturn2view1

---

## 2) Should you use the VS Code UI or the terminal?

### Recommended default: VS Code extension UI
Use the extension UI when you want:
- a clean chat panel inside the IDE
- inline diffs / reviewing plans before accepting
- @-mention files/line ranges easily
- multiple Claude conversations (tabs/windows) citeturn2view1turn2view0

### Terminal-style inside VS Code (if you prefer)
The extension can switch to a CLI-style terminal mode via the **“Use Terminal”** setting. citeturn2view0

### My practical advice
- Use **VS Code extension UI** for 80% of work (review, diffs, readability).
- Use **terminal CLI** for quick commands or if you’re already living in the terminal.

---

## 3) Setup (one-time)

### 3.1 Install Claude Code (CLI)
Follow the Claude Code quickstart:
- Install (Windows PowerShell): `irm https://claude.ai/install.ps1 | iex`
- Login: run `claude` and follow prompts citeturn1view1

### 3.2 Install the VS Code extension
Prereqs:
- VS Code **1.98+** citeturn2view1

Install:
1. VS Code → Extensions (`Ctrl+Shift+X`)
2. Search: **“Claude Code”**
3. Install
4. If it doesn’t show up: restart VS Code / “Developer: Reload Window” citeturn2view1

### 3.3 Make sure VS Code “trusts” the workspace
If VS Code is in **Restricted Mode**, the extension won’t work. citeturn2view2turn3search0

---

## 4) First time using Claude inside VS Code (baby steps)

### 4.1 Open Claude panel
The fastest way:
1. Open ANY file in the editor
2. Click the **spark icon** in the editor toolbar (top-right). citeturn2view2

Other ways:
- Command Palette (`Ctrl+Shift+P`) → type “Claude Code”
- Status bar: click “✱ Claude Code” (bottom-right) citeturn2view2

### 4.2 Send a prompt
Examples:
- “Explain what this project does.”
- “Where is the main entry point?”
- “I got this error — help me fix it.” citeturn1view1

### 4.3 (Optional) Switch to terminal mode
If you prefer CLI-style:
- VS Code Settings → Extensions → Claude Code → enable **Use Terminal** citeturn2view0

---

## 5) The single best daily workflow (plan → implement → verify)

### Step 1 — Plan first (especially for non-trivial tasks)
Tell Claude:
> “Plan mode: write a step-by-step plan first, then wait.”

Claude Code supports permission modes (normal / plan / auto-accept) and you can toggle modes with **Shift+Tab** (or Alt+M in some configs). citeturn1view2

### Step 2 — Implement (small chunks)
- Do one small change at a time.
- Prefer small commits.

### Step 3 — Verify before “done”
- Run tests / commands and paste output back to Claude.
- Don’t accept “should work” without evidence.

---

## 6) Power features that make you faster (and safer)

### 6.1 Multiple conversations (parallel thinking)
You can open Claude in a new tab/window, and each conversation has its own context. citeturn2view0  
Use it like:
- Tab 1: main implementation
- Tab 2: debugging / logs
- Tab 3: refactor ideas

### 6.2 Subagents (specialized “bots”)
Subagents are specialized assistants that run in their own context and report back (good for exploration, review, debugging). citeturn1view5  
In Claude Code: run:
- `/agents` (manage and view agents)

### 6.3 Skills (custom commands like /verify)
Skills are reusable instructions you can invoke with `/skill-name`. citeturn1view6  
Example:
- `/verify` to force “prove it works”
- `/review-me` to force “strict review”
- `/techdebt` for cleanup

### 6.4 Statusline (don’t lose track)
Use `/statusline` to generate a statusline script (shows model, context %, branch, etc.). citeturn3search3  
This helps avoid:
- “Oops I’m on main”
- “Context is full, Claude is forgetting”

### 6.5 Settings scopes (personal vs project)
Claude Code settings can be applied at different scopes: **user** (`~/.claude/`) vs **project** (`.claude/` committed to git). citeturn1view3turn3search1  
In Claude Code you can open the settings UI with `/config`. citeturn1view3

---

## 7) Safety basics (don’t skip)

- Only run Claude Code in folders you trust (VS Code Restricted Mode blocks the extension for a reason). citeturn2view2turn3search0  
- Claude Code includes protections like command-injection detection requiring approval for suspicious commands. citeturn3search4  
- On Windows, official security docs recommend avoiding WebDAV paths like `\\*` due to security risk. citeturn3search4  

---

## 8) Quick cheat sheet

### VS Code
- Install extension: `Ctrl+Shift+X` → search “Claude Code” citeturn2view1
- Open Claude: spark icon (needs a file open) citeturn2view2
- Command palette: `Ctrl+Shift+P` → “Claude Code” citeturn2view2
- Switch terminal mode: Settings → Extensions → Claude Code → “Use Terminal” citeturn2view0

### Claude Code shortcuts / commands
- Toggle permission modes: **Shift+Tab** citeturn1view2
- Switch model: **Alt+P** (Win/Linux) citeturn1view2
- Settings UI: `/config` citeturn1view3
- Subagents: `/agents` citeturn1view5
- Statusline: `/statusline ...` citeturn3search3
- Login: `/login` citeturn1view1

---

## 9) “How do I start programming with Claude tomorrow?”
1) Open repo in VS Code
2) Open a file → click spark icon
3) Ask: “Plan mode: I want to do X. Make a plan first.”
4) Implement small steps
5) Run tests
6) Ask Claude to review the diff and give a checklist
7) Commit + push

That’s it. Keep it boring and repeatable.
