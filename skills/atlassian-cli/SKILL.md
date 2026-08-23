---
name: atlassian-cli
description: >-
  Jira and Confluence Cloud from the shell via the `atl` CLI. This is the ONLY way to
  reach Jira/Confluence here — it replaces the
  mcp-atlassian MCP server. Covers work items, JQL search,
  transitions, comments (add/edit/delete), worklogs (add/edit/delete), attachments
  (upload/download), boards, sprints (incl. moving items into a sprint), and Confluence
  pages, comments, history and diffs. Triggers - "jira", "джира", "таска", "заведи
  таску", "затрекай час", "ворклог", "перенеси в In Progress", "закинь у спринт",
  "конфлюенс", "confluence", "сторінка в конфлі", "PROJ-123".
---

# atl — Jira + Confluence Cloud CLI

```bash
atl <command> [--json]
```

**This is a single-file tool you can edit.** It lives in this skill folder and is meant
to be patched when it falls short — see *When something does not work* at the
bottom before reaching for raw `curl`.

Python stdlib only, no
venv, no daemon, ~90 ms + network per call, zero resident memory between calls.
Credentials: `~/.atl.json` (mode 600). The token is read at call time, never printed,
never passed as an argument.

## Credentials

Resolved at call time, first hit wins: `~/.atl.json` -> `ATL_TOKEN` -> `token_command`
(a command that prints the token: 1Password, pass, Vault, OS keychain) ->
`~/.jira-api-token` -> a legacy mcp-atlassian entry in `~/.claude.json`.

`atl init` sets this up interactively; `atl init --scoped` configures a scoped token,
which requires routing through `api.atlassian.com` via a cloud id.

**Never print the token, never pass it as a command argument, never paste it anywhere.**
If a run warns that the config is world-readable, tell the user to `chmod 600 ~/.atl.json`
rather than ignoring it. Tokens are created and revoked at
https://id.atlassian.com/manage-profile/security/api-tokens

## Output contract

Default output is compact lines meant to be read directly. `--json` gives the raw API
payload for `jq`, and works **both before and after** the subcommand.

Pipe when you only need one value; do not pull whole payloads into context:

```bash
atl worklog list PROJ-123 --json | jq -r '.[].timeSpentSeconds' | paste -sd+ - | bc
atl search 'project = PROJ AND status = "In testing"' --json | jq -r '.[].key'
```

## Jira — work items

```bash
atl me                                   # who the token is, accountId, site
atl projects                             # key / type / name
atl fields sprint                        # find a custom field id by name

atl issue PROJ-123                        # compact view + description as Markdown
atl issue PROJ-123 --full                 # every field, incl. custom fields
atl issue PROJ-123 --fields summary,status
atl search 'assignee = currentUser() AND statusCategory != Done' --limit 20

atl create --project PROJ --type Task --summary "..." --description @body.md \
           --assignee me --labels backend --sprint 118
atl edit PROJ-123 --summary "..." --description @body.md --priority High
atl assign PROJ-123 "Jane Doe"      # display name or email; `none` unassigns
atl link PROJ-123 --to PROJ-125 --type Blocks
atl delete PROJ-123 --subtasks
```

`--description`, `--ac`, `--comment` and worklog comments accept inline Markdown or
`@path/to/file.md`. Use `@file` for anything long — it keeps the body out of shell
history and off the process list.

## Jira — statuses and comments

```bash
atl transitions PROJ-123                      # what is reachable from here, with ids
atl transition PROJ-123 --to "In Progress"    # fuzzy match on the TARGET status name
atl transition PROJ-123 --to Done --comment "shipped in v2.7.4"

atl comment PROJ-123 'text with **markdown**'
atl comments PROJ-123 --limit 5
atl comment-edit PROJ-123 34277 'rewritten text'
atl comment-rm PROJ-123 34277
```

## Jira — worklogs

```bash
atl worklog list PROJ-123 [--mine]
atl worklog add  PROJ-123 2h30m --date 2026-08-22 --at 10:00:00 --comment "..."
atl worklog edit PROJ-123 47005 --time 2h --comment "corrected"
atl worklog rm   PROJ-123 47005
atl report 2026-08-10 2026-08-14          # per-day report with the delta to target
```

Durations: `2h30m`, `1d`, `45m`, `1w2d`; a bare number is minutes. Jira's workday is
8h and its week 5d, so `1d` = 8h. `--date` defaults to today — **pass it explicitly
when logging a past day**. The local UTC offset is attached automatically; a naive
timestamp is rejected by the API.

## Jira — attachments

```bash
atl attach PROJ-123 shot.png notes.pdf
atl attachments PROJ-123
atl download PROJ-123 --name shot --dest ./tmp
atl attach-rm 29566
```

## Jira — boards and sprints

```bash
atl boards --project PROJ
atl sprints 42 [--state active|future|closed]
atl sprint current 42                       # -> id of the board's active sprint

atl sprint add 118 PROJ-123 PROJ-124          # move items into a sprint
atl sprint add current PROJ-123 --board 42   # same, resolving the active sprint
atl sprint backlog PROJ-123                   # pull back out to the backlog
atl sprint issues current --board 42

atl sprint create --board 42 --name "EA Sprint 20" --start 2026-08-24 --end 2026-09-07
atl sprint update 118 --state closed
```

`sprint add` chunks at 50 items per call, which is the Agile API's cap.

## Confluence

