import SwiftUI

struct ContentView: View {
    @EnvironmentObject var store: FDAStore
    @EnvironmentObject var alertsStore: AlertsStore
    @Binding var pendingCompanyCode: String?

    var body: some View {
        TabView {
            HomeView(pendingCompanyCode: $pendingCompanyCode)
                .tabItem { Label("허가 현황", systemImage: "pill.fill") }

            AlertsFeedView()
                .tabItem { Label("속보", systemImage: "bolt.fill") }
                .badge(alertsStore.unreadCount > 0 ? alertsStore.unreadCount : 0)

            SettingsView()
                .tabItem { Label("설정", systemImage: "bell.fill") }
        }
    }
}
