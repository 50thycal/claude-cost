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
      const token = await kv.get('github_token');
      return res.status(200).json({
        success: true,
        settings: {
          github_username: username || '',
          github_token: token ? '••••••••' : '' // Mask token for security
        }
      });
    }

    if (req.method === 'POST') {
      // Update settings
      const { github_username, github_token } = req.body;

      if (github_username !== undefined) {
        if (github_username) {
          await kv.set('github_username', github_username);
        } else {
          await kv.del('github_username');
        }
      }

      if (github_token !== undefined) {
        if (github_token && github_token !== '••••••••') {
          await kv.set('github_token', github_token);
        } else if (github_token === '') {
          await kv.del('github_token');
        }
        // If token is '••••••••', keep existing token (no change)
      }

      const currentToken = await kv.get('github_token');
      return res.status(200).json({
        success: true,
        settings: {
          github_username: github_username || '',
          github_token: currentToken ? '••••••••' : ''
        }
      });
    }

    return res.status(405).json({ error: 'Method not allowed' });

  } catch (error) {
    console.error('Settings error:', error);
    return res.status(500).json({ error: error.message });
  }
}
