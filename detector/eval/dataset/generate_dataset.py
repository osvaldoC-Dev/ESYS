"""
ESYS V1 Baseline Evaluation Dataset Generator
-----------------------------------------------
Produces a ~300 case ground-truth corpus for evaluating the outbound
detector pipeline (secrets + PII) and policy engine against the
locked go/no-go criteria:

  - Severity-weighted recall (weights fixed below, never re-tuned post-hoc)
  - False positive rate on clean/near-miss + code control set
  - Decision correctness (independent of finding correctness)

All secret/PII values are SYNTHETIC. No real credentials or real
personal data appear anywhere in this dataset. Formats are
structurally valid (correct prefixes, lengths, checksums where
applicable) but values are randomly generated and inert.

Severity weights (fixed, operational, not re-tunable after results come in):
  aws_access_key      5
  gcp_service_account 5
  azure_key           5
  db_connection_string 5
  github_token        4
  jwt                 4
  oauth_token         4
  email               2
  phone               2
  ssn                 2
  national_id         2
  credit_card         3
  structured_pii_json 3
  structured_pii_csv  3
  structured_pii_log  3
"""

import json
import random
import string
import base64
import uuid
import hashlib

random.seed(42)  # deterministic dataset generation

SEVERITY_WEIGHTS = {
    "aws_access_key": 5,
    "gcp_service_account": 5,
    "azure_key": 5,
    "db_connection_string": 5,
    "github_token": 4,
    "jwt": 4,
    "oauth_token": 4,
    "ssh_private_key": 5,
    "email": 2,
    "phone": 2,
    "ssn": 2,
    "national_id": 2,
    "credit_card": 3,
    "structured_pii_json": 3,
    "structured_pii_csv": 3,
    "structured_pii_log": 3,
    "source_code": 0,       # not a detection target, control group only
    "clean_near_miss": 0,   # not a detection target, FP control group only
}

cases = []
case_counter = 1

def new_case_id():
    global case_counter
    cid = f"baseline_{case_counter:04d}"
    case_counter += 1
    return cid

def rand_alnum(n, alphabet=string.ascii_uppercase + string.digits):
    return ''.join(random.choice(alphabet) for _ in range(n))

def rand_hex(n):
    return ''.join(random.choice("0123456789abcdef") for _ in range(n))

def make_jwt():
    header = base64.urlsafe_b64encode(json.dumps({"alg":"HS256","typ":"JWT"}).encode()).decode().rstrip("=")
    payload = base64.urlsafe_b64encode(json.dumps({"sub":str(uuid.uuid4()),"iat":1710000000}).encode()).decode().rstrip("=")
    sig = base64.urlsafe_b64encode(hashlib.sha256(rand_alnum(16).encode()).digest()).decode().rstrip("=")
    return f"{header}.{payload}.{sig}"

def add_case(category, subtype, prompt_text, expected_findings, expected_decision,
             difficulty, source, prompt_context, obfuscation="none", notes=""):
    cases.append({
        "case_id": new_case_id(),
        "category": category,
        "subtype": subtype,
        "severity_weight": SEVERITY_WEIGHTS.get(subtype, 0),
        "prompt_text": prompt_text,
        "prompt_context": prompt_context,
        "expected_findings": expected_findings,
        "expected_decision": expected_decision,
        "difficulty": difficulty,
        "obfuscation": obfuscation,
        "source": source,
        "notes": notes,
    })

def offset(text, needle):
    i = text.find(needle)
    return {"offset_start": i, "offset_end": i + len(needle)}

# -------------------------------------------------------------------
# 1. Cloud / infra secrets (60 cases) - weight 5, highest priority recall
# -------------------------------------------------------------------

# AWS access keys (trivial + realistic + obfuscated)
for i in range(15):
    key = "AKIA" + rand_alnum(16)
    text = f"Hey can you help debug this deploy script:\naws_access_key_id = {key}\naws_secret_access_key = {rand_alnum(40)}\nregion = us-east-1"
    add_case("secret", "aws_access_key", text, [{"category":"secret","subtype":"aws_access_key", **offset(text, key)}],
              "BLOCK", "trivial" if i < 8 else "realistic", "synthetic", "code_block",
              notes="standard AKIA-prefixed key in config block")

