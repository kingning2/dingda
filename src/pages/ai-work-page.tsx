import { AiWorkView } from "@/components/ai";

interface AiWorkPageProps {
  workId: string;
  onBack?: () => void;
}

export function AiWorkPage({ workId, onBack }: AiWorkPageProps) {
  return <AiWorkView workId={workId} onBack={onBack} />;
}
