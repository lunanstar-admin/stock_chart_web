// AppDelegate.swift — FDA 알리미
// UIApplicationDelegate: APNs 토큰 수신, 백그라운드 알림 처리.

import UIKit
import UserNotifications

final class AppDelegate: NSObject, UIApplicationDelegate {

    func application(
        _ application: UIApplication,
        didFinishLaunchingWithOptions launchOptions: [UIApplication.LaunchOptionsKey: Any]? = nil
    ) -> Bool {
        // NotificationService 는 singleton init 시 UNUserNotificationCenterDelegate 를 등록함
        _ = NotificationService.shared
        return true
    }

    // MARK: - APNs Token

    /// APNs 등록 성공 — 토큰을 Supabase에 등록
    func application(
        _ application: UIApplication,
        didRegisterForRemoteNotificationsWithDeviceToken deviceToken: Data
    ) {
        let token = deviceToken.map { String(format: "%02x", $0) }.joined()

        #if DEBUG
        let env = "sandbox"
        #else
        let env = "production"
        #endif

        Task {
            await NotificationService.shared.handleDeviceToken(token)
            // APIClient 를 통한 확장 등록 (앱 버전, OS 버전 포함)
            try? await APIClient.registerDevice(apnsToken: token, environment: env)
        }
    }

    /// APNs 등록 실패
    func application(
        _ application: UIApplication,
        didFailToRegisterForRemoteNotificationsWithError error: Error
    ) {
        print("[FDAAlert] APNs 등록 실패: \(error.localizedDescription)")
        NotificationService.shared.handleRegistrationFailure(error)
    }

    /// 백그라운드 원격 알림 수신 (content-available: 1) — 데이터 미리 갱신
    func application(
        _ application: UIApplication,
        didReceiveRemoteNotification userInfo: [AnyHashable: Any],
        fetchCompletionHandler completionHandler: @escaping (UIBackgroundFetchResult) -> Void
    ) {
        Task {
            await FDAStore.shared.refresh()
            completionHandler(.newData)
        }
    }
}
