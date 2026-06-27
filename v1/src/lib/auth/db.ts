// Re-exports the auth-managed Postgres pool + role type so route handlers and server
// helpers can share the same connection without reaching out of src/ via a long relative
// import. auth.ts lives at v1/auth.ts (next to next-auth); it owns the pool singleton.
export { getAuthPool, type SagadRole } from "../../../auth";
