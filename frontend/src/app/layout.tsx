import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'Sentinel AIRO',
  description: 'Behavioral governance layer and risk mitigation for traders.',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>
        <main>{children}</main>
      </body>
    </html>
  );
}
