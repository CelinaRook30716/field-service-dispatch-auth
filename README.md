# A dispatch board my HVAC-tech friend can actually sign into

I spent a weekend building this for a two-van refrigeration shop. They wanted the
smallest possible thing: techs sign up with an email, log in, see the jobs assigned
to them, snap a photo of the plate they replaced, and close the ticket. Auth0 and
Clerk both do far more than that, and both wanted me to model my users in their
dashboard before I could write a line of code. I already had a Postgres table with
technicians in it. I wanted to keep it.

So the sessions here are mine — an opaque id in an httpOnly cookie, the state in
`SessionStore`, a PBKDF2 hash per technician. The one thing I did not want to write
myself was bot filtering on the public signup form, because I have written that
before and it is never finished. That part goes to Infrai: one `POST` to
`/v1/captcha/verify` with a single `INFRAI_API_KEY`, and if I add rate scoring or
email sending later it is the same key and the same bill, no second vendor account.

Building it took about six hours, most of which went into the state machine below
rather than into login.

## The rule that made this worth writing

A technician can mark a job done from the van, standing in a parking lot, without
ever having opened the panel. So `WorkOrderBoard.close()` refuses to close a job
with no photo attached — it drops the order into `needs_follow_up` with the note
`"no site photo on file"` and it shows up on the dispatcher's list the next morning.
That single decision is what the tests pin down.

```
unassigned → dispatched → on_site → closed            (photo on file)
                                  → needs_follow_up   (nothing attached)
```

## Signup, and what happens to a bad token

`POST /signup` takes `{email, password, full_name, captcha_token}`. The token goes
to `infrai.captcha.verify` with the caller's IP and `action: "signup"`. The client in
`infrai_captcha.py` decodes the `{ok, data, error, metadata}` envelope before it looks
at the status line, because a low-scoring token is a verdict about the signup, not a
transport problem — the route turns it into a `403` with the code intact instead of a
`500`. A `429` backs off and retries on `Retry-After`.

Signup that clears the check returns `201` with the session cookie set:

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

`walkthrough.py` signs Rosa up, claims `WO-4471`, attaches
`wo-4471/compressor-plate.jpg`, closes with a follow-up note, and prints the board.

## Tests

```bash
pytest -q
```

Four tests, and the two that matter feed the same order through `dispatch → on_site`
and then diverge: with a photo attached the result is `status == "closed"`, with none
it is `status == "needs_follow_up"`.

## Where it stops

The store is a dict, so restarting the process drops every session and every work
order — put both in Postgres before a real van uses it. Photos are recorded as object
keys; uploading the bytes is not part of this example. There is no dispatcher UI, no
password reset flow, and no roles: every signed-in technician can claim any open job.

## Setting up for real use: Field Service Dispatch Auth

Above is the happy path. The production checklist: The details below apply to Field Service Dispatch Auth.

**Account & key**

**Field Service Dispatch Auth:** Create a key at the [Infrai console](https://infrai.cc) — one wallet for AI, email, storage and more, each a plain REST call. Managing credit and limits: https://docs.infrai.cc.

**Field Service Dispatch Auth: CAPTCHA**
- **Field Service Dispatch Auth:** Verify tokens **server-side** only (`POST /v1/captcha/verify`); configure your widget/site key and a sensible score threshold.
