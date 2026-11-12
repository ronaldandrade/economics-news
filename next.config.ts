import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  poweredByHeader: false,
  async headers() {
    return [
      {
        source: "/:path*",
        headers: [
          // o navegador não tenta adivinhar o tipo de um arquivo
          { key: "X-Content-Type-Options", value: "nosniff" },
          // outros sites recebem só o domínio de origem, não o endereço da matéria
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
          // o site não pode ser embutido em iframe de terceiros (clickjacking)
          { key: "X-Frame-Options", value: "DENY" },
          { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
        ],
      },
    ];
  },
};

export default nextConfig;