for i in range(10):
    key = "AKIA" + rand_alnum(16)
    # obfuscation: split across two string concatenations
    part1, part2 = key[:10], key[10:]
    text = f"const k = \"{part1}\" + \"{part2}\";\nconst secret = process.env.AWS_SECRET;"
    add_case("secret", "aws_access_key", text, [{"category":"secret","subtype":"aws_access_key","offset_start":text.find(part1),"offset_end":text.find(part2)+len(part2)}],
              "BLOCK", "obfuscated", "synthetic", "code_block", obfuscation="string_concatenation",
              notes="key split across two adjacent string literals")

for i in range(10):
    key = "AKIA" + rand_alnum(16)
    b64 = base64.b64encode(key.encode()).decode()
    text = f"Here's the encoded config blob: {b64}\nCan you decode and check if this is valid?"
    add_case("secret", "aws_access_key", text, [{"category":"secret","subtype":"aws_access_key", **offset(text, b64)}],
              "BLOCK", "obfuscated", "synthetic", "raw_paste", obfuscation="base64",
              notes="base64-encoded AWS key; tests entropy/decode-then-scan detector path")

# GCP service account JSON
for i in range(8):
    sa = {
        "type": "service_account",
        "project_id": f"proj-{rand_alnum(6).lower()}",
        "private_key_id": rand_hex(40),
        "private_key": "-----BEGIN PRIVATE KEY-----\n" + rand_alnum(200) + "\n-----END PRIVATE KEY-----\n",
        "client_email": f"svc-{rand_alnum(6).lower()}@proj.iam.gserviceaccount.com"
    }
    text = f"Can you validate this service account JSON?\n{json.dumps(sa, indent=2)}"
    add_case("secret", "gcp_service_account", text,
              [{"category":"secret","subtype":"gcp_service_account", **offset(text, "-----BEGIN PRIVATE KEY-----")}],
              "BLOCK", "trivial" if i < 5 else "realistic", "synthetic", "json_payload",
              notes="full GCP service account key JSON blob")

# Azure keys
for i in range(8):
    key = base64.b64encode(rand_alnum(32).encode()).decode()
    text = f"AzureWebJobsStorage=DefaultEndpointsProtocol=https;AccountName=mystorageacct;AccountKey={key};EndpointSuffix=core.windows.net"
    add_case("secret", "azure_key", text, [{"category":"secret","subtype":"azure_key", **offset(text, key)}],
              "BLOCK", "trivial" if i < 5 else "realistic", "synthetic", "raw_paste",
              notes="Azure storage account key in connection string form")

# DB connection strings
for i in range(19):
    dbtype = random.choice(["postgres", "mysql", "mongodb"])
    user = rand_alnum(6).lower()
    pw = rand_alnum(14)
    host = f"{rand_alnum(5).lower()}.rds.amazonaws.com"
    if dbtype == "mongodb":
        conn = f"mongodb+srv://{user}:{pw}@{host}/proddb?retryWrites=true"
    else:
        conn = f"{dbtype}://{user}:{pw}@{host}:5432/proddb"
    text = f"My connection keeps timing out, here's my config:\nDATABASE_URL={conn}\nPool size: 10"
    add_case("secret", "db_connection_string", text, [{"category":"secret","subtype":"db_connection_string", **offset(text, conn)}],
              "BLOCK", "trivial" if i < 12 else "realistic", "synthetic", "raw_paste",
              notes=f"{dbtype} connection string with embedded credentials")

# -------------------------------------------------------------------
# 2. Tokens: GitHub / JWT / OAuth (50 cases) - weight 4
# -------------------------------------------------------------------

for i in range(18):
    token = "ghp_" + rand_alnum(36, string.ascii_letters + string.digits)
    text = f"git remote set-url origin https://{token}@github.com/myorg/myrepo.git"
    add_case("secret", "github_token", text, [{"category":"secret","subtype":"github_token", **offset(text, token)}],
              "BLOCK", "trivial" if i < 10 else "realistic", "synthetic", "code_block",
              notes="GitHub PAT embedded in git remote URL")

for i in range(18):
    jwt = make_jwt()
    text = f"Authorization: Bearer {jwt}\n\nCan you tell me why this request returns 401?"
    add_case("secret", "jwt", text, [{"category":"secret","subtype":"jwt", **offset(text, jwt)}],
              "BLOCK", "trivial" if i < 10 else "realistic", "synthetic", "raw_paste",
              notes="JWT bearer token in Authorization header")

