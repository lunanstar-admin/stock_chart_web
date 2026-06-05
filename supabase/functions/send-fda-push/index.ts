import "jsr:@supabase/functions-js/edge-runtime.d.ts";
import { createClient } from "jsr:@supabase/supabase-js@2";

/**
 * POST /functions/v1/send-fda-push
 * GitHub Actions 배치에서 신규 FDA 허가 발생 시 호출.
 * Authorization: Bearer <SUPABASE_SERVICE_ROLE_KEY>
 *
 * Body (JSON):
 *   new_approvals: Array<{
 *     company_ko: string, company_en: string, code: string,
 *     app_number: string, app_type: string,
 *     brand_name: string, generic_name: string,
 *     approval_date: string
 *   }>
 *
 * 환경변수 (Supabase Secrets):
 *   APNS_KEY_P8     — Apple .p8 key 파일 내용 (-----BEGIN PRIVATE KEY----- 포함)
 *   APNS_KEY_ID     — Apple Developer > Keys 에서 확인 (10자리)
 *   APNS_TEAM_ID    — Apple Developer > Membership > Team ID (10자리)
 *   APNS_BUNDLE_ID  — 앱 Bundle ID (e.g. com.secomdal.fdaalert)
 *   APNS_ENV        — "production" | "sandbox" (default: production)
 */
Deno.serve(async (req: Request) => {
  if (req.method !== "POST") {
    return json({ error: "Method not allowed" }, 405);
  }

  // service_role 키로만 호출 허용 (Edge Function verify_jwt=true 로 설정)
  let body: { new_approvals?: ApprovalItem[] };
  try {
    body = await req.json();
  } catch {
    return json({ error: "Invalid JSON" }, 400);
  }

  const newApprovals = body.new_approvals ?? [];
  if (newApprovals.length === 0) {
    return json({ ok: true, sent: 0, skipped: "no new approvals" });
  }

  const supabase = createClient(
    Deno.env.get("SUPABASE_URL")!,
    Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!,
    { auth: { persistSession: false } },
  );

  // 신규 허가된 company_code 목록
  const newCodes = [...new Set(newApprovals.map((a) => a.code))];

  // 해당 기업 구독 or 'all' 구독 디바이스 조회
  const { data: watchlist, error: wErr } = await supabase
    .from("fda_watchlist")
    .select("apns_token, company_code, device_registrations(environment)")
    .or(
      `company_code.eq.all,company_code.in.(${newCodes.map((c) => `"${c}"`).join(",")})`,
    );

  if (wErr) {
    console.error("send-fda-push: watchlist query error", wErr);
    return json({ error: wErr.message }, 500);
  }

  if (!watchlist || watchlist.length === 0) {
    return json({ ok: true, sent: 0, skipped: "no subscribers" });
  }

  // 중복 제거 — 같은 토큰이 'all' + 특정 기업 모두 구독 시 한 번만 발송
  const tokenMap = new Map<string, "sandbox" | "production">();
  for (const row of watchlist) {
    const env =
      (row.device_registrations as { environment: string } | null)
        ?.environment === "sandbox"
        ? "sandbox"
        : "production";
    tokenMap.set(row.apns_token, env);
  }

  // APNs 설정
  const keyP8 = Deno.env.get("APNS_KEY_P8") ?? "";
  const keyId = Deno.env.get("APNS_KEY_ID") ?? "";
  const teamId = Deno.env.get("APNS_TEAM_ID") ?? "";
  const bundleId = Deno.env.get("APNS_BUNDLE_ID") ?? "";
  const apnsEnvOverride = Deno.env.get("APNS_ENV") ?? "production";

  if (!keyP8 || !keyId || !teamId || !bundleId) {
    console.error("send-fda-push: APNs secrets not configured");
    return json({ error: "APNs not configured" }, 500);
  }

  const apnsJwt = await generateAPNsJWT(keyP8, keyId, teamId);

  // 알림 메시지 구성 (첫 번째 허가 기준)
  const first = newApprovals[0];
  const title = "FDA 신규 허가";
  const body2 =
    newApprovals.length === 1
      ? `${first.company_ko} ${first.brand_name || first.app_number} (${first.app_type}) 허가 완료`
      : `${first.company_ko} 등 ${newApprovals.length}건의 신규 FDA 허가`;

  const payload = {
    aps: {
      alert: { title, body: body2 },
      sound: "default",
      badge: 1,
      "content-available": 1,
    },
    new_approvals: newApprovals.slice(0, 5), // 최대 5건만 포함
  };

  let sentCount = 0;
  const errors: string[] = [];

  for (const [token, env] of tokenMap) {
    const apnsHost =
      (apnsEnvOverride === "sandbox" || env === "sandbox")
        ? "api.sandbox.push.apple.com"
        : "api.push.apple.com";

    try {
      const res = await fetch(`https://${apnsHost}/3/device/${token}`, {
        method: "POST",
        headers: {
          "Authorization": `Bearer ${apnsJwt}`,
          "apns-topic": bundleId,
          "apns-push-type": "alert",
          "apns-priority": "10",
          "Content-Type": "application/json",
        },
        body: JSON.stringify(payload),
      });

      if (res.status === 200) {
        sentCount++;
      } else {
        const errBody = await res.text();
        console.warn(`APNs ${token.slice(0, 8)}... → ${res.status} ${errBody}`);
        // 410 = 토큰 만료/무효 → 삭제
        if (res.status === 410) {
          await supabase
            .from("device_registrations")
            .delete()
            .eq("apns_token", token);
        }
        errors.push(`${token.slice(0, 8)}: ${res.status}`);
      }
    } catch (e) {
      console.error(`APNs send error ${token.slice(0, 8)}:`, e);
      errors.push(`${token.slice(0, 8)}: network error`);
    }
  }

  console.info(`send-fda-push: sent=${sentCount}, errors=${errors.length}`);
  return json({ ok: true, sent: sentCount, errors: errors.slice(0, 10) });
});

