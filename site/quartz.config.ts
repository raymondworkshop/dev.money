import { QuartzConfig } from "./quartz/cfg"
import * as Plugin from "./quartz/plugins"

/**
 * Quartz 4 Configuration
 *
 * See https://quartz.jzhao.xyz/configuration for more information.
 */
const config: QuartzConfig = {
  configuration: {
    pageTitle: "dev.business",
    pageTitleSuffix: " - dev.business",
    enableSPA: true,
    enablePopovers: true,
    analytics: null,
    locale: "zh-CN",
    baseUrl: "dev-business.local",
    ignorePatterns: ["private", "templates", ".obsidian"],
    defaultDateType: "modified",
    theme: {
      fontOrigin: "googleFonts",
      cdnCaching: true,
      typography: {
        header: "Noto Sans SC",
        body: "Noto Sans SC",
        code: "IBM Plex Mono",
      },
      colors: {
        lightMode: {
          light: "#fbfaf7",
          lightgray: "#e8e2d8",
          gray: "#b7aa98",
          darkgray: "#4f4638",
          dark: "#241f18",
          secondary: "#7c4a03",
          tertiary: "#b7791f",
          highlight: "rgba(183, 121, 31, 0.14)",
          textHighlight: "#fff2a8aa",
        },
        darkMode: {
          light: "#11100d",
          lightgray: "#2d2923",
          gray: "#756b5b",
          darkgray: "#d9d0c1",
          dark: "#fff8ed",
          secondary: "#f0b35a",
          tertiary: "#d69e2e",
          highlight: "rgba(240, 179, 90, 0.16)",
          textHighlight: "#7c5a0088",
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
