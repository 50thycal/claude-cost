import { kv } from '@vercel/kv';

const GITHUB_USERNAME = '50thycal';

export default async function handler(req, res) {
  // Set CORS headers
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');

  if (req.method === 'OPTIONS') {
    return res.status(200).end();
  }

  if (req.method !== 'POST' && req.method !== 'GET') {
    return res.status(405).json({ error: 'Method not allowed' });
  }

  try {
    // Fetch user's public repos
    const reposResponse = await fetch(
      `https://api.github.com/users/${GITHUB_USERNAME}/repos?per_page=100&sort=updated`,
      {
        headers: {
          'Accept': 'application/vnd.github.v3+json',
          'User-Agent': 'Claude-Cost-Tracker'
        }
      }
    );
    const repos = await reposResponse.json();

    if (!Array.isArray(repos)) {
      throw new Error('Failed to fetch repos: ' + JSON.stringify(repos));
    }

    let prsFound = 0;
    let processedRepos = 0;

    // For each repo, fetch PRs
    for (const repo of repos.slice(0, 30)) {
      try {
        const prsResponse = await fetch(
          `https://api.github.com/repos/${repo.full_name}/pulls?state=all&per_page=100`,
          {
            headers: {
              'Accept': 'application/vnd.github.v3+json',
              'User-Agent': 'Claude-Cost-Tracker'
            }
          }
        );
        const prs = await prsResponse.json();

        if (!Array.isArray(prs)) continue;

        // Filter for Claude PRs
        const claudePRs = prs.filter(pr =>
          pr.head?.ref?.toLowerCase().includes('claude') ||
          pr.title?.toLowerCase().includes('claude')
        );

        for (const pr of claudePRs) {
          // Get full PR details
          const prDetailResponse = await fetch(pr.url, {
            headers: {
              'Accept': 'application/vnd.github.v3+json',
              'User-Agent': 'Claude-Cost-Tracker'
            }
          });
          const prDetail = await prDetailResponse.json();

          const prData = {
            pr_id: pr.id,
            repo_name: repo.full_name,
            repo_owner: repo.owner.login,
            pr_number: pr.number,
            title: pr.title,
            branch: pr.head?.ref,
            state: pr.state,
            additions: prDetail.additions || 0,
            deletions: prDetail.deletions || 0,
            changed_files: prDetail.changed_files || 0,
            created_at: pr.created_at,
            updated_at: pr.updated_at,
            merged_at: pr.merged_at,
            pr_url: pr.html_url,
            user_login: pr.user?.login
          };

          // Store PR in KV
          await kv.hset(`pr:${pr.id}`, prData);
          await kv.sadd('claude_pr_ids', pr.id);

          prsFound++;
        }

        processedRepos++;
      } catch (e) {
        console.error(`Error processing repo ${repo.full_name}:`, e);
      }
    }

    return res.status(200).json({
      success: true,
      repos_processed: processedRepos,
      prs_found: prsFound,
      synced_at: new Date().toISOString()
    });

  } catch (error) {
    console.error('Sync error:', error);
    return res.status(500).json({ error: error.message });
  }
}
