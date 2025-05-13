import { MetadataRoute } from "next"

export default function robots(): MetadataRoute.Robots {
  const baseUrl = process.env.SITE_URL || "https://intellio.kr"
  
  return {
    rules: [
      {
        userAgent: "*",
        disallow: process.env.NODE_ENV === "production" ? [] : ["/"],
      },
      {
        userAgent: "Yeti",
        allow: "/",
        disallow: ["/admin", "/auth"],
      },
    ],
    sitemap: `${baseUrl}/sitemap.xml`,
  }
} 