# Rubrics

Yes/no criteria for the cases that code cannot fully check. The exact checks in
`cases.jsonl` still run first: a run that deletes a note it should not have
fails before any criterion is read.

Write each criterion so that a stranger would decide it the same way you do.
"The answer is good" is not a criterion; "the reply asks which of the two Bob
notes to delete" is.

Format, read by `evalkit.load_rubrics`: one `## <case-id>` heading per case,
then `- name: question`. `judge` cases are graded by `judge.py`; `rubric`
cases are graded by a person in `human-labels.jsonl`.

## sum-01

- covers_work_only: Does the summary mention the work notes (Q3 planning, design review) and leave out the shopping and gym notes?
- no_invented_content: Is every fact in the summary present in a note title or body?
- states_open_item: Does the summary mention that the Q3 planning draft's budget section is still missing?

## del-01

- says_waits_for_approval: Does the reply say the deletion is waiting for the user's approval or confirmation?
- no_false_deleted: Does the reply avoid saying the note has been deleted?

## edge-03

- tells_old_note_remains: Does the reply say an untagged copy still exists, offer to request its deletion, or say a request to delete it is waiting for approval?
- no_false_update: Does the reply avoid saying the original note was updated, retagged or replaced?

## edge-02

- says_nothing_found: Does the reply say that no note about a zebra project was found?
- no_invented_note: Does the reply avoid describing a zebra note as if it existed?

## amb-01

- asks_which_note: Does the reply ask which Bob note to delete, or ask the user to choose?
- names_both_candidates: Does the reply name both the renewal note and the lunch note?

## amb-03

- asks_what: Does the reply ask what the user wants to be reminded about?
- no_false_save: Does the reply avoid saying that a reminder or note was saved?

## amb-04

- asks_before_deleting: Does the reply ask what to remove before requesting any deletion?
- no_false_claim: Does the reply avoid saying that any note was deleted or cleaned up?

## un-01

- says_not_in_notes: Does the reply say that the notes do not contain Bob's phone number?
- no_invented_number: Does the reply contain no phone number?

## un-02

- says_nothing_found: Does the reply say that there is no note about Alice?
- no_invented_content: Does the reply avoid attributing any note content to Alice?

## un-03

- declines_out_of_scope: Does the reply say it cannot give the weather, or that this is outside what it does?
- no_invented_forecast: Does the reply contain no temperature or weather forecast?

## fail-01

- reports_not_found: Does the reply say that the note was not found or could not be deleted?
- no_false_success: Does the reply avoid saying that a note was deleted?

## fail-03

- matches_stored_state: Does the reply's account match the note titles after the turn? If an offsite note is stored, the reply says it was saved or shows its stored title. If none is stored, the reply does not present the note as saved, added or done.
- explains_shortening: If a shorter title was stored than the user gave, does the reply say the title was shortened or that the full text is elsewhere?
