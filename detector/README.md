# esys-watch

Catch secrets and PII before you paste them into ChatGPT, Cursor, Copilot,
or any AI tool — locally, with zero setup, zero account, zero data ever
leaving your machine.
$ echo "my key is AKIAIQK2919AHEJ8CX9J" | esys-watch
ESYS WATCH

1 finding(s):

[secret] aws_access_key -> AK****************9J (pos 10-30)

Decisão: BLOCK

NÃO cola isto num prompt de IA contém dados sensíveis que não
deviam sair da tua máquina.
## Why

Every team using AI is leaking data through it and most don't know it
yet — a stack trace with an AWS key in it, a support ticket with a
customer's card number, a log line with a database password. `esys-watch`
is the first line of defense: a local check, before anything gets pasted
anywhere.

## What it catches

- **Secrets**: AWS/GCP/Azure keys, GitHub tokens, JWTs, OAuth tokens
  (Stripe, SendGrid, Slack, Twilio), DB connection strings, SSH keys —
  including base64-encoded and split/obfuscated variants
- **PII, across 4 regions**: emails, phones, credit cards, US SSN,
  Angola national ID, Brazil CPF/CNPJ (checksum-validated), South Africa
  national ID (checksum-validated), Nigeria NIN, EU IBAN
  (checksum-validated)

Validated against a 320-case labeled dataset: **100% recall, 0% false
positives.** See the root `README.md` for the full methodology.

## Install

```bash
git clone https://github.com/osvaldoC-Dev/ESYS.git
cd ESYS/detector
pip install -e .
```

No external dependencies — pure Python standard library. Works offline.

## Use

```bash
esys-watch path/to/file.txt          # scan a file
cat something.log | esys-watch       # or pipe anything into it
echo "some text" | esys-watch
```

Exit codes (useful for scripting / git hooks / CI): `0` = clean,
`1` = blocked (secret or high-sensitivity PII found), `2` = redactable
PII found (a safe version is printed for you to copy).

## Review past blocks

Every block gets logged locally (never sent anywhere). If you ever need
to check what got flagged, or decide something was a false positive:

```bash
esys-review              # list pending blocks
esys-review show <id>    # see the full original content
esys-review approve <id> # mark as reviewed / false positive
```

## What this is *not* (yet)

This is v0 — it proves the core detection works, reused from the same
engine that powers the full ESYS gateway. It doesn't yet watch your
clipboard automatically, and it's not published to PyPI (you install
from source). Both are on the roadmap once this gets real usage.
