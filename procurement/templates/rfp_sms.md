# RFP SMS Template

For vendors we only have a phone number for. Send **one-to-one** via QUO — never
group-message.

## Envelope

- **From**: your QUO business line (e.g. `+18135551234`)
- **To**: single vendor phone in E.164 format (`+18135550100`)

## Body (≤ 3 messages)

```
Hi {{VENDOR_NAME}} — {{COMPANY}} here. Requesting a bid for {{SCOPE}} on
{{SITE_ADDRESS}}. Bids due {{DEADLINE_DATE}}.

Plans (view-only): {{PLANS_URL}}

Reply Y to acknowledge and we'll send scope + site access details. Or
reply with your best contact email if you'd rather bid by email. Thanks!
```

## Rules

- **One recipient per send.** QUO's group-message shares one thread with all
  recipients — do not use it for RFPs.
- **Space sends.** ~30 sec between messages to different vendors to stay clear
  of carrier flagging.
- **No budget.** Same rule as email.
- **Same plans URL as the email RFP.** Sourced from the registry so email and
  SMS always match.
