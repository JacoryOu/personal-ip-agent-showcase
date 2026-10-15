// Data contracts for the canvas renderers.

export interface XhsCardData {
  card_type: 'cover' | 'point' | 'summary'
  index?: string
  badge?: string
  title?: string
  subtitle?: string
  tags?: string[]
  author?: string
  hook?: string
  image_prompt?: string
  suggested_prompt?: string
  step_number?: string
  key_points?: string[]
  pain_point_analysis?: string
  highlight?: string
  golden_quote?: string
  checklist?: string[]
  interaction_prompt?: string
  cta?: string
}

export interface WechatCoverData {
  title: string
  subtitle: string
  badge: string
  author: string
  ratio: string
}

export interface WechatQuoteData {
  quote: string
  source: string
  author: string
  ratio: string
}

export type VisualTheme = 'dark_gold' | 'indigo_purple' | 'clean_minimal'
