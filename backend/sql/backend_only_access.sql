-- Supabase deployment: only the trusted FastAPI database role accesses these
-- tables. Learner account ownership is enforced in the API, not by auth.uid().
-- This migration changes permissions and policies, never learner records.
DO $access$
DECLARE
    table_name text;
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'concept_check_app') THEN
        RAISE EXCEPTION 'Expected backend database role concept_check_app is missing';
    END IF;
    FOREACH table_name IN ARRAY ARRAY[
        'concepts', 'case_prompts', 'rubrics', 'sessions', 'messages', 'attempts',
        'gaps', 'criterion_assessments', 'interventions', 'attachments',
        'transcriptions', 'turn_idempotency', 'assessment_review_revisions',
        'case_review_revisions'
    ] LOOP
        IF to_regclass(format('public.%I', table_name)) IS NULL THEN
            RAISE EXCEPTION 'Expected application table % is missing', table_name;
        END IF;
        EXECUTE format('REVOKE ALL ON TABLE public.%I FROM PUBLIC, anon, authenticated', table_name);
        EXECUTE format('GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.%I TO concept_check_app', table_name);
        EXECUTE format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY', table_name);
        EXECUTE format('DROP POLICY IF EXISTS concept_check_backend_access ON public.%I', table_name);
        EXECUTE format('CREATE POLICY concept_check_backend_access ON public.%I FOR ALL TO concept_check_app USING (true) WITH CHECK (true)', table_name);
    END LOOP;
END
$access$;

-- Do not expose future tables created by either application table owner.
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public
    REVOKE ALL ON TABLES FROM PUBLIC, anon, authenticated;

-- The runtime owns users. The hosted migration role cannot SET ROLE to its
-- owner, so ensure_schema_columns enables that table's RLS as its owner on
-- application startup. users already has no anon/authenticated grants.
