import { IconBulb, IconHome, IconParts, IconScan, IconStore, IconWrench } from "./components/Icons";

export type Tab = "dashboard" | "scan" | "parts" | "recommend" | "build" | "workbench" | "market" | "cart";

export const NAV: { tab: Tab; label: string; short: string; Icon: typeof IconHome }[] = [
  { tab: "dashboard", label: "Dashboard", short: "Home", Icon: IconHome },
  { tab: "scan", label: "Scan parts", short: "Scan", Icon: IconScan },
  { tab: "parts", label: "My parts", short: "Parts", Icon: IconParts },
  { tab: "recommend", label: "Build with what I have", short: "Ideas", Icon: IconBulb },
  { tab: "build", label: "Guided build", short: "Build", Icon: IconWrench },
  { tab: "workbench", label: "Tools and testing", short: "Tools", Icon: IconParts },
  { tab: "market", label: "Marketplace", short: "Market", Icon: IconStore },
];
