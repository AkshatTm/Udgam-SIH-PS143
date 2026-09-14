import type { Metadata } from "next";
import localFont from "next/font/local";
import "./globals.css";

// Interface face. SF Pro Display/Text is used when the machine has it installed (see
// app/fonts/README.md for self-hosting it); Inter is the self-hosted fallback that guarantees
// the same shapes on a demo laptop that does not. Both are wired through --font-ui in
// globals.css — never reference a family name directly in a component.
const inter = localFont({
  src: "./fonts/InterVariable.woff2",
  variable: "--font-inter",
  weight: "100 900",
  display: "swap",
});

// Data face — every measured number on screen. Geist Mono stays: it is already self-hosted,
// and SF Mono is preferred ahead of it in the stack when present.
const geistMono = localFont({
  src: "./fonts/GeistMonoVF.woff",
  variable: "--font-geist-mono",
  weight: "100 900",
  display: "swap",
});

export const metadata: Metadata = {
  title: "UDGAM",
  description: "Oil spill detection, backward drift, and vessel attribution from SAR.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    // The font variables must land on <html>, not <body>: globals.css builds --font-ui on
    // :root, and a var() inside a custom property resolves against the element the property is
    // DECLARED on. With the classes on <body>, --font-inter is undefined at :root, which makes
    // the whole --font-ui declaration invalid and drops the app to a serif default.
    <html lang="en" className={`${inter.variable} ${geistMono.variable} h-full`}>
      <body className="h-full antialiased">{children}</body>
    </html>
  );
}
