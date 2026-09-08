# PaperSignal — Deployment Runbook (Hinglish)

Ye file batati hai ki AWS pe kya-kya banaya gaya, kaun se commands chalaye aur **kyun**,
kharcha kitna hoga, PDFs kaise delete karni hain, sab kaise hataana hai, aur doosre log
API kaise use karenge.

**Live setup:**

| | |
|---|---|
| Site | https://papersignal.duckdns.org |
| Server IP | `3.108.144.36` (Elastic IP) |
| Region | `ap-south-1` (Mumbai) |
| Instance | `i-00e91a19bccf107e9` (t3.micro) |
| Security group | `sg-03c173f37594f45b2` |
| Elastic IP allocation | `eipalloc-0be81bcedfc8abd78` |
| SSH key | `C:\Users\abidk\.ssh\papersignal.pem` |

---

## 1. Kaun se AWS services use hue

Sirf **teen** cheezein — koi complicated service nahi:

| Service | Kya hai | Kyun chahiye tha |
|---|---|---|
| **EC2** | Ek virtual computer (Ubuntu Linux) jo AWS ke data center me chalti hai | App ko 24x7 chalane ke liye ek machine chahiye jo band na ho |
| **EBS** | Us computer ki hard disk (20 GB) | OS, code, uploaded PDFs aur database yahin rehte hain |
| **Elastic IP** | Ek fixed public IP address | Bina iske server restart hone pe IP badal jaata, aur domain toot jaata |

Iske alawa do cheezein AWS ke bahar hain:

| | Kya hai | Kyun |
|---|---|---|
| **DuckDNS** | Free subdomain service | HTTPS certificate ke liye ek naam chahiye — sirf IP se certificate nahi milta |
| **Caddy** | Web server (server pe install hua) | HTTPS automatic lagata hai aur `/api` ko backend tak bhejta hai |

---

## 2. Kaun se commands chale aur kyun

### Step 1 — SSH key pair

```bash
aws ec2 create-key-pair --key-name papersignal --query 'KeyMaterial' --output text > ~/.ssh/papersignal.pem
```

**Kyun:** Linux server pe password se login nahi hota, key file se hota hai. Ye command ek
private key file banati hai — isi se server me ghusenge. Ye file kho gayi to server me
dobara nahi ja paoge.

### Step 2 — Security group (firewall)

```bash
aws ec2 create-security-group --group-name papersignal-sg --vpc-id vpc-xxxx
aws ec2 authorize-security-group-ingress --group-id sg-xxx --protocol tcp --port 22  --cidr 152.59.0.0/16
aws ec2 authorize-security-group-ingress --group-id sg-xxx --protocol tcp --port 80  --cidr 0.0.0.0/0
aws ec2 authorize-security-group-ingress --group-id sg-xxx --protocol tcp --port 443 --cidr 0.0.0.0/0
```

**Kyun:** Security group AWS ka firewall hai — decide karta hai kaun sa port kiske liye khula hai.

- **Port 22 (SSH)** sirf aapke internet provider ki range se — poori duniya se nahi
- **Port 80 (HTTP)** sabke liye — Let's Encrypt ko certificate dene ke liye chahiye
- **Port 443 (HTTPS)** sabke liye — asli traffic yahin se aata hai
- **Port 8000 kabhi nahi khola** — backend sirf server ke andar sunta hai, bahar se seedha
  pahunch nahi sakta. Caddy hi uska darwaza hai

### Step 3 — Server launch

```bash
aws ec2 run-instances \
  --image-id ami-0aa761682283b4cc8 \
  --instance-type t3.micro \
  --key-name papersignal \
  --security-group-ids sg-xxx \
  --block-device-mappings '[{"DeviceName":"/dev/sda1","Ebs":{"VolumeSize":20,"VolumeType":"gp3","DeleteOnTermination":true}}]'
```

**Kyun har option:**

