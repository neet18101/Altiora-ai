-- ================================================================
-- Altiora AI - Business Configuration Schema Migration
-- Run this in Supabase SQL Editor
-- ================================================================

-- ================================
-- Business Services Table
-- Services offered by the business
-- ================================
CREATE TABLE IF NOT EXISTS business_services (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  business_id UUID REFERENCES businesses(id) ON DELETE CASCADE NOT NULL,
  name VARCHAR(255) NOT NULL,
  description TEXT,
  duration_mins INTEGER DEFAULT 30,
  price DECIMAL(10, 2),
  is_active BOOLEAN DEFAULT true,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Index for faster lookups
CREATE INDEX IF NOT EXISTS idx_business_services_business_id ON business_services(business_id);

-- ================================
-- Business FAQs Table
-- Predefined Q&A for AI responses
-- ================================
CREATE TABLE IF NOT EXISTS business_faqs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  business_id UUID REFERENCES businesses(id) ON DELETE CASCADE NOT NULL,
  question TEXT NOT NULL,
  answer TEXT NOT NULL,
  category VARCHAR(100) DEFAULT 'General',
  keywords TEXT[], -- Array of keywords for matching
  priority INTEGER DEFAULT 0, -- Higher priority = shown first
  is_active BOOLEAN DEFAULT true,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Index for faster lookups
CREATE INDEX IF NOT EXISTS idx_business_faqs_business_id ON business_faqs(business_id);
CREATE INDEX IF NOT EXISTS idx_business_faqs_category ON business_faqs(category);

-- ================================
-- Business Working Hours Table
-- Weekly schedule for availability
-- ================================
CREATE TABLE IF NOT EXISTS business_hours (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  business_id UUID REFERENCES businesses(id) ON DELETE CASCADE NOT NULL,
  day_of_week INTEGER NOT NULL CHECK (day_of_week >= 0 AND day_of_week <= 6), -- 0=Sunday, 6=Saturday
  open_time TIME,
  close_time TIME,
  is_closed BOOLEAN DEFAULT false,
  is_24_hours BOOLEAN DEFAULT false,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(business_id, day_of_week)
);

-- Index for faster lookups
CREATE INDEX IF NOT EXISTS idx_business_hours_business_id ON business_hours(business_id);

-- ================================
-- Call Behavior Rules Table
-- Escalation and transfer logic
-- ================================
CREATE TABLE IF NOT EXISTS call_rules (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  business_id UUID REFERENCES businesses(id) ON DELETE CASCADE NOT NULL,
  agent_id UUID REFERENCES ai_agents(id) ON DELETE CASCADE,
  name VARCHAR(255) NOT NULL,
  description TEXT,
  rule_type VARCHAR(50) NOT NULL CHECK (rule_type IN ('escalation', 'transfer', 'voicemail', 'callback', 'custom')),
  trigger_condition JSONB NOT NULL DEFAULT '{}',
  -- Example: {"keywords": ["speak to human", "manager"], "sentiment": "frustrated", "max_duration_secs": 300}
  action JSONB NOT NULL DEFAULT '{}',
  -- Example: {"type": "transfer", "transfer_to": "+1234567890", "message": "Transferring you now..."}
  priority INTEGER DEFAULT 0, -- Higher priority rules evaluated first
  is_active BOOLEAN DEFAULT true,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Index for faster lookups
CREATE INDEX IF NOT EXISTS idx_call_rules_business_id ON call_rules(business_id);
CREATE INDEX IF NOT EXISTS idx_call_rules_agent_id ON call_rules(agent_id);
CREATE INDEX IF NOT EXISTS idx_call_rules_type ON call_rules(rule_type);

-- ================================
-- Add role column to profiles
-- For RBAC (Role-Based Access Control)
-- ================================
ALTER TABLE profiles ADD COLUMN IF NOT EXISTS role VARCHAR(50) DEFAULT 'user';
-- Roles: 'super_admin', 'business_admin', 'user'

-- ================================
-- Business Settings/Branding
-- Extended business configuration
-- ================================
ALTER TABLE businesses ADD COLUMN IF NOT EXISTS logo_url TEXT;
ALTER TABLE businesses ADD COLUMN IF NOT EXISTS primary_color VARCHAR(7) DEFAULT '#8B5CF6';
ALTER TABLE businesses ADD COLUMN IF NOT EXISTS tagline VARCHAR(255);
ALTER TABLE businesses ADD COLUMN IF NOT EXISTS support_email VARCHAR(255);
ALTER TABLE businesses ADD COLUMN IF NOT EXISTS support_phone VARCHAR(50);

-- ================================
-- Enable RLS (Row Level Security)
-- ================================
ALTER TABLE business_services ENABLE ROW LEVEL SECURITY;
ALTER TABLE business_faqs ENABLE ROW LEVEL SECURITY;
ALTER TABLE business_hours ENABLE ROW LEVEL SECURITY;
ALTER TABLE call_rules ENABLE ROW LEVEL SECURITY;

-- ================================
-- RLS Policies
-- Users can only access their own business data
-- ================================

-- Business Services Policies
CREATE POLICY "Users can view own business services" ON business_services
  FOR SELECT USING (
    business_id IN (
      SELECT id FROM businesses WHERE owner_id = auth.uid()
      UNION
      SELECT business_id FROM business_members WHERE user_id = auth.uid()
    )
  );

CREATE POLICY "Business owners can manage services" ON business_services
  FOR ALL USING (
    business_id IN (SELECT id FROM businesses WHERE owner_id = auth.uid())
  );

-- Business FAQs Policies
CREATE POLICY "Users can view own business faqs" ON business_faqs
  FOR SELECT USING (
    business_id IN (
      SELECT id FROM businesses WHERE owner_id = auth.uid()
      UNION
      SELECT business_id FROM business_members WHERE user_id = auth.uid()
    )
  );

CREATE POLICY "Business owners can manage faqs" ON business_faqs
  FOR ALL USING (
    business_id IN (SELECT id FROM businesses WHERE owner_id = auth.uid())
  );

-- Business Hours Policies
CREATE POLICY "Users can view own business hours" ON business_hours
  FOR SELECT USING (
    business_id IN (
      SELECT id FROM businesses WHERE owner_id = auth.uid()
      UNION
      SELECT business_id FROM business_members WHERE user_id = auth.uid()
    )
  );

CREATE POLICY "Business owners can manage hours" ON business_hours
  FOR ALL USING (
    business_id IN (SELECT id FROM businesses WHERE owner_id = auth.uid())
  );

-- Call Rules Policies
CREATE POLICY "Users can view own call rules" ON call_rules
  FOR SELECT USING (
    business_id IN (
      SELECT id FROM businesses WHERE owner_id = auth.uid()
      UNION
      SELECT business_id FROM business_members WHERE user_id = auth.uid()
    )
  );

CREATE POLICY "Business owners can manage call rules" ON call_rules
  FOR ALL USING (
    business_id IN (SELECT id FROM businesses WHERE owner_id = auth.uid())
  );

-- ================================
-- Helper function: Check if user is business admin
-- ================================
CREATE OR REPLACE FUNCTION is_business_admin(business_uuid UUID)
RETURNS BOOLEAN AS $$
BEGIN
  RETURN EXISTS (
    SELECT 1 FROM businesses WHERE id = business_uuid AND owner_id = auth.uid()
  ) OR EXISTS (
    SELECT 1 FROM business_members 
    WHERE business_id = business_uuid AND user_id = auth.uid() AND role = 'admin'
  );
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- ================================
-- Helper function: Check if user is super admin
-- ================================
CREATE OR REPLACE FUNCTION is_super_admin()
RETURNS BOOLEAN AS $$
BEGIN
  RETURN EXISTS (
    SELECT 1 FROM profiles WHERE id = auth.uid() AND role = 'super_admin'
  );
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;