```bash
atl conf spaces
atl conf search 'title ~ "Backend" order by lastmodified desc' --limit 10

atl conf get 12345678              # page as Markdown
atl conf get 12345678 --meta       # id / title / space / version / url
atl conf create --space DOCS --title "Notes" body.md [--parent 12345]
atl conf put 12345678 body.md --message "why this edit"
atl conf children 12345678
atl conf delete 12345678

atl conf comments 12345678         # threads, replies indented under their parent
atl conf comment 12345678 'text with **markdown**'
atl conf reply 87654321 'threaded reply'

atl conf history 12345678          # version / date / author / edit message
atl conf diff 12345678             # unified diff, previous version -> current
atl conf diff 12345678 --from 1 --to 3 --context 5

atl conf labels 12345678
atl conf label-add 12345678 backend reviewed
atl conf attach 12345678 diagram.png
```

Confluence Cloud v2 speaks ADF, so pages round-trip through the same Markdown
converter as Jira, and `conf diff` diffs the *Markdown* rather than raw XHTML.
Page body comes from a file path, or from stdin if omitted.

## Images and screenshots

Write plain Markdown with local paths. `atl` uploads each file as an attachment and
rewrites it into an ADF media node, so the picture appears **inline between the
paragraphs**, not as an anonymous file at the bottom.

```bash
atl create --project PROJ --type Bug --summary "..." --description @report.md
atl edit PROJ-123 --description @report.md
atl comment PROJ-123 'verified:

![after the fix](after.png)'
atl worklog add PROJ-123 1h --comment @notes.md
atl conf create --space DOCS --title "Postmortem" report.md
atl conf put 12345678 report.md
```

Where `report.md` contains:

```markdown
Text before.

![the broken state](screenshots/before.png)

Text after.
```

- **Relative paths resolve next to the `@file.md`**, so a document and its screenshots
  travel together. Inline bodies resolve against the current directory.
- **Only whole-line images become pictures.** `![x](a.png)` inside a sentence stays a
  link — ADF has no inline image Jira will render.
- **Remote `https://` images become links**, not embeds. Jira accepts an external media
  node but does not render it.
- **A missing file does not fail the call** — it becomes `[missing image: path]` and a
  warning on stderr, so a long document still posts.
- On `create`, the target does not exist yet, so `atl` creates it and then wires the
  images in a second call. That is one extra request, and it is automatic.

## Markdown <-> ADF

Supported both ways: headings, paragraphs, **bold**, *italic*, `code`, links, bullet
and ordered lists, fenced code blocks with a language, blockquotes, horizontal rules,
tables, and images (see above). Round-trip verified against the live API. Anything unsupported degrades to a
plain paragraph instead of failing the call — so exotic ADF (panels, expand blocks,
`@mentions`, nested tables) survives reading but flattens on write.

## Gotchas

- **Assignee by display name or email, never a guessed accountId.** `atl` resolves the
  name through `/user/search` and fails loudly on no match or an ambiguous one.
- **`transition --to` matches the target status, not the transition name.** Run
  `atl transitions KEY` when unsure; the same status can be reached by differently
  named transitions and ids differ per project.
- **Acceptance Criteria is a per-site custom field.** `atl` looks it up in the create
  metadata; if the site has no such field, `--ac` says so — put them in the description.
- **`delete` needs a project permission** most projects do not grant; expect
  `HTTP 403 — You do not have permission to delete issues in this project.`
- **The Sprint field id differs per site.** `atl` resolves it once and caches it in
  `~/.atl.json`; override with `--sprint-field` if the guess is wrong.
- Confluence v2 lists only top-level comments; `atl conf comments` fetches the reply
  threads itself, so it makes one extra call per comment.

## When something does not work

`atl` is ours. It is one file, no dependencies, and it is expected to grow — if a
command is missing or wrong, **fix the file, do not fall back to raw `curl`**.

```
atl                                       the whole tool (~1600 lines)
SKILL.md                                  this file — update it in the same edit
~/.atl.json                               url / user / token / confluence_url, mode 600
```

Layout of `atl.py`, top to bottom: credentials → HTTP (`api()`, `upload()`) →
Markdown/ADF converter → helpers → Jira read → Jira write → worklogs → attachments →
sprints → boards/meta → Confluence → argparse wiring in `build_parser()` → `main()`.

Adding a command is three small edits: a `cmd_*(creds, a)` function, a block in
`build_parser()`, and a line in this file. Follow the shape of the neighbours —
compact print by default, `if a.json: return out_json(...)` first.

Debugging:

- **See what the API really returned:** `atl <cmd> --json`. Errors already come back
  unwrapped as `atl: HTTP 400 — <the real message>`; the raw body is in `ApiError`.
- **A field is missing:** the default `--fields` list is deliberately short. Try
  `atl issue KEY --full`, or `atl fields <name>` to find a custom field id, then
  `--fields` / `--field id=value`.
- **Endpoint not covered:** Jira REST v3 is at `/rest/api/3/…`, Agile at
  `/rest/agile/1.0/…`, Confluence v2 at `/api/v2/…` under `confluence_url` (a few
  Confluence things — attachments, labels-add, per-version bodies — still need the v1
  `/rest/api/…` path). `api(creds, path, params, method, body, base=...)` handles auth
  and JSON both ways; that is usually the entire diff.
- **Do not hand-build ADF.** Call `md_to_adf(text)` for writes and `adf_to_md(node)`
  for reads.
- **Verify on a throwaway project before touching a real ticket.** `atl delete` often
  returns 403 (most projects do not grant the permission), so clean up by removing
  worklogs/attachments and parking the item in `Done`.

Known gaps, none of them in daily use: Jira Service Desk (queues, SLA), Proforma
forms, watchers, versions/releases, dev-info (linked branches and PRs), batch create,
remote issue links; Confluence page move and `search_user`. Add them the same way if
they ever come up.
