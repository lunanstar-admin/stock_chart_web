// FDAAlertApp.swift — FDA 알리미
// @main 진입점. AppDelegate, ContentView 는 별도 파일에 정의됨.

import SwiftUI
import UserNotifications

// MARK: - Main App

@main
struct FDAAlertApp: App {
    @UIApplicationDelegateAdaptor(AppDelegate.self) var appDelegate
    @StateObject private var store = FDAStore.shared
    @StateObject private var notificationService = NotificationService.shared
    @State private var pendingCompanyCode: String?

    var body: some Scene {
        WindowGroup {
            ContentView(pendingCompanyCode: $pendingCompanyCode)
                .environmentObject(store)
                .environmentObject(notificationService)
                .task { await store.refresh() }
                .onOpenURL { url in
                    // URL 스킴 딥링크: fdaalert://company/068270
                    if let link = DeepLink.from(url: url),
                       case .company(let code) = link.destination {
                        pendingCompanyCode = code
                    }
                }
                .onReceive(NotificationCenter.default.publisher(for: .fdaOpenCompany)) { notif in
                    pendingCompanyCode = notif.userInfo?["code"] as? String
                }
        }
    }
}
