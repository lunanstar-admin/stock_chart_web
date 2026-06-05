# FDA 알리미 — iOS 앱 설정 가이드

한국 바이오텍 기업의 FDA 허가를 추적하고 푸시 알림을 받는 iOS 앱입니다.

---

## 요구사항

- Xcode 15 이상
- iOS 16.0+
- Swift 5.9+
- Apple Developer Program 계정 (APNs 설정 필요)

---

## Xcode 프로젝트 생성

1. Xcode → **File > New > Project** → **App** 선택
2. 설정:
   - **Product Name**: `FDAAlert`
   - **Bundle Identifier**: `com.secomdal.fdaalert`
   - **Interface**: SwiftUI
   - **Language**: Swift
   - **Minimum Deployments**: iOS 16.0
3. 프로젝트 생성 후 `ios/FDAAlert/` 폴더의 Swift 파일을 Xcode 프로젝트에 추가:
   - `Config.swift`
   - `Models/Models.swift`
   - `Services/FDAService.swift`
   - `Services/NotificationService.swift`
   - `App/FDAAlertApp.swift`
   - `Views/HomeView.swift`
   - `Views/CompanyDetailView.swift`
   - `Views/SettingsView.swift`
   - `Views/Components.swift`

---

## Bundle ID 설정

`Config.swift`의 `bundleID`와 Xcode 프로젝트의 Bundle Identifier가 반드시 일치해야 합니다:

```
com.secomdal.fdaalert
```

---

## APNs (Apple Push Notification service) 설정

### 1. Apple Developer Console에서 APNs Key 생성

1. [developer.apple.com](https://developer.apple.com) → **Certificates, Identifiers & Profiles**
2. **Keys** → **+** 버튼
3. Key Name: `FDAAlert Push Key`
4. **Apple Push Notifications service (APNs)** 체크
5. **Continue** → **Register** → **Download** (`.p8` 파일, 한 번만 다운로드 가능)
6. **Key ID** 메모 (10자리 영문숫자)
7. **Team ID** 메모 (Apple Developer 계정 ID)

### 2. App ID에 Push Notifications Capability 추가

1. **Identifiers** → 앱 Bundle ID 선택
2. **Push Notifications** 체크 → **Save**

### 3. Xcode Capabilities 추가

1. Xcode → 프로젝트 타겟 선택
2. **Signing & Capabilities** 탭
3. **+ Capability** → **Push Notifications** 추가
4. **Background Modes** 추가 → **Remote notifications** 체크

### 4. URL Scheme 등록 (딥링크)

1. **Info** 탭 → **URL Types** → **+** 버튼
2. **URL Schemes**: `fdaalert`
3. **Role**: Viewer

---

## Supabase 설정

### 1. Supabase 프로젝트 확인

프로젝트 URL: `https://axbbjjpxspvvxbxvuzsz.supabase.co`

### 2. Supabase Anon Key 설정

`Config.swift`의 `supabaseAnonKey`를 실제 키로 교체:

```swift
static let supabaseAnonKey = "YOUR_ACTUAL_ANON_KEY_HERE"
```

Supabase Dashboard → **Settings > API > Project API keys > anon public**에서 확인

### 3. Edge Functions

앱에서 호출하는 Edge Functions:

| Function | 용도 |
|----------|------|
| `register-device` | APNs 토큰 + 구독 설정 저장 |
| `send-fda-push` | 신규 허가 발생 시 푸시 발송 (GitHub Actions 호출) |

Edge Function 배포:
```bash
supabase functions deploy register-device
supabase functions deploy send-fda-push
```

### 4. register-device 페이로드 형식

```json
{
  "device_token": "APNs 토큰 hex 문자열",
  "platform": "ios",
  "subscribe_all": true,
  "subscribed_codes": ["068270", "207940"]
}
```

---

## GitHub Actions Secrets 설정

GitHub Actions가 새 FDA 허가를 감지하면 `send-fda-push`를 호출합니다.

Repository → **Settings > Secrets and variables > Actions** → **New repository secret**:

| Secret 이름 | 값 |
|-------------|-----|
| `SUPABASE_URL` | `https://axbbjjpxspvvxbxvuzsz.supabase.co` |
| `SUPABASE_SERVICE_ROLE_KEY` | Supabase Dashboard의 service_role 키 |
| `APNS_KEY_ID` | APNs Key ID (10자리) |
| `APNS_TEAM_ID` | Apple Developer Team ID |
| `APNS_BUNDLE_ID` | `com.secomdal.fdaalert` |
| `APNS_KEY_P8` | `.p8` 파일의 전체 내용 |

---

## 딥링크 구조

알림 탭 시 특정 기업 상세 화면으로 이동:

### 푸시 알림 payload

```json
{
  "aps": {
    "alert": {
      "title": "셀트리온 FDA 허가",
      "body": "Zymfentra (infliximab-dyyb) BLA 허가"
    },
    "sound": "default",
    "badge": 1
  },
  "company_code": "068270"
}
```

### URL Scheme

```
fdaalert://company/068270
```

---

## 로컬 개발 & 시뮬레이터

- APNs는 실기기에서만 작동합니다 (시뮬레이터 불가)
- 시뮬레이터에서는 데이터 로드 및 UI만 테스트 가능
- 실기기 테스트 시 **Development** 프로비저닝 프로파일 필요

---

## 주요 파일 구조

```
ios/FDAAlert/
├── Config.swift                  # 전역 상수 (URL, 키, Bundle ID)
├── App/
│   └── FDAAlertApp.swift         # @main, AppDelegate, ContentView
├── Models/
│   └── Models.swift              # FDAData, Company, Approval, DeepLink
├── Services/
│   ├── FDAService.swift          # 데이터 fetch (FDAStore ObservableObject)
│   └── NotificationService.swift # APNs 등록, 구독 관리
└── Views/
    ├── HomeView.swift            # 메인 기업 목록 화면
    ├── CompanyDetailView.swift   # 기업 상세 + 허가 목록
    ├── SettingsView.swift        # 알림 설정 + 구독 관리
    └── Components.swift          # AppTypeBadge, NewBadge, CompanyRow 등
```

---

## 서드파티 의존성

없음 — Swift 표준 라이브러리 및 Apple 프레임워크만 사용:
- `SwiftUI`
- `UserNotifications`
- `SafariServices`
- `Foundation`
- `Combine`
