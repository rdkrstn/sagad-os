-- Heal existing deploys where 0010 created model_provider_config.updated_by as UUID.
--
-- users.id is SERIAL (INTEGER) in 0001_sagad_foundation.sql, so the trusted-context user_id
-- (users.id::text, e.g. "6") bound into a UUID updated_by column raised
-- `psycopg.errors.InvalidTextRepresentation: invalid input syntax for type uuid: "6"`
-- on every DB-backed PUT /model-providers (parameter $5 = updated_by). 0010 is fixed for
-- fresh deploys; this migration repairs tables that already exist with the wrong type.
--
-- Idempotent + data-safe: the ALTER only fires when the column is still UUID, so a fresh
-- deploy (0010 already created it as INTEGER) is a no-op and existing updated_by values
-- are preserved. No rows could have been stored under the bug (every upsert failed), so
-- the USING (NULL::integer) discard is harmless on the UUID -> INTEGER transition.

DO $$
BEGIN
  IF EXISTS (
    SELECT 1
    FROM information_schema.columns
    WHERE table_name = 'model_provider_config'
      AND column_name = 'updated_by'
      AND data_type = 'uuid'
  ) THEN
    ALTER TABLE model_provider_config
      ALTER COLUMN updated_by TYPE INTEGER USING (NULL::integer);
  END IF;
END $$;