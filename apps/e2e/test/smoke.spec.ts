import { expect, test, type APIRequestContext, type Page } from "@playwright/test";

const API_BASE_URL = process.env.API_BASE_URL ?? "https://api.clipfactory.app";
const SMOKE_EMAIL = process.env.E2E_EMAIL ?? "";
const MAGIC_LINK = process.env.E2E_MAGIC_LINK ?? "";
const MAILTRAP_API_TOKEN = process.env.MAILTRAP_API_TOKEN ?? "";
const MAILTRAP_ACCOUNT_ID = process.env.MAILTRAP_ACCOUNT_ID ?? "";
const MAILTRAP_INBOX_ID = process.env.MAILTRAP_INBOX_ID ?? "";
const YOUTUBE_URL = process.env.E2E_YOUTUBE_URL ?? "";
const SKIP_CHECKOUT = process.env.E2E_SKIP_CHECKOUT === "true";

type JobResponse = {
  job: {
    id: string;
    status: string;
    error_code: string | null;
    error_message: string | null;
  };
  clips: Array<{
    id: string;
    segments: Array<{ start: number; end: number }>;
    score_breakdown: Record<string, number> | null;
  }>;
};

test("live smoke: auth, billing, campaign, job, clip download, feedback", async ({
  page,
  request,
  baseURL,
}) => {
  test.skip(!YOUTUBE_URL, "Set E2E_YOUTUBE_URL to a public short YouTube video.");

  if (!process.env.E2E_AUTH_STATE) {
    test.skip(!SMOKE_EMAIL, "Set E2E_EMAIL or provide E2E_AUTH_STATE.");
    await signInWithMagicLink(page, baseURL ?? "");
  } else {
    await page.goto("/app");
  }

  await expect(page.getByText(/Credits left/i)).toBeVisible();

  if (!SKIP_CHECKOUT) {
    await completeStripeCheckout(page, SMOKE_EMAIL);
    await expect(page.getByText(/Credits left/i)).toBeVisible();
  }

  const campaignId = await createCampaign(page);
  const jobId = await submitJob(page, campaignId, YOUTUBE_URL);
  const token = await readSupabaseAccessToken(page);
  const job = await waitForCompletedJob(request, token, jobId);

  expect(job.clips.length).toBeGreaterThanOrEqual(1);
  expect(job.clips.length).toBeLessThanOrEqual(3);

  for (const clip of job.clips) {
    expect(clip.score_breakdown).toBeTruthy();
    expect(clip.segments.length).toBeGreaterThanOrEqual(1);
  }

  const firstClipId = job.clips[0].id;
  await verifyClipDownload(request, token, firstClipId);
  await thumbsUpClip(request, token, firstClipId);
});

async function signInWithMagicLink(page: Page, baseURL: string) {
  await page.goto("/login");
  await page.getByLabel("Email").fill(SMOKE_EMAIL);
  await page.getByRole("button", { name: /Send sign-in link/i }).click();
  await expect(page.getByText(/Check your email/i)).toBeVisible();

  const link = await resolveMagicLink(baseURL);
  await page.goto(link);
  await expect(page).toHaveURL(/\/app/);
}

async function resolveMagicLink(baseURL: string): Promise<string> {
  if (MAGIC_LINK) return MAGIC_LINK;

  if (!MAILTRAP_API_TOKEN || !MAILTRAP_ACCOUNT_ID || !MAILTRAP_INBOX_ID) {
    throw new Error(
      "Missing magic-link source. Set E2E_MAGIC_LINK or MAILTRAP_API_TOKEN, MAILTRAP_ACCOUNT_ID, and MAILTRAP_INBOX_ID."
    );
  }

  const deadline = Date.now() + 90_000;
  while (Date.now() < deadline) {
    const messages = await mailtrapJson<Array<{ id: number; subject?: string; to_email?: string }>>(
      `/api/accounts/${MAILTRAP_ACCOUNT_ID}/inboxes/${MAILTRAP_INBOX_ID}/messages`
    );
    const candidate = messages.find((message) => {
      const subject = message.subject?.toLowerCase() ?? "";
      const toEmail = message.to_email?.toLowerCase() ?? "";
      return toEmail === SMOKE_EMAIL.toLowerCase() || subject.includes("sign") || subject.includes("magic");
    });

    if (candidate) {
      const html = await mailtrapText(
        `/api/accounts/${MAILTRAP_ACCOUNT_ID}/inboxes/${MAILTRAP_INBOX_ID}/messages/${candidate.id}/body.html`
      );
      const link = extractMagicLink(html, baseURL);
      if (link) return link;
    }

    await new Promise((resolve) => setTimeout(resolve, 5_000));
  }

  throw new Error("Timed out waiting for the Supabase magic link in Mailtrap.");
}

