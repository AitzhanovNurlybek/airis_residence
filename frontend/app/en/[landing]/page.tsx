import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { ArticlePage, articleMetadata } from "@/components/content/ArticlePage";
import { articleByPath, landings, slugOf } from "@/lib/articles";
import { getRooms } from "@/lib/rooms";

/** English landing pages (lib/articles.ts): /en/almaty-city-centre-hotel etc. */
export const dynamicParams = false;

export function generateStaticParams() {
  return landings("en").map((article) => ({ landing: slugOf(article.path) }));
}

export async function generateMetadata(props: PageProps<"/en/[landing]">): Promise<Metadata> {
  const { landing } = await props.params;
  const article = articleByPath(`/en/${landing}`);
  return article ? articleMetadata(article) : {};
}

export default async function LandingPageEn(props: PageProps<"/en/[landing]">) {
  const { landing } = await props.params;
  const article = articleByPath(`/en/${landing}`);
  if (!article || article.kind !== "landing") notFound();
  return <ArticlePage article={article} rooms={await getRooms()} />;
}
