import { useEffect, useState, type ReactNode } from 'react';
import { ChevronDown, LayoutGrid, PanelLeftClose, PanelLeftOpen } from 'lucide-react';
import { CATEGORY_GROUPS_COLLAPSED_KEY, SIDEBAR_COLLAPSED_KEY } from '@/lib/i18n';
import { cn } from '@/lib/utils';
import type { CategoryGroupId } from '@/lib/categories';
import { useI18n } from './LocaleProvider';

interface CategoryOption {
  id: string;
  label: string;
  count: number;
}

interface CategoryGroup {
  groupId: CategoryGroupId;
  groupLabel: string;
  items: CategoryOption[];
}

interface CategorySidebarProps {
  title: string;
  allItem: CategoryOption;
  groups: CategoryGroup[];
  active: string;
  onSelect: (id: string) => void;
}

function readCollapsed(): boolean {
  if (typeof window === 'undefined') return false;
  return localStorage.getItem(SIDEBAR_COLLAPSED_KEY) === 'true';
}

function readGroupsCollapsed(): Record<string, boolean> {
  if (typeof window === 'undefined') return {};
  try {
    const raw = localStorage.getItem(CATEGORY_GROUPS_COLLAPSED_KEY);
    return raw ? (JSON.parse(raw) as Record<string, boolean>) : {};
  } catch {
    return {};
  }
}

export function CategorySidebar({
  title,
  allItem,
  groups,
  active,
  onSelect,
}: CategorySidebarProps) {
  const { t, categoryLabel } = useI18n();
  const [collapsed, setCollapsed] = useState(readCollapsed);
  const [groupsCollapsed, setGroupsCollapsed] = useState<Record<string, boolean>>(readGroupsCollapsed);

  useEffect(() => {
    localStorage.setItem(SIDEBAR_COLLAPSED_KEY, String(collapsed));
  }, [collapsed]);

  useEffect(() => {
    localStorage.setItem(CATEGORY_GROUPS_COLLAPSED_KEY, JSON.stringify(groupsCollapsed));
  }, [groupsCollapsed]);

  // Keep the group containing the active category expanded
  useEffect(() => {
    if (active === 'all') return;
    const owningGroup = groups.find(
      (g) => g.items.length > 1 && g.items.some((item) => item.id === active),
    );
    if (!owningGroup) return;
    setGroupsCollapsed((prev) => {
      if (prev[owningGroup.groupId] === false) return prev;
      return { ...prev, [owningGroup.groupId]: false };
    });
  }, [active, groups]);

  const toggleGroup = (groupId: CategoryGroupId) => {
    setGroupsCollapsed((prev) => ({
      ...prev,
      [groupId]: prev[groupId] === false,
    }));
  };

  const isGroupExpanded = (groupId: CategoryGroupId) => groupsCollapsed[groupId] === false;

  const activeLabel =
    active === 'all' ? allItem.label : categoryLabel(active);

  return (
    <aside
      className={cn(
        'hidden shrink-0 border-r border-border transition-[width] duration-200 ease-out lg:block',
        collapsed ? 'w-14' : 'w-52',
      )}
    >
      <nav className="sticky top-[57px] flex max-h-[calc(100vh-57px)] flex-col overflow-hidden py-4">
        <div
          className={cn(
            'mb-3 flex items-center',
            collapsed ? 'justify-center px-2' : 'justify-between px-3',
          )}
        >
          {!collapsed && (
            <p className="text-[11px] font-semibold uppercase tracking-wide text-muted">{title}</p>
          )}
          <button
            type="button"
            onClick={() => setCollapsed((v) => !v)}
            className="flex h-8 w-8 items-center justify-center rounded-lg border border-border text-muted transition hover:border-accent/40 hover:text-foreground"
            aria-label={collapsed ? t('expandSidebar') : t('collapseSidebar')}
            title={collapsed ? t('expandSidebar') : t('collapseSidebar')}
          >
            {collapsed ? <PanelLeftOpen className="h-4 w-4" /> : <PanelLeftClose className="h-4 w-4" />}
          </button>
        </div>

        {collapsed ? (
          <div className="flex flex-1 flex-col items-center gap-2 px-2">
            <CollapsedNavButton
              active={active === 'all'}
              label={allItem.label}
              onClick={() => onSelect('all')}
            >
              <LayoutGrid className="h-4 w-4" />
            </CollapsedNavButton>
            {active !== 'all' && (
              <span
                className="max-w-full truncate rounded-md bg-accent/10 px-1.5 py-0.5 text-[10px] font-medium text-accent"
                title={activeLabel}
              >
                {activeLabel.slice(0, 2)}
              </span>
            )}
          </div>
        ) : (
          <div className="flex-1 overflow-y-auto pr-3">
            <ul className="mb-4 space-y-0.5">
              <li>
                <CategoryButton
                  item={allItem}
                  active={active === allItem.id}
                  onSelect={() => onSelect(allItem.id)}
                />
              </li>
            </ul>

            {groups.map((group) =>
              group.items.length === 1 ? (
                <div key={group.items[0].id} className="mb-2">
                  <CategoryButton
                    item={group.items[0]}
                    active={active === group.items[0].id}
                    onSelect={() => onSelect(group.items[0].id)}
                  />
                </div>
              ) : (
                <CollapsibleCategoryGroup
                  key={group.groupId}
                  group={group}
                  active={active}
                  expanded={isGroupExpanded(group.groupId)}
                  onToggle={() => toggleGroup(group.groupId)}
                  onSelect={onSelect}
                />
              ),
            )}
          </div>
        )}
      </nav>
    </aside>
  );
}