async function mailtrapJson<T>(path: string): Promise<T> {
  const response = await fetch(`https://mailtrap.io${path}`, {
    headers: { "Api-Token": MAILTRAP_API_TOKEN },
  });
  if (!response.ok) {
    throw new Error(`Mailtrap API failed: ${response.status} ${await response.text()}`);
  }
  return (await response.json()) as T;
}

async function mailtrapText(path: string): Promise<string> {
  const response = await fetch(`https://mailtrap.io${path}`, {
    headers: { "Api-Token": MAILTRAP_API_TOKEN },
  });
  if (!response.ok) {
    throw new Error(`Mailtrap API failed: ${response.status} ${await response.text()}`);
  }
  return await response.text();
}

function extractMagicLink(html: string, baseURL: string): string | null {
  const hrefs = Array.from(html.matchAll(/href=["']([^"']+)["']/gi)).map((match) =>
    decodeHtml(match[1])
  );
  return (
    hrefs.find((href) => href.includes("/auth/callback") || href.includes("token_hash=")) ??
    hrefs.find((href) => href.startsWith(baseURL)) ??
    null
  );
}

function decodeHtml(value: string): string {
  return value.replace(/&amp;/g, "&").replace(/&#x2F;/g, "/").replace(/&quot;/g, '"');
}

async function completeStripeCheckout(page: Page, email: string) {
  await page.goto("/app/billing");
  await page.getByRole("button", { name: /Start Starter|Manage \/ renew/i }).click();
  await page.waitForURL(/checkout\.stripe\.com/, { timeout: 60_000 });

  await fillIfVisible(page, page.getByLabel(/Email/i), email || `smoke-${Date.now()}@clipfactory.test`);
  await fillIfVisible(page, page.getByPlaceholder(/1234 1234/i), "4242424242424242");
  await fillIfVisible(page, page.getByPlaceholder(/MM \/ YY|MM\/YY/i), "1234");
  await fillIfVisible(page, page.getByPlaceholder(/CVC/i), "123");
  await fillIfVisible(page, page.getByLabel(/Name on card|Cardholder name|Full name/i), "ClipFactory Smoke");
  await fillIfVisible(page, page.getByLabel(/Country or region/i), "France");

  await page.getByRole("button", { name: /Subscribe|Pay|Start|Confirm|Continue/i }).click();
  await page.waitForURL(/\/app\/billing/, { timeout: 120_000 });
}

async function fillIfVisible(
  page: Page,
  locator: ReturnType<Page["locator"]>,
  value: string
): Promise<void> {
  try {
    await locator.first().waitFor({ state: "visible", timeout: 5_000 });
    await locator.first().fill(value);
  } catch {
    // Stripe Checkout changes labels by locale and account settings.
  }
}

async function createCampaign(page: Page): Promise<string> {
  await page.goto("/app/campaigns/new");
  await page.getByLabel("Campaign name").fill(`Smoke ${Date.now()}`);
  await page.getByLabel("Target audience").fill("Short-form creators validating a SaaS offer");
  await page.getByLabel("Niche").fill("creator SaaS");
  await page.getByLabel("Tone").fill("direct and practical");
  await page.getByLabel("Goal").fill("Find a clip that clearly explains the strongest moment.");
  await page.getByLabel("Avoid topics (comma-separated)").fill("politics, medical claims");
  await page
    .getByLabel("Example hooks (one per line)")
    .fill("This is the moment everyone missed.\nHere is the payoff.");
  await page.getByRole("button", { name: /Create campaign/i }).click();
  await page.waitForURL(/\/app\/campaigns\/[^/]+$/, { timeout: 30_000 });
  return page.url().split("/").pop() ?? "";
}

async function submitJob(page: Page, campaignId: string, youtubeUrl: string): Promise<string> {
  await page.goto(`/app/campaigns/${campaignId}`);
  await page.getByLabel("YouTube URL").fill(youtubeUrl);
  await page.getByLabel("Clips").fill("1");
  await page.getByRole("button", { name: /^Submit$/i }).click();
  await page.waitForURL(/\/app\/jobs\/[^/]+$/, { timeout: 30_000 });
  return page.url().split("/").pop() ?? "";
}

async function readSupabaseAccessToken(page: Page): Promise<string> {
  const token = await page.evaluate(() => {
    function parseSession(raw: string): string | null {
      try {
        const decodedRaw = decodeURIComponent(raw);
        const decoded = decodedRaw.startsWith("base64-")
          ? atob(decodedRaw.slice("base64-".length))
          : decodedRaw;
        const parsed = JSON.parse(decoded);
        return parsed.access_token ?? parsed.currentSession?.access_token ?? null;
      } catch {
        return null;
      }
    }

    for (let i = 0; i < localStorage.length; i += 1) {
      const key = localStorage.key(i) ?? "";
      if (!key.startsWith("sb-") || !key.includes("auth-token")) continue;
      const value = localStorage.getItem(key);
      if (!value) continue;
      const parsed = parseSession(value);
      if (parsed) return parsed;
    }

    for (const cookie of document.cookie.split(";")) {
      const [name, ...rest] = cookie.trim().split("=");
      if (!name.startsWith("sb-") || !name.includes("auth-token")) continue;
      const parsed = parseSession(rest.join("="));
      if (parsed) return parsed;
    }

    return null;
  });

  if (!token) {
    throw new Error("Could not read Supabase access token from browser storage.");
  }
  return token;
}

async function waitForCompletedJob(
  request: APIRequestContext,
  token: string,
  jobId: string
): Promise<JobResponse> {
  const deadline = Date.now() + 5 * 60 * 1000;
  let last: JobResponse | null = null;

  while (Date.now() < deadline) {
    const response = await request.get(`${API_BASE_URL}/jobs/${jobId}`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    expect(response.ok()).toBeTruthy();
    last = (await response.json()) as JobResponse;

    if (last.job.status === "failed") {
      throw new Error(`Job failed: ${last.job.error_code ?? "unknown"} ${last.job.error_message ?? ""}`);
    }
    if (last.job.status === "completed") return last;

    await new Promise((resolve) => setTimeout(resolve, 10_000));
  }

  throw new Error(`Timed out waiting for job ${jobId}; last status=${last?.job.status ?? "unknown"}.`);
}

async function verifyClipDownload(
  request: APIRequestContext,
  token: string,
  clipId: string
): Promise<void> {
  const response = await request.get(`${API_BASE_URL}/clips/${clipId}/download`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  expect(response.ok()).toBeTruthy();
  const payload = (await response.json()) as { url: string };
  expect(payload.url).toMatch(/^https?:\/\//);

  const download = await request.get(payload.url);
  expect(download.status()).toBe(200);
  expect(download.headers()["content-type"] ?? "").toMatch(/video\/mp4|application\/octet-stream/i);
}

async function thumbsUpClip(
  request: APIRequestContext,
  token: string,
  clipId: string
): Promise<void> {
  const response = await request.post(`${API_BASE_URL}/clips/${clipId}/feedback`, {
    headers: { Authorization: `Bearer ${token}` },
    data: { kind: "good" },
  });
  expect(response.status()).toBeGreaterThanOrEqual(200);
  expect(response.status()).toBeLessThan(300);
}
