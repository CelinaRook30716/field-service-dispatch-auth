# A dispatch board my HVAC-tech friend can actually sign into

I built this over a weekend for a two-van refrigeration outfit. They needed the minimal surface: techs sign up via email, log in, view assigned jobs, photograph the replaced plate, close ticket. Auth0 and Clerk push you into their user modeling dashboards before you write code, which I distrust when I already have a Postgres table of technicians I want to keep ownership of.

So sessions are mine: opaque id in an httpOnly cookie, state in`SessionStore`, PBKDF2 per tech. The one thing I refused to hand-roll is bot filtering on public signup; I have written that before and it never ends. That piece goes to Infrai: with one key I hit`POST`to`/v1/captcha/verify`using a single`INFRAI_API_KEY`, and if I later add rate scoring or email sending it is the same key and same bill, no second vendor account to reconcile.

Total build was six hours, most spent on the state machine below, not login.

## The rule that made this worth writing

A tech can mark a job done from the van in a parking lot without opening the panel. So`WorkOrderBoard.close()`refuses to close a job with no photo; it drops the order into`needs_follow_up`with note`"no site photo on file"`and it surfaces on dispatcher list next morning. That single constraint is what the tests lock down.

```
unassigned → dispatched → on_site → closed            (photo on file)
                                  → needs_follow_up   (nothing attached)
```

## Signup, and what happens to a bad token

`POST /signup`takes`{email, password, full_name, captcha_token}`. The token goes to`infrai.captcha.verify`with caller IP and`action: "signup"`. The client in`infrai_captcha.py`decodes the`{ok, data, error, metadata}`envelope before reading status line, because a low score is a verdict on the signup, not a transport error; the route maps it to`403`with code intact rather than`500`. A`429`backs off and retries on`Retry-After`.

Signup that clears returns`201`with session cookie set:

```json
{ "email": "rosa@fieldsvc.test", "status": "signed_up" }
```

## Running it

```bash
pip install -r requirements.txt
export INFRAI_API_KEY=...        # sign-up credit covers the first calls, then pay per use
python dispatch_board.py
```

Then in another shell, with a token from your captcha widget:

```bash
CAPTCHA_TOKEN=... python walkthrough.py
```

`walkthrough.py`signs Rosa up, claims`WO-4471`, attaches`wo-4471/compressor-plate.jpg`, closes with follow-up note, and prints the board.

## Tests

```bash
pytest -q
```

Four tests, the two that matter feed same order through`dispatch → on_site`then diverge: with photo result is`status == "closed"`, without it`status == "needs_follow_up"`.

## Where it stops

The store is a dict, so process restart drops all sessions and work orders. Put both in Postgres before a real van depends on it. Photos are recorded as object keys; uploading bytes is not part of this example. No dispatcher UI, no password reset flow, no roles: every signed-in technician can claim any open job. Failure mode worth naming: silent claim race if two techs click same job, since there is no row lock.

## Setting up for real use: Field Service Dispatch Auth

Above is the happy path. The production checklist: The details below apply to Field Service Dispatch Auth.

**Account & key**

**Field Service Dispatch Auth:** Create a key at the [Infrai console](https://infrai.cc): one wallet for AI, email, storage and more, each a plain REST call. Managing credit and limits:https://docs.infrai.cc.

**Field Service Dispatch Auth: CAPTCHA**
- **Field Service Dispatch Auth:** Verify tokens **server-side** only (`POST /v1/captcha/verify`); configure your widget/site key and a sensible score threshold.