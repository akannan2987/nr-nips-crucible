// SH-13: the page says which instance it is, in words and in colour, so
// that a tester with two tabs open never confuses beta with production.
// The colours are the ones the documents use: indigo for production, amber
// for beta (docs/14-beta-instance.md). Class names are written out in full
// so the style build can find them. Shared by the layout's top bar and,
// since SH-3a, by the login page, which must say where it belongs before
// anything else is shown.
export const INSTANCE_STYLE = {
  default: {
    bar: 'bg-white border-b',
    pill: 'bg-indigo-100 text-indigo-800 border-indigo-300',
    title: 'the default instance: the real registry',
  },
  named: {
    bar: 'bg-amber-50 border-b-2 border-amber-300',
    pill: 'bg-amber-100 text-amber-900 border-amber-400',
    title: 'a named instance: a copy for testing, separate from production',
  },
}

export const styleFor = (instance) =>
  instance && instance.name ? INSTANCE_STYLE.named : INSTANCE_STYLE.default

// The tab title as index.html wrote it, before any instance prefix.
export const BASE_TITLE = document.title
