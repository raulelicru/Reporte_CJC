import { getCampaigns, resolveCampaign, type CampaignRow } from "./queries";

/** Contexto de página: campañas + campaña activa a partir del param `c`. */
export async function pageContext(searchParams: { c?: string }): Promise<{
  campaigns: CampaignRow[];
  actual: CampaignRow | null;
}> {
  const campaigns = await getCampaigns();
  const actual = await resolveCampaign(campaigns, searchParams.c);
  return { campaigns, actual };
}
