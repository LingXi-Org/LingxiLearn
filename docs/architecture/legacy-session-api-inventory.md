# Legacy Session API inventory

The browser product uses AgentTask for creation, polling, interaction, event streaming, and
artifact delivery. The older Session HTTP surface has no runtime frontend callers and is
removed as part of issue #70. Database retirement is intentionally separate because learning
evidence and reports still carry historical session foreign keys.

| Endpoint | Current frontend caller | Historical only | Replacement | Delete condition |
| --- | --- | --- | --- | --- |
| `POST /api/sessions` | None | Yes | `POST /api/agent-tasks` | Met: no product caller |
| `GET /api/sessions/{id}` | None | Yes | `GET /api/agent-tasks/{id}` | Met: no product caller |
| `POST /api/sessions/{id}/answer` | None | Yes | `POST /api/agent-tasks/{id}/interactions/{interactionId}/answer` | Met: no product caller |
| `GET /api/sessions/{id}/report` | None | Yes | AgentTask artifacts/evidence | Met: no product caller |
| `GET /api/sessions/{id}/artifact/{artifactId}` | None | Yes | `GET /api/agent-tasks/{id}/artifacts/{kind}` | Met: no product caller |
| `GET /api/sessions/{id}/events` | None | Yes | `GET /api/agent-tasks/{id}/events` | Met: no product caller |

The removed TypeScript client was only re-exported by the former Lingxi API facade; repository-wide
reachability found no calls to those exports. Legacy persistence may remain readable for data
migration, but V1 AgentTask services must not depend on Session route or conversation services.
