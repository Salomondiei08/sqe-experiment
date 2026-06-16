# Tomorrow Talk Checklist

## Before the talk

- Open `presentation/sqe_conference_slides.html` in a browser.
- Test right arrow, left arrow, and space navigation.
- Open `presentation/sqe_conference_speaker_notes.md` in a separate window.
- Confirm the browser zoom is at 100%.
- Use full-screen mode for the talk.

## Core message

Say this clearly:

"The memory may be present, but the query does not look like the memory. SQE asks the memory index again using execution-style traces and paraphrases, only when the initial retrieval looks uncertain."

## Claims to make

- SQE is a retrieval-time method.
- The memory-writing pipeline is unchanged.
- In the current retrieval study, SQE shows a small Recall@5 signal across independent memory-index seeds.
- The current gate is not yet fully solved.

## Claims to avoid

- Do not claim improved Pass@1.
- Do not claim improved end-to-end agent task success.
- Do not claim human-validated query realism.
- Do not claim SQE clearly beats the random-gated budget control.

## If asked about limitations

Answer:

"The main limitations are that Pass@1 has not been run yet, human labels are still missing, and the confidence gate needs stronger calibration."

## If asked what is next

Answer:

"The next steps are downstream Pass@1 evaluation, human query-quality audit, better gate validation, and public release of the code and dataset package."
