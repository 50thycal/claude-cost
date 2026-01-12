-- Supabase SQL Schema for Claude Code Cost Tracker
-- Run this in your Supabase SQL Editor (supabase.com > Your Project > SQL Editor)

-- Create the claude_prs table
CREATE TABLE IF NOT EXISTS claude_prs (
    id BIGSERIAL PRIMARY KEY,
    pr_id BIGINT UNIQUE NOT NULL,
    repo_name TEXT NOT NULL,
    repo_owner TEXT,
    pr_number INTEGER NOT NULL,
    title TEXT,
    branch TEXT,
    state TEXT,
    additions INTEGER DEFAULT 0,
    deletions INTEGER DEFAULT 0,
    changed_files INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ,
    merged_at TIMESTAMPTZ,
    pr_url TEXT,
    user_login TEXT,
    inserted_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create index for faster queries
CREATE INDEX IF NOT EXISTS idx_claude_prs_created_at ON claude_prs(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_claude_prs_repo_name ON claude_prs(repo_name);

-- Enable Row Level Security (optional but recommended)
ALTER TABLE claude_prs ENABLE ROW LEVEL SECURITY;

-- Create a policy that allows all operations (since this is a personal tracker)
-- For multi-user support, you'd want more restrictive policies
CREATE POLICY "Allow all operations" ON claude_prs
    FOR ALL
    USING (true)
    WITH CHECK (true);

-- Grant access to the anon role (used by the public API)
GRANT ALL ON claude_prs TO anon;
GRANT USAGE, SELECT ON SEQUENCE claude_prs_id_seq TO anon;
