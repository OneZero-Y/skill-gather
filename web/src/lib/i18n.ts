export type Locale = 'zh' | 'en';

export const LOCALE_STORAGE_KEY = 'skill-gather-locale';
export const SIDEBAR_COLLAPSED_KEY = 'skill-gather-sidebar-collapsed';
export const CATEGORY_GROUPS_COLLAPSED_KEY = 'skill-gather-category-groups-collapsed';

const CATEGORY_LABELS: Record<Locale, Record<string, string>> = {
  zh: {
    development: '软件开发',
    creative: '创意',
    document: '文档',
    devops: '部署运维',
    security: '安全',
    data: '数据',
    content: '内容',
    ecommerce: '电商',
    education: '教育',
    productivity: '效率',
    other: '其他',
  },
  en: {
    development: 'Software Dev',
    creative: 'Creative',
    document: 'Document',
    devops: 'DevOps',
    security: 'Security',
    data: 'Data',
    content: 'Content',
    ecommerce: 'E-commerce',
    education: 'Education',
    productivity: 'Productivity',
    other: 'Other',
  },
};

const CATEGORY_GROUP_LABELS: Record<Locale, Record<string, string>> = {
  zh: {
    engineering: '开发与工程',
    content: '内容与创意',
    business: '效率与商业',
    other: '其他',
  },
  en: {
    engineering: 'Engineering',
    content: 'Content',
    business: 'Business',
    other: 'Other',
  },
};

const MESSAGES = {
  zh: {
    siteDescription: 'AI Agent Skill 发现引擎 · 兼容性注册表',
    heroTitle: '发现 Agent Skills',
    heroSubtitle: '聚合 GitHub、SkillHub 等来源，兼容 Cursor · Claude · Kiro · Codex',
    heroBrowseCategories: '按分类浏览',
    browseByCategory: '按分类浏览',
    viewAll: '查看全部',
    categorySkillCount: '{count} 个 skill',
    officialSkills: '官方来源',
    popularSkills: '热门（Stars）',
    exploreCatalog: '探索全部',
    statsUpdated: '更新于 {time}',
    filterCategory: '分类',
    filterSource: '来源',
    filterPlatform: '平台',
    filterAll: '全部',
    featured: '精选高分',
    allSkills: '全部 Skill',
    showingCount: '显示 {shown} / {total} 条',
    pageRange: '第 {start}–{end} 条，共 {total} 条 · 第 {page}/{pages} 页',
    prev: '上一页',
    next: '下一页',
    sortBy: '排序',
    sortScore: '评分最高',
    sortStars: 'Stars 最多',
    sortName: '名称 A–Z',
    filters: '筛选',
    clearAll: '清除筛选',
    noResults: '没有匹配的 skill，请调整筛选条件',
    loadMore: '加载更多',
    footerUpdated: '数据更新于 {date}',
    searchPlaceholder: '搜索 skill…',
    searchInputPlaceholder: '搜索 skill 名称、描述、标签…',
    searchNoResults: '无匹配结果',
    back: '返回',
    category: '分类',
    source: '来源',
    license: '许可证',
    installs: '安装量',
    compatiblePlatforms: '兼容平台',
    tags: '标签',
    viewSource: '查看来源',
    copyAria: '复制',
    copySuccess: '已复制到剪贴板',
    installGuide: '安装到本地',
    installCliTitle: 'CLI 一键安装',
    installCliPrereqBefore: '需先安装 ',
    installCliPrereqAfter: ' CLI 和 git，不同平台命令不同。',
    installSourceHint: 'GitHub 源地址 — 打开查看 skill 文件，或 clone 后复制到下方对应目录。',
    installManualNote: '各 Agent 的 skills 目录（手动安装时复制到此）：',
    openOnGithub: '在 GitHub 打开',
    installSourceUnavailable: '暂无可用安装源地址。',
    toggleTheme: '切换主题',
    toggleLocale: '切换语言',
    collapseSidebar: '收起分类',
    expandSidebar: '展开分类',
  },
  en: {
    siteDescription: 'AI Agent Skill discovery engine · compatibility registry',
    heroTitle: 'Discover Agent Skills',
    heroSubtitle: 'Indexed from GitHub, SkillHub & more — for Cursor, Claude, Kiro & Codex',
    heroBrowseCategories: 'Browse by category',
    browseByCategory: 'Browse by category',
    viewAll: 'View all',
    categorySkillCount: '{count} skills',
    officialSkills: 'Official sources',
    popularSkills: 'Popular (Stars)',
    exploreCatalog: 'Explore all',
    statsUpdated: 'Updated {time}',
    filterCategory: 'Category',
    filterSource: 'Source',
    filterPlatform: 'Platform',
    filterAll: 'All',
    featured: 'Featured',
    allSkills: 'All Skills',
    showingCount: 'Showing {shown} / {total}',
    pageRange: '{start}–{end} of {total} · Page {page}/{pages}',
    prev: 'Previous',
    next: 'Next',
    sortBy: 'Sort',
    sortScore: 'Top score',
    sortStars: 'Most stars',
    sortName: 'Name A–Z',
    filters: 'Filters',
    clearAll: 'Clear filters',
    noResults: 'No skills match your filters',
    loadMore: 'Load more',
    footerUpdated: 'Updated {date}',
    searchPlaceholder: 'Search skills…',
    searchInputPlaceholder: 'Search by name, description, tags…',
    searchNoResults: 'No results',
    back: 'Back',
    category: 'Category',
    source: 'Source',
    license: 'License',
    installs: 'Installs',
    compatiblePlatforms: 'Compatible platforms',
    tags: 'Tags',
    viewSource: 'View source',
    copyAria: 'Copy',
    copySuccess: 'Copied to clipboard',
    installGuide: 'Install locally',
    installCliTitle: 'CLI install',
    installCliPrereqBefore: 'Install ',
    installCliPrereqAfter: ' CLI and git first. Commands differ by platform.',
    installSourceHint: 'GitHub source — open to browse the skill files, or clone and copy into a directory below.',
    installManualNote: 'Agent skills directories (for manual install):',
    openOnGithub: 'Open on GitHub',
    installSourceUnavailable: 'No install source URL available.',
    toggleTheme: 'Toggle theme',
    toggleLocale: 'Switch language',
    collapseSidebar: 'Collapse categories',
    expandSidebar: 'Expand categories',
  },
} as const;

export type MessageKey = keyof typeof MESSAGES.zh;

export function resolveLocale(stored: string | null, browserLang?: string): Locale {
  // 1. Explicit user choice takes priority
  if (stored === 'zh' || stored === 'en') return stored;
  // 2. Detect from browser language (navigator.language)
  if (browserLang) {
    const lang = browserLang.toLowerCase();
    if (lang.startsWith('zh')) return 'zh';
  }
  // 3. Default to English
  return 'en';
}

export function localeToHtmlLang(locale: Locale): string {
  return locale === 'en' ? 'en' : 'zh-CN';
}

export function getCategoryLabel(locale: Locale, id: string): string {
  return CATEGORY_LABELS[locale][id] ?? id;
}

export function getCategoryGroupLabel(locale: Locale, groupId: string): string {
  return CATEGORY_GROUP_LABELS[locale][groupId] ?? groupId;
}

export function translate(locale: Locale, key: MessageKey, vars?: Record<string, string | number>): string {
  let text: string = MESSAGES[locale][key];
  if (vars) {
    for (const [name, value] of Object.entries(vars)) {
      text = text.replace(`{${name}}`, String(value));
    }
  }
  return text;
}
