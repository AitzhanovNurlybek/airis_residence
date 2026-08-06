import { redirect } from "next/navigation";

import { SiteVideosBoard } from "@/components/admin/SiteVideosBoard";
import { adminFetch, isAdminSignedIn } from "@/lib/adminServer";
import type { AdminSiteVideo } from "@/lib/siteVideoTypes";

export default async function AdminSiteVideosPage() {
  if (!(await isAdminSignedIn())) redirect("/admin/login");

  const res = await adminFetch("/api/admin/site-videos");
  const items: AdminSiteVideo[] = res.ok ? await res.json() : [];

  return <SiteVideosBoard items={items} />;
}
