import { defineConfig, devices } from "@playwright/test";

// Smoke com lojas reais: roda à mão (npx playwright test -c playwright.real.config.ts),
// nunca na CI. Poucas buscas, e o critério é consistência, não preço.
// Com SITE_REMOTO (o preview de homologação, por exemplo), roda contra ele sem subir nada local.
// O site de homologação é protegido: ESTADO_BYPASS aponta para um arquivo de estado com o cookie
// do segredo de bypass (docs/homologacao.md).
const REMOTO = process.env.SITE_REMOTO?.replace(/\/$/, "");
const SITE = REMOTO ?? "http://127.0.0.1:3031";
const API = "http://127.0.0.1:8020";
const PYTHON =
  process.platform === "win32" ? String.raw`.venv\Scripts\python.exe` : ".venv/bin/python";

export default defineConfig({
  testDir: "e2e-real",
  workers: 1,
  timeout: 90_000,
  reporter: [["list"]],
  use: {
    baseURL: SITE,
    channel: "chrome",
    locale: "pt-BR",
    colorScheme: "light",
    storageState: process.env.ESTADO_BYPASS,
  },
  projects: [
    { name: "desktop", use: { viewport: { width: 1440, height: 900 } } },
    { name: "celular", use: { ...devices["Pixel 7"], channel: "chrome" } },
  ],
  webServer: REMOTO
    ? undefined
    : [
        {
          command: `${PYTHON} -m uvicorn app.main:app --host 127.0.0.1 --port 8020`,
          cwd: "../backend",
          url: `${API}/saude`,
          env: { ...process.env, ORIGENS_CORS: JSON.stringify([SITE]) } as Record<string, string>,
          timeout: 60_000,
          reuseExistingServer: false,
        },
        {
          command: "npm run build && npx next start -p 3031",
          url: SITE,
          env: {
            ...process.env,
            NEXT_PUBLIC_URL_API: API,
            NEXT_PUBLIC_URL_SITE: SITE,
          } as Record<string, string>,
          timeout: 240_000,
          reuseExistingServer: false,
        },
      ],
});