for i in range(14):
    token = rand_alnum(32, string.ascii_letters + string.digits)
    provider = random.choice(["slack", "stripe", "sendgrid", "twilio"])
    prefix = {"slack": "xoxb-", "stripe": "sk_live_", "sendgrid": "SG.", "twilio": "SK"}[provider]
    full = prefix + token
    text = f"Testing the {provider} integration with key: {full}\nGetting a 403, any ideas?"
    add_case("secret", "oauth_token", text, [{"category":"secret","subtype":"oauth_token", **offset(text, full)}],
              "BLOCK", "trivial" if i < 8 else "realistic", "synthetic", "chat_turn",
              notes=f"{provider}-style API token with vendor prefix")

# -------------------------------------------------------------------
# 3. SSH private keys (10 cases) - weight 5
# -------------------------------------------------------------------
for i in range(10):
    body = "\n".join(rand_alnum(64) for _ in range(6))
    text = f"-----BEGIN OPENSSH PRIVATE KEY-----\n{body}\n-----END OPENSSH PRIVATE KEY-----\n\nCan you help me fix permissions on this?"
    add_case("secret", "ssh_private_key", text, [{"category":"secret","subtype":"ssh_private_key", **offset(text, "-----BEGIN OPENSSH PRIVATE KEY-----")}],
              "BLOCK", "trivial" if i < 6 else "realistic", "synthetic", "raw_paste",
              notes="PEM-format SSH private key block")

# -------------------------------------------------------------------
# 4. PII - simple (60 cases) - weight 2
# -------------------------------------------------------------------
first_names = ["Maria","Joao","Ana","Carlos","Sofia","Miguel","Ines","Rui","Beatriz","Tiago"]
last_names = ["Silva","Santos","Ferreira","Pereira","Costa","Rodrigues","Martins","Gomes"]

for i in range(20):
    email = f"{random.choice(first_names).lower()}.{random.choice(last_names).lower()}{random.randint(1,99)}@{random.choice(['gmail.com','outlook.com','yahoo.com','company.com'])}"
    text = f"Please send the invoice to {email} once it's ready, and cc finance@ourcompany.com"
    add_case("pii", "email", text, [{"category":"pii","subtype":"email", **offset(text, email)}],
              "REDACT", "trivial", "synthetic", "chat_turn",
              notes="customer email in casual request")

for i in range(20):
    phone = f"+244 9{random.randint(10,99)} {random.randint(100,999)} {random.randint(100,999)}"
    text = f"Client called from {phone}, wants a callback about the order tomorrow morning."
    add_case("pii", "phone", text, [{"category":"pii","subtype":"phone", **offset(text, phone)}],
              "REDACT", "trivial", "synthetic", "chat_turn",
              notes="Angolan-format phone number")

for i in range(10):
    ssn = f"{random.randint(100,999)}-{random.randint(10,99)}-{random.randint(1000,9999)}"
    text = f"For the background check form, applicant SSN is {ssn}, DOB 1990-04-12."
    add_case("pii", "ssn", text, [{"category":"pii","subtype":"ssn", **offset(text, ssn)}],
              "BLOCK", "trivial", "synthetic", "chat_turn",
              notes="US-format SSN")

for i in range(10):
    nid = f"{rand_alnum(9, string.digits)}{random.choice(string.ascii_uppercase)}{random.choice(string.ascii_uppercase)}{random.randint(10,50)}"
    text = f"Client national ID for the contract: {nid}. Please attach to the file."
    add_case("pii", "national_id", text, [{"category":"pii","subtype":"national_id", **offset(text, nid)}],
              "BLOCK", "realistic", "synthetic", "chat_turn",
              notes="Angolan BI-style national ID format")

# -------------------------------------------------------------------
# 5. PII - structured (30 cases) - weight 3
# -------------------------------------------------------------------
for i in range(10):
    row = {"name": f"{random.choice(first_names)} {random.choice(last_names)}",
           "email": f"user{random.randint(100,999)}@example.com",
           "card": f"4{rand_alnum(15, string.digits)}"}
    text = f"Here's a sample customer record from our export, does this JSON schema look right?\n{json.dumps(row, indent=2)}"
    add_case("pii", "structured_pii_json", text,
              [{"category":"pii","subtype":"credit_card", **offset(text, row["card"])},
               {"category":"pii","subtype":"email", **offset(text, row["email"])}],
              "BLOCK", "realistic", "synthetic", "json_payload",
              notes="customer record JSON with nested PII fields")

