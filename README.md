# Claude Code Cost Tracker

Track estimated Claude Code usage costs based on your GitHub PR activity. Mobile-friendly dashboard with real-time webhook updates.

## Features

- **Estimates costs** from code changes (lines added/deleted, files changed)
- **Real-time updates** via GitHub webhooks
- **Mobile-friendly** dashboard designed for phone use
- **Model switching** - Compare costs across Sonnet, Opus, and Haiku
- **Time filtering** - Today, week, month, all-time views
- **Uses Vercel KV** - No external database needed

## How It Works

The app tracks PRs that have "claude" in the branch name or title. It estimates costs using:

```
Input Tokens ≈ (files × 1000) + (lines changed × 2) + 5000 overhead
Output Tokens ≈ (lines added × 4) + 500 overhead
Cost = (input/1M × input_price) + (output/1M × output_price)
```

**Note:** These are estimates based on code output, not actual usage.

---

## Setup (5 minutes)

### Step 1: Deploy to Vercel

1. Push this repo to your GitHub
2. Go to [vercel.com](https://vercel.com) → **Add New** → **Project**
3. Import your repo
4. Deploy (KV is already configured on your account)

### Step 2: Set Up GitHub Webhooks

For each repo you want to track:

1. Go to repo **Settings** → **Webhooks** → **Add webhook**
2. Configure:
   - **Payload URL:** `https://your-app.vercel.app/api/webhook`
   - **Content type:** `application/json`
   - **Events:** Select "Pull requests" only
3. Click **Add webhook**

### Step 3: Initial Sync

1. Open your Vercel app URL
2. Click **Sync** to fetch existing PRs
3. Done! New PRs auto-tracked via webhooks

---

## File Structure

```
├── index.html          # Mobile dashboard
├── api/
│   ├── webhook.js      # GitHub webhook handler
│   ├── sync.js         # Manual sync endpoint
│   └── prs.js          # Fetch PRs endpoint
├── vercel.json         # Vercel config
└── package.json        # Dependencies (@vercel/kv)
```

---

## Customization

### Change Tracked Username

Edit `api/sync.js` line 3:
```js
const GITHUB_USERNAME = '50thycal';  // Change this
```

### Adjust Estimation

Edit `ESTIMATION` in `index.html`:
```js
const ESTIMATION = {
    tokensPerLineAdded: 4,
    contextTokensPerFile: 1000,
    baseOverheadTokens: 5000,
    outputOverheadTokens: 500
};
```

---

## Troubleshooting

**"Connection error"**
- Check Vercel function logs
- Ensure KV is connected to your project

**No PRs after sync**
- PRs must have "claude" in branch name OR title
- Check GitHub API rate limits

**Webhook not working**
- Check webhook delivery logs in GitHub
- Verify URL matches your deployment

---

## License

MIT
