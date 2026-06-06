// Config.swift — FDA 알리미
// 앱 전역 상수. 빌드 환경에 따라 Debug/Release 분기 가능.

import Foundation

enum Config {

    // MARK: - Supabase

    /// Supabase 프로젝트 URL
    static let supabaseURL = "https://axbbjjpxspvvxbxvuzsz.supabase.co"

    /// Supabase anon (publishable) key — RLS 로 INSERT/SELECT 만 허용.
    /// 공개되어도 안전한 클라이언트 키 (service_role 과 다름).
    static let supabaseAnonKey = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImF4YmJqanB4c3B2dnhieHZ1enN6Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzY1MzQyOTUsImV4cCI6MjA5MjExMDI5NX0.z_XWmVLb1j6AqrGgbTCA3cxIlj2MDm8LUXZIY_knNak"

    // MARK: - Edge Functions

    /// 디바이스 APNs 토큰 등록 엔드포인트
    static let registerDeviceEndpoint = supabaseURL + "/functions/v1/register-device"

    /// FDA 신규 허가 푸시 발송 엔드포인트 (GitHub Actions → Supabase)
    static let sendFDAPushEndpoint = supabaseURL + "/functions/v1/send-fda-push"

    // MARK: - Data

    /// FDA 허가 JSON 데이터 URL
    static let fdaDataURL = URL(string: "https://secomdal.com/data/fda_approvals.json")!

    /// DART + FDA RSS 실시간 속보 JSON URL
    static let fdaAlertsURL = URL(string: "https://secomdal.com/data/fda_alerts.json")!

    // MARK: - App

    /// 앱 이름
    static let appName = "FDA 알리미"

    /// 앱 번들 ID (Xcode 프로젝트 설정과 일치해야 함)
    static let bundleID = "com.secomdal.fdaalert"

    /// 딥링크 URL 스킴
    static let urlScheme = "fdaalert"

    /// 데이터 캐시 유효 시간 (초) — 10분
    static let cacheMaxAge: TimeInterval = 600

    /// 네트워크 요청 타임아웃 (초)
    static let requestTimeout: TimeInterval = 15
}
