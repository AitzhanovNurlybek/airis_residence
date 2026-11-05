import type { Metadata } from "next";

import { GuideHub } from "@/components/content/GuideHub";
import { pageMetadata } from "@/lib/seo";

export const metadata: Metadata = pageMetadata({
  title: "Almaty Travel Guide — from a hotel in the city centre",
  description:
    "How to get from Almaty Airport, what to see in the centre, how to visit Medeu and Shymbulak, and which area of Almaty to stay in.",
  path: "/en/almaty",
});

export default function GuideHubPageEn() {
  return <GuideHub lang="en" />;
}
