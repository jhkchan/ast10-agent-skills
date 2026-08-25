Your current audit-logging design has several strong elements that align with AST09 principles, such as immutable append-only logging, correction handling, timestamping, and backups. However, it does not yet meet full compliance-grade audit evidence standards under AST09. Here’s what’s missing:

1. **Immutable Log Storage**: While writes go through an append-only trigger, Postgres tables alone are not inherently tamper-proof. AST09 requires immutable logs that prevent deletion or modification even by administrators. Your trigger can be bypassed or altered if database privileges are escalated. To comply, you must use write-once, read-many (WORM) storage, or a dedicated log service with cryptographic integrity (e.g., hashed log chains or integration with a secure audit trail system).

2. **Correction Integrity**: While correction rows are allowed, AST09 requires that original entries remain unaltered and that corrections be strictly traceable. You must ensure that correction rows:
   - Reference the original erroneous row (e.g., via foreign key or unique ID).
   - Include the reason code, actor (who made the correction), and timestamp.
   - Are themselves immutable and append-only.
   Without these, the audit trail lacks integrity and non-repudiation.

3. **Authentication and Authorization Controls**: AST09 mandates that log creation and correction actions are tied to authenticated identities. You must confirm that:
   - `agent_id` is derived from authenticated, uniquely identifiable actors.
   - Access to the logging mechanism (including correction) is strictly role-based and logged separately.
   - Administrative or platform-level access is monitored and limited.

4. **Log Completeness and Verifiability**: The five captured fields are reasonable, but AST09 expects logs to support reconstruction of events. You should assess whether missing context (e.g., input parameters, session ID, target resource, or environment) could undermine forensic analysis. While not always required, richer context strengthens compliance.

5. **Retention and Backup Integrity**: Nightly backups are insufficient under AST09. Backups must be:
   - Encrypted and integrity-protected.
   - Regularly tested for restorability.
   - Retained in accordance with policy (400 days may be acceptable, but confirm it meets regulatory minimums for your domain).
   Without protected, verifiable backups, the audit log may be deemed unreliable.

6. **Monitoring and Alerting**: AST09 expects active monitoring of the logging system. You must demonstrate:
   - Alerts for logging failures or anomalies.
   - Regular review of log completeness and system health.

In summary: your design is strong but not yet compliance-grade. To meet AST09, you need **immutable storage, protected backups, strictly governed corrections with full provenance, authentication linkage, and active monitoring**. Without these, an external auditor is likely to flag gaps in the integrity and reliability of your audit evidence.