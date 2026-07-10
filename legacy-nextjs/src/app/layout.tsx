import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Arabela · Inteligencia de Cobranza",
  description:
    "Motor de atribución y clasificación de gestores para campañas de cobranza Arabela.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="es">
      <body>{children}</body>
    </html>
  );
}
