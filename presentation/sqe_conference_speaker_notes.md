# SQE Conference Talk Speaker Notes

Talk date: May 16, 2026

## 1. Title

Introduce the project as a retrieval method for long-horizon agent memory.

Do not start with implementation details. Start with the practical problem: agents remember many things, but they often fail to retrieve the right memory later.

## 2. The talk in one minute

Use this slide to give the audience the whole story before the details.

Main line:
"The problem is not that the memory is always missing. Often, it is present but written in a different language from the later question. SQE asks the memory index again using execution-style traces and paraphrases, but only when retrieval looks uncertain."

## 3. Why retrieval fails

Explain the vocabulary mismatch in plain terms.

Example:
"The stored memory may say `pytest failed with KeyError in cache.py`, while the later question says `how did we fix the cache lookup bug?` A standard retriever may not connect these two."

## 4. Simple intuition

Repeat the key sentence:
"Ask the memory index in the language the memory was written in."

This is the most understandable nontechnical summary of the method.

## 5. How SQE works

Walk through the figure from left to right.

Emphasize:
- The memory store is unchanged.
- The method runs normal dense retrieval first.
- Expansion happens only for low-confidence queries.
- The generated traces are retrieval probes, not claims that those executions happened.
- Reciprocal Rank Fusion combines the ranked lists.

## 6. Evaluation design

Define Recall@5 simply:
"Recall@5 asks whether the correct memory appears somewhere in the first five retrieved memories."

Say clearly:
"This is not yet a final agent-success result. It is a retrieval study."

## 7. Main retrieval result

Use careful wording:
"In the seed-42 audit run, SQE is close to dense retrieval and clearly above Hybrid-RRF. It does not beat dense retrieval in this run."

Do not say:
"SQE improves agents."

## 8. Method comparison

Explain that this slide compares retrieval methods under the same memory store.

Suggested line:
"The result is encouraging but not decisive. SQE is not a magic improvement over every baseline; the value is that it is cheap to add and gives a small signal across seeds."

## 9. Across independent memory seeds

This is the strongest current retrieval evidence.

Say:
"Across eight independently rebuilt memory-index seeds, SQE averages 69.4% Recall@5, dense retrieval averages 68.5%, and the paired difference is about 0.9 points."

Then add:
"The comparison against the random-gated budget control is not conclusive, so the current gate is not yet the full answer."

## 10. Confidence gate weakness

Be direct:
"This is the main weakness of the current paper. Top-1 dense score is not a clean confidence signal."

This honesty helps the work sound like serious research rather than promotion.

## 11. What can be claimed today

Use this slide if reviewers ask what is already proven.

Supported:
- Retrieval-time retrofit.
- Memory-writing pipeline unchanged.
- Reduced expansion calls relative to always-expand.
- Small retrieval-only Recall@5 signal across seeds.

Not supported yet:
- Pass@1 improvement.
- Human-validated query realism.
- Solved gate calibration.
- Clear win over random-gated expansion.

## 12. Next steps

Frame the remaining work as a research plan:
1. Run downstream Pass@1.
2. Collect human audit labels.
3. Improve and validate the gate.
4. Release code and dataset artifacts.

## 13. Closing

End with:
"The takeaway is that SQE is a practical retrieval-time idea. The current evidence is a modest retrieval signal, and the next step is to test whether that signal improves end-to-end agent behavior."

## Q&A guardrails

If asked whether SQE improves software-agent performance:
"Not yet established. We have retrieval evidence, but Pass@1 evaluation is still required."

If asked why dense retrieval is hard to beat:
"Dense retrieval is a strong baseline. SQE helps some queries but hurts others, which is why gate calibration matters."

If asked whether generated traces are fake data:
"They are not added to memory and are not evaluated as facts. They are only temporary retrieval probes."

If asked what makes this publishable:
"The publishable contribution depends on completing downstream Pass@1, human query audit, and stronger gate validation. The current package is a rigorous retrieval study and identifies the calibration gap."
