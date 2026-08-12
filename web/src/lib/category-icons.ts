import {
  BarChart3,
  BookOpen,
  Code2,
  Layers,
  Palette,
  Server,
  Shield,
  ShoppingBag,
  Sparkles,
  type LucideIcon,
} from 'lucide-react';

export const CATEGORY_ICONS: Record<string, LucideIcon> = {
  development: Code2,
  devops: Server,
  data: BarChart3,
  security: Shield,
  creative: Palette,
  document: BookOpen,
  content: Sparkles,
  productivity: Layers,
  ecommerce: ShoppingBag,
  education: BookOpen,
  other: Layers,
};

export function getCategoryIcon(id: string): LucideIcon {
  return CATEGORY_ICONS[id] ?? Layers;
}
