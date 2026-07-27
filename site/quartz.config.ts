import { QuartzConfig } from "./quartz/cfg"
import * as Plugin from "./quartz/plugins"

/**
 * Quartz 4 Configuration
 *
 * See https://quartz.jzhao.xyz/configuration for more information.
 */
const config: QuartzConfig = {
  configuration: {
    pageTitle: "dev.news-wiki",
    pageTitleSuffix: "",
    enableSPA: true,
    enablePopovers: true,
    analytics: null,
    locale: "zh-CN",
    baseUrl: "news-wiki.pages.dev",
    ignorePatterns: ["private", "templates", ".obsidian"],
    defaultDateType: "modified",
    theme: {
      fontOrigin: "local",
      cdnCaching: true,
      typography: {
        header: "SF Mono",
        body: "SF Mono",
        code: "SF Mono",
      },
      colors: {
        lightMode: {
          light: "#f5f6f4",
          lightgray: "#e2e5e0",
          gray: "#8a9188",
          darkgray: "#3a4340",
          dark: "#1a2428",
          secondary: "#3d6b5a",
          tertiary: "#5a8a76",
          highlight: "rgba(61, 107, 90, 0.12)",
          textHighlight: "#d4e8a8aa",
        },
        darkMode: {
          light: "#121816",
          lightgray: "#2a332f",
          gray: "#7a8580",
          darkgray: "#d0d6d2",
          dark: "#f0f2ef",
          secondary: "#7aab96",
          tertiary: "#9bc4b0",
          highlight: "rgba(122, 171, 150, 0.16)",
          textHighlight: "#5a7a3088",
        },
      },
    },
  },
  plugins: {
    transformers: [
      Plugin.FrontMatter(),
      Plugin.CreatedModifiedDate({
        priority: ["frontmatter", "filesystem"],
      }),
      Plugin.SyntaxHighlighting({
        theme: {
          light: "github-light",
          dark: "github-dark",
        },
        keepBackground: false,
      }),
      Plugin.ObsidianFlavoredMarkdown({ enableInHtmlEmbed: false }),
      Plugin.GitHubFlavoredMarkdown(),
      Plugin.TableOfContents(),
      Plugin.CrawlLinks({ markdownLinkResolution: "shortest" }),
      Plugin.Description(),
      Plugin.Latex({ renderEngine: "katex" }),
    ],
    filters: [Plugin.RemoveDrafts()],
    emitters: [
      Plugin.AliasRedirects(),
      Plugin.ComponentResources(),
      Plugin.ContentPage(),
      Plugin.FolderPage(),
      Plugin.TagPage(),
      Plugin.ContentIndex({
        enableSiteMap: true,
        enableRSS: true,
      }),
      Plugin.Assets(),
      Plugin.Static(),
      Plugin.Favicon(),
      Plugin.NotFoundPage(),
      // Keep builds fast and deployment-friendly.
      // Plugin.CustomOgImages(),
    ],
  },
}

export default config