- `--image-id` — Ubuntu 22.04 ka official image (Canonical ka, ID region ke hisaab se badalti hai)
- `--instance-type t3.micro` — free tier wali machine (2 CPU, 1 GB RAM)
- `--key-name` — Step 1 wali key, taaki SSH ho sake
- `--block-device-mappings` — 20 GB disk. `DeleteOnTermination: true` matlab instance
  terminate karne pe disk bhi apne aap delete ho jaayegi — bhoolne pe bill nahi banega

### Step 4 — Elastic IP

```bash
aws ec2 allocate-address --domain vpc
aws ec2 associate-address --instance-id i-xxx --allocation-id eipalloc-xxx
```

**Kyun:** Normal EC2 ka public IP restart pe badal jaata hai. Elastic IP fix rehta hai, isliye
DuckDNS ka naam hamesha sahi jagah point karta rahega.

### Step 5 — Server ke andar setup

```bash
ssh -i ~/.ssh/papersignal.pem ubuntu@3.108.144.36
curl -fsSL https://raw.githubusercontent.com/abidraza5594/Paper-Signal/main/infra/setup-ec2.sh | bash
```

Ye script ye sab karti hai:

| Kaam | Kyun |
|---|---|
| Python 3.11 install | Backend Python pe chalta hai |
| **2 GB swap file** banana | 1 GB RAM kam hai. Swap "extra RAM" ki tarah kaam karta hai — memory bharne pe app crash hone ke bajaye thoda slow ho jaata hai |
| Caddy install | HTTPS aur reverse proxy ke liye |
| GitHub se code clone | Aapka app |
| virtualenv + dependencies | Python packages alag folder me, system Python se mix na hon |
| systemd service banana | Server restart ho ya app crash ho, apne aap wapas chalu ho jaaye |

### Step 6 — Configuration

Server pe `backend/.env` me:

```
MISTRAL_API_KEYS=<aapki key>
REQUIRE_API_KEY=true              # bina API key koi call nahi kar sakta
ADMIN_TOKEN=<key banane ke liye>
LOCAL_WORKER_COUNT=2              # 10 nahi — 1 GB RAM me 10 parallel PDF crash kar denge
MAX_UPLOAD_MB=200                 # upload disk pe stream hota hai, RAM me nahi
MAX_PDF_PAGES=50                  # ek page ek-ek karke render hota hai, peak RAM nahi badhti
MAX_BATCH_FILES=10                # files disk pe jaati hain, sirf 2 ek saath process hoti hain
CORS_ORIGINS=https://papersignal.duckdns.org   # browser clients ke domain yahan add karo
```

**Sirf `LOCAL_WORKER_COUNT` kam rakha hai, baaki limits poori hain.** `t3.micro` me 1 GB RAM
hai, aur RAM ka asli dabaav *parallel* jobs se aata hai — har job apna page image me render
karta hai. File size aur page count se peak RAM nahi badhti: upload chunk-by-chunk disk pe
likha jaata hai, aur pages ek-ek karke render hote hain. Isliye 200 MB aur 50 pages safe hain,
par 10 parallel jobs nahi.

### Step 7 — Frontend upload

```powershell
cd frontend
npm run build
scp -i ~/.ssh/papersignal.pem -r dist/frontend/browser/* ubuntu@3.108.144.36:/var/www/papersignal/
```

**Kyun laptop pe build kiya, server pe nahi:** Angular build ko ~2 GB RAM chahiye. Server pe
sirf 1 GB hai — wahan build karte to fail ho jaata.

### Step 8 — HTTPS

DuckDNS pe `papersignal` naam ko `3.108.144.36` pe point kiya, phir Caddy config:

```
papersignal.duckdns.org {
	root * /var/www/papersignal
	handle /api/* { reverse_proxy localhost:8000 }
	handle { try_files {path} /index.html; file_server }
	request_body { max_size 220MB }
}
```

