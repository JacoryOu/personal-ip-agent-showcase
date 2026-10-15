/**
 * Public barrel for the doocs/md WeChat rendering engine.
 *
 * The implementation now lives in ./doocsRenderer/* split by responsibility:
 *  - types.ts       theme keys, section illustration + render option shapes
 *  - themes.ts      the four doocs themes and their palette configuration
 *  - markdown.ts    escaping, markdown stripping and section extraction
 *  - renderer.ts    the Markdown -> WeChat inline-styled HTML compiler
 *  - clipboard.ts   rich-text and single-image clipboard export
 *
 * Every previously exported symbol stays importable from this original path.
 */
export * from './doocsRenderer/types'
export * from './doocsRenderer/themes'
export * from './doocsRenderer/markdown'
export * from './doocsRenderer/renderer'
export * from './doocsRenderer/clipboard'
