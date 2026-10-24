/**
 * Shared iconography for achievements (ACH-005): one lucide glyph per rarity
 * band and per catalog group. Kept out of the pure helpers in `achievements.ts`
 * so those stay component-free and easy to test.
 */
import {
  Activity,
  Award,
  Brain,
  Cpu,
  Crown,
  Flag,
  Gem,
  GraduationCap,
  Layers,
  Medal,
  Swords,
  Target,
  Timer,
  Trophy,
  Users,
  Zap,
  type LucideIcon,
} from 'lucide-react';

import type { AchievementTier } from './api-types';

export const TIER_ICONS: Record<AchievementTier, LucideIcon> = {
  bronze: Medal,
  silver: Award,
  gold: Trophy,
  diamond: Gem,
  legendary: Crown,
};

export const GROUP_ICONS: Record<string, LucideIcon> = {
  play: Flag,
  result: Swords,
  points: Target,
  tactics: Zap,
  pieces: Layers,
  endurance: Timer,
  habit: Activity,
  review: Brain,
  engine: Cpu,
  mode: Users,
  training: GraduationCap,
};

export const DEFAULT_GROUP_ICON = Trophy;