// ── APNs JWT 생성 (ES256) ─────────────────────────────────────────────────

interface ApprovalItem {
  company_ko: string;
  company_en: string;
  code: string;
  app_number: string;
  app_type: string;
  brand_name: string;
  generic_name: string;
  approval_date: string;
}

function pemToArrayBuffer(pem: string): ArrayBuffer {
  const b64 = pem
    .replace(/-----BEGIN PRIVATE KEY-----/, "")
    .replace(/-----END PRIVATE KEY-----/, "")
    .replace(/\s+/g, "");
  const binary = atob(b64);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
  return bytes.buffer;
}

function base64UrlEncode(data: string | ArrayBuffer): string {
  let binary: string;
  if (typeof data === "string") {
    binary = btoa(unescape(encodeURIComponent(data)));
  } else {
    const bytes = new Uint8Array(data);
    binary = "";
    for (const b of bytes) binary += String.fromCharCode(b);
    binary = btoa(binary);
  }
  return binary.replace(/\+/g, "-").replace(/\//g, "_").replace(/=/g, "");
}

async function generateAPNsJWT(
  keyP8: string,
  keyId: string,
  teamId: string,
): Promise<string> {
  const key = await crypto.subtle.importKey(
    "pkcs8",
    pemToArrayBuffer(keyP8),
    { name: "ECDSA", namedCurve: "P-256" },
    false,
    ["sign"],
  );
  const header = base64UrlEncode(JSON.stringify({ alg: "ES256", kid: keyId }));
  const payload = base64UrlEncode(
    JSON.stringify({ iss: teamId, iat: Math.floor(Date.now() / 1000) }),
  );
  const sigInput = `${header}.${payload}`;
  const sig = await crypto.subtle.sign(
    { name: "ECDSA", hash: "SHA-256" },
    key,
    new TextEncoder().encode(sigInput),
  );
  return `${sigInput}.${base64UrlEncode(sig)}`;
}

function json(data: unknown, status = 200): Response {
  return new Response(JSON.stringify(data), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}
