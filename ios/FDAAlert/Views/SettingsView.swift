// SettingsView.swift — FDA 알리미
// 알림 토글 및 구독 관리 화면.

import SwiftUI
import UserNotifications

struct SettingsView: View {
    @EnvironmentObject private var store: FDAStore
    @EnvironmentObject private var notificationService: NotificationService

    // MARK: - Body

    var body: some View {
        NavigationStack {
            List {
                // 알림 섹션
                notificationSection

                // 구독 관리 섹션
                if notificationService.notificationsEnabled {
                    subscriptionSection
                }

                // 앱 정보 섹션
                appInfoSection
            }
            .listStyle(.insetGrouped)
            .navigationTitle("설정")
            .navigationBarTitleDisplayMode(.large)
            .refreshable {
                await notificationService.refreshAuthorizationStatus()
            }
        }
    }

    // MARK: - Notification Section

    private var notificationSection: some View {
        Section {
            // 알림 마스터 토글
            HStack {
                VStack(alignment: .leading, spacing: 2) {
                    Text("FDA 허가 알림")
                        .font(.body)
                    Text(statusDescription)
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
                Spacer()
                Toggle("", isOn: $notificationService.notificationsEnabled)
                    .labelsHidden()
            }
            .padding(.vertical, 2)

            // 시스템 알림 허용 필요 안내
            if notificationService.authorizationStatus == .denied {
                HStack(spacing: 10) {
                    Image(systemName: "exclamationmark.triangle.fill")
                        .foregroundStyle(.orange)
                    Text("시스템 설정에서 알림을 허용해야 합니다.")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                    Spacer()
                    Button("설정 열기") {
                        if let url = URL(string: UIApplication.openSettingsURLString) {
                            UIApplication.shared.open(url)
                        }
                    }
                    .font(.caption)
                    .buttonStyle(.bordered)
                    .controlSize(.mini)
                }
            }

            // 등록 오류 표시
            if let error = notificationService.registrationError {
                HStack(spacing: 8) {
                    Image(systemName: "xmark.circle.fill")
                        .foregroundStyle(.red)
                    Text(error)
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
            }

        } header: {
            Text("알림")
        } footer: {
            Text("새로운 FDA 허가가 발생하면 푸시 알림을 받을 수 있습니다.")
        }
    }

    private var statusDescription: String {
        switch notificationService.authorizationStatus {
        case .authorized:
            return notificationService.notificationsEnabled ? "알림이 활성화되어 있습니다" : "알림이 비활성화되어 있습니다"
        case .denied:
            return "시스템에서 알림이 차단되어 있습니다"
        case .notDetermined:
            return "알림 권한을 아직 요청하지 않았습니다"
        case .provisional:
            return "임시 알림 권한이 부여되어 있습니다"
        case .ephemeral:
            return "임시 알림이 허용되어 있습니다"
        @unknown default:
            return "알림 상태를 확인할 수 없습니다"
        }
    }

    // MARK: - Subscription Section

    private var subscriptionSection: some View {
        Section {
            // 전체 구독 토글
            Toggle(isOn: $notificationService.subscribeAll) {
                VStack(alignment: .leading, spacing: 2) {
                    Text("모든 기업 구독")
                        .font(.body)
                    Text("새 허가가 발생한 모든 기업의 알림을 받습니다")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
            }

            // 개별 구독 (전체 구독이 꺼진 경우)
            if !notificationService.subscribeAll,
               let companies = store.data?.companies {
                ForEach(companies) { company in
                    HStack {
                        VStack(alignment: .leading, spacing: 2) {
                            HStack(spacing: 6) {
                                Text(company.nameKo)
                                    .font(.body)
                                if company.hasNewApprovals {
                                    NewBadge()
                                }
                            }
                            Text(company.sector)
                                .font(.caption)
                                .foregroundStyle(.secondary)
                        }
                        Spacer()
                        Toggle(
                            "",
                            isOn: Binding(
                                get: { notificationService.subscribedCodes.contains(company.code) },
                                set: { _ in notificationService.toggleSubscription(code: company.code) }
                            )
                        )
                        .labelsHidden()
                    }
                    .padding(.vertical, 2)
                }
            }

        } header: {
            Text("구독 관리")
        } footer: {
            if notificationService.subscribeAll {
                Text("전체 구독 중: 모든 한국 바이오텍 기업의 새 FDA 허가 알림을 받습니다.")
            } else {
                let count = notificationService.subscribedCodes.count
                Text("\(count)개 기업을 구독 중입니다.")
            }
        }
    }

    // MARK: - App Info Section

    private var appInfoSection: some View {
        Section {
            // 데이터 새로 고침
            Button {
                Task { await store.refresh() }
            } label: {
                HStack {
                    Label("데이터 새로 고침", systemImage: "arrow.clockwise")
                    Spacer()
                    if store.isLoading {
                        ProgressView()
                            .scaleEffect(0.8)
                    }
                }
            }
            .disabled(store.isLoading)

            // 데이터 출처
            HStack {
                Label("데이터 출처", systemImage: "doc.text")
                Spacer()
                Text("secomdal.com")
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }

            // 버전 정보
            HStack {
                Label("버전", systemImage: "info.circle")
                Spacer()
                Text(appVersion)
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }

        } header: {
            Text("앱 정보")
        }
    }

    // MARK: - Helpers

    private var appVersion: String {
        let version = Bundle.main.infoDictionary?["CFBundleShortVersionString"] as? String ?? "1.0"
        let build = Bundle.main.infoDictionary?["CFBundleVersion"] as? String ?? "1"
        return "\(version) (\(build))"
    }
}

// MARK: - Preview

#if DEBUG
#Preview {
    SettingsView()
        .environmentObject(FDAStore.shared)
        .environmentObject(NotificationService.shared)
}
#endif