**Kyun HTTPS zaroori hai:** API key har request ke header me jaati hai. HTTP pe wo plain text
me travel karti hai — beech me koi bhi padh sakta hai. Caddy ne Let's Encrypt se certificate
apne aap le liya, kuch karna nahi pada.

---

## 3. Deploy karte waqt jo problem aayi

**SSH connect nahi ho raha tha** — timeout aa raha tha, jabki AWS ki sab settings sahi thi.

Wajah: aapka internet provider **CGNAT** use karta hai. Matlab aapka public IP fix nahi hai —
alag-alag connections pe alag IP milta hai. `checkip.amazonaws.com` ne `152.59.103.159` bataya,
par server ko `152.59.101.61` dikha. Security group me pehle wala IP daala tha, isliye dusre
se connection block ho raha tha.

**Fix:** SSH rule ko poore provider range (`152.59.0.0/16`) pe khola.

**Iska matlab:** agar aap dusre WiFi ya mobile data se connect karoge to SSH kaam nahi karega.
Us waqt ye chalana padega:

```powershell
aws ec2 authorize-security-group-ingress --group-id sg-03c173f37594f45b2 --protocol tcp --port 22 --cidr <naya-range>/16
```

---

## 4. Kharcha kitna aayega

### Abhi (free tier ke andar) — **$0 per month**

| Cheez | Free tier | Hum use kar rahe hain |
|---|---|---|
| EC2 t3.micro | 750 ghante/mahina | ~730 ghante (poora mahina) |
| EBS storage | 30 GB | 20 GB |
| Public IPv4 | 750 ghante/mahina | ~730 ghante |
| Data transfer out | 100 GB/mahina | bahut kam |

Ek hi instance poora mahina chalao to bilkul fit baith jaata hai.

### Free tier khatam hone ke baad — **lagbhag $13-14 per month**

| Cheez | Approx |
|---|---|
| EC2 t3.micro (730 ghante) | ~$8 |
| EBS 20 GB gp3 | ~$2 |
| Public IPv4 address | ~$3.5 |
| **Total** | **~$13.5** (₹1,150 ke aas-paas) |

