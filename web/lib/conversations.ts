import type { ConversationSummary } from "./types";

/** Sidebar conversation list from the mockup. */
export const conversations: ConversationSummary[] = [
  {
    id: "turn-1",
    title: "WMI execution → CAPEC mapping",
    mode: "query",
    timeLabel: "2m ago",
    group: "Today",
    active: true,
  },
  {
    id: "c-2",
    title: "Lateral movement via SMB shares",
    mode: "plan",
    timeLabel: "1h ago",
    group: "Today",
  },
  {
    id: "c-3",
    title: "Credential dumping techniques",
    mode: "query",
    timeLabel: "Yesterday",
    group: "Yesterday",
  },
  {
    id: "c-4",
    title: "Phishing → initial access chains",
    mode: "plan",
    timeLabel: "Mon",
    group: "This week",
  },
  {
    id: "c-5",
    title: "DNS tunneling detection patterns",
    mode: "query",
    timeLabel: "Sun",
    group: "This week",
  },
];
