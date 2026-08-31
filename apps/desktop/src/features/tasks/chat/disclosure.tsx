/**
 * Harness 风格折叠行 — 标题 · 摘要 · 可展开正文。
 */

import { ChevronDown, ChevronRight } from "@desk/ui/icons";
import { useState, type ReactNode } from "react";

import { chatStyles as s } from "./styles";

export function firstLine(text: string): string {
  const newline = text.indexOf("\n");
  return newline === -1 ? text : text.slice(0, newline);
}

export function latestLine(text: string): string {
  const visible = text.trimEnd();
  const newline = visible.lastIndexOf("\n");
  return newline === -1 ? visible : visible.slice(newline + 1);
}

export interface DisclosureProps {
  title: string;
  summary: string;
  body?: ReactNode | ((ctx: { expanded: boolean; userToggled: boolean }) => ReactNode);
  running?: boolean;
  icon: ReactNode;
  defaultExpanded?: boolean;
}

export function Disclosure({
  title,
  summary,
  body,
  running,
  icon,
  defaultExpanded = false,
}: DisclosureProps) {
  const expandable = body != null && body !== false && body !== "";
  const [expanded, setExpanded] = useState(defaultExpanded);
  const [userToggled, setUserToggled] = useState(false);
  const open = expanded && expandable;
  const bodyContent =
    typeof body === "function" ? body({ expanded: open, userToggled }) : body;

  return (
    <div style={s.disclosure}>
      <button
        type="button"
        style={s.disclosureRow}
        aria-expanded={open}
        onClick={() => {
          if (expandable) {
            setUserToggled(true);
            setExpanded((value) => !value);
          }
        }}
      >
        <span style={s.disclosureLeading}>{icon}</span>
        <span style={s.disclosureTitle}>{title}</span>
        <span style={s.disclosureSeparator} aria-hidden />
        <span style={s.disclosureSummary(running)}>{summary}</span>
        {expandable ? (
          <span style={s.disclosureChevron} aria-hidden>
            {open ? <ChevronDown className="size-3.5" /> : <ChevronRight className="size-3.5" />}
          </span>
        ) : null}
      </button>
      {open && bodyContent ? <div style={s.disclosureBody}>{bodyContent}</div> : null}
    </div>
  );
}

export interface ProcessToggleProps {
  label: string;
  open: boolean;
  onToggle: () => void;
}

/** Turn 级过程折叠控制器（对齐 harness TurnProcessNodeView）。 */
export function ProcessToggle({ label, open, onToggle }: ProcessToggleProps) {
  return (
    <button
      type="button"
      style={s.processToggle(open)}
      aria-expanded={open}
      onClick={onToggle}
    >
      <span style={s.processToggleLabel}>{label}</span>
      <ChevronDown className="size-4" style={s.processToggleChevron(open)} aria-hidden />
    </button>
  );
}
