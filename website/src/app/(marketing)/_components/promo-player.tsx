"use client";

import { Player } from "@remotion/player";
import { DingDaPromo } from "@/remotion/DingDa/DingDaPromo";
import {
  DURATION_IN_FRAMES,
  VIDEO_FPS,
  VIDEO_HEIGHT,
  VIDEO_WIDTH,
} from "@/types/constants";
import { asset } from "@/lib/site";

export default function PromoPlayer() {
  return (
    <div className="aspect-video w-full overflow-hidden rounded-2xl border border-[#ddcdab] bg-black shadow-xl">
      <Player
        component={DingDaPromo}
        durationInFrames={DURATION_IN_FRAMES}
        fps={VIDEO_FPS}
        compositionWidth={VIDEO_WIDTH}
        compositionHeight={VIDEO_HEIGHT}
        style={{ width: "100%", display: "block" }}
        controls
        autoPlay
        loop
        initiallyMuted
        acknowledgeRemotionLicense
      />
    </div>
  );
}

export function DingDaLogo({ size = 32 }: { size?: number }) {
  return (
    // eslint-disable-next-line @next/next/no-img-element
    <img
      src={asset("assets/logo.webp")}
      alt="叮答"
      width={size}
      height={size}
      className="rounded-lg object-cover"
    />
  );
}
