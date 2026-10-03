# Monitoring profile — technical spec

**Parent architecture:** [MVP architecture](../../architecture-tech-stack.md)  
**Behavior:** [Task spec](task_spec.md)

## Storage

- `monitor_profile`: one row for the default workspace, with creation, update, and last-review timestamps.
- `monitor_rule`: profile ID, kind, original value, normalized value. Enforce uniqueness on `(profile_id, kind, normalized_value)`.
- `source_config`: one row per source with an enabled flag; unique `(profile_id, source_key)`.

Normalize rules by trimming whitespace, collapsing repeated spaces, and case-folding for duplicate comparison. Preserve the operator's original spelling for display. Limit individual values to 100 characters, matching the prototype input. Empty rules are not stored.

## API and behavior

- `GET /api/profile` returns the singleton profile, rules grouped by kind, source toggles, and the fixed four-hour schedule. It returns no secrets.
- `PUT /api/profile` validates and replaces rules and toggles in one database transaction. A malformed rule or unknown source rejects the entire update.
- On the first transition from no saved monitoring rules to a non-empty saved profile, enqueue one `initial` collection run in the same transaction. Later saves do not repeat it.
- Each queued run stores a snapshot of the relevant profile values so changes made during collection apply to the next run.

The UI uses the Monitoring screen and sends one `PUT` on Save. Client-side add controls show blank and duplicate errors next to the affected rule kind. The API validates the complete payload again, and a rejected save keeps unsaved local edits visible with the server error beside the Save control.

## Dependencies

Run creation and profile snapshots use the [Collection technical spec](../signal-collection/technical_spec.md). Keys and RSS URLs remain environment configuration as defined by the parent architecture.
