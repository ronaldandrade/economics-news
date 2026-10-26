import type { MetadataRoute } from "next";
import { todasNoticias } from "@/lib/noticias";
import { SITE_URL } from "@/lib/site";

export default function sitemap(): MetadataRoute.Sitemap {
  const noticias = todasNoticias();
  return [
    { url: SITE_URL, lastModified: noticias[0]?.date, changeFrequency: "daily", priority: 1 },
    ...noticias.map((n) => ({ url: `${SITE_URL}/noticias/${n.slug}`, lastModified: n.date, priority: 0.7 })),
  ];
}
