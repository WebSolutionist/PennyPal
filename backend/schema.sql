-- SQL Script to create the memories table in Supabase (Updated for Phase 4)
-- Run this in your Supabase SQL Editor

CREATE TABLE IF NOT EXISTS public.memories (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    session_id TEXT NOT NULL,
    category TEXT NOT NULL CHECK (category IN ('Goals', 'Habits & Behaviors', 'Feelings & Attitudes', 'Constraints & Facts', 'Action Plan Commitments')),
    content TEXT NOT NULL,
    importance INTEGER NOT NULL CHECK (importance >= 1 AND importance <= 5),
    emotional_tone TEXT DEFAULT 'neutral',
    mention_count INTEGER DEFAULT 1,
    is_active BOOLEAN DEFAULT TRUE NOT NULL,
    parent_memory_id UUID REFERENCES public.memories(id) ON DELETE SET NULL,
    last_session_seen TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- Index for fast lookups by session_id
CREATE INDEX IF NOT EXISTS memories_session_id_idx ON public.memories (session_id);
CREATE INDEX IF NOT EXISTS memories_active_idx ON public.memories (is_active);
