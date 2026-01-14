import { kv } from '@vercel/kv';

// Helper to build headers with optional auth token
function getHeaders(token) {
  const headers = {
    'Accept': 'application/vnd.github.v3+json',
    'User-Agent': 'Claude-Cost-Tracker'
  };
  if (token) {
    headers['Authorization'] = `token ${token}`;
  }
  return headers;
}

// Helper to check rate limit from response headers
function checkRateLimit(response) {
  const remaining = parseInt(response.headers.get('x-ratelimit-remaining') || '999');
  const resetTime = parseInt(response.headers.get('x-ratelimit-reset') || '0');
  const limit = parseInt(response.headers.get('x-ratelimit-limit') || '60');

  return {
    remaining,
    resetTime,
    limit,
    isLimited: remaining <= 0
  };
}

// Helper to parse Link header for pagination
function getNextPageUrl(response) {
  const linkHeader = response.headers.get('link');
  if (!linkHeader) return null;

  const links = linkHeader.split(',');
  for (const link of links) {
    const match = link.match(/<([^>]+)>;\s*rel="next"/);
    if (match) return match[1];
  }
  return null;
}

// Fetch all pages from a paginated GitHub endpoint
async function fetchAllPages(url, headers, maxPages = 50) {
  const allItems = [];
  let currentUrl = url;
  let pageCount = 0;

  while (currentUrl && pageCount < maxPages) {
    const response = await fetch(currentUrl, { headers });

    // Check rate limit
    const rateLimit = checkRateLimit(response);
    if (rateLimit.isLimited) {
      const resetDate = new Date(rateLimit.resetTime * 1000);
      throw new Error(`GitHub API rate limit exceeded. Resets at ${resetDate.toISOString()}. Consider adding a GitHub token for higher limits (5000/hour vs 60/hour).`);
    }

    if (!response.ok) {
      const errorBody = await response.text();
      throw new Error(`GitHub API error (${response.status}): ${errorBody}`);
    }

    const data = await response.json();
    if (!Array.isArray(data)) {
      throw new Error('Unexpected response format: ' + JSON.stringify(data));
    }

    allItems.push(...data);
    currentUrl = getNextPageUrl(response);
    pageCount++;
  }

  return allItems;
}

// Check if a PR is a Claude PR based on branch, title, or author
function isClaudePR(pr) {
  const branch = pr.head?.ref?.toLowerCase() || '';
  const title = pr.title?.toLowerCase() || '';
  const author = pr.user?.login?.toLowerCase() || '';

  // Check branch name for 'claude'
  if (branch.includes('claude')) return true;

  // Check title for 'claude'
  if (title.includes('claude')) return true;

  // Check if author contains 'claude' (e.g., 'claude[bot]', 'claude-dev', etc.)
  if (author.includes('claude')) return true;

  return false;
}

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
    // Get username from query params, body, or stored setting
    let username = req.query.username || req.body?.username;

    // If no username provided, try to get from stored settings
    if (!username) {
      username = await kv.get('github_username');
    }

    if (!username) {
      return res.status(400).json({
        error: 'No GitHub username configured. Please set it in settings.'
      });
    }

    // Store the username for future use
    await kv.set('github_username', username);

    // Get optional GitHub token for higher rate limits
    const token = await kv.get('github_token');
    const headers = getHeaders(token);

    // Track sync progress
    const syncProgress = {
      repos_found: 0,
      repos_processed: 0,
      prs_found: 0,
      claude_prs_found: 0,
      rate_limit_remaining: null,
      rate_limit_limit: null,
      errors: []
    };

    // Fetch ALL user's public repos with pagination
    console.log(`Fetching repos for user: ${username}`);
    const repos = await fetchAllPages(
      `https://api.github.com/users/${username}/repos?per_page=100&sort=updated`,
      headers
    );

    syncProgress.repos_found = repos.length;
    console.log(`Found ${repos.length} repos`);

    // Process ALL repos (no more 30 repo limit!)
    for (const repo of repos) {
      try {
        // Fetch ALL PRs for this repo with pagination
        const prs = await fetchAllPages(
          `https://api.github.com/repos/${repo.full_name}/pulls?state=all&per_page=100`,
          headers
        );

        syncProgress.prs_found += prs.length;

        // Filter for Claude PRs using expanded detection
        const claudePRs = prs.filter(isClaudePR);

        for (const pr of claudePRs) {
          // Get full PR details for additions/deletions/changed_files
          const prDetailResponse = await fetch(pr.url, { headers });

          // Check rate limit on each request
          const rateLimit = checkRateLimit(prDetailResponse);
          syncProgress.rate_limit_remaining = rateLimit.remaining;
          syncProgress.rate_limit_limit = rateLimit.limit;

          if (rateLimit.isLimited) {
            const resetDate = new Date(rateLimit.resetTime * 1000);
            throw new Error(`Rate limit exceeded. Resets at ${resetDate.toISOString()}`);
          }

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

          syncProgress.claude_prs_found++;
        }

        syncProgress.repos_processed++;

        // Log progress every 10 repos
        if (syncProgress.repos_processed % 10 === 0) {
          console.log(`Progress: ${syncProgress.repos_processed}/${repos.length} repos, ${syncProgress.claude_prs_found} Claude PRs found`);
        }
      } catch (e) {
        console.error(`Error processing repo ${repo.full_name}:`, e);
        syncProgress.errors.push({
          repo: repo.full_name,
          error: e.message
        });

        // If rate limited, stop processing
        if (e.message.includes('rate limit')) {
          break;
        }
      }
    }

    return res.status(200).json({
      success: true,
      repos_found: syncProgress.repos_found,
      repos_processed: syncProgress.repos_processed,
      total_prs_scanned: syncProgress.prs_found,
      claude_prs_found: syncProgress.claude_prs_found,
      rate_limit: {
        remaining: syncProgress.rate_limit_remaining,
        limit: syncProgress.rate_limit_limit,
        has_token: !!token
      },
      errors: syncProgress.errors.length > 0 ? syncProgress.errors : undefined,
      synced_at: new Date().toISOString()
    });

  } catch (error) {
    console.error('Sync error:', error);
    return res.status(500).json({
      error: error.message,
      hint: error.message.includes('rate limit')
        ? 'Add a GitHub Personal Access Token in settings for 5000 requests/hour instead of 60.'
        : undefined
    });
  }
}
