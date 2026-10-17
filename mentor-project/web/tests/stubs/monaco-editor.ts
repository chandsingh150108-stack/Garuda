/** Vitest stub for monaco-editor: the real package has no entry resolvable
 * under vitest's bundler and cannot run in jsdom anyway. Code.tsx only
 * imports it lazily when `?plain=1` is absent. */
export const editor = {
  create: () => ({
    dispose: () => {},
    deltaDecorations: () => [],
    revealLinesInCenter: () => {},
  }),
};

export class Range {
  constructor(..._args: number[]) {}
}
