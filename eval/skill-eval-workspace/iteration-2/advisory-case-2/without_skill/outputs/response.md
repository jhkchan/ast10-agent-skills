Origin AST id: AST-98765

Contributing entries:
- Entry ID: LOG-2024-5012 (Owner: Jane Cho, Cloud Governance Team) – Action: Provide evidence of approval workflow for the skill installation prior to deployment.
- Entry ID: INVT-8843 (Owner: Marcus Reed, IT Operations) – Action: Update discovery tooling to capture and retain service principal associations for third-party skills.
- Entry ID: SEC-2024-0331 (Owner: Naomi Patel, Security Compliance) – Action: Validate current tenant-wide admin consent assignments and enforce deprovisioning policies for offboarded personnel.

The receiving category (Identity & Access Governance) can confirm only that the service principal exists and currently holds admin consent at the tenant level. It cannot confirm who originally approved the skill installation, as no audit trail or authorization record is available within the current IAM systems. Absent integration with deployment pipelines or change management logs, the category cannot reliably verify ownership or legitimacy of historical consents.