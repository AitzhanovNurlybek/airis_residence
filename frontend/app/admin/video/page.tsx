import { redirect } from "next/navigation";

import { SiteVideosBoard } from "@/components/admin/SiteVideosBoard";
import { adminFetch, isAdminSignedIn } from "@/lib/adminServer";
import type { AdminSiteVideo } from "@/lib/siteVideoTypes";

export default async function AdminSiteVideosPage() {
  const [signedIn, res] = await Promise.all([
    isAdminSignedIn(),
    adminFetch("/api/admin/site-videos"),
  ]);
  if (!signedIn) redirect("/admin/login");
  const items: AdminSiteVideo[] = res.ok ? await res.json() : [];

  return <SiteVideosBoard items={items} />;
}
