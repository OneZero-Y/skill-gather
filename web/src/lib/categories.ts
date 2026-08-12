/** Sidebar grouping — clarifies that DevOps ≠ general software development. */

export const CATEGORY_GROUP_ORDER = ['engineering', 'content', 'business', 'other'] as const;

export type CategoryGroupId = (typeof CATEGORY_GROUP_ORDER)[number];

/** Which registry categories belong to each sidebar group. */
export const CATEGORY_GROUP_MEMBERS: Record<CategoryGroupId, string[]> = {
  engineering: ['development', 'devops', 'data', 'security'],
  content: ['creative', 'document', 'content'],
  business: ['productivity', 'ecommerce', 'education'],
  other: [],
};

export function groupCategories<T extends { id: string }>(
  items: T[],
): Array<{ groupId: CategoryGroupId; items: T[] }> {
  const byId = new Map(items.map((item) => [item.id, item]));
  const used = new Set<string>();

  const groups = CATEGORY_GROUP_ORDER.map((groupId) => {
    const members = CATEGORY_GROUP_MEMBERS[groupId]
      .map((id) => byId.get(id))
      .filter((item): item is T => {
        if (!item) return false;
        used.add(item.id);
        return true;
      });
    return { groupId, items: members };
  }).filter((g) => g.items.length > 0);

  const rest = items.filter((item) => !used.has(item.id));
  if (rest.length > 0) {
    groups.push({ groupId: 'other', items: rest });
  }

  return groups;
}
