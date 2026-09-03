import { useState } from "react";
import { TypePillRow } from "./type-pill-row";
import type { HomeTypeChipId } from "@/lib/mock-data";
import type { ComposerSubmitPayload } from "@/contracts/composer";
import { PromptComposer, useComposerAgentOptions } from "@/components/composer";
import { Card, CardContent } from "@/components/ui/card";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";

interface HomeHeroProps {
  onSubmit?: (payload: ComposerSubmitPayload, chipId: HomeTypeChipId) => void;
}

export function HomeHero({ onSubmit }: HomeHeroProps) {
  const [activeChipId, setActiveChipId] = useState<HomeTypeChipId>("prototype");
  const agents = useComposerAgentOptions();

  return (
    <section className="flex flex-col items-center gap-6 px-4 pt-16 pb-4" data-testid="home-hero">
      <div className="flex flex-col items-center gap-2">
        <Avatar className="size-10 rounded-[10px]">
          <AvatarImage src="/logo-mark.svg" alt="" />
          <AvatarFallback className="rounded-[10px]">叮</AvatarFallback>
        </Avatar>
        <h1 className="m-0 text-center text-[29px] font-semibold tracking-tight text-foreground">叮答</h1>
        <p className="m-0 text-center text-[13px] text-muted-foreground">描述你的想法，开始创作</p>
      </div>

      <TypePillRow activeChipId={activeChipId} onPick={setActiveChipId} />

      <Card className="w-full max-w-[720px] gap-0 py-0 ring-border/60">
        <CardContent className="px-4 pb-3 pt-4">
          <PromptComposer
            agents={agents}
            placeholder="描述你想创建的内容… 可上传参考图"
            onSubmit={(payload) => onSubmit?.(payload, activeChipId)}
          />
        </CardContent>
      </Card>
    </section>
  );
}
