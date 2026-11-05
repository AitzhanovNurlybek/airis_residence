import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { ArticlePage, articleMetadata } from "@/components/content/ArticlePage";
import { articleByPath, landings, slugOf } from "@/lib/articles";
import { getRooms } from "@/lib/rooms";

/**
 * Посадочные страницы под поисковые запросы (lib/articles.ts):
 * /gostinica-v-centre-almaty, /otel-dlya-komandirovki и т. д.
 *
 * Список адресов закрыт (dynamicParams = false): любой другой адрес
 * первого уровня, которого нет среди статей и обычных страниц, — честная
 * 404, а не пустая статья.
 */
export const dynamicParams = false;

export function generateStaticParams() {
  return landings("ru").map((article) => ({ landing: slugOf(article.path) }));
}

export async function generateMetadata(props: PageProps<"/[landing]">): Promise<Metadata> {
  const { landing } = await props.params;
  const article = articleByPath(`/${landing}`);
  return article ? articleMetadata(article) : {};
}

export default async function LandingPage(props: PageProps<"/[landing]">) {
  const { landing } = await props.params;
  const article = articleByPath(`/${landing}`);
  if (!article || article.kind !== "landing") notFound();
  return <ArticlePage article={article} rooms={await getRooms()} />;
}
