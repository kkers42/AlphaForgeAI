# AlphaForgeAI News Pipeline — n8n Setup Guide

## What Was Created

`n8n/news_pipeline.json` — an importable n8n workflow that:

- Runs **twice daily** at 13:00 UTC and 22:00 UTC (~8 AM and 6 PM Eastern)
- Pulls from **8 RSS feeds**: CoinDesk, Cointelegraph, The Block, Decrypt, Bitcoin Magazine, Coinbase Blog, Binance Blog, Kraken Blog
- **Deduplicates** by URL across runs (persisted in n8n workflow static data — no database needed)
- Sends all new articles to **OpenAI** (`gpt-4o-mini`) for scoring, summarising, and classifying
- Filters to articles with **relevance score ≥ 7**
- **POSTs approved articles** to `AlphaForgeAI /api/news/ingest`
- Generates a **X.com post** for the top 1–3 stories (calm, professional, no financial advice)
- **Posts to X.com** via OAuth2

---

## Step 1 — Import the Workflow

1. Open your n8n instance at `n8n.snowportal.cloud`
2. Go to **Workflows → Import from File**
3. Select `n8n/news_pipeline.json`
4. The workflow imports as **inactive** — do not activate until credentials are wired

---

## Step 2 — Credentials to Configure

You need **three credentials** in n8n's Credentials manager.

### 2a — OpenAI (already exists)

1. Go to **Credentials → Search "OpenAI"**
2. Find your existing OpenAI credential — note the **credential ID** (shown in the URL when you open it, e.g. `/credentials/7`)
3. In the imported workflow, open both **"OpenAI: Analyze Articles"** and **"OpenAI: Generate X Post"** nodes
4. In each node → Credential dropdown → select your existing OpenAI credential
5. _(The JSON has `REPLACE_WITH_YOUR_OPENAI_CRED_ID` as a placeholder — selecting in the UI replaces it)_

### 2b — AlphaForgeAI API Key (Header Auth — NEW)

This is the `NEWS_INGEST_API_KEY` that protects the `/api/news/ingest` endpoint.

**Generate a key on the server:**
```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

**Add it to the Cloud Run service** (in GCP Console or via gcloud):
```bash
gcloud run services update alphaforgeai \
  --update-env-vars NEWS_INGEST_API_KEY=<your-generated-key> \
  --region us-central1
```

**Create the n8n credential:**
1. Go to n8n → **Credentials → New → "Header Auth"**
2. Name: `AlphaForgeAI News API Key`
3. Name field: `Authorization`
4. Value field: `Bearer <your-generated-key>`
5. Save
6. Open the **"AlphaForgeAI: Ingest News"** node → select this credential

### 2c — X.com / Twitter OAuth2 (NEW)

1. Go to [developer.twitter.com](https://developer.twitter.com) → your app → **User authentication settings**
2. Enable **OAuth 2.0** with Read+Write permissions, App type: Web App
3. Set callback URL to: `https://n8n.snowportal.cloud/rest/oauth2-credential/callback`
4. Note your **Client ID** and **Client Secret**
5. In n8n → **Credentials → New → "X (Twitter) OAuth2 API"**
6. Paste Client ID + Client Secret → Connect (will open OAuth flow)
7. Name it: `X account`
8. Open the **"X: Post to X.com"** node → select this credential

---

## Step 3 — Verify the AlphaForgeAI URL

Open the **"AlphaForgeAI: Ingest News"** node. The URL is set to:
```
https://alphaforgeai.io/api/news/ingest
```
Update this to match your live Cloud Run URL if it differs.

---

## Step 4 — Activate the Workflow

Once all three credentials are connected:
1. Toggle the workflow to **Active**
2. It will fire at the next scheduled time (13:00 or 22:00 UTC)

---

## Manual Test Instructions

### Test 1 — Dry run (no external posts)

Before activating, test the first half manually:

1. In the workflow, **temporarily disable** the last two nodes:
   - Right-click **"X: Post to X.com"** → Disable
   - Right-click **"OpenAI: Generate X Post"** → Disable (optional, saves cost)
2. Click **"Execute Workflow"** (▶ button)
3. Watch each node execute. Check:
   - "Parse RSS + Deduplicate" output: should show `count > 0`
   - "Parse + Filter Qualified" output: should show scored articles
   - "AlphaForgeAI: Ingest News" output: should return `{"accepted": true, ...}`
4. Visit `https://alphaforgeai.io/news` — articles should appear

### Test 2 — Full run including X post

1. Re-enable the X and OpenAI nodes
2. Click **"Execute Workflow"** again
3. Check "Extract Tweet Text" output: shows the generated tweet
4. Check "X: Post to X.com" output: shows `id` of the posted tweet
5. Verify the tweet appears on the AlphaForgeAI X account

### Test 3 — Deduplication

Run the workflow a second time immediately. The "Parse RSS + Deduplicate" node should report `count: 0` (all URLs already seen). No OpenAI call is made. No X post is made. The execution stops cleanly after dedup.

---

## Tuning

| Parameter | Location | Default | Notes |
|---|---|---|---|
| Schedule times | "Schedule: Twice Daily" node | 13:00 + 22:00 UTC | Adjust cron: `0 14,21 * * *` for different times |
| Relevance threshold | "Parse + Filter Qualified" node, line `>= 7` | 7 | Raise to 8 for fewer, higher-quality articles |
| Article batch cap | "Prepare OpenAI Prompt" node, `.slice(0, 40)` | 40 | Reduce to lower OpenAI cost |
| Max seen URL history | "Parse RSS + Deduplicate" node, `.slice(-2000)` | 2000 | Keeps ~2-3 months of history |
| Tweet character limit | "Extract Tweet Text" node | 275 | X hard limit is 280; 275 gives margin |
| RSS feeds | "Define RSS Feeds" node | 8 feeds | Add/remove feed objects as needed |

---

## Estimated OpenAI Cost

- `gpt-4o-mini` is very cheap: ~$0.15 / 1M input tokens
- Typical run: 40 articles × ~300 tokens each = ~12,000 tokens input
- Cost per run: **~$0.002 USD** (~$0.004/day, ~$1.40/year)

---

## What Requires Manual Setup (Summary)

| Item | Status | Action Required |
|---|---|---|
| OpenAI credential | ✅ Already in n8n | Re-select in both OpenAI nodes after import |
| `NEWS_INGEST_API_KEY` | ❌ Need to generate + deploy | Generate key, set in Cloud Run, create Header Auth cred in n8n |
| `GCS_NEWS_BUCKET` | ❌ Need to create | Create `alphaforgeai-news` bucket in GCP; grant Cloud Run SA `objectAdmin` |
| X OAuth2 credential | ❌ Need to create | Set up X dev app + OAuth2 flow in n8n |
| AlphaForgeAI URL | ⚠️ Check | Confirm `https://alphaforgeai.io` is the live URL in the ingest node |
| Workflow active | ❌ Off by default | Activate after all credentials are connected |

---

## GCS Bucket Setup (one-time)

```bash
# Create the news bucket
gsutil mb -p <your-gcp-project> -l us-central1 gs://alphaforgeai-news

# Grant Cloud Run service account access
gsutil iam ch serviceAccount:<cloud-run-sa>@<project>.iam.gserviceaccount.com:objectAdmin gs://alphaforgeai-news
```

Replace `<cloud-run-sa>` and `<project>` with your GCP values. The SA is likely the same one that already has access to `alphaforgeai-explainers`.