for i in range(10):
    header = "id,name,email,phone"
    row = f"{i+1},{random.choice(first_names)} {random.choice(last_names)},user{i}@example.com,+244911{random.randint(100000,999999)}"
    text = f"CSV export sample:\n{header}\n{row}\n\nCan you write a parser for this format?"
    add_case("pii", "structured_pii_csv", text,
              [{"category":"pii","subtype":"email", **offset(text, row.split(',')[2])}],
              "BLOCK", "realistic", "synthetic", "json_payload",
              notes="CSV row with embedded PII, tests non-JSON structured extraction")

for i in range(10):
    ip = f"10.{random.randint(0,255)}.{random.randint(0,255)}.{random.randint(0,255)}"
    email = f"admin{random.randint(1,99)}@internal.corp"
    log = f"[2026-07-05 10:22:31] INFO user_login user={email} ip={ip} status=200"
    text = f"Getting weird behavior in prod, here's the log line:\n{log}\nAny idea why this keeps repeating?"
    add_case("pii", "structured_pii_log", text,
              [{"category":"pii","subtype":"email", **offset(text, email)}],
              "REDACT", "realistic", "synthetic", "log_dump",
              notes="application log line with embedded email, tests log-format extraction")

# -------------------------------------------------------------------
# 6. Non-English PII (20 cases)
# -------------------------------------------------------------------
pt_names = ["Manuel Kiala", "Domingas Chissano", "Eduardo Bumba", "Nzinga Vunge"]
for i in range(10):
    email = f"{random.choice(['manuel','domingas','eduardo','nzinga'])}.{rand_alnum(4).lower()}@empresa.co.ao"
    text = f"Por favor envie a fatura para {email} antes de sexta-feira, obrigado."
    add_case("pii", "email", text, [{"category":"pii","subtype":"email", **offset(text, email)}],
              "REDACT", "realistic", "synthetic", "chat_turn",
              notes="Portuguese-language prompt, tests non-English NER coverage")

for i in range(10):
    name = random.choice(pt_names)
    phone = f"+244 9{random.randint(10,99)} {random.randint(100,999)} {random.randint(100,999)}"
    text = f"O cliente {name} ligou do número {phone}, precisa de uma resposta urgente sobre o pedido."
    add_case("pii", "phone", text, [{"category":"pii","subtype":"phone", **offset(text, phone)}],
              "REDACT", "realistic", "synthetic", "chat_turn",
              notes="Portuguese-language prompt with name + phone, tests multilingual NER")

# -------------------------------------------------------------------
# 7. Source code / stack traces - FALSE POSITIVE CONTROL GROUP (30 cases)
#    Goal: these should generally NOT block. Excluded from recall scoring,
#    included only in false-positive-rate scoring.
# -------------------------------------------------------------------
code_snippets = [
    "def calculate_total(items):\n    return sum(i.price * i.qty for i in items)",
    "SELECT * FROM orders WHERE customer_id = ? AND status = 'pending';",
    "public class OrderService {\n    private final Repository repo;\n    public OrderService(Repository r) { this.repo = r; }\n}",
    "const uuid = crypto.randomUUID();\nconsole.log('Generated session:', uuid);",
    "Traceback (most recent call last):\n  File \"app.py\", line 42, in <module>\n    result = process(data)\nKeyError: 'total'",
    "import numpy as np\narr = np.array([1,2,3])\nprint(arr.mean())",
    "func main() {\n    fmt.Println(\"hello world\")\n}",
    "git log --oneline -n 10",
    "docker run -p 8080:8080 myimage:latest",
    "npm install express --save",
]
for i in range(20):
    snippet = code_snippets[i % len(code_snippets)]
    text = f"Can you review this code and suggest improvements?\n```\n{snippet}\n```"
    add_case("source_code", "source_code", text, [], "ALLOW", "realistic", "synthetic", "code_block",
              notes="ordinary code paste, should not trigger secret/PII detectors")

for i in range(10):
    trace_id = str(uuid.uuid4())
    text = f"Getting this error, trace id {trace_id}:\nTraceback (most recent call last):\n  File \"main.py\", line 10, in <module>\n    raise ValueError('bad input')\nValueError: bad input"
    add_case("source_code", "source_code", text, [], "ALLOW", "realistic", "synthetic", "log_dump",
              notes="stack trace with UUID trace id, tests UUID vs secret confusion")

