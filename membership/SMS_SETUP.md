# Text reminders — setup

The site is ready to text members before their Dot meets. It stays **off** until the
Twilio settings below are added, so nothing can be sent by accident.

## What it does

- About 3 hours before a Dot meets, each member with a seat in that Dot (and its
  Ambassador) gets one text: `The Dot Com Experience: Midtown Dot meets today at 7:00 PM
  at 1200 K St. Reply STOP to opt out.`
- Only members who ticked "Text me a reminder before my Dot meets", have a phone number,
  and are in good standing are texted. One text per member per meeting.
- Never before 8am or after 9pm in the Dot's time zone. A reminder that would fall
  earlier waits until 8am; a meeting before 8am is announced at 6pm the evening before.
- When a member opts in, they get one confirmation text. Replying STOP switches their
  reminders off on the site too; START switches them back on.
- Every text is recorded under **Admin → Text messages → Sms logs**.

## Step 1 — Twilio account and carrier registration (you; allow days to weeks)

US carriers block texts from unregistered senders, so this step cannot be skipped.

1. Create an account at twilio.com in the name of **WC Services LLC** and upgrade it from trial.
2. Buy a phone number with SMS capability.
3. Register for **A2P 10DLC** (Twilio Console → Messaging → Regulatory Compliance):
   - **Brand**: WC Services LLC, its EIN and business address, website `https://www.thedotx.com`.
   - **Campaign**: use case "Account Notification" (or "Low Volume Mixed").
   - Twilio shows the current registration fees before you submit.
4. Wait for approval. Texts sent before approval are filtered by carriers.

Answers Twilio's campaign form will ask for:

| Question | Answer |
| --- | --- |
| Campaign description | Reminders to paying members of The Dot Com Experience about their weekly in-person group meeting ("Dot"): day, time and place. |
| How do people opt in? | Signed-in members tick an unchecked box, "Text me a reminder before my Dot meets", on their profile page at members.thedotx.com/accounts/profile/edit/. The box states message frequency, that message and data rates may apply, and STOP/HELP. Consent is optional and not a condition of membership. |
| Sample message 1 | The Dot Com Experience: Midtown Dot meets today at 7:00 PM at 1200 K St. Reply STOP to opt out. |
| Sample message 2 | The Dot Com Experience: You're signed up for Dot reminders, about 1 msg/week. Msg & data rates may apply. Reply HELP for help, STOP to opt out. |
| Opt-out / help keywords | STOP, HELP |
| Privacy policy / terms | https://www.thedotx.com/privacy · https://www.thedotx.com/terms |

## Step 2 — Messaging Service (Twilio Console)

1. Messaging → Services → create one, add your number to its sender pool, attach the approved campaign.
2. In the service's **Integration** settings, set "Send a webhook" for incoming messages to
   `https://members.thedotx.com/sms/inbound/` (HTTP POST).
3. Copy the Messaging Service SID (`MG…`).

## Step 3 — Heroku config vars (app `thedotx-members`)

| Key | Value |
| --- | --- |
| `TWILIO_ACCOUNT_SID` | starts with `AC…` (Twilio Console home) |
| `TWILIO_AUTH_TOKEN` | the Auth Token beside it — a secret; never share it |
| `TWILIO_MESSAGING_SERVICE_SID` | `MG…` from step 2 |

Optional: `SMS_REMINDER_HOURS_BEFORE` (default `3`).

## Step 4 — Run the reminder job (Heroku Scheduler)

1. `thedotx-members` → Resources → Add-ons → add **Heroku Scheduler**.
2. Open it → Create job → every 10 minutes → command:
   `python manage.py send_dot_reminders`

Running it often is safe: nobody is texted twice for the same meeting.

## Step 5 — Set each Dot's schedule

Admin → Dots → open a Dot → set **Meeting night** (e.g. `Tuesday`), **Meeting time**
(e.g. `7:00 PM`) and **Time zone**, and add its members under "Dot memberships". The Dots
list shows when each Dot's next reminder goes out.

## Step 6 — Test

Admin → Profiles → tick your own profile (opted in, with your phone) → action
**"Send a test text to selected"**. Then reply STOP from your phone and confirm the
"Text me a reminder" box on your profile is now unticked.
