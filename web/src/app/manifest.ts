import type { MetadataRoute } from "next";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "Health Buddy",
    short_name: "Health Buddy",
    description: "Meals, steps and sleep for the whole family, in English and Telugu.",
    start_url: "/",
    display: "standalone",
    background_color: "#edf0f3",
    theme_color: "#3d3a9e",
    icons: [{ src: "/icon.svg", sizes: "any", type: "image/svg+xml", purpose: "any" }],
  };
}
