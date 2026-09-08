# PaperSignal — Runbook (Hinglish)

Ye file batati hai ki service **kis cheez par** chal rahi hai, **kaun se AWS services** use
hue aur kyun, deploy **kaise** karna hai, kharcha kitna hai, aur sab kaise band karna hai.

**Live:**

| | |
|---|---|
| URL | https://ydb2zmspyn.ap-south-1.awsapprunner.com |
| Region | `ap-south-1` (Mumbai) |
| Service | App Runner — `papersignal` |
| Instance size | 1 vCPU / 2 GB |

Ek hi URL par sab kuch hai: website, documentation (`/documentation`), demo page
(`/demo.html`), Swagger (`/api/docs`) aur API (`/api/v1/...`).

---

## 1. Ye "serverless" kaise hai

Pehle EC2 par tha — ek machine jo humein khud chalani padti thi: OS updates, restart,
disk, SSH keys, firewall, HTTPS certificate. Ab wo sab AWS sambhalta hai.

| Pehle (EC2) | Ab (serverless) |
|---|---|
| Ek Linux machine, humari zimmedari | **App Runner** — container, AWS chalata hai |
| SQLite file disk par | **DynamoDB** — managed database |
| PDFs local disk par | **S3** — object storage |
| DuckDNS + Caddy + Let's Encrypt | **HTTPS built-in**, kuch setup nahi |
| Traffic badhe to hum bada server lete | **Auto-scale** |
| SSH karke deploy | `docker push` + ek command |

**"Serverless" ka matlab "muft" nahi hai** — matlab ye ki koi server manage nahi karna.
Kharcha section 5 me hai.

---

## 2. Kaun se AWS services use hue

Paanch, aur har ek ka ek hi kaam hai:

| Service | Kya karta hai | Kyun zaroori tha |
|---|---|---|
| **App Runner** | Container ko internet par chalata hai | Aapka Python app kahin to chalna chahiye. Ye HTTPS, scaling aur restart khud sambhalta hai |
| **ECR** | Container image ka storage | App Runner ko image kahin se lena hota hai |
| **S3** | Uploaded PDFs | Container kabhi bhi replace ho sakta hai, to files uske andar nahi rakh sakte |
| **DynamoDB** | Jobs, API keys, usage counts | Wahi wajah — data container ke bahar chahiye |
| **IAM** | Do roles (permissions) | Container ko sirf apne bucket aur tables ka access ho, poore AWS ka nahi |

Ye **nahi** chahiye pade: EC2, load balancer, DuckDNS, Caddy, SSL certificate, SSH keys,
security groups, Elastic IP. Sab hat gaye.

### Banaye gaye resources

| Resource | Naam |
|---|---|
| App Runner service | `papersignal` |
| ECR repository | `papersignal-api` |
| S3 bucket | `papersignal-uploads-397332850029` |
| DynamoDB | `papersignal-jobs`, `papersignal-api-keys`, `papersignal-usage` |
| IAM roles | `PaperSignalAppRunnerECR`, `PaperSignalAppRunnerTask` |

---

## 3. Data kahan rehta hai

### S3 — uploaded PDFs
Har PDF `uploads/<random>.pdf` naam se jaati hai. Bucket **poori tarah private** hai —
internet se koi seedha nahi khol sakta, sirf app padh sakta hai.

**7 din baad PDFs apne aap delete ho jaati hain** (lifecycle rule). Pehle EC2 par ye nahi
tha aur disk bharta rehta tha.

### DynamoDB — teen tables

| Table | Key | Kya rakhta hai |
|---|---|---|
| `papersignal-jobs` | extraction_id + job_id | Har document ka status aur nikala hua JSON |
| `papersignal-api-keys` | key_hash | Keys — **sirf hash**, asli key kabhi store nahi hoti |
| `papersignal-usage` | api_key_id + period | Har key ne mahine me kitne documents use kiye |

Teeno **pay-per-request** par hain: jitna use, utna paisa. Idle par kuch nahi.
Free tier itna bada hai ki is load par kharcha practically zero rehta hai.

Usage count **atomic** hai (DynamoDB ka `ADD`), isliye do container ek saath count karein
to bhi ginti galat nahi hoti.

---

## 4. Deploy kaise karna hai

### Pehli baar setup (ho chuka hai)

```powershell
# 1. S3 bucket, private + 7-din auto-delete
aws s3api create-bucket --bucket papersignal-uploads-397332850029 --region ap-south-1 `
  --create-bucket-configuration LocationConstraint=ap-south-1
