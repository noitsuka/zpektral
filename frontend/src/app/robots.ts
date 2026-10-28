import type { MetadataRoute } from "next";

import { URL_DO_SITE } from "@/nucleo/site";

export default function robos(): MetadataRoute.Robots {
  return {
    rules: { userAgent: "*", allow: "/", disallow: ["/busca"] },
    sitemap: `${URL_DO_SITE}/sitemap.xml`,
  };
}
