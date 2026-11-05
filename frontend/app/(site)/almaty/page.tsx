import type { Metadata } from "next";

import { GuideHub } from "@/components/content/GuideHub";
import { pageMetadata } from "@/lib/seo";

export const metadata: Metadata = pageMetadata({
  title: "Путеводитель по Алматы от отеля в центре",
  description:
    "Как добраться из аэропорта Алматы, что посмотреть в центре, как поехать на Медеу и Шымбулак и какой район выбрать для проживания.",
  path: "/almaty",
});

export default function GuideHubPage() {
  return <GuideHub lang="ru" />;
}
