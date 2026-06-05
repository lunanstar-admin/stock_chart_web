import "jsr:@supabase/functions-js/edge-runtime.d.ts";
import { createClient } from "jsr:@supabase/supabase-js@2";

/**
 * POST /functions/v1/register-device
 * iOS 앱에서 APNs 토큰 등록/갱신 + 구독 설정.
 *
 * Body (JSON):
 *   apns_token:    string   — APNs device token (hex string)
 *   environment:   "sandbox" | "production"  (default: production)
 *   app_version:   string   — e.g. "1.0.0"
 *   os_version:    string   — e.g. "17.4"
 *   subscriptions: string[] — ["all"] or ["068270", "207940", ...]
 *
 * Returns: { ok: true } or { error: string }
 */
Deno.serve(async (req: Request) => {
  if (req.method === "OPTIONS") {
    return new Response(null, {
      headers: {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Headers": "Content-Type, Authorization",
        "Access-Control-Allow-Methods": "POST, OPTIONS",
      },
    });
  }

  if (req.method !== "POST") {
    return json({ error: "Method not allowed" }, 405);
  }

  let body: {
    apns_token?: string;
    environment?: string;
    app_version?: string;
    os_version?: string;
    subscriptions?: string[];
  };

  try {
    body = await req.json();
  } catch {
    return json({ error: "Invalid JSON" }, 400);
  }

  const { apns_token, environment = "production", app_version, os_version, subscriptions = ["all"] } = body;

  if (!apns_token || typeof apns_token !== "string" || apns_token.length < 32) {
    return json({ error: "Invalid apns_token" }, 400);
  }
  if (!["sandbox", "production"].includes(environment)) {
    return json({ error: "Invalid environment" }, 400);
  }

  const supabase = createClient(
    Deno.env.get("SUPABASE_URL")!,
    Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!,
    { auth: { persistSession: false } },
  );

  // 디바이스 등록 upsert
  const { error: regError } = await supabase
    .from("device_registrations")
    .upsert(
      {
        apns_token,
        environment,
        app_version: app_version ?? null,
        os_version: os_version ?? null,
        last_active_at: new Date().toISOString(),
      },
      { onConflict: "apns_token" },
    );

  if (regError) {
    console.error("register-device: upsert error", regError);
    return json({ error: "DB error: " + regError.message }, 500);
  }

  // 기존 구독 삭제 후 새로 삽입 (교체 방식)
  await supabase.from("fda_watchlist").delete().eq("apns_token", apns_token);

  const watchRows = subscriptions
    .filter((s) => typeof s === "string" && s.length > 0)
    .map((company_code) => ({ apns_token, company_code }));

  if (watchRows.length > 0) {
    const { error: watchError } = await supabase
      .from("fda_watchlist")
      .insert(watchRows);
    if (watchError) {
      console.error("register-device: watchlist insert error", watchError);
    }
  }

  return json({ ok: true });
});

function json(data: unknown, status = 200): Response {
  return new Response(JSON.stringify(data), {
    status,
    headers: {
      "Content-Type": "application/json",
      "Access-Control-Allow-Origin": "*",
    },
  });
}
