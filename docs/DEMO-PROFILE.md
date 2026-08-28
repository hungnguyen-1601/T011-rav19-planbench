# The demo profile, and how to take it off again

PlanBench decides what it is allowed to do from
`PLANBENCH_DEPLOYMENT_PROFILE`. There are three answers, and the
difference between them is not cosmetic — each one settles whether one
person may approve their own work, and whether an account may hold every
capability at once.

| Profile | For | Roles | Duties |
|---|---|---|---|
| `production` | a server several people share | granted one at a time through `/admin/users` | `strict` |
| `desktop-single-user` | the packaged Windows app | the seeded account holds engineer + reviewer + admin | `relaxed` |
| `demo` | one machine, for showing the product | one `demo_owner` holds everything | `relaxed` |

**An absent variable means `production`.** A server running today has no
such line in its environment, and the reading of silence that keeps it
safe is the strict one. The desktop launcher does not rely on this: it
states its own profile in the process before any setting is read, so an
installed copy whose `.env` predates roles still behaves like the
desktop build it is.

---

## Turning the demo profile on

For a machine used to present the product. It is a change to one
already-installed copy, not a different build.

1. Close the app.
2. Open `%LOCALAPPDATA%\PlanBench\.env`.
3. Set these, keeping whatever is already there:

```
PLANBENCH_DEPLOYMENT_PROFILE=demo
PLANBENCH_SEPARATION_OF_DUTIES=relaxed
PLANBENCH_ENABLE_DEV_LOGIN=true
PLANBENCH_DEMO_OWNER_NICKNAME=admin
```

4. Start the app and sign in as usual. The account named above is
   granted `demo_owner` on that first sign-in and keyed by its immutable
   id from then on — renaming it later changes nothing.

What you get: one badge, **Demo Owner**; every menu; and a banner that
cannot be dismissed saying the deployment is running with every
capability in one pair of hands.

### Two things it refuses to do

**A second demo owner.** The role carries every capability there is, so
"there is exactly one" is a guarantee the database makes with a partial
unique index rather than one a service check makes politely. Pointing
`PLANBENCH_DEMO_OWNER_*` at a different account while the first still
holds it makes the app refuse to start — a restart is not allowed to
transfer every permission in the system quietly.

**Skipping the workflow.** A demo owner still submits, claims,
acknowledges and then approves. That is the point: the demonstration
shows the real process performed by one person, not a shortcut around
it. Self-approvals are written to the trail as `self_approve_config`,
and the exported configuration says `approval: self`, so nothing in the
record ever claims a second human looked.

---

## Taking it off before production

Do this in order. Step 2 is not optional and the server enforces it:
revoking the last account that can manage users is refused, so an
attempt to skip it fails rather than locking everybody out.

1. **Back up.** Copy `%LOCALAPPDATA%\PlanBench\planbench.db`, and export
   the trail: `GET /api/v1/admin/audit`.
2. **Give somebody real roles.** Through `/admin/users`, grant the
   packages the person actually needs — `engineer`, `reviewer`,
   `admin`, or a combination. Do this *before* step 3.
3. **Revoke `demo_owner`.** Remove the row from `user_roles`. There is
   no route for it, deliberately: a role that no administrator can grant
   is a role no administrator should be able to move.

   ```sql
   DELETE FROM user_roles WHERE role = 'demo_owner';
   ```

4. **Change the profile.**

```
PLANBENCH_DEPLOYMENT_PROFILE=production
PLANBENCH_SEPARATION_OF_DUTIES=strict
```

   and delete every `PLANBENCH_DEMO_OWNER_*` line.

5. **Start it.** A production deployment that still holds a demo owner
   **refuses to start**, and says which account. That refusal is the
   check: if the app comes up, step 3 worked.

### What is not removed, and why

The trail keeps every entry recorded under `actor_roles=demo_owner`, and
the code keeps recognising that name forever. Those entries are the
record of what was done during the demonstration; a parser that stopped
understanding the word would turn them into rows nobody can read, which
is the one thing an append-only trail may never become.

---

## Reference

- `apps/api/planbench_api/deployment.py` — the profiles, the guards, and
  what each refuses.
- `apps/desktop/planbench_desktop/provision.py` — what the launcher
  supplies when `.env` is silent.
- `contracts/CONTRACTS.md` HĐ-14 — the contract clause, where
  `demo_owner` is defined as a deployment-profile exception rather than
  a role anybody does business under.
- `tests/desktop/test_upgrade_keeps_access.py` — the regression that
  keeps an upgrade from taking somebody's access away.
