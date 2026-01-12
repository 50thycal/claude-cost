import { createClient } from '@supabase/supabase-js';

const supabase = createClient(
  process.env.SUPABASE_URL,
  process.env.SUPABASE_SERVICE_KEY
);

export default async function handler(req, res) {
  // Set CORS headers
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');

  if (req.method === 'OPTIONS') {
    return res.status(200).end();
  }

  if (req.method !== 'GET') {
    return res.status(405).json({ error: 'Method not allowed' });
  }

  try {
    // Fetch all Claude PRs
    const { data, error } = await supabase
      .from('claude_prs')
      .select('*')
      .order('created_at', { ascending: false });

    if (error) {
      throw new Error('Database error: ' + error.message);
    }

    return res.status(200).json({
      success: true,
      prs: data || [],
      count: data?.length || 0
    });

  } catch (error) {
    console.error('Error fetching PRs:', error);
    return res.status(500).json({ error: error.message });
  }
}
