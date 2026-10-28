import type { MetadataRoute } from "next";

import { URL_DO_SITE } from "@/nucleo/site";

export default function mapaDoSite(): MetadataRoute.Sitemap {
  return ["", "/privacidade"].map((caminho) => ({ url: `${URL_DO_SITE}${caminho}` }));
}
