import { kv } from '@vercel/kv';

export default async function handler(req, res) {
  // Only accept POST requests
  if (req.method !== 'POST') {
    return res.status(405).json({ error: 'Method not allowed' });
  }

  // Verify this is a GitHub webhook
  const event = req.headers['x-github-event'];

  if (event !== 'pull_request') {
    return res.status(200).json({ message: 'Ignored event: ' + event });
  }

  try {
    const payload = req.body;
    const action = payload.action;
    const pr = payload.pull_request;
    const repo = payload.repository;

    // Only process relevant events
    if (!['opened', 'closed', 'synchronize', 'reopened'].includes(action)) {
      return res.status(200).json({ message: 'Ignored action: ' + action });
    }

    // Check if this is a Claude PR
    const branchName = pr.head?.ref || '';
    const title = pr.title || '';

    const isClaudePR =
      branchName.toLowerCase().includes('claude') ||
      title.toLowerCase().includes('claude');

    if (!isClaudePR) {
      return res.status(200).json({ message: 'Not a Claude PR, ignored' });
    }

    // Fetch full PR details for additions/deletions
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

    // Store in Vercel KV
    await kv.hset(`pr:${pr.id}`, prData);
    await kv.sadd('claude_pr_ids', pr.id);

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
