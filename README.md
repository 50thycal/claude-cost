# Claude Code Cost Tracker

Track estimated Claude Code usage costs based on your GitHub PR activity. Mobile-friendly dashboard with real-time webhook updates.

## Features

- **Estimates costs** from code changes (lines added/deleted, files changed)
- **Real-time updates** via GitHub webhooks
- **Mobile-friendly** dashboard designed for phone use
- **Model switching** - Compare costs across Sonnet, Opus, and Haiku
- **Time filtering** - Today, week, month, all-time views
- **PR details** - Click through to view each PR on GitHub

## How It Works

The app tracks PRs that have "claude" in the branch name or title (how Claude Code names its branches). It estimates costs using:

```
Input Tokens ≈ (files × 1000) + (lines changed × 2) + 5000 overhead
Output Tokens ≈ (lines added × 4) + 500 overhead
Cost = (input/1M × input_price) + (output/1M × output_price)
```

**Note:** These are estimates based on code output, not actual usage. Real costs depend on context read, conversation length, and thinking time.

---

## Setup Guide (10 minutes)

### Step 1: Create Supabase Project (Free)

1. Go to [supabase.com](https://supabase.com) and sign up/login
2. Click **New Project**
3. Name it `claude-costs` (or anything)
4. Set a database password (save it somewhere)
5. Choose a region close to you
6. Click **Create Project** and wait ~2 minutes

### Step 2: Set Up Database

1. In Supabase, go to **SQL Editor** (left sidebar)
2. Click **New Query**
3. Copy the contents of `supabase-schema.sql` from this repo
4. Click **Run** (or Cmd+Enter)
5. You should see "Success" message

### Step 3: Get Supabase Keys

1. Go to **Project Settings** → **API** (left sidebar)
2. Copy these values (you'll need them for Vercel):
   - **Project URL** (looks like `https://xxxxx.supabase.co`)
   - **service_role key** (the secret one, NOT anon)

### Step 4: Deploy to Vercel

1. Push this repo to your GitHub account (or fork it)
2. Go to [vercel.com](https://vercel.com) and sign up/login with GitHub
3. Click **Add New** → **Project**
4. Import your repo
5. Before deploying, add **Environment Variables**:
   - `SUPABASE_URL` = your Project URL from Step 3
   - `SUPABASE_SERVICE_KEY` = your service_role key from Step 3
6. Click **Deploy**
7. Wait ~1 minute, then note your deployment URL (e.g., `claude-costs.vercel.app`)

### Step 5: Set Up GitHub Webhook (Real-time Updates)

1. Go to your GitHub repo (any repo you want to track)
2. Go to **Settings** → **Webhooks** → **Add webhook**
3. Configure:
   - **Payload URL:** `https://your-vercel-url.vercel.app/api/webhook`
   - **Content type:** `application/json`
   - **Secret:** (leave blank for now)
   - **Events:** Select "Pull requests" only
4. Click **Add webhook**
5. Repeat for each repo you want to track

### Step 6: Initial Sync

1. Open your Vercel app URL in a browser
2. Click the **Sync** button
3. Wait while it fetches your existing Claude PRs
4. Done! New PRs will be tracked automatically via webhooks

---

## File Structure

```
├── index.html          # Main dashboard (static)
├── api/
│   ├── webhook.js      # GitHub webhook handler
│   ├── sync.js         # Manual sync endpoint
│   └── prs.js          # Fetch PRs endpoint
├── vercel.json         # Vercel configuration
├── package.json        # Dependencies
├── supabase-schema.sql # Database setup script
└── README.md           # This file
```

---

## Customization

### Change Tracked Username

Edit `api/sync.js` line 8:
```js
const GITHUB_USERNAME = '50thycal';  // Change this
```

### Adjust Cost Estimation

Edit the `ESTIMATION` object in `index.html`:
```js
const ESTIMATION = {
    tokensPerLineAdded: 4,      // Tokens per line of output
    contextTokensPerFile: 1000,  // Context per file touched
    baseOverheadTokens: 5000,    // Base conversation overhead
    outputOverheadTokens: 500    // Output overhead
};
```

### Update Pricing

Edit the `PRICING` object in `index.html`:
```js
const PRICING = {
    sonnet: { input: 3, output: 15, name: 'Claude Sonnet' },
    opus: { input: 15, output: 75, name: 'Claude Opus' },
    haiku: { input: 0.25, output: 1.25, name: 'Claude Haiku' }
};
```

---

## Troubleshooting

**"Connection error" on load**
- Check Vercel logs for API errors
- Verify environment variables are set correctly
- Make sure Supabase table was created

**No PRs showing after sync**
- PRs must have "claude" in branch name OR title
- Check GitHub API rate limits (60/hour for unauthenticated)
- Check Vercel function logs

**Webhook not triggering**
- Verify webhook URL is correct
- Check GitHub webhook delivery logs
- Ensure webhook is set to "Pull requests" events

---

## Local Development

```bash
# Install dependencies
npm install

# Run the Flask version (reads local Claude Code data)
python app.py

# For Vercel functions, use Vercel CLI
npm i -g vercel
vercel dev
```

---

## License

MIT - Do whatever you want with it.
