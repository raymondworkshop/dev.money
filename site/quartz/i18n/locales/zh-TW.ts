import { Translation } from "./definition"

export default {
  propertyDefaults: {
    title: "未有標題",
    description: "未有描述",
  },
  components: {
    callout: {
      note: "筆記",
      abstract: "摘要",
      info: "提示",
      todo: "待辦",
      tip: "提示",
      success: "成功",
      question: "問題",
      warning: "警告",
      failure: "失敗",
      danger: "危險",
      bug: "錯誤",
      example: "範例",
      quote: "引用",
    },
    backlinks: {
      title: "提到呢篇",
      noBacklinksFound: "暫時未有其他文章提到呢篇",
    },
    themeToggle: {
      lightMode: "淺色",
      darkMode: "深色",
    },
    readerMode: {
      title: "閱讀模式",
    },
    explorer: {
      title: "瀏覽",
    },
    footer: {
      createdWith: "Created with",
    },
    graph: {
      title: "關係圖",
    },
    recentNotes: {
      title: "近排筆記",
      seeRemainingMore: ({ remaining }) => `再睇多 ${remaining} 篇 →`,
    },
    transcludes: {
      transcludeOf: ({ targetSlug }) => `包含 ${targetSlug}`,
      linkToOriginal: "去原文",
    },
    search: {
      title: "搵",
      searchBarPlaceholder: "搵文章…",
    },
    tableOfContents: {
      title: "目錄",
    },
    contentMeta: {
      readingTime: ({ minutes }) => `大概要睇 ${minutes} 分鐘`,
    },
  },
  pages: {
    rss: {
      recentNotes: "近排筆記",
      lastFewNotes: ({ count }) => `近排 ${count} 篇`,
    },
    error: {
      title: "搵唔到",
      notFound: "呢篇係私人筆記，或者已經唔存在。",
      home: "返主頁",
    },
    folderContent: {
      folder: "資料夾",
      itemsUnderFolder: ({ count }) => `呢個資料夾有 ${count} 篇文章。`,
    },
    tagContent: {
      tag: "標籤",
      tagIndex: "標籤一覽",
      itemsUnderTag: ({ count }) => `呢個標籤有 ${count} 篇文章。`,
      showingFirst: ({ count }) => `顯示頭 ${count} 個標籤。`,
      totalTags: ({ count }) => `合共 ${count} 個標籤。`,
    },
  },
} as const satisfies Translation
