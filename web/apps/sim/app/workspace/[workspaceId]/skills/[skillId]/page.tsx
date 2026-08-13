import { SkillDetail } from './skill-detail'

export function generateStaticParams() {
  // The skills are served by the LingxiLearn API at runtime, while the web
  // bundle is exported statically. Include the bundled ids so the native
  // detail route is present in deployments that serve exact static paths;
  // the workspace shell also handles newly added ids client-side.
  return [
    'adaptive-pedagogy',
    'curriculum-graph-builder',
    'interactive-lecture-deck',
    'interactive-visual-explainer',
    'learner-state-reflector',
    'lesson-intro',
    'quiz-generator',
    'skill-eval-harness',
  ].map((skillId) => ({ workspaceId: 'lingxi', skillId }))
}

export default async function Page({
  params,
}: {
  params: Promise<{ workspaceId: string; skillId: string }>
}) {
  const { workspaceId, skillId } = await params
  return <SkillDetail workspaceId={workspaceId} skillId={skillId} />
}
