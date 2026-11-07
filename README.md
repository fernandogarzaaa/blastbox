# Blastbox: Prove-It CSV Analyst

Entry for the Vultr: Agent Rush Hackathon on lablab.ai, Challenge 1:
Blast Radius Zero. Solo, online. Built during the November 3-8, 2026
build window.

## What it does

A web agent that answers a question about a CSV file with real
executed code, not a description of what it would do.

1. The user pastes a CSV and a question.
2. Code is generated via Vultr Serverless Inference
   (https://api.vultrinference.com/v1, OpenAI-compatible), or supplied
   directly when testing the sandbox.
3. The code passes a static policy gate before execution: only an
   allowlist of modules (csv, json, math, statistics, collections, re,
   datetime), and open() only on the literal `input.csv` in read mode.
   Imports of os, sys, subprocess, socket, urllib, requests, and
   others are blocked, as are eval, exec, dunder access, and any
   other file path or write mode.
4. The code runs in a fresh container per task on the Vultr VM:
   --network none, --cap-drop ALL, 256 MB memory, 0.5 CPU, 64 pids,
   read-only root filesystem, read-only input.csv mount, container
   removed after the run (--rm). No API keys or host paths enter
   the container.
5. Real stdout, stderr, exit code, and a receipt return to the user:
   SHA-256 of code and input, limits applied, backend, duration.
   A failed generated run is retried once with the error fed back.

The containment moment for the demo video: hostile code
(`import socket`) is blocked by the policy gate before execution,
with an empty stdout and a named reason, while the same UI runs a
legitimate analysis to real numbers.

## Run locally (dev backend)

```
python3 -m app.server   # PORT env, default 8000, backend local
python3 -m unittest discover -s tests -v
```

The local backend applies the same policy plus OS rlimits, a
scrubbed environment, and a 10 second timeout, in a temp dir
containing only input.csv. It is a development backend, not the
production containment claim. Production containment is the Docker
backend (`SANDBOX_BACKEND=docker`, `SANDBOX_IMAGE` env).

## Deploy on Vultr (pending, see Day 1 status)

- App image: Dockerfile (standard library only, no pip install).
- Sandbox image: Dockerfile.sandbox (python:3.12-slim, stdlib only).
- VM runs the app with SANDBOX_BACKEND=docker and Docker installed,
  plus VULTR_INFERENCE_API_KEY and VULTR_INFERENCE_MODEL set in the
  VM environment, never in the repo or the sandbox.
- Public demo URL and LabLab submission happen only when the VM
  deployment and a live Docker run are verified. No partial entry
  is submitted.

## Vultr services used

- Vultr Cloud Compute (VM backend, web app on Vultr).
- Vultr Serverless Inference (agent LLM calls, required for
  Challenge 1).
- Docker on the VM for isolated sandboxes (event-recommended
  approach; Vultr GPUs are not available for this event and are
  not used).

## Prior work reused, and what is new here

Inan's anchor-harness repo (private, sandboxed executors with
receipts) informed the receipt design. This entry is new code
written in the event window: policy gate, runner, inference client,
web UI, and tests are all in this repo. Playwright material found
in his repos was plugin templates, not a browser agent, so this
entry uses Pattern A (sandboxed code execution) rather than
Pattern B.

## Day 1 status (November 3, 2026, verified)

- Event brief read from lablab.ai: two tracks, Blast Radius Zero
  and Powering the Future of Work, no newly announced tracks.
  Submission needs a GitHub repo, Vultr VM backend, public demo
  URL, recorded demo video, architecture explanation, and one
  containment moment in the video.
- 16 unit tests pass (policy, local runner, Docker command and
  wiring with a mocked Docker call, inference prompt and parsing).
- Web server smoke-tested locally: health ok, sample analysis
  returns coffee 1750 and beans 1200, hostile code blocked with
  reason "blocked import: socket", and a blank-code request with
  no inference key returns a clear error instead of fake output.
- Not yet done, and not claimed: Vultr $200 credit claim, Vultr VM
  deployment, a live Docker-backend run, a live Serverless
  Inference generation, demo video, public demo URL, LabLab
  submission.

## Day 2 status (November 4, 2026, verified)

- Gift code located, not yet redeemed: the signed-in LabLab event page's
  Vultr promotion link carries promo=HACKATHON, so the code value is
  HACKATHON. It has not been applied at Vultr, so the $200 balance is
  unconfirmed. The LabLab coupon page's "Claim Coupon" button was not
  clicked; whether it reveals a different code is unresolved.
- Credit claim blocked at Vultr sign-in: no saved Vultr login exists for
  fernandogarzaaa@gmail.com, no password was invented or reused, and
  1Password is not connected. Inan must sign in to an existing Vultr
  account or create one with a password he sets, then apply HACKATHON
  in Billing and confirm $200.00 Remaining Credit. VM, live Docker run,
  live inference, demo video, and submission all wait on this step.
- Build unchanged from Day 1. Tests re-run: 16 pass. No TODO/FIXME markers.

## Day 3 status (November 5, 2026, verified)

- Event brief re-read from lablab.ai: same two tracks, Blast Radius Zero
  and Powering the Future of Work, no newly announced tracks. Window
  unchanged at 2026-11-03T16:00Z to 2026-11-08T23:00Z. Submission needs
  unchanged: GitHub repo, Vultr VM backend, public demo URL, recorded
  demo video, architecture explanation, one containment moment.
