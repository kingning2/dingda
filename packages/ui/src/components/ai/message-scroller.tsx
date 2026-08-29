/**
 * MessageScroller — @shadcn/react 原语 + desk 样式包装。
 */

import type * as React from "react";
import {
  MessageScroller as Primitive,
  useMessageScroller,
  useMessageScrollerScrollable,
  useMessageScrollerVisibility,
} from "@shadcn/react/message-scroller";

import { cn } from "../../lib/cn";

function Root({
  className,
  ...props
}: React.ComponentProps<typeof Primitive.Root>) {
  return (
    <Primitive.Root
      className={cn("relative flex min-h-0 flex-1 flex-col overflow-hidden", className)}
      {...props}
    />
  );
}

function Viewport({
  className,
  ...props
}: React.ComponentProps<typeof Primitive.Viewport>) {
  return (
    <Primitive.Viewport
      className={cn("min-h-0 flex-1 overflow-y-auto outline-none", className)}
      {...props}
    />
  );
}

function Content({
  className,
  ...props
}: React.ComponentProps<typeof Primitive.Content>) {
  return (
    <Primitive.Content
      className={cn("mx-auto flex w-full max-w-2xl flex-col gap-3 p-3", className)}
      {...props}
    />
  );
}

function Item({
  className,
  ...props
}: React.ComponentProps<typeof Primitive.Item>) {
  return <Primitive.Item className={cn("w-full", className)} {...props} />;
}

function Button({
  className,
  ...props
}: React.ComponentProps<typeof Primitive.Button>) {
  return (
    <Primitive.Button
      className={cn(
        "absolute bottom-3 left-1/2 z-10 -translate-x-1/2 rounded-full border border-border bg-background px-3 py-1 text-[length:var(--text-xs)] shadow-sm",
        className,
      )}
      {...props}
    />
  );
}

export const MessageScroller = {
  Provider: Primitive.Provider,
  Root,
  Viewport,
  Content,
  Item,
  Button,
};

export {
  useMessageScroller,
  useMessageScrollerScrollable,
  useMessageScrollerVisibility,
};
