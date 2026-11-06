#!/bin/bash
# Blastbox VM setup for a Vultr Cloud Compute instance (Ubuntu).
# Run on the VM after copying this repo to /opt/blastbox, and after
# creating /etc/blastbox.env with VULTR_INFERENCE_API_KEY and
# VULTR_INFERENCE_MODEL (never commit that file; it holds a secret).
# Steps: install Docker and Python, build the sandbox image, install
# and start the blastbox systemd service. The app itself runs on the
# VM host (stdlib only, no pip install); only task code runs inside
# Docker containers, via the SANDBOX_BACKEND=docker path in app/runner.py.
set -euo pipefail

if [ "$(id -u)" -ne 0 ]; then
  echo "run as root (sudo) on the VM" >&2
  exit 1
fi

if [ ! -f /opt/blastbox/app/server.py ] || [ ! -f /etc/blastbox.env ]; then
  echo "need /opt/blastbox/app/server.py and /etc/blastbox.env on the VM" >&2
  exit 1
fi

apt-get update
apt-get install -y docker.io python3
systemctl enable --now docker

cd /opt/blastbox
docker build -f Dockerfile.sandbox -t blastbox-sandbox:latest .

cp deploy/blastbox.service /etc/systemd/system/blastbox.service
systemctl daemon-reload
systemctl enable --now blastbox
systemctl status blastbox --no-pager
curl -sS http://127.0.0.1:8000/api/health
echo
echo "VM setup done. Public demo URL is the VM IP on port 8000."
