import { Sidebar } from "@/components/Sidebar";
import { CampaignSelector } from "@/components/CampaignSelector";
import { getCampaigns, getProfile } from "@/lib/data/queries";

// Todo el dashboard depende de sesión/cookies ⇒ render dinámico, sin prerender.
export const dynamic = "force-dynamic";

export default async function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const [profile, campaigns] = await Promise.all([getProfile(), getCampaigns()]);

  return (
    <div className="flex min-h-screen">
      <Sidebar rol={profile?.rol} />
      <div className="flex-1 min-w-0">
        <header className="sticky top-0 z-10 bg-bg/90 backdrop-blur border-b border-line px-8 py-3 flex items-center justify-between gap-4 no-print">
          <CampaignSelector campaigns={campaigns} />
          <div className="text-xs text-ink70">{profile?.nombre ?? ""}</div>
        </header>
        <main className="px-8 py-6 max-w-6xl">{children}</main>
      </div>
    </div>
  );
}
