import { PageLayout, SharedLayout } from "./quartz/cfg"
import * as Component from "./quartz/components"
import { QuartzComponentProps } from "./quartz/components/types"

const isHome = (page: QuartzComponentProps) => page.fileData.slug === "index"

const isTopicIndex = (page: QuartzComponentProps) => {
  const slug = page.fileData.slug ?? ""
  return slug !== "index" && /\/index$/.test(slug)
}

const isArticlePage = (page: QuartzComponentProps) => !isHome(page) && !isTopicIndex(page)

const leftChrome = [
  Component.PageTitle(),
  Component.MobileOnly(Component.Spacer()),
  Component.Search(),
  Component.Darkmode(),
  Component.TopicNav(),
]

// components shared across all pages
export const sharedPageComponents: SharedLayout = {
  head: Component.Head(),
  header: [],
  afterBody: [],
  footer: Component.Footer({
    links: {},
  }),
}

// components for pages that display a single page (e.g. a single note)
export const defaultContentPageLayout: PageLayout = {
  beforeBody: [
    Component.ConditionalRender({
      component: Component.Breadcrumbs(),
      condition: (page) => !isHome(page),
    }),
    Component.ConditionalRender({
      component: Component.ArticleTitle(),
      condition: (page) => {
        const slug = page.fileData.slug ?? ""
        return slug !== "index" && !/\/index$/.test(slug)
      },
    }),
    Component.ConditionalRender({
      component: Component.ContentMeta(),
      condition: (page) => {
        const slug = page.fileData.slug ?? ""
        return slug !== "index" && !/\/index$/.test(slug)
      },
    }),
    Component.TagList(),
  ],
  left: [
    ...leftChrome,
    Component.ConditionalRender({
      component: Component.ReaderMode(),
      condition: isArticlePage,
    }),
  ],
  // Desktop articles only: local graph in the right rail.
  right: [
    Component.ConditionalRender({
      component: Component.DesktopUp(Component.Graph()),
      condition: isArticlePage,
    }),
  ],
  // All viewports: Backlinks after the body, above Stay Updated / ©.
  afterBody: [
    Component.ConditionalRender({
      component: Component.Backlinks(),
      condition: isArticlePage,
    }),
  ],
}

// components for pages that display lists of pages  (e.g. tags or folders)
export const defaultListPageLayout: PageLayout = {
  beforeBody: [
    Component.Breadcrumbs(),
    Component.ConditionalRender({
      component: Component.ArticleTitle(),
      condition: (page) => {
        const slug = page.fileData.slug ?? ""
        return !/\/index$/.test(slug) && slug !== "index"
      },
    }),
    Component.ConditionalRender({
      component: Component.ContentMeta(),
      condition: (page) => {
        const slug = page.fileData.slug ?? ""
        return !/\/index$/.test(slug) && slug !== "index"
      },
    }),
  ],
  left: leftChrome,
  right: [],
}
