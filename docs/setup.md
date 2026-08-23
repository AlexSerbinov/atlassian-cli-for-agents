# Setup

Two things to get right: **getting a token**, and **where you keep it**. The second one
matters more than people expect — an Atlassian API token is a bearer credential that can
do everything your account can, in every project you can see.

---

## 1. Create an API token

Go to **[id.atlassian.com/manage-profile/security/api-tokens](https://id.atlassian.com/manage-profile/security/api-tokens)**

Or navigate there by hand: click your avatar (top right of any Atlassian page) →
**Manage account** → **Security** tab → **Create and manage API tokens**.

Then:

1. Click **Create API token** — the plain one, not "Create API token with scopes"
   (see [scoped tokens](#scoped-tokens) below if you want least privilege).
2. **Label** it something you will recognise in six months: `atl on my laptop`.
   The label is the only way to tell tokens apart when you revoke one later.
3. **Expiry** — 1 day to 1 year, default 1 year. Shorter is better; you can always
   make another. Atlassian will email you before it lapses.
4. **Copy it immediately.** It is shown exactly once and cannot be recovered. If you
   lose it, revoke it and make a new one.

> **The token is not your password**, and it does not carry your 2FA. Anyone holding it
> can read and write everything your account can, until it expires or you revoke it.
> Revoke from the same page — a revoked token stops working within seconds.

Official docs:
[Manage API tokens for your Atlassian account](https://support.atlassian.com/atlassian-account/docs/manage-api-tokens-for-your-atlassian-account/)

---

## 2. Point `atl` at it

```bash
atl init
```

It asks for three things — site URL, account email, and where to keep the token — then
writes `~/.atl.json` with mode `600` and makes one authenticated call to prove it works.

```console
$ atl me
Jane Doe <jane@acme.com>
accountId: 557058:1a2b3c4d-…
site:      https://acme.atlassian.net
```

The **email must be the one the token belongs to.** Atlassian's Basic auth is
`email:token`, and a mismatch returns a confusing `401` rather than a useful error.

---

## 3. Where to keep the token

`atl` reads a token from four places, in this order. The first one that yields a value wins.

| # | Source | Good for |
|---|--------|----------|
| 1 | `token` in `~/.atl.json` | one laptop, simplest thing that works |
| 2 | `ATL_TOKEN` environment variable | CI, containers, one-off shells |
| 3 | `token_command` in `~/.atl.json` | **password managers — the recommended setup** |
| 4 | an existing `atlassian` entry in `~/.claude.json` | migrating off mcp-atlassian |

### Recommended: `token_command`

Instead of storing the secret, store **a command that prints it**. `atl` runs it, reads
stdout, and uses the result. The token never sits in a file `atl` owns, never appears in
a command line, and `atl` never learns where it actually lives.

```json
{
  "url": "https://acme.atlassian.net",
  "user": "jane@acme.com",
  "token_command": "security find-generic-password -s atl -a jane@acme.com -w"
}
```

Recipes for the common managers:

<table>
<tr><th>Manager</th><th>Store it once</th><th><code>token_command</code></th></tr>
<tr>
<td><b>macOS Keychain</b></td>
<td><code>security add-generic-password -U -s atl -a jane@acme.com -w 'TOKEN'</code></td>
<td><code>security find-generic-password -s atl -a jane@acme.com -w</code></td>
</tr>
<tr>
<td><b>GNOME Keyring</b><br/>(libsecret)</td>
<td><code>secret-tool store --label=atl service atl account jane@acme.com</code></td>
<td><code>secret-tool lookup service atl account jane@acme.com</code></td>
</tr>
<tr>
<td><b>1Password</b></td>
<td>add an item in the app</td>
<td><code>op read op://Private/atl/credential</code></td>
</tr>
<tr>
<td><b>pass</b> / <b>gopass</b></td>
<td><code>pass insert atlassian/api-token</code></td>
<td><code>pass show atlassian/api-token</code></td>
</tr>
<tr>
<td><b>HashiCorp Vault</b></td>
<td><code>vault kv put secret/atl token=TOKEN</code></td>
<td><code>vault kv get -field=token secret/atl</code></td>
</tr>
</table>

`atl init` offers to write the keychain recipe for your platform automatically.

> One honest caveat on the "store it once" column: `security add-generic-password -w TOKEN`
> puts the token in that process's arguments for the fraction of a second it runs, so it is
> briefly visible in `ps`. `secret-tool store` and `pass insert` read from stdin and do not
> have this problem. On macOS you can sidestep it entirely by adding the item by hand in
> **Keychain Access** (service `atl`, account = your email).

### Simple: the config file

```json
{
  "url": "https://acme.atlassian.net",
  "user": "jane@acme.com",
  "token": "ATATT3xFfGF0…"
}
```

`atl init` writes it as mode `600` — owner read/write only. `atl` re-checks that on every
run and warns on stderr if the file has become readable by others:

```
atl: warning — /home/jane/.atl.json is readable by other users (mode 0644). Run: chmod 600 ~/.atl.json
```

Plain-text on disk is a real trade-off, and it is the same one `~/.netrc`, `~/.aws/credentials`
and `~/.npmrc` make. It is fine on a laptop with full-disk encryption and one user. It is not
fine on a shared box, in a synced folder, or anywhere a backup tool will pick it up.

### CI and containers

```bash
export ATL_URL=https://acme.atlassian.net
export ATL_USER=ci-bot@acme.com
export ATL_TOKEN=…       # from your CI secret store, never committed
```

Use a [service account](https://support.atlassian.com/user-management/docs/manage-api-tokens-for-service-accounts/)
rather than a person's token, so the pipeline does not break when someone leaves.

---

## Rules that apply whichever you pick

- **Never commit it.** This repo's `.gitignore` already excludes `.atl.json`, `*.token`
  and `.env`, but check your own repos too.
- **Never paste it into a chat, an issue, or a prompt.** If a token has ever been shown to
  anything you do not control, revoke it — rotation is free, cleanup is not.
- **One token per machine.** Then losing a laptop means revoking one line, not re-keying
  everywhere.
- **Set a real expiry.** A year is the default, not a recommendation.
- **Revoke on the way out.** Same page you created it on.

If a token leaks: revoke it first, then investigate. Atlassian audit logs are under
**Settings → Audit log** on the admin side.

---

## Scoped tokens

Atlassian also issues **scoped** tokens, which carry only the permissions you tick rather
than everything your account can do. They are the better choice for anything automated.

Two things to know before you switch:

1. **Scoped tokens only work against `api.atlassian.com`**, never against
   `https://yoursite.atlassian.net`. `atl` handles this — give it your site's cloud id and
   it routes API calls through the gateway while keeping human-facing links on the site:

   ```bash
   atl init --scoped     # reads the cloud id from your site automatically
   ```

   which stores:

   ```json
   { "url": "https://acme.atlassian.net", "user": "…", "cloud_id": "95c15bb3-…" }
   ```

   You can look the cloud id up yourself at
   `https://yoursite.atlassian.net/_edge/tenant_info` — it is public and needs no auth.

2. **Scopes cannot be edited after creation.** Miss one and you make a new token.

Scopes covering what `atl` does:

| Area | Scopes |
|---|---|
| Read issues, search, boards, sprints | `read:jira-work`, `read:jira-user` |
| Create/edit issues, comments, worklogs, attachments, transitions | `write:jira-work` |
| Sprint writes (`atl sprint add/create/update`) | `manage:jira-project` |
| Read Confluence pages, spaces, comments | `read:confluence-content.all`, `read:confluence-space.summary` |
| Create/edit pages, comments, labels | `write:confluence-content` |
| Upload page attachments | `write:confluence-file` |

Full lists: [Jira scopes](https://developer.atlassian.com/cloud/jira/platform/scopes-for-oauth-2-3LO-and-forge-apps/) ·
[Confluence scopes](https://developer.atlassian.com/cloud/confluence/scopes-for-oauth-2-3LO-and-forge-apps/) ·
[Scoped API tokens](https://support.atlassian.com/confluence/kb/scoped-api-tokens-in-confluence-cloud/)

> The gateway routing is verified end to end against a live site. The scope list above is
> mapped from the endpoints `atl` calls and is a starting point rather than a tested
> minimum — if you find one is missing or unnecessary, please open an issue.

---

## Troubleshooting

| Symptom | Cause |
|---|---|
| `401 Unauthorized` | Wrong email, truncated token, or it expired. Tokens are long — make sure the whole thing was copied. |
| `401` right after switching to a scoped token | Scoped tokens need `cloud_id`; run `atl init --scoped`. |
| `403` on a specific action | The token works; your **account** lacks that permission in that project. `atl delete` hits this most. |
| `404` on an issue you can see in the browser | Different site, or the browser session is a different account. Check `atl me`. |
| `token_command exited 1` | The manager is locked or the entry name is wrong. Run the command by hand. |
| `token_command produced no output` | Command succeeded but printed nothing — usually a typo'd entry name. |
| Warning about file permissions | `chmod 600 ~/.atl.json`. |

Check what `atl` resolved without revealing anything:

```bash
atl me                                          # identity + which site
python3 -c "import json;d=json.load(open('$HOME/.atl.json'));print({k:('***' if k=='token' else v) for k,v in d.items()})"
```
