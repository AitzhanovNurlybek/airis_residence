import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { ArticlePage, articleMetadata } from "@/components/content/ArticlePage";
import { articleByPath, guides, slugOf } from "@/lib/articles";
import { getRooms } from "@/lib/rooms";

/** Almaty travel guide articles (lib/articles.ts). */
export const dynamicParams = false;

export function generateStaticParams() {
  return guides("en").map((article) => ({ slug: slugOf(article.path) }));
}

export async function generateMetadata(props: PageProps<"/en/almaty/[slug]">): Promise<Metadata> {
  const { slug } = await props.params;
  const article = articleByPath(`/en/almaty/${slug}`);
  return article ? articleMetadata(article) : {};
}

export default async function GuidePageEn(props: PageProps<"/en/almaty/[slug]">) {
  const { slug } = await props.params;
  const article = articleByPath(`/en/almaty/${slug}`);
  if (!article) notFound();
  return <ArticlePage article={article} rooms={await getRooms()} />;
}
