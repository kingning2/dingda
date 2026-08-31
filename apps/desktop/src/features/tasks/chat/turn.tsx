/**
 * 助手单轮 — 思考折叠 / 工具卡 / Markdown。
 */

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { AgentThought } from "@desk/ui";
import { Lightbulb, Terminal } from "@desk/ui/icons";

import { CHAT_COPY, toolDisplayName, toolSummary, toolResultBody } from "./copy";
import { Disclosure, firstLine, latestLine } from "./disclosure";
import { ProgressiveText } from "./streaming-text";
import { chatStyles as s } from "./styles";
import type { ChatMessage } from "./use-chat";

function runThoughtSummary(thought: AgentThought): string {
  if (thought.status === "running") {
    const partial = thought.detailText?.trim();
    if (partial) {
      return latestLine(partial);
    }
    return CHAT_COPY.deepDiving;
  }
  if (thought.status === "error") {
    return "失败";
  }
  const body = thought.detailText?.trim();
  if (body) {
    return firstLine(body) || CHAT_COPY.toolDone;
  }
  return CHAT_COPY.toolDone;
}

function RunThoughtBody({
  thought,
  expanded,
  userToggled,
}: {
  thought: AgentThought;
  expanded: boolean;
  userToggled: boolean;
}) {
  const detailText = thought.detailText?.trim() ?? "";
  const live = thought.detailStreaming || thought.status === "running";
  const streaming = live && expanded && !userToggled;

  if (detailText) {
    return <ProgressiveText text={detailText} streaming={streaming} />;
  }

  if (thought.detail) {
    return <>{thought.detail}</>;
  }

  if (thought.status === "running") {
    return <span style={s.thinking}>{CHAT_COPY.deepDiving}</span>;
  }

  return null;
}

function Markdown({ text, streaming }: { text: string; streaming?: boolean }) {
  if (!text) {
    return null;
  }
  return (
    <div style={s.markdown}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          p: ({ children }) => <p style={s.markdownP}>{children}</p>,
          h1: ({ children }) => <h1 style={s.markdownHeading}>{children}</h1>,
          h2: ({ children }) => <h2 style={s.markdownHeading}>{children}</h2>,
          h3: ({ children }) => <h3 style={s.markdownHeading}>{children}</h3>,
          ul: ({ children }) => <ul style={s.markdownList}>{children}</ul>,
          ol: ({ children }) => <ol style={s.markdownList}>{children}</ol>,
          li: ({ children }) => <li style={s.markdownLi}>{children}</li>,
          a: ({ children, href }) => (
            <a href={href} style={s.markdownLink}>
              {children}
            </a>
          ),
          code: ({ children, className }) =>
            className ? (
              <code>{children}</code>
            ) : (
              <code style={s.markdownCode}>{children}</code>
            ),
          pre: ({ children }) => <pre style={s.markdownPre}>{children}</pre>,
          blockquote: ({ children }) => (
            <blockquote style={s.markdownBlockquote}>{children}</blockquote>
          ),
        }}
      >
        {text}
      </ReactMarkdown>
      {streaming ? <span style={s.cursor} aria-hidden /> : null}
    </div>
  );
}

export function AssistantTurn({ message }: { message: ChatMessage }) {
  const reasoning = message.reasoning?.trim() ?? "";
  const tools = message.tools ?? [];
  const runThoughts = message.runThoughts ?? [];
  const answer = message.content;
  const waiting =
    message.streaming &&
    !reasoning &&
    !answer &&
    tools.length === 0 &&
    runThoughts.length === 0 &&
    !message.reasoningStreaming;

  return (
    <div style={s.assistantTurn}>
      {waiting ? (
        <span style={s.thinking} role="status" aria-live="polite">
          {CHAT_COPY.deepDiving}
        </span>
      ) : null}

      {reasoning ? (
        <Disclosure
          title={CHAT_COPY.think}
          summary={
            message.reasoningStreaming ? latestLine(reasoning) : firstLine(reasoning) || reasoning
          }
          body={reasoning}
          running={message.reasoningStreaming}
          icon={<Lightbulb className="size-3.5" />}
          defaultExpanded={message.reasoningStreaming}
        />
      ) : null}

      {tools.map((tool) => (
        <Disclosure
          key={tool.id}
          title={toolDisplayName(tool.name)}
          summary={toolSummary(tool.name, tool.args, tool.result, tool.status === "running")}
          body={toolResultBody(tool.name, tool.result, tool.args)}
          running={tool.status === "running"}
          icon={<Terminal className="size-3.5" />}
          defaultExpanded={tool.status === "running"}
        />
      ))}

      {runThoughts.map((thought) => {
        const hasBody =
          Boolean(thought.detailText?.trim()) ||
          thought.detail != null ||
          thought.status === "running";
        return (
          <Disclosure
            key={thought.id}
            title={thought.label}
            summary={runThoughtSummary(thought)}
            body={
              hasBody
                ? ({ expanded, userToggled }) => (
                    <RunThoughtBody thought={thought} expanded={expanded} userToggled={userToggled} />
                  )
                : undefined
            }
            running={thought.status === "running" || thought.detailStreaming}
            icon={<Terminal className="size-3.5" />}
            defaultExpanded={thought.status === "running"}
          />
        );
      })}

      {answer ? <Markdown text={answer} streaming={message.streaming} /> : null}

      {!waiting &&
      !reasoning &&
      tools.length === 0 &&
      runThoughts.length === 0 &&
      !answer &&
      !message.streaming ? (
        <span style={s.thinking}>{CHAT_COPY.emptyReply}</span>
      ) : null}
    </div>
  );
}
