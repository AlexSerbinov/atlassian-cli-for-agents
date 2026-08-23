# atl vs mcp-atlassian — the full comparison

Measured against [mcp-atlassian](https://github.com/sooperset/mcp-atlassian) **0.21.0**
on a live Jira + Confluence Cloud site, August 2026.

This document is deliberately unflattering where it should be. mcp-atlassian is a good
project with far broader API coverage than `atl` has; the trade is coverage for cost.

---

## 1. Resource cost

| | mcp-atlassian 0.21 | atl |
|---|---|---|
| Process model | resident daemon, one **per editor session** | starts, works, exits |
| Memory, 1 session | 137 MB | 0 between calls |
| Memory, 10 sessions | ~1.4 GB | 0 |
| Cold start | once per session | ~90 ms per call |
| Dependencies | ~40 packages in a venv | none (stdlib) |
| Install size | ~90 MB venv | 60 KB, one file |
| Python | 3.10+ | 3.8+ |

The per-session multiplication is the part people miss. The daemon does not know whether
you will touch Jira today; it holds its memory either way.

## 2. Context cost

### Tool schemas

mcp-atlassian exposes **72 tools** — 49 Jira, 23 Confluence. Their docstrings and
parameter schemas total ~141 KB of text:

| File | Docstrings | Signatures |
|---|--:|--:|
| `jira.py` | 23.9 KB | 66.5 KB |
| `confluence.py` | 12.5 KB | 38.3 KB |
| **Total** | | **~141 KB ≈ 35,000 tokens** |

Clients that load every schema upfront pay all of it. Clients that defer schemas (Claude
Code 2.1+ does) pay only for what gets used — measured at ~700 tokens per tool loaded,
plus ~800 tokens for the always-present list of 72 tool names.

`atl`'s `SKILL.md` is 9 KB ≈ 2,300 tokens, loaded once, and covers all 46 commands.

### Response payloads

Same queries, same site, same day.

| Operation | `atl` | mcp-atlassian / raw JSON | Reduction |
|---|--:|--:|--:|
| search, 20 issues | 2,916 B | **13,500 B** † | **4.6×** |
| view one issue | 6,859 B | 56,296 B | 8.2× |
| read 5 comments | 5,075 B | 42,625 B | 8.4× |
| list transitions | 935 B | 14,201 B | 15.2× |
| list worklogs | 139 B | 3,297 B | 23.7× |
| list boards | 816 B | 12,432 B | 15.2× |
| list projects | 1,042 B | 26,476 B | 25.4× |
| list sprints | 1,055 B | 7,217 B | 6.8× |

† measured against mcp-atlassian directly. Other rows compare against the raw Jira REST
payload — the upper bound, since mcp-atlassian trims some fields. Real MCP figures sit
between the two columns.

**Why the gap is so wide.** Here is one row of a 20-row mcp-atlassian search result:

```json
{
  "id": "27714",
  "key": "PROJ-738",
  "summary": "User message is not delivered to manager …",
  "status": { "name": "Release branch", "category": "In Progress", "color": "yellow" },
  "issue_type": { "name": "Bug" },
  "priority": { "name": "High" },
  "assignee": {
    "display_name": "Jane Doe",
    "name": "Jane Doe",
    "email": "jane@corp.com",
    "avatar_url": "https://avatar-management--avatars.us-west-2.prod.public.atl-paas.net/557058:1a2b3c4d-0000-0000-0000-000000000000…/aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee…/48"
  }
}
```

That `avatar_url` is 200 characters, and it repeats identically on all twenty rows for
the same person. The model reads it twenty times. `atl` prints:

```
PROJ-738   Release branch Bug      Jane Doe             User message is not delivered to manager …
```

## 3. Capability

### Operations mcp-atlassian cannot do

Verified against 0.21.0 source, not inferred:

| Operation | mcp-atlassian | atl |
|---|---|---|
| Edit a worklog | ✗ — only `get_worklog` and `add_worklog` exist | `atl worklog edit` |
| Delete a worklog | ✗ same | `atl worklog rm` |
| Upload a **Jira** attachment | ✗ — the string `upload` appears 0 times in `jira.py` | `atl attach` |
| Transition **with** a comment | ✗ — fails with *"Operation value must be an Atlassian Document"* | `atl transition --comment` |
| Confluence version diff | raw XHTML | unified diff on rendered Markdown |

The transition failure is a symptom of a deeper gap: Jira REST v3 and Confluence Cloud v2
take rich text as **ADF**, a JSON tree. Without an ADF builder you cannot write a comment,
a description, or a page body. `atl` ships a Markdown ↔ ADF converter in both directions.

Note: mcp-atlassian *does* have `confluence_upload_attachment`. Only the Jira side is
missing, which is the side people actually need for screenshots on tickets.

### Operations atl does not do

`atl` implements ~35 of the 72. Missing, roughly in order of how likely you are to want them:

| Area | mcp-atlassian tools | Status in atl |
|---|---|---|
| Watchers | `add_watcher`, `remove_watcher`, `get_issue_watchers` | not implemented |
| Versions / releases | `create_version`, `batch_create_versions`, `get_project_versions` | not implemented |
| Development info | `get_issue_development_info`, `get_issues_development_info` | not implemented |
| Jira Service Desk | `get_queue_issues`, `get_service_desk_queues`, `get_service_desk_for_project`, `get_issue_sla` | not implemented |
| Proforma forms | `get_issue_proforma_forms`, `get_proforma_form_details`, `update_proforma_form_answers` | not implemented |
| Batch / misc | `batch_create_issues`, `batch_get_changelogs`, `create_remote_issue_link`, `get_project_components`, `get_field_options`, `get_issue_dates`, `get_issue_images`, `link_to_epic`, `remove_issue_link`, `get_link_types` | not implemented |
| Confluence | `move_page`, `search_user`, `get_page_views`, `get_page_diff`, `get_page_history`* | `history` and `diff` implemented; move / user search / views are not |

\* `atl conf history` and `atl conf diff` cover the equivalent ground.

### Deployment and auth

| | mcp-atlassian | atl |
|---|---|---|
| Jira/Confluence **Cloud** | ✓ | ✓ |
| **Server / Data Center** | ✓ | ✗ |
| API token | ✓ | ✓ |
| OAuth 2.0 | ✓ | ✗ |
| Personal access token (DC) | ✓ | ✗ |

Server/DC users who want the CLI approach should look at
[atlassian-skills](https://github.com/eunsanMountain/atlassian-skills), which targets
on-prem specifically.

## 4. Security

| | mcp-atlassian | atl |
|---|---|---|
| Where the token lives | server config; commonly passed as CLI flags | `~/.atl.json`, mode 600 |
| Visible in `ps aux` | **yes**, for the daemon's whole lifetime | no |
| Read into memory | for the session's duration | for ~90 ms |
| Enforced by a test | — | yes, an AST walk asserts the token is read only inside `_auth_header` |

A typical mcp-atlassian invocation looks like this in the process table:

```console
$ ps aux | grep mcp-atlassian
… mcp-atlassian --jira-token=ATATT3xFfGF0EXAMPLE-not-a-real-token-0000000000 --jira-username=you@corp.com
```

Any process running as any user on that machine can read it. This is a property of
passing secrets as arguments, not a flaw unique to mcp-atlassian — but it disappears
when there is no long-lived process.

## 5. When to pick which

**Use mcp-atlassian if:** you are on Server/Data Center, you need OAuth, or your workflow
touches Service Desk, Proforma forms, watchers, or release versions.

**Use atl if:** you are on Cloud, your workflow is issues / comments / worklogs / sprints /
pages, and you care about context budget, memory, or running many agent sessions at once.

**Use both:** nothing stops you. They read the same API with the same token.
