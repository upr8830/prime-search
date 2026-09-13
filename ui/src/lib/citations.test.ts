import { describe, expect, it } from "vitest";

import { normalizeSources, remarkCitations, splitCitations } from "./citations";

describe("citations", () => {
  it("splits [n] markers out of text, including adjacent ones and gaps", () => {
    expect(splitCitations("Covered [1][17].")).toEqual([
      { kind: "text", value: "Covered " },
      { kind: "cite", n: 1 },
      { kind: "cite", n: 17 },
      { kind: "text", value: "." },
    ]);
    expect(splitCitations("no citations")).toEqual([{ kind: "text", value: "no citations" }]);
  });

  it("turns the Sources block's indented URLs into autolinks, not code", () => {
    const sources = "## Sources\n\n[1] LCD L33822 - Glucose Monitors. CMS. primary_policy.\n    https://www.cms.gov/lcd?id=33822\n";
    expect(normalizeSources(sources)).toBe(
      "## Sources\n\n[1] LCD L33822 - Glucose Monitors. CMS. primary_policy.\n<https://www.cms.gov/lcd?id=33822>\n",
    );
  });

  it("marks citations in text but not inside code or links", () => {
    const tree = {
      type: "root",
      children: [
        { type: "paragraph", children: [{ type: "text", value: "Insulin-treated [2]; see " }, { type: "inlineCode", value: "[3]" }] },
        { type: "paragraph", children: [{ type: "link", children: [{ type: "text", value: "[4]" }] }] },
      ],
    };
    remarkCitations()(tree);
    const [first, second] = tree.children as { children: { type: string; value?: string; data?: unknown }[] }[];
    expect(first.children.map((child) => child.type)).toEqual(["text", "citation", "text", "inlineCode"]);
    expect(first.children[1].data).toEqual({ hName: "sup", hProperties: { dataCite: 2 } });
    expect(second.children[0].type).toBe("link");
  });
});
