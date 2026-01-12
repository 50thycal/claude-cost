import { kv } from '@vercel/kv';

export default async function handler(req, res) {
  // Set CORS headers
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, OPTIONS');

  if (req.method === 'OPTIONS') {
    return res.status(200).end();
  }

  if (req.method !== 'GET') {
    return res.status(405).json({ error: 'Method not allowed' });
  }

  try {
    // Get all PRs from KV (stored as a hash map by pr_id)
    const prIds = await kv.smembers('claude_pr_ids') || [];

    if (prIds.length === 0) {
      return res.status(200).json({ success: true, prs: [], count: 0 });
    }

    // Fetch all PR data
    const prs = [];
    for (const prId of prIds) {
      const pr = await kv.hgetall(`pr:${prId}`);
      if (pr) {
        prs.push(pr);
      }
    }

    // Sort by created_at descending
    prs.sort((a, b) => new Date(b.created_at) - new Date(a.created_at));

    return res.status(200).json({
      success: true,
      prs,
      count: prs.length
    });

  } catch (error) {
    console.error('Error fetching PRs:', error);
    return res.status(500).json({ error: error.message });
  }
}
