// NotificationService.swift — FDA 알리미
// 알림 권한 요청, APNs 토큰 Supabase 등록, 구독 관리.

import Foundation
import UserNotifications
import UIKit

// MARK: - Subscription Store

/// UserDefaults 기반 구독 설정 저장소
private final class SubscriptionStore {
    private enum Keys {
        static let notificationsEnabled = "notifications_enabled"
        static let subscribeAll         = "subscribe_all"
        static let subscribedCodes      = "subscribed_codes"
        static let deviceToken          = "device_token"
        static let tokenRegistered      = "token_registered"
    }

    private let defaults = UserDefaults.standard

    var notificationsEnabled: Bool {
        get { defaults.bool(forKey: Keys.notificationsEnabled) }
        set { defaults.set(newValue, forKey: Keys.notificationsEnabled) }
    }

    /// 기본값 true — 최초 설치 시 전체 구독
    var subscribeAll: Bool {
        get {
            if defaults.object(forKey: Keys.subscribeAll) == nil { return true }
            return defaults.bool(forKey: Keys.subscribeAll)
        }
        set { defaults.set(newValue, forKey: Keys.subscribeAll) }
    }

    var subscribedCodes: Set<String> {
        get { Set(defaults.stringArray(forKey: Keys.subscribedCodes) ?? []) }
        set { defaults.set(Array(newValue), forKey: Keys.subscribedCodes) }
    }

    var deviceToken: String? {
        get { defaults.string(forKey: Keys.deviceToken) }
        set { defaults.set(newValue, forKey: Keys.deviceToken) }
    }

    var tokenRegistered: Bool {
        get { defaults.bool(forKey: Keys.tokenRegistered) }
        set { defaults.set(newValue, forKey: Keys.tokenRegistered) }
    }

    func isSubscribed(to code: String) -> Bool {
        subscribeAll || subscribedCodes.contains(code)
    }
}

// MARK: - NotificationService

final class NotificationService: NSObject, UNUserNotificationCenterDelegate, ObservableObject {

    // MARK: Singleton
    static let shared = NotificationService()

    // MARK: Published State
    @Published private(set) var authorizationStatus: UNAuthorizationStatus = .notDetermined
    @Published var notificationsEnabled: Bool = false {
        didSet {
            store.notificationsEnabled = notificationsEnabled
            if notificationsEnabled {
                Task { await requestPermissionAndRegister() }
            }
        }
    }
    @Published var subscribeAll: Bool = true {
        didSet {
            store.subscribeAll = subscribeAll
            Task { await syncSubscription() }
        }
    }
    @Published var subscribedCodes: Set<String> = [] {
        didSet {
            store.subscribedCodes = subscribedCodes
            Task { await syncSubscription() }
        }
    }
    @Published private(set) var isRegistering: Bool = false
    @Published private(set) var registrationError: String?

    // MARK: Private
    private let store = SubscriptionStore()
    private let session: URLSession = {
        let cfg = URLSessionConfiguration.default
        cfg.timeoutIntervalForRequest = Config.requestTimeout
        return URLSession(configuration: cfg)
    }()

    // MARK: Init

    private override init() {
        super.init()
        UNUserNotificationCenter.current().delegate = self
        // 저장된 설정 복원
        notificationsEnabled = store.notificationsEnabled
        subscribeAll = store.subscribeAll
        subscribedCodes = store.subscribedCodes
        Task { await refreshAuthorizationStatus() }
    }

    // MARK: Public API

    func requestAuthorization() async -> Bool {
        do {
            let granted = try await UNUserNotificationCenter.current()
                .requestAuthorization(options: [.alert, .sound, .badge])
            await refreshAuthorizationStatus()
            return granted
        } catch {
            return false
        }
    }

    func registerIfAuthorized() async {
        let settings = await UNUserNotificationCenter.current().notificationSettings()
        guard settings.authorizationStatus == .authorized else { return }
        await MainActor.run {
            UIApplication.shared.registerForRemoteNotifications()
        }
    }

