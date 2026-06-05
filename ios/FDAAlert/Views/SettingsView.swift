import SwiftUI
import UserNotifications

struct SettingsView: View {
    @AppStorage("notifyAll") private var notifyAll = true
    @AppStorage("subscribedCodes") private var subscribedCodesRaw = "all"
    @State private var authStatus: UNAuthorizationStatus = .notDetermined
    @EnvironmentObject var store: FDAStore

    var subscribedCodes: Set<String> {
        Set(subscribedCodesRaw.split(separator: ",").map(String.init))
    }

    var body: some View {
        NavigationStack {
            Form {
                notificationSection
                subscriptionSection
                infoSection
            }
            .navigationTitle("설정")
        }
        .task { await checkAuthStatus() }
    }

    private var notificationSection: some View {
        Section {
            if authStatus == .denied {
                HStack {
                    Image(systemName: "bell.slash.fill").foregroundStyle(.red)
                    VStack(alignment: .leading) {
                        Text("알림 권한 없음").bold()
                        Text("설정 앱에서 알림을 허용해주세요")
                            .font(.caption).foregroundStyle(.secondary)
                    }
                    Spacer()
                    Button("설정 열기") {
                        if let url = URL(string: UIApplication.openSettingsURLString) {
                            UIApplication.shared.open(url)
                        }
                    }
                    .font(.caption)
                }
            } else {
                Toggle(isOn: $notifyAll) {
                    Label("신규 FDA 허가 알림", systemImage: "bell.fill")
                }
                .onChange(of: notifyAll) { _, enabled in
                    if enabled { Task { await enableNotifications() } }
                }
            }
        } header: {
            Text("알림")
        } footer: {
            Text("국내 바이오기업의 미국 FDA 신규 허가 시 카카오톡 알림을 받습니다.")
        }
    }

    private var subscriptionSection: some View {
        Section {
            Toggle(isOn: Binding(
                get: { subscribedCodes.contains("all") },
                set: { all in
                    subscribedCodesRaw = all ? "all" : ""
                    saveSubscription(all ? ["all"] : [])
                }
            )) {
                Label("전체 기업 구독", systemImage: "building.2.fill")
            }

            if !subscribedCodes.contains("all") {
                ForEach(store.data?.companies ?? []) { company in
                    Toggle(isOn: Binding(
                        get: { subscribedCodes.contains(company.code) },
                        set: { on in
                            var codes = subscribedCodes
                            if on { codes.insert(company.code) } else { codes.remove(company.code) }
                            subscribedCodesRaw = codes.joined(separator: ",")
                            saveSubscription(Array(codes))
                        }
                    )) {
                        HStack {
                            Text(company.nameKo)
                            Spacer()
                            Text(company.sector)
                                .font(.caption).foregroundStyle(.secondary)
                        }
                    }
                }
            }
        } header: {
            Text("구독 기업")
        } footer: {
            Text("특정 기업만 선택하면 해당 기업의 허가만 알림으로 받습니다.")
        }
    }

    private var infoSection: some View {
        Section("정보") {
            LabeledContent("데이터 출처", value: "openFDA API")
            LabeledContent("업데이트 주기", value: "매일 장마감 후")
            if let version = Bundle.main.infoDictionary?["CFBundleShortVersionString"] as? String {
                LabeledContent("앱 버전", value: version)
            }
            Link(destination: URL(string: "https://secomdal.com/fda")!) {
                Label("secomdal.com FDA 페이지", systemImage: "arrow.up.right.square")
            }
        }
    }

    private func checkAuthStatus() async {
        authStatus = await UNUserNotificationCenter.current().notificationSettings().authorizationStatus
    }

    private func enableNotifications() async {
        let granted = await NotificationService.shared.requestAuthorization()
        if granted {
            await NotificationService.shared.registerIfAuthorized()
        }
        await checkAuthStatus()
    }

    private func saveSubscription(_ codes: [String]) {
        Task {
            guard let token = UserDefaults.standard.string(forKey: "apnsToken") else { return }
            #if DEBUG
            let env = "sandbox"
            #else
            let env = "production"
            #endif
            try? await APIClient.registerDevice(
                apnsToken: token,
                environment: env,
                subscriptions: codes.isEmpty ? ["all"] : codes
            )
        }
    }
}