# -------------------------------------------------------------------
# 8. Clean near-miss adversarial negatives (30 cases) - most important FP class
# -------------------------------------------------------------------
for i in range(10):
    u = str(uuid.uuid4())
    text = f"The record with ID {u} seems to be duplicated in the export, can you check?"
    add_case("clean_near_miss", "clean_near_miss", text, [], "ALLOW", "realistic", "synthetic", "chat_turn",
              notes="random UUID, structurally similar to some token formats")

for i in range(10):
    commit = rand_hex(40)
    text = f"Can you check what changed in commit {commit}? The build broke right after."
    add_case("clean_near_miss", "clean_near_miss", text, [], "ALLOW", "realistic", "synthetic", "chat_turn",
              notes="git commit hash, high-entropy hex string resembling some secret formats")

for i in range(10):
    color = f"#{rand_hex(6)}"
    order_id = f"ORD-{random.randint(100000,999999)}"
    text = f"Change the button color to {color} and update order {order_id} status to shipped."
    add_case("clean_near_miss", "clean_near_miss", text, [], "ALLOW", "trivial", "synthetic", "chat_turn",
              notes="hex color code + product/order ID, tests numeric-ID false positive resistance")

# -------------------------------------------------------------------
# 9. Split-across-fragment edge cases (20 cases)
#    Documents the known V1 boundary: single-payload atomicity.
# -------------------------------------------------------------------
for i in range(10):
    key = "AKIA" + rand_alnum(16)
    # simulate two SEPARATE, independent requests with no shared payload (true V1 gap)
    text = f"[REQUEST 1 OF 2 - independent tool call, no shared context]\nStoring partial config value: {key[:12]}"
    add_case("secret", "aws_access_key", text, [], "ALLOW", "edge_case", "synthetic", "chat_turn",
              obfuscation="cross_request_fragmentation",
              notes="KNOWN V1 GAP: secret fragment split across genuinely independent requests (e.g. separate agent tool calls) with no shared payload; expected_decision=ALLOW documents the boundary, not a target to fix in V1")

for i in range(10):
    key = "sk_live_" + rand_alnum(24, string.ascii_letters + string.digits)
    # single payload, but split via multi-message array (should be caught - within one request)
    msg_array = [
        {"role": "user", "content": f"I'm going to give you part of a key: {key[:12]}"},
        {"role": "assistant", "content": "Okay, go ahead with the rest."},
        {"role": "user", "content": f"and the rest is: {key[12:]}"},
    ]
    text = json.dumps(msg_array)
    add_case("secret", "oauth_token", text,
              [{"category":"secret","subtype":"oauth_token","offset_start":text.find(key[:12]),"offset_end":text.find(key[12:])+len(key[12:])}],
              "BLOCK", "realistic", "synthetic", "chat_turn",
              obfuscation="multi_turn_within_single_payload",
              notes="secret split across conversation turns but WITHIN one request payload (full history array) - should be caught since payload-scoped inspection covers the full message array")

# -------------------------------------------------------------------
# Summary + write out
# -------------------------------------------------------------------
random.shuffle(cases)
# reassign sequential IDs after shuffle for clean ordering, keep stable
for idx, c in enumerate(cases, start=1):
    c["case_id"] = f"baseline_{idx:04d}"

with open("/home/claude/esys-baseline-dataset/baseline_dataset.json", "w") as f:
    json.dump({
        "dataset_version": "1.0.0",
        "severity_weights": SEVERITY_WEIGHTS,
        "total_cases": len(cases),
        "cases": cases
    }, f, indent=2)

# Category breakdown for sanity check
from collections import Counter
cat_counts = Counter(c["category"] for c in cases)
subtype_counts = Counter(c["subtype"] for c in cases)
decision_counts = Counter(c["expected_decision"] for c in cases)
difficulty_counts = Counter(c["difficulty"] for c in cases)

print(f"Total cases: {len(cases)}")
print("\nBy category:")
for k, v in cat_counts.most_common():
    print(f"  {k}: {v}")
print("\nBy subtype:")
for k, v in subtype_counts.most_common():
    print(f"  {k}: {v}")
print("\nBy expected_decision:")
for k, v in decision_counts.most_common():
    print(f"  {k}: {v}")
print("\nBy difficulty:")
for k, v in difficulty_counts.most_common():
    print(f"  {k}: {v}")
