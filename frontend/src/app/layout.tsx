import type { Metadata } from "next";
import { Providers } from "./providers";
import "./globals.css";

export const metadata: Metadata = {
  title: "Signal Clone",
  description: "A real-time messaging app — Signal-style UX.",
};

// This inline script sets the saved theme BEFORE React hydrates, so there is no
// flash of the wrong theme on load. It reads the same key the Settings toggle
// writes to.
const themeInit = `
(function () {
  try {
    var t = localStorage.getItem('signal_theme') || 'light';
    document.documentElement.setAttribute('data-theme', t);
  } catch (e) {}
})();
`;

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeInit }} />
      </head>
      <body>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
