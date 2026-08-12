# Runtime notes

Recommended execution:
- enqueue after `adaptive-pedagogy` result is rendered;
- batch several UI events when convenient;
- do not exceed host privacy/retention policy;
- write proposals through the host state store, not directly.

Fallback:
- if the background queue is unavailable, store raw events and run this Skill at session end.
