import SwiftUI

struct ContentView: View {
    @EnvironmentObject var store: FDAStore
    @Binding var pendingCompanyCode: String?

    var body: some View {
        TabView {
            HomeView(pendingCompanyCode: $pendingCompanyCode)
                .tabItem { Label("허가 현황", systemImage: "pill.fill") }

            SettingsView()
                .tabItem { Label("설정", systemImage: "bell.fill") }
        }
    }
}
