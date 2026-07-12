"use client";

import { useEffect, useRef, useState, type FormEvent, type KeyboardEvent } from "react";
import { Button } from "@/components/ui/button";
import { Send, Sparkles } from "lucide-react";

interface ChatInputProps {
  onSend: (query: string) => void;
  disabled?: boolean;
}

export function ChatInput({ onSend, disabled }: ChatInputProps) {
  const [value, setValue] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (!disabled) textareaRef.current?.focus();
  }, [disabled]);

  const adjustHeight = () => {
    const el = textareaRef.current;
    if (el) {
      el.style.height = "auto";
      el.style.height = `${Math.min(el.scrollHeight, 160)}px`;
    }
  };

  const handleSubmit = (e?: FormEvent) => {
    e?.preventDefault();
    const trimmed = value.trim();
    if (!trimmed || disabled) return;
    onSend(trimmed);
    setValue("");
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
    }
    textareaRef.current?.focus();
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
    if (e.key === "Escape") {
      setValue("");
    }
  };

  return (
    <form onSubmit={handleSubmit} role="form" aria-label="Ask a question" className="w-full">
      <div className="relative flex items-end gap-2 rounded-2xl border border-input bg-background px-4 py-3 shadow-sm ring-offset-background transition-all focus-within:ring-2 focus-within:ring-ring focus-within:ring-offset-2">
        <Sparkles className="mb-1 h-4 w-4 shrink-0 text-muted-foreground" />
        <textarea
          ref={textareaRef}
          value={value}
          onChange={(e) => {
            setValue(e.target.value);
            adjustHeight();
          }}
          onKeyDown={handleKeyDown}
          placeholder="Ask a question about your data..."
          disabled={disabled}
          rows={1}
          className="min-h-[24px] w-full resize-none bg-transparent text-sm outline-none placeholder:text-muted-foreground/60 disabled:cursor-not-allowed"
          aria-label="Your question"
        />
        <Button
          type="submit"
          size="icon"
          disabled={disabled || !value.trim()}
          className="mb-0.5 h-8 w-8 shrink-0 rounded-full"
          aria-label="Submit question"
        >
          <Send className="h-4 w-4" />
        </Button>
      </div>
    </form>
  );
}
