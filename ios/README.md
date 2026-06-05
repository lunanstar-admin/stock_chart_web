# FDA 알리미 iOS 앱

국내 바이오기업 미국 FDA 허가 알림 서비스 — iOS Native App

## Xcode 프로젝트 설정

### 1. 프로젝트 생성
1. Xcode 열기 → **File > New > Project**
2. **App** 선택 → Next
3. 설정:
   - Product Name: `FDA알리미`
   - Bundle Identifier: `com.secomdal.fdaalert` (또는 원하는 ID)
   - Interface: **SwiftUI**
   - Language: **Swift**
   - Minimum Deployments: **iOS 16.0**

### 2. 소스 파일 추가
`ios/FDAAlert/` 폴더의 파일들을 Xcode 프로젝트에 추가:
```
Config.swift
App/FDAAlertApp.swift
App/AppDelegate.swift
Models/Models.swift
Services/FDAService.swift
Services/NotificationService.swift
Services/APIClient.swift
Views/ContentView.swift
Views/HomeView.swift
Views/CompanyDetailView.swift
Views/SettingsView.swift
```

### 3. Capabilities 추가
Xcode → 프로젝트 선택 → **Signing & Capabilities** 탭:
- **+ Capability** 클릭 → **Push Notifications** 추가
- **+ Capability** 클릭 → **Background Modes** 추가 → **Remote notifications** 체크

### 4. Config.swift 수정
```swift
static let supabaseURL = "https://axbbjjpxspvvxbxvuzsz.supabase.co"
static let supabaseAnonKey = "YOUR_SUPABASE_ANON_KEY"  // ← Supabase Dashboard에서 확인
```

---

## APNs (Push Notification) 설정

### Apple Developer Console
1. https://developer.apple.com 로그인
2. **Certificates, Identifiers & Profiles** → **Keys**
3. **+** 버튼 → Key Name: `FDA 알리미 APNs`
4. **Apple Push Notifications service (APNs)** 체크 → Continue → Register
5. **Download** → `.p8` 파일 저장 (한 번만 다운로드 가능!)
6. Key ID 메모 (10자리)
7. **Membership** → Team ID 메모 (10자리)

### Supabase Secrets 등록
Supabase Dashboard → **Settings > Edge Functions > Secrets**:

| 키 | 값 |
|----|----|
| `APNS_KEY_P8` | `.p8` 파일 전체 내용 (`-----BEGIN PRIVATE KEY-----` 포함) |
| `APNS_KEY_ID` | Apple Developer Key ID (10자리) |
| `APNS_TEAM_ID` | Apple Developer Team ID (10자리) |
| `APNS_BUNDLE_ID` | `com.secomdal.fdaalert` |
| `APNS_ENV` | `production` (App Store) 또는 `sandbox` (개발) |

### GitHub Repository Secrets 등록
GitHub → Settings → Secrets and variables → Actions:

| 키 | 값 |
|----|----|
| `SUPABASE_URL` | `https://axbbjjpxspvvxbxvuzsz.supabase.co` |
| `SUPABASE_SERVICE_ROLE_KEY` | Supabase Dashboard → Settings → API → service_role key |

---

## Supabase 설정

### 1. DB 마이그레이션 실행
Supabase Dashboard → **SQL Editor**에서 실행:
```
supabase/migrations/20260604_ios_device_registrations.sql
supabase/migrations/20260604_fda_notifications.sql
```

### 2. Edge Functions 배포
```bash
cd stock_chart_web
supabase functions deploy register-device --no-verify-jwt
supabase functions deploy send-fda-push
```

또는 Supabase MCP로 자동 배포됨.

---

## 알림 흐름

```
앱 실행 → 알림 권한 요청 → APNs 토큰 획득
→ Supabase register-device 저장
→ (매일) GitHub Actions daily-batch 실행
→ fda_approvals.py: 신규 허가 감지
→ Supabase send-fda-push 호출
→ APNs → iOS 푸시 알림
```

---

## 배지 타입 설명

| 배지 | 의미 |
|------|------|
| **BLA** | Biologics License Application — 바이오의약품 (항체, 백신 등) |
| **NDA** | New Drug Application — 합성 신약 |
| **ANDA** | Abbreviated NDA — 제네릭 의약품 |

---

## App Store 배포

1. Xcode → **Product > Archive**
2. **Distribute App** → **App Store Connect**
3. App Store Connect에서 앱 정보 입력 후 심사 제출
4. 보통 1-7일 소요

