# Quality gate

Before returning:

- use only supplied taught content and learner evidence;
- generate no more than three candidates and ensure they are materially different;
- attach evidence references to every candidate and to the selected task;
- keep one main judgment per task;
- ensure the selected task is independently solvable and answerable from the evidence boundary;
- check target type and difficulty against learner evidence;
- set `prefetch.blocking=false` and include discard conditions;
- keep `public_task` free of answer, explanation, rubric, keywords, and internal assumptions;
- separate `grading_key` from every learner-visible field;
- write all learner-visible prose in Simplified Chinese;
- return `insufficient_evidence` instead of filling gaps with outside facts.
