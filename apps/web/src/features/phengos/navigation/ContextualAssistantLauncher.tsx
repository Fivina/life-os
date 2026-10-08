import { Minus, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { useNavigate } from "react-router-dom";

import { AssistantPage } from "../../assistant/AssistantPage";
import "./ContextualAssistantLauncher.css";

export type ChatWorkspace = "calendar" | "kitchen";

/** A view of the canonical Chat runtime that leaves the underlying workspace intact. */
export function ContextualAssistantLauncher({ workspace }: { workspace: ChatWorkspace }) {
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const [mounted, setMounted] = useState(false);
  const [narrow, setNarrow] = useState(() => window.matchMedia?.("(max-width: 640px)").matches ?? false);
  const launcher = useRef<HTMLButtonElement>(null);
  const dialog = useRef<HTMLDialogElement>(null);
  const presentation = useRef<boolean | null>(null);
  const label = workspace === "calendar" ? "Calendar" : "Kitchen";

  useEffect(() => {
    const media = window.matchMedia?.("(max-width: 640px)");
    if (!media) return;
    const update = () => setNarrow(media.matches);
    if (typeof media.addEventListener === "function") {
      media.addEventListener("change", update);
      return () => media.removeEventListener("change", update);
    }
    // Older WebViews and deliberately minimal test doubles expose the legacy API.
    if (typeof media.addListener === "function") {
      media.addListener(update);
      return () => media.removeListener(update);
    }
  }, []);

  useEffect(() => {
    const element = dialog.current;
    if (!element) return;
    if (!open) {
      if (element.open) {
        element.close();
        launcher.current?.focus({ preventScroll: true });
      }
      presentation.current = null;
      return;
    }
    // A dialog must be closed before changing between modeless and modal modes.
    const firstOpen = !element.open;
    if (element.open && presentation.current !== narrow) element.close();
    if (!element.open) {
      if (narrow) element.showModal();
      else element.show();
    }
    presentation.current = narrow;
    if (firstOpen) element.querySelector<HTMLTextAreaElement>("textarea")?.focus({ preventScroll: true });
  }, [open, narrow]);

  function close() { setOpen(false); }

  function openFullChat(threadId: string | null) {
    close();
    navigate(threadId ? `/chat?thread=${encodeURIComponent(threadId)}` : "/chat");
  }

  return <>
    <button ref={launcher} className="pn-context-chat-trigger" data-workspace={workspace} type="button"
      aria-label={`${open ? "Minimize" : "Open"} ${label} chat`} title={`${label} chat`}
      aria-haspopup="dialog" aria-expanded={open} aria-controls={`pn-context-chat-${workspace}`}
      onClick={() => { setMounted(true); setOpen(value => !value); }}>
      <span className="pn-circle" aria-hidden="true" />
    </button>
    {createPortal(<dialog ref={dialog} id={`pn-context-chat-${workspace}`} className="pn-context-chat" data-workspace={workspace}
      aria-label={`${label} chat`} aria-modal={open && narrow ? true : undefined}
      onCancel={event => {
        event.preventDefault();
        // Confirmation/feedback dialogs own Escape while they are visible.
        if (!dialog.current?.querySelector('[role="dialog"][aria-modal="true"]')) close();
      }}
      onKeyDown={event => {
        if (event.key !== "Escape" || event.defaultPrevented || narrow) return;
        if ((event.target as HTMLElement).closest('[role="dialog"][aria-modal="true"]')) return;
        event.preventDefault();
        event.stopPropagation();
        close();
      }}>
      <header className="pn-context-chat-heading">
        <span><i className="pn-circle" aria-hidden="true" />{label} chat</span>
        <div>
          <button type="button" aria-label="Minimize chat" title="Minimize chat" onClick={close}><Minus size={17} /></button>
          <button type="button" aria-label="Close chat" title="Close chat" onClick={close}><X size={17} /></button>
        </div>
      </header>
      {mounted && <AssistantPage mode="embedded" workspaceKey={workspace}
        initialRole={workspace === "kitchen" ? "CHEF" : "GENERAL_ASSISTANT"} onOpenFullChat={openFullChat} />}
    </dialog>, document.body)}
  </>;
}
