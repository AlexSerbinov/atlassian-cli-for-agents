# atl

**Jira and Confluence Cloud from your shell — built for AI coding agents.**

A single-file, zero-dependency CLI that replaces the [mcp-atlassian](https://github.com/sooperset/mcp-atlassian) MCP server. Same operations, **5–25× fewer tokens**, no resident process, and it does three things the MCP server cannot do at all.

[![tests](https://github.com/AlexSerbinov/atl/actions/workflows/test.yml/badge.svg)](https://github.com/AlexSerbinov/atl/actions/workflows/test.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
![Python](https://img.shields.io/badge/python-3.8%2B-blue)
![dependencies](https://img.shields.io/badge/dependencies-none-brightgreen)

```console
$ atl issue EA-1257
EA-1257  Generated API types cannot be regenerated — minified DTO class names are unstable
  status:   In testing   type: Task   prio: Medium
  assignee: Alex Serbinov   reporter: Anna K.
  labels:   backend, frontend, tech-debt
  time:     spent 30m  est —
  url:      https://acme.atlassian.net/browse/EA-1257

--- description ---
## Problem
`npm run generate:admin` cannot be run. Regenerating the types produces a …
```

That is the whole response. The equivalent MCP call returns 56 KB of JSON, and your model pays for every byte of it.

---

## Why this exists

MCP is a good protocol for a lot of things. For a REST API that an agent calls dozens of times a day, it has three costs that compound:

**1. Every response is raw JSON, and the model reads all of it.**

A 20-issue search through mcp-atlassian returns 13.5 KB. The same search here returns 2.9 KB. The difference is not compression — it is that the MCP response repeats the same 200-character `avatar_url` on all twenty rows, for the same person, plus `id`, `self` links, and status colors nobody asked for. With a CLI, `jq`, `grep` and `head` do the filtering in the shell, and intermediate JSON never enters the context window at all.

**2. One resident process per editor session.**

mcp-atlassian is a Python daemon. Open ten terminal tabs with your agent and you have ten copies, ~137 MB each, sitting there whether or not you touch Jira that day.

| | mcp-atlassian 0.21 | atl |
|---|---|---|
| 1 session | 137 MB | 0 MB |
| 10 sessions | 1.4 GB | 0 MB |
| 20 sessions | 2.7 GB | 0 MB |

`atl` starts in ~90 ms, does the call, and exits.

**3. Tool schemas are not free.**

mcp-atlassian exposes **72 tools** (49 Jira + 23 Confluence). Their descriptions and parameter schemas total ~141 KB — roughly **35,000 tokens** if a client loads them all. Modern clients defer schemas and load them on demand, which helps, but you still pay ~700 tokens per tool the moment you use it. This README's companion `SKILL.md` is 9 KB — about 2,300 tokens, loaded once, and it documents all 46 commands.

---

## Measured

Same site, same queries, same day. Compact `atl` output vs. what the model actually receives.

| Operation | `atl` | mcp-atlassian / raw JSON | Reduction |
|---|--:|--:|--:|
| search, 20 issues | 2.9 KB | **13.5 KB** † | **4.6×** |
| view one issue | 6.9 KB | 56 KB | 8.2× |
| read comments | 5.1 KB | 43 KB | 8.4× |
| list transitions | 0.9 KB | 14 KB | 15× |
| list worklogs | 0.14 KB | 3.3 KB | 24× |
| list boards | 0.8 KB | 12 KB | 15× |
| list projects | 1.0 KB | 26 KB | 25× |

† measured against mcp-atlassian 0.21.0 directly. The other rows compare against the raw Jira REST payload, which is the upper bound — mcp-atlassian trims some fields, so its real numbers sit between the two columns.

A typical time-tracking session is 15–25 Jira calls. That is ~150–200 KB of context through MCP against ~20 KB here.

---

## What it does that mcp-atlassian cannot

These are not efficiency wins. They are operations that have no MCP tool at all, verified against mcp-atlassian 0.21.0.

| | mcp-atlassian | atl |
|---|---|---|
| **Edit a worklog** | ✗ no tool | `atl worklog edit KEY ID --time 2h` |
| **Delete a worklog** | ✗ no tool | `atl worklog rm KEY ID` |
| **Upload a Jira attachment** | ✗ download only | `atl attach KEY shot.png` |
| **Transition + comment** | ✗ fails: *"Operation value must be an Atlassian Document"* | `atl transition KEY --to Done --comment "…"` |
| **Diff two Confluence versions** | raw XHTML | unified diff on rendered Markdown |

The transition-with-comment failure is the interesting one. Jira REST v3 and Confluence Cloud v2 take rich text as **ADF** (Atlassian Document Format), a JSON tree. A tool that cannot build ADF cannot write a comment, a description, or a page body. `atl` ships a Markdown ↔ ADF converter — headings, lists, code blocks with language, blockquotes, rules, links, inline marks, and tables, round-tripping in both directions.

```console
$ atl conf diff 829718529
--- v2
+++ v3
@@ -1,8 +1,7 @@
 # Release checklist

-Second version — line changed.
+Third version.

 - alpha
-- beta
 - gamma added
```

---

## Install

**One file, no dependencies.** Pick whichever you like:

```bash
# curl
curl -fsSL https://raw.githubusercontent.com/AlexSerbinov/atl/main/atl -o ~/.local/bin/atl
chmod +x ~/.local/bin/atl

# pip
pip install atl-cli

# git
git clone https://github.com/AlexSerbinov/atl && ln -s "$PWD/atl/atl" ~/.local/bin/atl
```

Then:

```bash
atl init      # prompts for site URL, email, API token; writes ~/.atl.json (mode 600)
atl me        # verify
```

Get an API token at [id.atlassian.com/manage-profile/security/api-tokens](https://id.atlassian.com/manage-profile/security/api-tokens).

**Migrating from mcp-atlassian?** Skip `atl init`. If the `atlassian` server is still in your `~/.claude.json`, `atl` reads the credentials straight out of it and works with zero configuration. Remove the server when you are satisfied.

Credentials are resolved in this order: `~/.atl.json` → `ATL_URL`/`ATL_USER`/`ATL_TOKEN` → `~/.jira-api-token` → the legacy MCP config.

---

## Use it

Compact output by default. `--json` gives the untouched API payload, and works both before and after the subcommand.

### Work items

```bash
atl issue EA-1257                    # compact view, description rendered as Markdown
atl issue EA-1257 --full             # every field, including custom fields
atl search 'assignee = currentUser() AND statusCategory != Done' --limit 20

atl create --project EA --type Task --summary "…" --description @body.md \
           --assignee me --labels backend --sprint 2466
atl edit EA-1257 --summary "…" --priority High
atl assign EA-1257 "Alex Serbinov"   # display name or email; `none` unassigns
atl link EA-1257 --to EA-1258 --type Blocks
atl delete EA-1257 --subtasks
```

`--description`, `--comment` and worklog comments take inline Markdown or `@path/to/file.md`. Use `@file` for anything long — it keeps the body out of your shell history.

### Statuses and comments

```bash
atl transitions EA-1257                        # what is reachable now, with ids
atl transition EA-1257 --to "In Progress"      # fuzzy match on the target status
atl transition EA-1257 --to Done --comment "shipped in v2.7.4"

atl comment EA-1257 'text with **markdown**'
atl comments EA-1257 --limit 5
atl comment-edit EA-1257 34277 'rewritten'
atl comment-rm EA-1257 34277
```

### Worklogs

```bash
atl worklog list EA-1257 [--mine]
atl worklog add  EA-1257 2h30m --date 2026-08-22 --at 10:00:00 --comment "…"
atl worklog edit EA-1257 47005 --time 2h
atl worklog rm   EA-1257 47005
atl report 2026-08-10 2026-08-14               # per-day totals with delta to target
```

Durations: `2h30m`, `1d`, `45m`, `1w2d`; a bare number is minutes. Jira's workday is 8h and its week 5d, so `1d` = 8h. `--date` defaults to today, so pass it explicitly for past days. The local UTC offset is attached automatically — Jira rejects a naive timestamp.

### Sprints, boards, attachments

```bash
atl boards --project EA
atl sprint current 216                         # id of the board's active sprint
atl sprint add current EA-1257 EA-1259 --board 216
atl sprint backlog EA-1257
atl sprint create --board 216 --name "Sprint 20" --start 2026-08-24 --end 2026-09-07

atl attach EA-1257 shot.png notes.pdf
atl download EA-1257 --name shot --dest ./tmp
atl attach-rm 29566
```

### Confluence

```bash
atl conf search 'title ~ "Backend" order by lastmodified desc'
atl conf get 829718529                         # page as Markdown
atl conf create --space DOCS --title "Notes" body.md
atl conf put 829718529 body.md --message "why this edit"

atl conf comments 829718529                    # threads, replies indented
atl conf comment 829718529 'text'
atl conf reply 829620248 'threaded reply'

atl conf history 829718529
atl conf diff 829718529 --from 1 --to 3
atl conf labels 829718529
```

### Compose it

The point of a CLI is that the shell does the work:

```bash
# total logged on an issue, in hours
atl worklog list EA-1257 --json | jq '[.[].timeSpentSeconds] | add / 3600'

# move everything ready-to-test into the active sprint
atl search 'project = EA AND status = "Ready for QA"' --json \
  | jq -r '.[].key' | xargs atl sprint add current --board 216

# every issue you touched last week, as a changelog
atl report 2026-08-17 2026-08-21
```

---

## Using it with an AI agent

The repo ships a [Claude Code skill](skills/atlassian-cli/SKILL.md) — drop it in and the agent learns all 46 commands from one 9 KB document:

```bash
cp -r skills/atlassian-cli ~/.claude/skills/
```

For other agents, point them at `SKILL.md` or at `atl --help`. There is no protocol to implement and no server to run: the agent already knows how to run shell commands.

---

## When you should use mcp-atlassian instead

`atl` covers about 35 of mcp-atlassian's 72 tools — the ones that carry day-to-day work. It does **not** implement:

- **Jira Service Desk** — queues, SLA, request types
- **Proforma forms**
- **Watchers** — add/remove/list
- **Versions and releases** — `fixVersion` management
- **Development info** — linked branches and pull requests
- **Batch create**, remote issue links, project components, field options
- **Confluence** page move, user search, page-view analytics

If your workflow lives in Service Desk or Proforma, use mcp-atlassian. If it is issues, comments, worklogs, sprints and pages, `atl` covers it and costs a fraction.

Also worth knowing: mcp-atlassian supports **Server/Data Center** as well as Cloud, plus OAuth. `atl` is **Cloud + API token only**. Server/DC users should look at [atlassian-skills](https://github.com/eunsanMountain/atlassian-skills), which takes the same CLI approach for on-prem.

---

## How it works

One file, ~1,600 lines, standard library only. Top to bottom:

```
credentials  →  HTTP (api(), upload())  →  Markdown ↔ ADF  →  helpers
             →  Jira read  →  Jira write  →  worklogs  →  attachments
             →  sprints  →  boards/meta  →  Confluence  →  argparse  →  main()
```

Adding a command is three edits: a `cmd_*(creds, a)` function, a block in `build_parser()`, and a line in the README. `api(creds, path, params, method, body, base=…)` handles auth and JSON in both directions, so most new endpoints are a five-line function.

Rules the code follows, if you send a PR:

- **Compact print by default**, `if a.json: return out_json(...)` as the first line of every command.
- **Never hand-build ADF.** Call `md_to_adf(text)` and `adf_to_md(node)`.
- **Never put the token on a command line.** It is read from disk inside `_auth_header` and nowhere else — there is a test that enforces this by walking the AST.

### Security

The token is read from `~/.atl.json` (mode 600) at call time and used only to build a `Basic` auth header. It is never printed, never logged, and never becomes a process argument.

That last point is not theoretical. An MCP server configured the usual way receives its credentials as command-line flags, which means your Jira token is visible in `ps aux` to every process on the machine, for as long as the server runs:

```console
$ ps aux | grep mcp-atlassian
… mcp-atlassian --jira-token=ATATT3xFfGF0EXAMPLE-not-a-real-token-0000000000 --jira-username=you@corp.com
```

---

## Tests

39 offline tests. No network, no credentials, no Atlassian account:

```bash
python -m unittest discover -s tests -v
```

They cover the Markdown ↔ ADF converter both directions (including the ADF invariant that a text node may never be empty), round-trip idempotency, duration parsing, timestamp shape, credential resolution across all four sources, error unwrapping for both the Jira and Confluence error shapes, and the token-handling rule above.

CI runs them on Linux and macOS against Python 3.8, 3.11 and 3.13.

Every write path was additionally exercised against a live Jira Cloud site: create → comment → transition-with-comment → edit → worklog add/edit/delete → attach/download/delete → sprint add/backlog → assign, and for Confluence create → read → update → comment → reply → history → diff → label → delete.

---

## Contributing

Issues and PRs welcome. The missing tool categories listed above are the obvious first contributions, and each is a small, self-contained function.

Please keep the two hard constraints: **standard library only**, and **one file**. They are what make this thing trivial to audit, vendor and trust with a credential.

## License

MIT — see [LICENSE](LICENSE).
