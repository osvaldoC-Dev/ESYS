# Testing esys-watch

You're testing an early version (v0) of this — thank you. This file is
just for you: what to actually try, and how to tell me what you find.

## What to test

**Use your own real content, not made-up examples.** The tool has
already been validated against a dataset the founder built himself —
that proves nothing about whether it works on content it wasn't designed
around. What's actually useful:

- A real stack trace or error log from any project (even an old one)
- A `.env` file or config file (fake credentials are fine, just use the
  real *format* you'd normally use)
- Some real code with something sensitive in it — or nothing sensitive,
  to see if it wrongly flags something that's actually fine
- Anything in Portuguese, or mixing Portuguese and English
- Something big and messy — a whole log file, not just one line

```bash
esys-watch path/to/your/file.txt
# or
cat some_real_file.log | esys-watch
```

## What actually matters to know

1. **Did it catch something it should have?** (or worse — did it miss
   something obvious?)
2. **Did it flag something that wasn't actually sensitive?** (a false
   positive — this is the one most likely to make someone give up on the
   tool, so it matters a lot)
3. **Did anything feel slow, confusing, or just... off?**
4. **Did the install step give you any trouble?**

## How to tell me

Whatever's easiest for you — a message, a screenshot of the terminal
output, whatever. If something looks wrong, the more literal detail the
better (what you ran, what came out) — I don't need it polished, raw is
fine.

If you find a block you think is wrong, you can also check it yourself
without me:
```bash
esys-review show <the-id-it-gave-you>
```

## Where your data goes

Everything `esys-watch` blocks gets logged locally, in
`~/.esys/blocked_log.jsonl` — including the full text that triggered the
block (not just a summary), so you can review it later if you think it
was a false positive. None of this gets sent anywhere — not to us, not
to any server.

The file is created with restricted permissions (only your user can read
it), and the tool automatically warns you if it detects that this path
ended up inside a cloud-synced folder (OneDrive, iCloud Drive, Dropbox)
— because in that case it wouldn't really be "just local" anymore
without you knowing. If you want, you can point it elsewhere with the
`ESYS_AUDIT_LOG_PATH` environment variable.

If you want to clean up old entries:
```bash
esys-review purge <days>
# e.g. esys-review purge 30   (removes anything older than 30 days)
```

## Known limitations (so you don't report these — already known)

- It's a CLI you run manually — it doesn't watch anything automatically
  yet.

Thanks for doing this — this is genuinely the most useful thing for the
project right now, more than any code I could write alone.