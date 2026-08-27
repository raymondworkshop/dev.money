// @ts-ignore
import darkmodeScript from "./scripts/darkmode.inline"
import styles from "./styles/darkmode.scss"
import { QuartzComponent, QuartzComponentConstructor, QuartzComponentProps } from "./types"
import { i18n } from "../i18n"
import { classNames } from "../util/lang"

const Darkmode: QuartzComponent = ({ displayClass, cfg }: QuartzComponentProps) => {
  const darkLabel = i18n(cfg.locale).components.themeToggle.darkMode
  const lightLabel = i18n(cfg.locale).components.themeToggle.lightMode

  return (
    <button
      class={classNames(displayClass, "darkmode")}
      type="button"
      aria-label={`${lightLabel} / ${darkLabel}`}
      title={`${lightLabel} / ${darkLabel}`}
    >
      <span class="darkmode-side darkmode-light">
        <svg class="darkmode-sun" viewBox="0 0 24 24" aria-hidden="true">
          <circle cx="12" cy="12" r="3.5" fill="none" stroke="currentColor" stroke-width="1.5" />
          <path
            d="M12 2.5v2.2M12 19.3v2.2M2.5 12h2.2M19.3 12h2.2M5.1 5.1l1.6 1.6M17.3 17.3l1.6 1.6M5.1 18.9l1.6-1.6M17.3 6.7l1.6-1.6"
            fill="none"
            stroke="currentColor"
            stroke-width="1.5"
            stroke-linecap="round"
          />
        </svg>
        <span class="darkmode-label">{lightLabel}</span>
      </span>

      <span class="darkmode-track" aria-hidden="true">
        <span class="darkmode-thumb"></span>
      </span>

      <span class="darkmode-side darkmode-dark">
        <span class="darkmode-label">{darkLabel}</span>
        <svg class="darkmode-moon" viewBox="0 0 24 24" aria-hidden="true">
          <path
            d="M18.5 14.2A7.2 7.2 0 019.8 5.5 7.5 7.5 0 1018.5 14.2z"
            fill="none"
            stroke="currentColor"
            stroke-width="1.5"
            stroke-linejoin="round"
          />
        </svg>
      </span>
    </button>
  )
}

Darkmode.beforeDOMLoaded = darkmodeScript
Darkmode.css = styles

export default (() => Darkmode) satisfies QuartzComponentConstructor