Ye approximate hai — exact rate ke liye [AWS Pricing Calculator](https://calculator.aws) dekho.

### Alag se: Mistral API

AWS ke bahar hai. Har PDF page ka kharcha model pe depend karta hai. Ye aapke Mistral account
se katega, AWS se nahi.

### Paisa lagne ki sabse badi wajah

1. **Elastic IP release na karna** — instance terminate karne ke baad bhi IP hourly charge
   karta hai. Ye sabse common surprise bill hai
2. **Instance sirf Stop karna, Terminate nahi** — stopped instance ka EBS bill chalta rehta hai
3. **Free tier ke 12 mahine khatam ho jaana** — koi notification nahi aata, bill aa jaata hai

**Isliye billing alarm zaroor lagao:** Billing → Budgets → Create budget → $1 → email alert.

---

## 5. Uploaded PDFs kaise delete karein

Server pe PDFs apne aap delete **nahi** hoti. Disk bharta rehta hai. Teen tareeke:

### A. Ek PDF — website se
"Earlier jobs" section kholo, job ke aage `×` dabao. Job aur uski PDF dono chali jaayengi.

### B. Ek PDF — API se
```bash
curl -X DELETE -H "X-API-Key: ps_live_..." https://papersignal.duckdns.org/api/jobs/<job_id>
```

### C. Bahut saari ek saath — cleanup script

```bash
ssh -i ~/.ssh/papersignal.pem ubuntu@3.108.144.36
cd ~/Paper-Signal/backend

# pehle dekho kya delete hoga (kuch delete nahi hoga)
./.venv/bin/python cleanup.py --older-than 7

# ab actually delete karo
./.venv/bin/python cleanup.py --older-than 7 --yes

# sab finished jobs
./.venv/bin/python cleanup.py --all --yes
```

`--yes` लगाए बिना ye sirf batata hai kya jaayega — galti se sab delete nahi hoga.
Jo jobs abhi chal rahi hain unhe kabhi haath nahi lagata.

### Har raat apne aap delete ho jaaye

```bash
crontab -e
```
Neeche ye line daal do:
```
0 2 * * * cd /home/ubuntu/Paper-Signal/backend && ./.venv/bin/python cleanup.py --older-than 7 --yes >> /tmp/cleanup.log 2>&1
```
Roz raat 2 baje 7 din se purani jobs aur unki PDFs delete ho jaayengi.

### Disk kitna bhara hai dekhne ke liye
```bash
df -h /
du -sh ~/Paper-Signal/backend/data/uploads
```

---

## 6. Doosre log API kaise use karenge

### Aapko kya karna hai

Har client ke liye **alag key** banao:

```bash
ssh -i ~/.ssh/papersignal.pem ubuntu@3.108.144.36
cd ~/Paper-Signal/backend
./.venv/bin/python manage_keys.py create "Client ka naam" --rate-limit 60 --quota 200
```

Alag-alag key isliye ki har client sirf apne documents dekh paye, aur zaroorat pade to ek
client ki key band kar sako baaki ko chhue bina:

```bash
./.venv/bin/python manage_keys.py list                    # kaun kitna use kar raha hai
./.venv/bin/python manage_keys.py revoke <key_id>         # ek client band
```

Client ko teen cheezein bhejo:
1. URL — `https://papersignal.duckdns.org`
2. Unki key — `ps_live_...`
3. [API.md](API.md)

### Client apne application me kaise lagayega

Sirf do calls hain. Key har request ke header me jaati hai.

**Python:**
```python
import requests, time

BASE = "https://papersignal.duckdns.org"
HEADERS = {"X-API-Key": "ps_live_..."}
SCHEMA = '{"type":"object","properties":{"trainName":{"type":"string"},"trainNumber":{"type":"number"}}}'

# 1. PDFs bhejo
r = requests.post(f"{BASE}/api/jobs/batch", headers=HEADERS,
    files=[("files", open("a.pdf", "rb")), ("files", open("b.pdf", "rb"))],
    data={"output_template": SCHEMA, "ocr_mode": "auto"})
batch_id = r.json()["batch_id"]

# 2. result ka wait karo
while True:
    jobs = requests.get(f"{BASE}/api/batches/{batch_id}", headers=HEADERS).json()
    if all(j["status"] in ("completed", "failed") for j in jobs):
        break
    time.sleep(2)

for j in jobs:
    print(j["file_name"], "->", j.get("result", {}).get("data"))
```

**Node.js:**
```javascript
const BASE = "https://papersignal.duckdns.org";
const HEADERS = { "X-API-Key": "ps_live_..." };

const form = new FormData();
form.append("files", fs.createReadStream("a.pdf"));
form.append("output_template", JSON.stringify({
  type: "object",
  properties: { trainName: { type: "string" } }
}));

const res = await fetch(`${BASE}/api/jobs/batch`, {
  method: "POST", headers: HEADERS, body: form
});
const { batch_id } = await res.json();

// har 2 second me check karo
let jobs;
do {
  await new Promise(r => setTimeout(r, 2000));
  jobs = await (await fetch(`${BASE}/api/batches/${batch_id}`, { headers: HEADERS })).json();
} while (jobs.some(j => j.status === "queued" || j.status === "processing"));

jobs.forEach(j => console.log(j.file_name, j.result?.data));
```

**Zaroori baat:** result turant nahi milta. `POST` sirf kaam queue karta hai (`202` deta hai),
phir har 2 second me poll karna padta hai. Ek PDF me 15-30 second lag sakte hain.

### Client ko kya limits milengi

- Rate limit cross → **429** (`Retry-After` header me batata hai kitna ruko)
- Mahine ka quota khatam → **402**
- Galat/band key → **401**
- Doosre client ka job maanga → **404**

Client apna balance khud dekh sakta hai: `GET /api/usage`

---

## 7. Manager ko API docs kaise dun

[API.md](API.md) me poori technical documentation hai — saare endpoints, fields, status codes,
JSON Schema rules, aur ek end-to-end example.

Bhejne ke teen tareeke:

1. **GitHub link** — https://github.com/abidraza5594/Paper-Signal/blob/main/API.md
   (agar repo private hai to manager ko access dena padega)
2. **Live interactive docs** — https://papersignal.duckdns.org/api/docs
   Ye khud API se banta hai, isliye hamesha updated rehta hai. Yahan browser me hi endpoints
   try kiye ja sakte hain
3. **File bhej do** — `API.md` seedha attach kar do

Manager technical na hon to `/api/docs` link sabse achha hai — wahan sab kuch dikhta hai aur
click karke chala kar dekh sakte hain.

---

## 8. Sab kuch kaise hataana hai

Demo khatam hone pe **teen** cheezein hatani hain. Teeno zaroori hain.

### Pehle data bacha lo (agar chahiye)

```powershell
scp -i C:\Users\abidk\.ssh\papersignal.pem ubuntu@3.108.144.36:~/Paper-Signal/backend/data/*.sqlite3 .
```

### Phir delete karo

```powershell
# 1. server band karo (disk bhi saath jaayegi, kyunki DeleteOnTermination=true tha)
aws ec2 terminate-instances --instance-ids i-00e91a19bccf107e9

# 2. Elastic IP release karo -- YE SABSE ZAROORI HAI
aws ec2 release-address --allocation-id eipalloc-0be81bcedfc8abd78

# 3. security group aur key pair (optional, inka koi paisa nahi lagta)
aws ec2 delete-security-group --group-id sg-03c173f37594f45b2
aws ec2 delete-key-pair --key-name papersignal
```

Security group tabhi delete hoga jab instance poori tarah terminate ho jaaye — 2-3 minute lagte hain.

### Confirm karo ki sach me sab gaya

```powershell
aws ec2 describe-instances --instance-ids i-00e91a19bccf107e9 --query 'Reservations[0].Instances[0].State.Name'
# "terminated" aana chahiye

aws ec2 describe-addresses
# khaali list aani chahiye -- agar koi IP dikhe to wo paisa kaat raha hai

aws ec2 describe-volumes --query 'Volumes[].{id:VolumeId,state:State}'
# khaali list aani chahiye
```

**Billing alarm mat hatana.** Wo chalta rehne do — kuch chhoot gaya to email aa jaayega.

DuckDNS ka naam bhi delete kar sakte ho (duckdns.org pe "delete domain"), par uska koi
paisa nahi lagta, chhod dene me bhi harj nahi.

---

## 9. Roz ke kaam

```bash
# server me ghusna
ssh -i C:\Users\abidk\.ssh\papersignal.pem ubuntu@3.108.144.36

# app chal raha hai ya nahi
sudo systemctl status papersignal

# app ke logs (live)
sudo journalctl -u papersignal -f

# app restart (.env badalne ke baad hamesha)
sudo systemctl restart papersignal

# nayi code changes lena
cd ~/Paper-Signal && git pull && sudo systemctl restart papersignal

# frontend update (laptop se)
cd frontend && npm run build
scp -i ~/.ssh/papersignal.pem -r dist/frontend/browser/* ubuntu@3.108.144.36:/var/www/papersignal/
```

### Kuch kharab ho jaaye to

| Problem | Kya dekho |
|---|---|
| Site nahi khul rahi | `sudo systemctl status caddy` |
| 502 error | Backend band hai: `sudo systemctl status papersignal` phir `journalctl -u papersignal -n 50` |
| App baar-baar restart ho raha | RAM khatam. `free -h` dekho, `LOCAL_WORKER_COUNT` aur kam karo |
| Jobs fail ho rahi hain | Mistral key khatam ya galat: `.env` check karo |
| SSH nahi lag raha | Aapka IP badal gaya — Section 3 dekho |
| Disk full | Section 5 wala cleanup chalao |
