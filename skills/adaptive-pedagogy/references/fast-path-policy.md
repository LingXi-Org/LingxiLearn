# Fast-path policy checklist

Return the response only after checking:

## Interaction
- [ ] At most one mandatory learner action.
- [ ] No standalone confidence question unless calibration itself is the objective.
- [ ] No forced "agree/disagree with my learner model" turn.
- [ ] If two mandatory prompts have already occurred without new explanatory value, this response
      delivers useful support rather than another generic question.

## Personalization
- [ ] The selected action is justified by concrete recent evidence.
- [ ] A correct demonstrated relation is not re-taught.
- [ ] A likely slip is not escalated into a long misconception dialogue.
- [ ] A stable misconception is challenged with evidence, not merely contradicted.

## Assistance
- [ ] The response provides the minimum useful assistance level.
- [ ] If the learner is stuck, the new response adds information; it does not simply say "try again".
- [ ] High-reveal help sets/sustains `verification_debt` rather than forcing immediate verification.

## Latency
- [ ] Normal path has one blocking Skill inference.
- [ ] Background state reflection is non-blocking.
- [ ] Optional visual work has a usable text fallback.
- [ ] No delegation to old micro-strategy Skills.

## Agency
- [ ] Support choices are offered only when meaningful.
- [ ] Choices are momentary preferences, not "learning style" labels.