aws s3api put-public-access-block --bucket papersignal-uploads-397332850029 `
  --public-access-block-configuration "BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true"

# 2. DynamoDB tables (pay-per-request)
aws dynamodb create-table --table-name papersignal-jobs `
  --attribute-definitions AttributeName=extraction_id,AttributeType=S AttributeName=job_id,AttributeType=S `
  --key-schema AttributeName=extraction_id,KeyType=HASH AttributeName=job_id,KeyType=RANGE `
  --global-secondary-indexes '[{"IndexName":"job_id-index","KeySchema":[{"AttributeName":"job_id","KeyType":"HASH"}],"Projection":{"ProjectionType":"ALL"}}]' `
  --billing-mode PAY_PER_REQUEST

# 3. IAM roles -- container ko sirf apne bucket aur tables ka access
#    (poora JSON docs/ me hai; role ke paas AdministratorAccess nahi hai)

# 4. App Runner service
aws apprunner create-service --cli-input-json file://apprunner.json
```

### Roz ka deploy (code badalne par)

```powershell
# 1. Tests -- pehle ye, warna toota code live chala jaayega
cd backend; .\.venv\Scripts\python.exe -m pytest -q
cd ..\frontend; npm test -- --watch=false

# 2. Frontend build karke backend me copy (container dono serve karta hai)
npm run build
Remove-Item -Recurse -Force ..\backend\web
Copy-Item -Recurse dist\frontend\browser ..\backend\web

# 3. Image banao aur ECR pe bhejo
cd ..\backend
aws ecr get-login-password --region ap-south-1 | `
  docker login --username AWS --password-stdin 397332850029.dkr.ecr.ap-south-1.amazonaws.com
docker build -t papersignal-api:latest .
docker tag papersignal-api:latest 397332850029.dkr.ecr.ap-south-1.amazonaws.com/papersignal-api:latest
docker push 397332850029.dkr.ecr.ap-south-1.amazonaws.com/papersignal-api:latest

# 4. Deploy
aws apprunner start-deployment --service-arn arn:aws:apprunner:ap-south-1:397332850029:service/papersignal/667bba16f804404d9457da542b9bb068
```

Deploy me 3-5 minute lagte hain. Purana version tab tak chalta rehta hai, phir naya aata hai
— matlab **downtime nahi** hota.

**Frontend laptop par build karte hain**, server par nahi — Angular build ko ~2 GB RAM chahiye.

### Settings badalni ho (limits, keys)

Console → App Runner → `papersignal` → Configuration → Edit → environment variables.
Save karte hi service apne aap redeploy ho jaati hai.

| Variable | Abhi | Kya karta hai |
|---|---|---|
| `MISTRAL_API_KEYS` | (secret) | AI provider ki key. Comma se do keys de sakte hain — pehli fail ho to doosri chalti hai |
| `ADMIN_TOKEN` | (secret) | Nayi API key banane ke liye |
| `REQUIRE_API_KEY` | `true` | Bina key koi call nahi kar sakta |
| `LOCAL_WORKER_COUNT` | `4` | Ek saath kitne PDF process honge |
| `MAX_PDF_PAGES` | `50` | Ek PDF me max pages |
| `CORS_ORIGINS` | localhost:5500 | Browser clients ke domain yahan add karo |

---

## 5. Kharcha

| Cheez | Kharcha |
|---|---|
| **App Runner** (1 vCPU / 2 GB) | **~$13-15/month** — chahe traffic ho ya na ho |
| S3 | ~$0 (free tier; PDFs 7 din me delete) |
| DynamoDB | ~$0 (free tier; pay-per-request) |
| ECR | ~$0 (image 500 MB free tier me) |
| **Total** | **~$13-15/month** (₹1,200 ke aas-paas) |

Iske alawa **Mistral API** ka kharcha alag hai — wo AWS ka nahi, aapke Mistral account ka.

### Ye samajhna zaroori hai

Pehla EC2 setup free tier me **$0** ka tha. App Runner me **idle hone par bhi** provisioned
memory ka charge lagta hai. Serverless ka matlab "server manage nahi karna" hai — "muft" nahi.

**Demo ke beech me pause kar do**, compute ka bill ruk jaayega:
```powershell
aws apprunner pause-service  --service-arn arn:aws:apprunner:ap-south-1:397332850029:service/papersignal/667bba16f804404d9457da542b9bb068
aws apprunner resume-service --service-arn arn:aws:apprunner:ap-south-1:397332850029:service/papersignal/667bba16f804404d9457da542b9bb068
```
Resume me 1-2 minute lagte hain.

**Billing alarm zaroor lagao:** Billing → Budgets → $5 budget → email alert.

Agar sach me **zero-when-idle** chahiye to AWS Lambda hi ek raasta hai. Par Lambda me
background worker nahi chalta — poora job queue (SQS) wala rewrite karna padega, 3-4 din ka
kaam. Is load par bachat ~$13/month hogi, isliye abhi iska matlab nahi banta.

---

## 6. Roz ke kaam

```powershell
# service ka haal
aws apprunner describe-service --service-arn <ARN> --query 'Service.Status'

