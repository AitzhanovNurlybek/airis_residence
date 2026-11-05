import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { ArticlePage, articleMetadata } from "@/components/content/ArticlePage";
import { articleByPath, guides, slugOf } from "@/lib/articles";
import { getRooms } from "@/lib/rooms";

/** Статьи путеводителя по Алматы (lib/articles.ts). */
export const dynamicParams = false;

export function generateStaticParams() {
  return guides("ru").map((article) => ({ slug: slugOf(article.path) }));
}

export async function generateMetadata(props: PageProps<"/almaty/[slug]">): Promise<Metadata> {
  const { slug } = await props.params;
  const article = articleByPath(`/almaty/${slug}`);
  return article ? articleMetadata(article) : {};
}

export default async function GuidePage(props: PageProps<"/almaty/[slug]">) {
  const { slug } = await props.params;
  const article = articleByPath(`/almaty/${slug}`);
  if (!article) notFound();
  return <ArticlePage article={article} rooms={await getRooms()} />;
}
