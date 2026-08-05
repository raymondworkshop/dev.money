import { QuartzComponent, QuartzComponentConstructor, QuartzComponentProps } from "./types"
import { concatenateResources } from "../util/resources"
import StayUpdated from "./StayUpdated"
import style from "./styles/footer.scss"

interface Options {
  links: Record<string, string>
}

const FooterSubscribe = StayUpdated({ idPrefix: "footer-subscribe" })

export default ((opts?: Options) => {
  const Footer: QuartzComponent = (props: QuartzComponentProps) => {
    const { displayClass, ...rest } = props
    const year = new Date().getFullYear()
    const links = Object.entries(opts?.links ?? {})
    return (
      <footer class={`${displayClass ?? ""}`}>
        <FooterSubscribe {...rest} />
        <p class="footer-copy">© {year} Bean Workshop Ltd.</p>
        {links.length > 0 && (
          <ul>
            {links.map(([text, link]) => (
              <li>
                <a href={link}>{text}</a>
              </li>
            ))}
          </ul>
        )}
      </footer>
    )
  }

  Footer.css = concatenateResources(style, FooterSubscribe.css)
  Footer.afterDOMLoaded = FooterSubscribe.afterDOMLoaded
  return Footer
}) satisfies QuartzComponentConstructor
