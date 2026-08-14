import { api, subscribeAgentEvents } from '@/lib/lingxi/api'
import type { AgentTaskEvent } from '@/lib/lingxi/types'

export class LingxiWorkspaceClient {
  listChats = api.agentTasks;
  getTask = api.agentTask;
  createTask = api.createAgentTask;
  sendMessage = api.agentMessage;
  listSkills = api.skills;
  getContext = api.context;
  getPreferences = api.preferences;
  updatePreferences = api.updatePreferences;
  submitQuiz = api.submitAgentQuiz;
  artifactUrl = api.agentArtifactUrl;
  fetchArtifact = api.fetchArtifact;

  subscribeTask(taskId: string, onEvent: (event: AgentTaskEvent) => void, from = 0, onEnd?: (status: string) => void) {
    return subscribeAgentEvents(taskId, onEvent, { from, onEnd });
  }
}

export const lingxiWorkspaceClient = new LingxiWorkspaceClient();
