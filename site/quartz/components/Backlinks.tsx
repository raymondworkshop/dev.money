import { QuartzComponent, QuartzComponentConstructor, QuartzComponentProps } from "./types"
import style from "./styles/backlinks.scss"
import { resolveRelative, simplifySlug } from "../util/path"
import { i18n } from "../i18n"
import { classNames } from "../util/lang"
import { QuartzPluginData } from "../plugins/vfile"

interface BacklinksOptions {
  hideWhenEmpty: boolean
  /** Max links shown before a More disclosure. */
  limit: number
}

const defaultOptions: BacklinksOptions = {
  hideWhenEmpty: true,
  limit: 5,
}

function entryDate(file: QuartzPluginData): Date | undefined {
  return file.dates?.published ?? file.dates?.created ?? file.dates?.modified
}

function formatRecentDate(d: Date): string {
  return d.toISOString().slice(0, 10)
}

function entryBlurb(file: QuartzPluginData): string | undefined {
  const raw =
    (typeof file.frontmatter?.description === "string" && file.frontmatter.description) ||
    (typeof file.description === "string" && file.description) ||
    undefined
  if (!raw) return undefined
  const text = raw.replace(/\s+/g, " ").trim()
  if (!text) return undefined
  return text.length > 90 ? `${text.slice(0, 89).trim()}…` : text
}

/** Drop site hubs/listings — they link broadly and aren't meaningful "mentions". */
function isNoiseBacklink(file: QuartzPluginData): boolean {
  const full = (file.slug ?? "").replace(/\\/g, "/")
  const simple = String(simplifySlug(file.slug!))
  if (simple === "index" || simple === "" || simple === "." || simple === "articles") {
    return true
  }
  if (full === "index" || full === "articles" || full.endsWith("/index")) {
    return true
  }
  const title = (file.frontmatter?.title ?? "").trim().toLowerCase()
  if (title === "news wiki" || title === "articles" || title === "all articles") {
    return true
  }
  return false
}

export default ((opts?: Partial<BacklinksOptions>) => {
  const options: BacklinksOptions = { ...defaultOptions, ...opts }

  const Backlinks: QuartzComponent = ({
    fileData,
    allFiles,
    displayClass,
    cfg,
  }: QuartzComponentProps) => {
    const slug = simplifySlug(fileData.slug!)
    const backlinkFiles = allFiles
      .filter(
        (file) =>
          file.slug !== fileData.slug &&
          !isNoiseBacklink(file) &&
          file.links?.includes(slug),
      )
      .sort((a, b) => {
        const da = entryDate(a)?.getTime() ?? 0
        const db = entryDate(b)?.getTime() ?? 0
        return db - da
      })

    if (options.hideWhenEmpty && backlinkFiles.length == 0) {
      return null
    }

    const limit = Math.max(0, options.limit)
    const visible = backlinkFiles.slice(0, limit)
    const rest = backlinkFiles.slice(limit)

    const renderItem = (f: QuartzPluginData) => {
      const date = entryDate(f)
      const blurb = entryBlurb(f)
      return (
        <li>
          {date && <span class="recent-date">{formatRecentDate(date)}</span>}
          <a href={resolveRelative(fileData.slug!, f.slug!)} class="internal">
            {f.frontmatter?.title}
          </a>
          {blurb && <span class="topic-blurb"> — {blurb}</span>}
        </li>
      )
    }

    return (
      <div class={classNames(displayClass, "backlinks")}>
        <h3>{i18n(cfg.locale).components.backlinks.title}</h3>
        {backlinkFiles.length > 0 ? (
          <>
            <ul class="backlinks-list">{visible.map(renderItem)}</ul>
            {rest.length > 0 && (
              <details class="backlinks-more">
                <summary>
                  More <span class="backlinks-more-count">({rest.length})</span>
                </summary>
                <ul class="backlinks-list">{rest.map(renderItem)}</ul>
              </details>
            )}
          </>
        ) : (
          <ul class="backlinks-list backlinks-list-empty">
            <li>{i18n(cfg.locale).components.backlinks.noBacklinksFound}</li>
          </ul>
        )}
      </div>
    )
  }

  Backlinks.css = style
  return Backlinks
}) satisfies QuartzComponentConstructor