    func refreshAuthorizationStatus() async {
        let settings = await UNUserNotificationCenter.current().notificationSettings()
        await MainActor.run {
            self.authorizationStatus = settings.authorizationStatus
        }
    }

    func handleDeviceToken(_ token: String) async {
        store.deviceToken = token
        store.tokenRegistered = false
        await registerWithSupabase(token: token)
    }

    func handleRegistrationFailure(_ error: Error) {
        Task { @MainActor in
            self.registrationError = error.localizedDescription
        }
    }

    func isSubscribed(to code: String) -> Bool {
        store.isSubscribed(to: code)
    }

    func toggleSubscription(code: String) {
        if subscribedCodes.contains(code) {
            subscribedCodes.remove(code)
        } else {
            subscribedCodes.insert(code)
        }
    }

    // MARK: - UNUserNotificationCenterDelegate

    /// 포그라운드에서 알림 표시
    func userNotificationCenter(
        _ center: UNUserNotificationCenter,
        willPresent notification: UNNotification,
        withCompletionHandler handler: @escaping (UNNotificationPresentationOptions) -> Void
    ) {
        handler([.banner, .sound, .badge])
    }

    /// 알림 탭 처리 → DeepLink 발행
    func userNotificationCenter(
        _ center: UNUserNotificationCenter,
        didReceive response: UNNotificationResponse,
        withCompletionHandler handler: @escaping () -> Void
    ) {
        let userInfo = response.notification.request.content.userInfo
        if let code = userInfo["company_code"] as? String, !code.isEmpty {
            NotificationCenter.default.post(
                name: .fdaOpenCompany,
                object: nil,
                userInfo: ["code": code]
            )
        }
        handler()
    }

    // MARK: Private

    private func requestPermissionAndRegister() async {
        await MainActor.run { isRegistering = true }
        defer { Task { @MainActor in self.isRegistering = false } }

        let granted = await requestAuthorization()
        guard granted else {
            await MainActor.run { self.notificationsEnabled = false }
            return
        }
        await MainActor.run {
            UIApplication.shared.registerForRemoteNotifications()
        }
    }

    private func registerWithSupabase(token: String) async {
        guard let url = URL(string: Config.registerDeviceEndpoint) else { return }

        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.setValue("Bearer \(Config.supabaseAnonKey)", forHTTPHeaderField: "Authorization")
        request.setValue(Config.supabaseAnonKey, forHTTPHeaderField: "apikey")

        // Edge Function expects: apns_token, environment, subscriptions[]
        let subscriptions: [String] = store.subscribeAll
            ? ["all"]
            : Array(store.subscribedCodes)
        #if DEBUG
        let environment = "sandbox"
        #else
        let environment = "production"
        #endif

        let payload: [String: Any] = [
            "apns_token":    token,
            "environment":   environment,
            "subscriptions": subscriptions,
        ]

        do {
            request.httpBody = try JSONSerialization.data(withJSONObject: payload)
            let (_, response) = try await session.data(for: request)
            if let http = response as? HTTPURLResponse, (200...299).contains(http.statusCode) {
                store.tokenRegistered = true
                await MainActor.run { self.registrationError = nil }
                print("[FDAAlert] 디바이스 등록 성공: \(token.prefix(8))...")
            } else if let http = response as? HTTPURLResponse {
                print("[FDAAlert] 디바이스 등록 실패: HTTP \(http.statusCode)")
            }
        } catch {
            await MainActor.run { self.registrationError = error.localizedDescription }
            print("[FDAAlert] 디바이스 등록 오류: \(error)")
        }
    }

    private func syncSubscription() async {
        guard let token = store.deviceToken, store.tokenRegistered else { return }
        await registerWithSupabase(token: token)
    }
}

// MARK: - Notification Name

extension Notification.Name {
    static let fdaOpenCompany = Notification.Name("fdaOpenCompany")
    /// 하위 호환 (기존 코드 참조용)
    static let openCompany = Notification.Name("openCompany")
}