# logs
aws logs tail /aws/apprunner/papersignal/667bba16f804404d9457da542b9bb068/application --follow

# nayi client key banao (App Runner console ke Shell se, ya API se)
curl.exe -X POST https://ydb2zmspyn.ap-south-1.awsapprunner.com/api/v1/keys `
  -H "X-Admin-Token: $ADMIN" -H "Content-Type: application/json" --data "@key.json"

# S3 me kitni files padi hain
aws s3 ls s3://papersignal-uploads-397332850029/uploads/ --summarize | tail -2
```

### Kuch kharab ho jaye

| Problem | Kya dekho |
|---|---|
| Site nahi khul rahi | `describe-service` me Status; `RUNNING` hona chahiye |
| Deploy fail hua | App Runner console → Logs → Deployment logs |
| Jobs `AI_RATE_LIMITED` de rahe | Mistral account ki limit. `MISTRAL_API_KEYS` check karo |
| Jobs `AI_AUTH_FAILED` | Mistral key galat ya expire |
| Browser client block ho raha | Uska domain `CORS_ORIGINS` me add karo |

---

## 7. Sab kaise band karein

```powershell
$ARN = "arn:aws:apprunner:ap-south-1:397332850029:service/papersignal/667bba16f804404d9457da542b9bb068"

# 1. sabse pehle data bacha lo (agar chahiye)
aws dynamodb scan --table-name papersignal-jobs > jobs-backup.json
aws s3 sync s3://papersignal-uploads-397332850029/uploads/ ./pdf-backup/

# 2. App Runner -- yahi paisa kaat raha hai
aws apprunner delete-service --service-arn $ARN

# 3. baaki
aws s3 rm s3://papersignal-uploads-397332850029 --recursive
aws s3api delete-bucket --bucket papersignal-uploads-397332850029
aws dynamodb delete-table --table-name papersignal-jobs
aws dynamodb delete-table --table-name papersignal-api-keys
aws dynamodb delete-table --table-name papersignal-usage
aws ecr delete-repository --repository-name papersignal-api --force
aws iam delete-role-policy --role-name PaperSignalAppRunnerTask --policy-name PaperSignalDataAccess
aws iam delete-role --role-name PaperSignalAppRunnerTask
aws iam detach-role-policy --role-name PaperSignalAppRunnerECR --policy-arn arn:aws:iam::aws:policy/service-role/AWSAppRunnerServicePolicyForECRAccess
aws iam delete-role --role-name PaperSignalAppRunnerECR
```

Aakhir me **`deploy-user` ki access key delete kar dena** — uske paas `AdministratorAccess`
hai: IAM → Users → deploy-user → Security credentials → access key → Delete.

### Purana EC2 setup

Sab hat chuka hai — instance, Elastic IP, disk, security group. Ek cheez baaki hai:
**DuckDNS ka `papersignal.duckdns.org`** abhi bhi purani IP (`3.108.144.36`) par point karta
hai, jo AWS ne wapas le li hai aur kisi aur ko de sakta hai. duckdns.org par jaakar us domain
ko **delete** kar dena, warna purana link kisi anjaan server par khulega.

---

## 8. Abhi ki limits

`GET /api/health` par hamesha current values dikhti hain.

| Limit | Value |
|---|---|
| Ek batch me files | 10 |
| Har file | 200 MB |
| Har PDF | 50 pages |
| Ek saath process | 4 |
| Ek PDF ka time | ~2-4 second (50-page PDF ~50 second) |

---

## 9. Jo abhi bhi kaccha hai

Manager ko ye bhi bata dena, taaki baad me surprise na ho:

- **Uploaded PDFs 7 din baad delete ho jaati hain.** Business record chahiye to result apne
  system me save kar lena.
- **Malware scanning nahi hai** uploaded files par.
- **Mistral ka rate limit** hamare control me nahi. Wo block kare to jobs `AI_RATE_LIMITED`
  ke saath fail hoti hain — service theek hoti hai, provider nahi.
- **Load testing nahi hui.** Ek saath bahut saare users aayein to kya hoga, ye napa nahi gaya.
- **`deploy-user` ke paas `AdministratorAccess` hai** — demo ke liye theek, production ke liye
  usse kam karna chahiye.
