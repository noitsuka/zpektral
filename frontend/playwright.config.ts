import { defineConfig, devices } from "@playwright/test";

const PORTA = 3030;
// Host fictício: todas as chamadas a ele são respondidas pelos testes com dados fixos.
export const API_FALSA = "http://127.0.0.1:3999";

export default defineConfig({
  testDir: "e2e",
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  reporter: [["list"]],
  use: {
    baseURL: `http://127.0.0.1:${PORTA}`,
    channel: "chrome",
    locale: "pt-BR",
    timezoneId: "America/Sao_Paulo",
    colorScheme: "light",
    trace: "retain-on-failure",
  },
  projects: [
    { name: "desktop", use: { viewport: { width: 1440, height: 900 } } },
    { name: "celular", use: { ...devices["Pixel 7"], channel: "chrome" } },
  ],
  webServer: {
    command: `npm run build && npx next start -p ${PORTA}`,
    url: `http://127.0.0.1:${PORTA}`,
    env: { NEXT_PUBLIC_URL_API: API_FALSA, NEXT_PUBLIC_URL_SITE: `http://127.0.0.1:${PORTA}` },
    timeout: 240_000,
    reuseExistingServer: !process.env.CI,
  },
});
