import { kv } from '@vercel/kv';

export default async function handler(req, res) {
  // Set CORS headers
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');

  if (req.method === 'OPTIONS') {
    return res.status(200).end();
  }

  try {
    if (req.method === 'GET') {
      // Get current settings
      const username = await kv.get('github_username');
      return res.status(200).json({
        success: true,
        settings: {
          github_username: username || ''
        }
      });
    }

    if (req.method === 'POST') {
      // Update settings
      const { github_username } = req.body;

      if (github_username !== undefined) {
        if (github_username) {
          await kv.set('github_username', github_username);
        } else {
          await kv.del('github_username');
        }
      }

      return res.status(200).json({
        success: true,
        settings: {
          github_username: github_username || ''
        }
      });
    }

    return res.status(405).json({ error: 'Method not allowed' });

  } catch (error) {
    console.error('Settings error:', error);
    return res.status(500).json({ error: error.message });
  }
}
