import React from 'react';
import { AbsoluteFill } from 'remotion';
import { Intro } from './scenes/Intro';
import { Accounts } from './scenes/Accounts';
import { Messages } from './scenes/Messages';
import { Ai } from './scenes/Ai';
import { Orders } from './scenes/Orders';
import { Local } from './scenes/Local';
import { SCENES, SCENE_DURATION } from './timing';
import { COLORS } from './theme';

/** DingDa 60s 宣传片：6 场景平滑切换。 */
export const DingDaPromo: React.FC = () => {
  return (
    <AbsoluteFill style={{ backgroundColor: COLORS.bg }}>
      <Intro start={SCENES.intro} duration={SCENE_DURATION.intro} />
      <Accounts start={SCENES.accounts} duration={SCENE_DURATION.accounts} />
      <Messages start={SCENES.messages} duration={SCENE_DURATION.messages} />
      <Ai start={SCENES.ai} duration={SCENE_DURATION.ai} />
      <Orders start={SCENES.orders} duration={SCENE_DURATION.orders} />
      <Local start={SCENES.local} duration={SCENE_DURATION.local} />
    </AbsoluteFill>
  );
};
