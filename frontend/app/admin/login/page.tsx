import type { Metadata } from "next";
import { redirect } from "next/navigation";

import { LoginForm } from "@/components/admin/LoginForm";
import { isAdminSignedIn } from "@/lib/adminServer";

export const metadata: Metadata = {
  title: "Вход в управление",
  robots: { index: false, follow: false },
};

export default async function AdminLoginPage() {
  if (await isAdminSignedIn()) redirect("/admin");
  return <LoginForm />;
}
