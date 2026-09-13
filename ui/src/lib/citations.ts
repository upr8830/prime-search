/**
 * `[n]` citations in a PRIME answer (docs/03 §8, docs/07 §3).
 *
 * The synthesizer writes `[n]` markers where n is `Citation.n`. Numbers can have gaps,
 * and a number with no citation is left as plain text. Its Sources block puts each URL on
 * its own indented line; the rewrite below turns those into autolinks, so Markdown never
 * reads them as indented code.
 */

const MARKER = /\[(\d{1,3})\]/g;
const INDENTED_URL = /^[ \t]+(https?:\/\/\S+)[ \t]*$/gm;

export type Piece = { kind: "text"; value: string } | { kind: "cite"; n: number };

/** "Covered [1][3]." -> text "Covered ", cite 1, cite 3, text "." */
export function splitCitations(text: string): Piece[] {
  const pieces: Piece[] = [];
  let last = 0;
  for (const match of text.matchAll(MARKER)) {
    const index = match.index ?? 0;
    if (index > last) pieces.push({ kind: "text", value: text.slice(last, index) });
    pieces.push({ kind: "cite", n: Number(match[1]) });
    last = index + match[0].length;
  }
  if (last < text.length) pieces.push({ kind: "text", value: text.slice(last) });
  return pieces;
}

/** Indented URL lines (the Sources block) become `<url>` autolinks on their own line. */
export function normalizeSources(markdown: string): string {
  return markdown.replace(INDENTED_URL, (_line, url: string) => `<${url}>`);
}

// A minimal mdast shape, so the plugin needs no @types/mdast of its own.
type MdNode = {
  type: string;
  value?: string;
  children?: MdNode[];
  data?: { hName?: string; hProperties?: Record<string, unknown> };
};

const SKIP = new Set(["code", "inlineCode", "link", "linkReference", "definition", "html"]);

function transform(node: MdNode): void {
  if (!node.children) return;
  const children: MdNode[] = [];
  for (const child of node.children) {
    if (child.type === "text" && child.value && MARKER.test(child.value)) {
      MARKER.lastIndex = 0;
      for (const piece of splitCitations(child.value)) {
        children.push(
          piece.kind === "text"
            ? { type: "text", value: piece.value }
            : {
                type: "citation",
                children: [{ type: "text", value: `[${piece.n}]` }],
                data: { hName: "sup", hProperties: { dataCite: piece.n } },
              },
        );
      }
    } else {
      MARKER.lastIndex = 0;
      if (!SKIP.has(child.type)) transform(child);
      children.push(child);
    }
  }
  node.children = children;
}

/** remark plugin: `[n]` in text becomes `<sup data-cite="n">[n]</sup>` for `CitationRef`. */
export function remarkCitations() {
  return (tree: unknown) => {
    transform(tree as MdNode);
  };
}
