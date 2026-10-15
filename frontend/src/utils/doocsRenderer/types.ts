// doocs/md layout & style rendering engine for WeChat Official Accounts.
// See the original module docblock in ../../../utils/doocsRenderer.ts for the full
// feature overview of the Markdown-to-WeChat-HTML compiler.

export type DoocsThemeKey = 'emerald' | 'ocean' | 'orange' | 'purple'

export interface SectionIllustration {
  id?: string
  section_title: string
  section_index?: number
  anchor?: string
  caption: string
  prompt: string
  prompt_zh?: string
  prompt_en?: string
  image_url?: string
  is_generating?: boolean
}

export interface DoocsRenderOptions {
  theme?: DoocsThemeKey | string
  title?: string
  author?: string
  illustrations?: SectionIllustration[]
  enableFootnotes?: boolean
  includeHeaderInBody?: boolean
}