function CollapsibleCategoryGroup({
  group,
  active,
  expanded,
  onToggle,
  onSelect,
}: {
  group: CategoryGroup;
  active: string;
  expanded: boolean;
  onToggle: () => void;
  onSelect: (id: string) => void;
}) {
  const groupTotal = group.items.reduce((sum, item) => sum + item.count, 0);
  const hasActive = group.items.some((item) => item.id === active);

  return (
    <div className="mb-2">
      <button
        type="button"
        onClick={onToggle}
        className={cn(
          'flex w-full items-center gap-1 rounded-lg px-3 py-1.5 text-left transition hover:bg-card',
          hasActive && !expanded && 'text-accent',
        )}
      >
        <ChevronDown
          className={cn(
            'h-3.5 w-3.5 shrink-0 text-muted transition-transform duration-200',
            !expanded && '-rotate-90',
          )}
        />
        <span className="min-w-0 flex-1 truncate text-[10px] font-semibold uppercase tracking-wide text-muted/80">
          {group.groupLabel}
        </span>
        <span className="shrink-0 text-[10px] text-muted/70">{groupTotal}</span>
      </button>

      {expanded && (
        <ul className="mt-0.5 space-y-0.5">
          {group.items.map((item) => (
            <li key={item.id}>
              <CategoryButton
                item={item}
                active={active === item.id}
                onSelect={() => onSelect(item.id)}
                indented
              />
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function CollapsedNavButton({
  active,
  label,
  onClick,
  children,
}: {
  active: boolean;
  label: string;
  onClick: () => void;
  children: ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      title={label}
      className={cn(
        'flex h-9 w-9 items-center justify-center rounded-xl transition',
        active
          ? 'bg-accent/10 text-accent'
          : 'text-muted hover:bg-card hover:text-foreground',
      )}
    >
      {children}
    </button>
  );
}

function CategoryButton({
  item,
  active,
  onSelect,
  indented = false,
}: {
  item: CategoryOption;
  active: boolean;
  onSelect: () => void;
  indented?: boolean;
}) {
  return (
    <button
      type="button"
      onClick={onSelect}
      className={cn(
        'flex w-full items-center justify-between rounded-xl py-2 text-left text-sm transition',
        indented ? 'pl-5 pr-3' : 'px-3',
        active
          ? 'bg-accent/10 font-medium text-accent'
          : 'text-muted hover:bg-card hover:text-foreground',
      )}
    >
      <span className="truncate">{item.label}</span>
      <span className="ml-2 shrink-0 text-xs opacity-70">{item.count}</span>
    </button>
  );
}

/** Mobile / tablet horizontal category strip */
export function CategoryStrip({
  items,
  active,
  onSelect,
}: {
  items: CategoryOption[];
  active: string;
  onSelect: (id: string) => void;
}) {
  return (
    <div className="chip-scroll flex gap-2 overflow-x-auto pb-1 lg:hidden">
      {items.map((item) => (
        <button
          key={item.id}
          type="button"
          onClick={() => onSelect(item.id)}
          className={cn(
            'inline-flex shrink-0 items-center gap-1.5 rounded-full border px-3.5 py-2 text-sm transition',
            active === item.id
              ? 'border-accent bg-accent/10 font-medium text-accent'
              : 'border-border bg-background text-muted',
          )}
        >
          {item.label}
          <span className="text-[10px] opacity-70">{item.count}</span>
        </button>
      ))}
    </div>
  );
}
