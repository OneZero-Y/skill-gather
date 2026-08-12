export type Locale = 'zh' | 'en';

export const LOCALE_STORAGE_KEY = 'skill-store-locale';

const CATEGORY_LABELS: Record<Locale, Record<string, string>> = {
  zh: {
    development: '开发',
    creative: '创意',
    document: '文档',
    devops: 'DevOps',
    security: '安全',
    data: '数据',
    content: '内容',
    ecommerce: '电商',
    education: '教育',
    productivity: '效率',
    other: '其他',
  },
  en: {
    development: 'Development',
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

const MESSAGES = {
  zh: {
    siteDescription: 'AI Agent Skill 发现引擎 · 兼容性注册表',
    statsSummary: '{total} 个 skill · {sources} 个来源',
    filterCategory: '分类',
    filterSource: '来源',
    filterPlatform: '平台',
    filterAll: '全部',
    featured: '精选高分',
    allSkills: '全部 Skill',
    showingCount: '显示 {shown} / {total} 条',
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
    copyInstall: '复制安装命令',
    toggleTheme: '切换主题',
    toggleLocale: '切换语言',
  },
  en: {
    siteDescription: 'AI Agent Skill discovery engine · compatibility registry',
    statsSummary: '{total} skills · {sources} sources',
    filterCategory: 'Category',
    filterSource: 'Source',
    filterPlatform: 'Platform',
    filterAll: 'All',
    featured: 'Featured',
    allSkills: 'All Skills',
    showingCount: 'Showing {shown} / {total}',
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
    copyInstall: 'Copy install command',
    toggleTheme: 'Toggle theme',
    toggleLocale: 'Switch language',
  },
} as const;

export type MessageKey = keyof typeof MESSAGES.zh;

export function resolveLocale(stored: string | null, browserLang: string): Locale {
  if (stored === 'zh' || stored === 'en') return stored;
  return browserLang.toLowerCase().startsWith('zh') ? 'zh' : 'en';
}

export function localeToHtmlLang(locale: Locale): string {
  return locale === 'en' ? 'en' : 'zh-CN';
}

export function getCategoryLabel(locale: Locale, id: string): string {
  return CATEGORY_LABELS[locale][id] ?? id;
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
