import { SkillsConsole } from "@/components/agent-studio/agent-studio-console";
import { getSkills } from "@/lib/api/sagad-api";

export default async function SkillsPage() {
  const skills = await getSkills();

  return <SkillsConsole skills={skills} />;
}
