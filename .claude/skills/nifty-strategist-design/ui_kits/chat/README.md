# Chat UI kit

A high-fidelity recreation of the Nifty Strategist **conversational chat surface** — `/chat/:threadId` in production. This is the primary entry point for most users: a left rail of past threads, a centered message stream rendered as markdown, a sticky composer pinned to the bottom, and a render-UI confirmation card whenever the agent wants to place an order.

## What's inside

- `index.html` — the entry point. Boots React + Babel and assembles everything.
- `Icon.jsx` — the same tiny Lucide adapter used in the cockpit kit.
- `Sidebar.jsx` — left rail with new-chat button, thread list, and a small user footer.
- `MessageBubble.jsx` — renders one assistant or user message; the assistant variant supports markdown, headings, bullet lists, and an inline **trade confirmation card** (`⚠️ Approve / Reject`).
- `ChatInput.jsx` — the composer at the bottom: auto-resizing textarea + image / file / voice / send.
- `App.jsx` — stitches it together, manages thread state, replies, and the confirm flow.
- `styles.css` — local layout & component styling, leans on `colors_and_type.css` tokens.

## Tone in the sample replies

The kit ships with three sample assistant messages that match the voice rules in the main README — fact, then interpretation, then suggestion, in calm second person. Use them as references when writing real product copy.

## Coverage

Covers the chat thread itself, the composer, and the confirmation card. Not covered (would each be a separate surface): voice transcription UI, slash-command picker, file attachment preview row, the model-selector dropdown, the settings drawer.
