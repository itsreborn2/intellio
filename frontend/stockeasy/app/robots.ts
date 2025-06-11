import { MetadataRoute } from "next"

export default function robots(): MetadataRoute.Robots {
  const baseUrl = process.env.SITE_URL || "https://stockeasy.intellio.kr"
  
  return {
    rules: [
      {
        userAgent: "*",
        disallow: process.env.NODE_ENV === "production" ? [] : ["/"],
      },
      {
        userAgent: "Yeti",
        allow: "/",
        disallow: ["/admin", "/auth", "/api-test"],
      },
    ],
    sitemap: `${baseUrl}/sitemap.xml`,
  }
} 