import { createClient } from '@supabase/supabase-js';

// Initialize Supabase client
const supabase = createClient(
  process.env.SUPABASE_URL,
  process.env.SUPABASE_SERVICE_KEY
);

export default async function handler(req, res) {
  // Only accept POST requests
  if (req.method !== 'POST') {
    return res.status(405).json({ error: 'Method not allowed' });
  }

  // Verify this is a GitHub webhook (optional: add secret verification)
  const event = req.headers['x-github-event'];

  if (event !== 'pull_request') {
    return res.status(200).json({ message: 'Ignored event: ' + event });
  }

  try {
    const payload = req.body;
    const action = payload.action;
    const pr = payload.pull_request;
    const repo = payload.repository;

    // Only process opened, closed, or synchronize events
    if (!['opened', 'closed', 'synchronize', 'reopened'].includes(action)) {
      return res.status(200).json({ message: 'Ignored action: ' + action });
    }

    // Check if this is a Claude PR (branch name or title contains 'claude')
    const branchName = pr.head?.ref || '';
    const title = pr.title || '';

    const isClaudePR =
      branchName.toLowerCase().includes('claude') ||
      title.toLowerCase().includes('claude');

    if (!isClaudePR) {
      return res.status(200).json({ message: 'Not a Claude PR, ignored' });
    }

    // Fetch full PR details to get additions/deletions
    const prDetailsResponse = await fetch(pr.url, {
      headers: {
        'Accept': 'application/vnd.github.v3+json',
        'User-Agent': 'Claude-Cost-Tracker'
      }
    });
    const prDetails = await prDetailsResponse.json();

    // Prepare PR data
    const prData = {
      pr_id: pr.id,
      repo_name: repo.full_name,
      repo_owner: repo.owner.login,
      pr_number: pr.number,
      title: pr.title,
      branch: branchName,
      state: pr.state,
      additions: prDetails.additions || 0,
      deletions: prDetails.deletions || 0,
      changed_files: prDetails.changed_files || 0,
      created_at: pr.created_at,
      updated_at: pr.updated_at,
      merged_at: pr.merged_at,
      pr_url: pr.html_url,
      user_login: pr.user?.login
    };

    // Upsert to Supabase
    const { error } = await supabase
      .from('claude_prs')
      .upsert(prData, { onConflict: 'pr_id' });

    if (error) {
      console.error('Supabase error:', error);
      return res.status(500).json({ error: 'Database error', details: error.message });
    }

    console.log(`Processed PR #${pr.number} from ${repo.full_name}: ${action}`);

    return res.status(200).json({
      success: true,
      action,
      pr_id: pr.id,
      repo: repo.full_name
    });

  } catch (error) {
    console.error('Webhook error:', error);
    return res.status(500).json({ error: 'Internal server error', details: error.message });
  }
}
