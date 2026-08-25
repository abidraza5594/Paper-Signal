# Deploying PaperSignal on AWS Free Tier

A single EC2 instance with HTTPS, suitable for a demo or a small pilot. No code changes
are needed — the app runs on SQLite and local disk, which is fine for one server.

Read [Section 8](#8-shutting-it-down) before you start: this is a temporary setup and you
must terminate it deliberately, or it will start costing money.

---

## 1. What the free tier gives you, and what it costs you

| Resource | Free allowance | Notes |
|---|---|---|
| EC2 `t3.micro` / `t2.micro` | 750 hours/month for 12 months | One instance running full-time fits exactly. |
| EBS storage | 30 GB | 20 GB is plenty here. |
| Data transfer out | 100 GB/month | Nowhere near the limit for a demo. |
| Elastic IP | Free **only while attached to a running instance** | An unattached one is billed hourly. |

AWS changed its free tier for accounts created after mid-2025 (credit-based instead of the
12-month allowance). Check **Billing → Free tier** in the console to see which one you are on.

**Set a billing alarm before anything else.** Billing → Budgets → create a $1 budget with an
email alert. It takes two minutes and it is the only thing standing between a misconfiguration
and a surprise bill.

### The one real constraint: 1 GB RAM

`t3.micro` has 1 GB. This app renders PDF pages to images, which is memory-hungry. Two
consequences:

1. **Set `LOCAL_WORKER_COUNT=2`** in `.env`, not the default 10. Ten parallel renders will
   exhaust 1 GB and the kernel will kill the process.
2. **Do not run `npm run build` on the server.** The Angular build needs roughly 2 GB and will
   fail. Build on your laptop and upload the output — covered in step 6.

The setup script also adds 2 GB of swap, which keeps the box alive through memory spikes
instead of hard-crashing.

---

## 2. Launch the instance

EC2 → Launch instance:

| Setting | Value |
|---|---|
| Name | `papersignal` |
| AMI | Ubuntu Server 22.04 LTS (64-bit x86) |
| Instance type | `t3.micro` (or `t2.micro` — whichever is marked free-tier eligible) |
| Key pair | Create one, download the `.pem`, keep it safe |
| Storage | 20 GB gp3 |

**Security group** — this part matters:

| Type | Port | Source | Why |
|---|---|---|---|
| SSH | 22 | **My IP** | Never `0.0.0.0/0`. |
| HTTP | 80 | Anywhere | Let's Encrypt needs it to issue the certificate. |
| HTTPS | 443 | Anywhere | The actual traffic. |

**Do not open port 8000.** The API listens on loopback only; Caddy is the public face.

After launch, allocate an **Elastic IP** and associate it with the instance, so the address
survives a reboot.

---

## 3. Get a hostname

HTTPS needs a hostname — a bare IP cannot get a certificate. API keys travel in a request
header, so plain HTTP is not an option once anyone else uses this.

No domain? [duckdns.org](https://www.duckdns.org) gives you a free subdomain in about a
minute: sign in, pick a name such as `papersignal`, and point it at your Elastic IP. You get
`papersignal.duckdns.org`, and Caddy will issue a real certificate for it.

If you own a domain, add an `A` record pointing to the Elastic IP instead.

---

## 4. Run the setup script

SSH in:

```bash
ssh -i papersignal.pem ubuntu@<elastic-ip>
```

Then:

```bash
curl -fsSL https://raw.githubusercontent.com/abidraza5594/Paper-Signal/main/infra/setup-ec2.sh | bash
```

This installs Python and Caddy, adds swap, clones the repo, creates the virtualenv, installs
dependencies, and registers the systemd service. It prints a generated `ADMIN_TOKEN` — copy it.

---

## 5. Configure

```bash
nano ~/Paper-Signal/backend/.env
```

The values that matter:

```
MISTRAL_API_KEYS=<your Mistral key>
REQUIRE_API_KEY=true
ADMIN_TOKEN=<the value the script printed>
LOCAL_WORKER_COUNT=2
CORS_ORIGINS=https://papersignal.duckdns.org
```

`CORS_ORIGINS` must be the exact URL you will open in the browser, or the console will not be
able to call its own API.

Then the web server:

```bash
sudo cp ~/Paper-Signal/infra/Caddyfile /etc/caddy/Caddyfile
sudo nano /etc/caddy/Caddyfile     # replace papersignal.duckdns.org with your hostname
sudo systemctl restart papersignal caddy
```

Check it came up:

```bash
sudo systemctl status papersignal
curl -s localhost:8000/api/health
```

`"require_api_key":true` confirms key mode is on.

---

## 6. Upload the frontend

**On your laptop**, in the project folder:

```powershell
cd frontend
npm run build
scp -i papersignal.pem -r dist/frontend/browser/* ubuntu@<elastic-ip>:/var/www/papersignal/
```

Open `https://papersignal.duckdns.org`. The first load may take a few seconds while Caddy
obtains the certificate.

---

## 7. Issue a key and test

On the server:

```bash
cd ~/Paper-Signal/backend
./.venv/bin/python manage_keys.py create "Demo" --rate-limit 60 --quota 200
```

Copy the `ps_live_...` value — it is shown once.

Paste it into the web console when it asks, or test the API directly from your laptop:

```bash
curl -H "X-API-Key: ps_live_..." https://papersignal.duckdns.org/api/usage
```

Full endpoint reference: [API.md](API.md).

---

## 8. Shutting it down

When the demo is over:

1. **EC2 → Instances → Terminate.** Stopping is not enough; a stopped instance still bills for
   its EBS volume.
2. **EC2 → Volumes** — confirm the 20 GB volume is gone. Terminate usually deletes it, but check.
3. **EC2 → Elastic IPs → Release.** An Elastic IP with nothing attached is billed by the hour.
   This is the single most common source of unexpected charges.
4. Leave the billing alarm in place.

Anything you want to keep — extracted results, issued keys — download first:

```bash
scp -i papersignal.pem ubuntu@<elastic-ip>:~/Paper-Signal/backend/data/*.sqlite3 ./
```

---

## 9. Known limits of this setup

Honest about what you are showing:

- **One instance only.** Jobs, API keys, and usage live in SQLite; uploads live on the instance's
  disk. Two servers cannot share them. Moving to RDS PostgreSQL and S3 is the next step if this
  goes past a pilot.
- **Rate limiting is per process**, so it is exact here but would need Redis behind a load balancer.
- **Uploaded PDFs are never deleted automatically.** On a 20 GB disk that is fine for a demo;
  a long-running service needs a retention policy.
- **No malware scanning** of uploaded files.
- **`.env` holds the Mistral key in plain text.** Acceptable on a throwaway demo box; use AWS
  Secrets Manager for anything real.
- **If the instance restarts, data survives** (it is on EBS), but a terminate destroys everything.

---

## 10. If something breaks

| Symptom | Check |
|---|---|
| Site does not load at all | Security group has 80 and 443 open; `sudo systemctl status caddy` |
| Certificate error | DNS actually points at the Elastic IP: `dig +short your-host`. Caddy retries every few minutes. |
| `502 Bad Gateway` | Backend is down: `sudo systemctl status papersignal`, then `sudo journalctl -u papersignal -n 50` |
| Jobs fail with an AI error | `MISTRAL_API_KEYS` missing or out of quota in `.env`; restart after editing |
| Backend keeps restarting | Out of memory. Confirm `LOCAL_WORKER_COUNT=2` and `free -h` shows swap active. |
| Console loads but API calls fail | `CORS_ORIGINS` does not match the URL in the browser |
| 401 on every call | Key mode is on and no key is set — paste one in the console |

Any `.env` change needs `sudo systemctl restart papersignal` to take effect.
