import { Fragment, type CSSProperties, type ReactNode } from "react";
import type { CodeLang } from "@/lib/types";
import { CONSOLE_BG, SHADOW } from "@/lib/ui";

/** Token colors — Woven Dusk console palette. */
const COLOR = {
  string: "#4e9e96",
  number: "#c9924a",
  keyword: "#c9924a",
  method: "#c9924a",
  comment: "#5e726c",
  plain: "#c9c6bd",
} as const;

type TokType = keyof typeof COLOR;
interface Pattern {
  re: RegExp;
  type: TokType;
}

function patternsFor(lang: CodeLang): Pattern[] {
  const common: Pattern[] = [
    { re: /"[^"]*"/y, type: "string" },
    { re: /'[^']*'/y, type: "string" },
    { re: /\b\d+(?:\.\d+)?\b/y, type: "number" },
  ];
  if (lang === "cypher") {
    return [
      {
        re: /\b(?:MATCH|OPTIONAL|WHERE|RETURN|LIMIT|WITH|UNWIND|ORDER|BY|SKIP|AND|OR|NOT|AS|DISTINCT|CALL|MERGE|CREATE|SET)\b/y,
        type: "keyword",
      },
      ...common,
    ];
  }
  if (lang === "gremlin") {
    return [{ re: /(?<=\.)[a-zA-Z_]\w*/y, type: "method" }, ...common];
  }
  return common;
}

function tokenizeLine(line: string, patterns: Pattern[]): ReactNode[] {
  const trimmed = line.trimStart();
  if (trimmed.startsWith("#") || trimmed.startsWith("//")) {
    return [
      <span key="c" style={{ color: COLOR.comment }}>
        {line}
      </span>,
    ];
  }

  const nodes: ReactNode[] = [];
  let plain = "";
  let i = 0;
  const flushPlain = (key: string) => {
    if (plain) {
      nodes.push(<Fragment key={key}>{plain}</Fragment>);
      plain = "";
    }
  };

  while (i < line.length) {
    let matched = false;
    for (const { re, type } of patterns) {
      re.lastIndex = i;
      const m = re.exec(line);
      if (m && m.index === i && m[0].length > 0) {
        flushPlain(`p${i}`);
        nodes.push(
          <span key={`t${i}`} style={{ color: COLOR[type] }}>
            {m[0]}
          </span>,
        );
        i += m[0].length;
        matched = true;
        break;
      }
    }
    if (!matched) {
      plain += line[i];
      i += 1;
    }
  }
  flushPlain("pEnd");
  return nodes;
}

interface CodeBlockProps {
  code: string;
  lang?: CodeLang;
  /** Teal-tinted ring for emphasized blocks (gate, validated query). */
  emphasis?: boolean;
  className?: string;
  style?: CSSProperties;
}

/** Read-only mono code block with lightweight Woven Dusk syntax tinting. */
export function CodeBlock({
  code,
  lang = "text",
  emphasis,
  className = "",
  style,
}: CodeBlockProps) {
  const patterns = patternsFor(lang);
  const lines = code.split("\n");
  return (
    <pre
      className={`m-0 overflow-x-auto rounded-lg px-3.5 py-3 font-mono text-[11px] leading-[1.65] ${className}`}
      style={{
        background: CONSOLE_BG,
        boxShadow: emphasis ? "rgba(78,158,150,0.25) 0 0 0 1px" : SHADOW.hairline,
        color: COLOR.plain,
        ...style,
      }}
    >
      {lines.map((line, idx) => (
        <Fragment key={idx}>
          {tokenizeLine(line, patterns)}
          {idx < lines.length - 1 ? "\n" : null}
        </Fragment>
      ))}
    </pre>
  );
}