- Gmail re-checked: no mail from vultr.com since Nov 4, and no Vultr
  verification, welcome, or billing mail. The only Vultr-related mail
  since Nov 4 is the already-known Nov 4 LabLab onsite-attendance
  nudge. No evidence Inan has created or signed in to a Vultr account
  yet, so the $200 credit (promo HACKATHON) remains unredeemed and
  unconfirmed.
- Build verified again: 16 unit tests pass, and a live local server
  smoke test on port 8124 returned health ok, sample analysis
  beans 1200 and coffee 1750 with exit code 0, and hostile
  `import socket` blocked with reason "blocked import: socket" and
  empty stdout. That is the demo containment moment, on the local
  backend only; the Docker-backend version is still VM-unverified.
- New, VM-ready deployment files: deploy/vm-setup.sh (installs
  Docker and Python on the VM, builds the sandbox image, installs
  and starts the service) and deploy/blastbox.service (app on the
  VM host, Docker backend for task code only, inference key from
  /etc/blastbox.env, never in the repo). vm-setup.sh passes
  `bash -n`. The service unit is not verified in this sandbox:
  systemd-analyze could not resolve docker.service here, so the
  unit, like the Docker backend, waits for VM verification.
- Not done, not submitted: Vultr account and credit claim, VM,
  public demo URL, demo video, LabLab submission. Video escalation
  deadline is Nov 6 per the task: if the Vultr account still does
  not exist by the Nov 6 run, the video blocker escalates to Inan
  then, since the video needs a working VM demo to capture.

## Day 4 status (November 6, 2026, verified)

- Event brief re-read from lablab.ai: same two tracks, Blast Radius Zero
  and Powering the Future of Work, no newly announced tracks. Window
  unchanged at 2026-11-03T16:00Z to 2026-11-08T23:00Z. Submission needs
  unchanged: GitHub repo, Vultr VM backend, public demo URL, recorded
  demo video, architecture explanation, one containment moment.
- Gmail re-checked: no mail from vultr.com since Nov 5, and no Vultr
  verification, welcome, or billing mail. The only Vultr-related mail
  since Nov 5 is the already-known Nov 5 LabLab onsite-attendance
  nudge. No evidence Inan has created or signed in to a Vultr account
  yet, so the $200 credit (promo HACKATHON) remains unredeemed and
  unconfirmed.
- Build verified again: 16 unit tests pass. No TODO/FIXME markers.
- Public repo created and code pushed: https://github.com/fernandogarzaaa/blastbox
- ESCALATED Nov 6: the demo video is now the blocking item. The video
  must show the app running on the Vultr VM with a containment moment,
  and there is no Vultr account, no VM, no public demo URL, and no
  live inference yet. Inan must create or sign in to a Vultr account
  for fernandogarzaaa@gmail.com and apply HACKATHON in Billing, then
  the VM deploy, live Docker run, live inference check, and video
  recording can proceed. Submission is due Nov 9, 7:00 AM Manila.
- Not done, not submitted: Vultr account and credit claim, VM,
  public demo URL, demo video, LabLab submission.

## Day 5 status (November 7, 2026, verified)

- Event brief re-read from lablab.ai: same two tracks, Blast Radius Zero
  and Powering the Future of Work, no newly announced tracks. Window
  unchanged at 2026-11-03T16:00Z to 2026-11-08T23:00Z. Submission needs
  unchanged: GitHub repo, Vultr VM backend, public demo URL, recorded
  demo video, architecture explanation, one containment moment.
- Gmail re-checked: no mail from vultr.com since Nov 6, and no Vultr
  verification, welcome, or billing mail. The only Vultr-related mail
  since Nov 6 is the already-known Nov 6 LabLab onsite-attendance
  nudge. No evidence Inan has created or signed in to a Vultr account
  yet, so the $200 credit (promo HACKATHON) remains unredeemed and
  unconfirmed.
- Regression found and fixed: 1 of 16 tests failed on this run.
  Root cause was the test, not the product: the sandbox VM gained a
  Docker CLI binary (docker 29.1.3, daemon not running), so the
  missing-binary test's assumption that no docker binary exists no
  longer held and the docker-run error path returned no reason field.
  Fixed by mocking the missing binary in the test and by adding a
  reason to every failed docker-run receipt in app/runner.py.
  Tests re-run: 16 pass. Local smoke test on port 8126: health ok,
  sample analysis beans 1200 and coffee 1750 with exit code 0 in
  36ms, hostile `import socket` blocked with reason
  "blocked import: socket" and empty stdout.
- STILL BLOCKED, escalated Nov 6: no Vultr account, no VM, no public
  demo URL, no live inference, no demo video. Submission is due
  Nov 9, 7:00 AM Manila; the build window ends Nov 8, 23:00 UTC.
  Do not submit until VM + live Docker + live inference are verified.

## Blockers and next steps

- Vultr gift code: the event page says the code is shared at
  kickoff. Kickoff is November 3, 15:00 UTC (23:00 Manila), after
  this morning run, and no code arrived by email as of this run.
  The credit claim and VM provisioning wait on that code. No
  payment details are entered at any point.
- Inference key: needs the Vultr account and Serverless Inference
  access from the same kickoff flow. The key goes to the Secure
  Vault, never into chat, memory, or files.
- Next runs: claim credits at kickoff, provision the VM, verify a
  live Docker run and a live inference generation, then record
  the demo video with the containment moment.
