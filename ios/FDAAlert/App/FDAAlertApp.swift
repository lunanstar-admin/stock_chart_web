import SwiftUI

@main
struct FDAAlertApp: App {
    @UIApplicationDelegateAdaptor(AppDelegate.self) var appDelegate
    @StateObject private var store = FDAStore()
    @State private var pendingCompanyCode: String?

    var body: some Scene {
        WindowGroup {
            ContentView(pendingCompanyCode: $pendingCompanyCode)
                .environmentObject(store)
                .task { await store.load() }
                .onReceive(NotificationCenter.default.publisher(for: .openCompany)) { notif in
                    pendingCompanyCode = notif.userInfo?["code"] as? String
                }
        }
    }
}
