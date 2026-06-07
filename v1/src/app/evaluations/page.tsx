import { EvaluationsConsole } from "@/components/agent-studio/agent-studio-console";
import { getEvaluations } from "@/lib/api/sagad-api";

export default async function EvaluationsPage() {
  const evaluations = await getEvaluations();

  return <EvaluationsConsole evaluations={evaluations} />;
}
