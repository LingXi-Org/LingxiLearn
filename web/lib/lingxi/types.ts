/** Small wire types for the LingxiGraph REST/SSE API. */

export interface AgentTaskEvent {
  sequence: number
  kind: string
  agent: string
  payload: Record<string, unknown>
  ts: string | null
}

export type AgentTaskStatus =
  | 'queued'
  | 'running'
  | 'awaiting_user'
  | 'handed_off'
  | 'completed'
  | 'partial'
  | 'failed'

export interface AgentAgentSnapshot {
  status: 'pending' | 'queued' | 'running' | 'completed' | 'failed'
  error?: string
}

export type KnowledgeLearningState =
  | 'unknown'
  | 'not_observed'
  | 'emerging'
  | 'demonstrated'
  | 'misconception_evidence'
  | 'needs_recheck'

export interface KnowledgeGraphNode {
  id: string
  label: string
  type: string
  importance: number
  is_current: boolean
  learning_state: KnowledgeLearningState
  level?: number
  position?: { x: number; y: number }
  aliases?: string[]
  description?: string
  source_refs?: string[]
}

export interface KnowledgeGraphEdge {
  id: string
  source: string
  target: string
  relation: string
  relation_label: string
  directed: boolean
  importance?: number
}

export interface KnowledgeGraphData {
  graph_id: string
  revision: number
  title: string
  domain: string
  nodes: KnowledgeGraphNode[]
  edges: KnowledgeGraphEdge[]
  root_node_ids: string[]
}

export interface PublicQuizQuestion {
  id: string
  type: 'single_choice' | 'multi_choice' | 'short_text'
  prompt: string
  options: Array<{ id: string; label: string }>
  points: number
}

export interface PublicQuiz {
  schema_version: 'quiz-generation-result.v1'
  task_id: string
  title: string
  instructions: string
  questions: PublicQuizQuestion[]
  total_points: number
}

export interface QuizSubmissionSnapshot {
  submission_id: string
  submitted_at: string | null
  total_score: number
  total_points: number
  per_question: Array<{ id: string; correct: boolean; score: number; points: number }>
  handoff_reason: string
}

export interface AgentTaskSnapshot {
  id: string
  status: AgentTaskStatus
  prompt: string
  graph_version: string
  intent: {
    topic?: string
    learning_objective?: string
    learner_level?: string
    course_context?: string
    language?: string
    target_duration_sec?: number
  }
  agents: Record<string, AgentAgentSnapshot>
  artifacts: {
    lesson_intro: ArtifactSnapshot
    lecture_deck: ArtifactSnapshot
    quiz: { available: boolean; data?: PublicQuiz | null }
    visual: ArtifactSnapshot
    knowledge_graph?: KnowledgeGraphArtifactSnapshot
  }
  quiz_submission: QuizSubmissionSnapshot | null
  error: string
  created_at: string | null
  updated_at: string | null
}

export interface ArtifactSnapshot {
  available: boolean
  url: string
  metadata?: Record<string, unknown>
}

export interface KnowledgeGraphArtifactSnapshot {
  available: boolean
  graph_id?: string | null
  revision?: number | null
  url: string
  status?: string
  error?: string
}
