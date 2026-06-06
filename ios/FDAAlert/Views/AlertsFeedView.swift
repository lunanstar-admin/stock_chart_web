// AlertsFeedView.swift — FDA 알리미
// DART 공시 + FDA RSS 실시간 속보 피드.

import SwiftUI

struct AlertsFeedView: View {
    @EnvironmentObject private var store: AlertsStore
    @Environment(\.openURL) private var openURL

    var body: some View {
        NavigationStack {
            Group {
                if store.isLoading && store.alerts.isEmpty {
                    ProgressView("불러오는 중…")
                        .frame(maxWidth: .infinity, maxHeight: .infinity)
                } else if let error = store.errorMessage, store.alerts.isEmpty {
                    ContentUnavailableView {
                        Label("오류", systemImage: "exclamationmark.triangle")
                    } description: {
                        Text(error)
                    } actions: {
                        Button("다시 시도") { Task { await store.refresh() } }
                    }
                } else if store.alerts.isEmpty {
                    ContentUnavailableView {
                        Label("속보 없음", systemImage: "bolt.slash")
                    } description: {
                        Text("최근 FDA / DART 속보가 없습니다.")
                    }
                } else {
                    alertsList
                }
            }
            .navigationTitle("FDA 속보")
            .navigationBarTitleDisplayMode(.large)
            .refreshable { await store.refresh() }
            .toolbar {
                if store.unreadCount > 0 {
                    ToolbarItem(placement: .navigationBarTrailing) {
                        Button("모두 읽음") { store.markAllRead() }
                            .font(.subheadline)
                    }
                }
            }
        }
        .task { store.load() }
    }

    // MARK: - Alerts List

    private var alertsList: some View {
        ZStack(alignment: .bottom) {
            List(store.alerts) { alert in
                AlertRow(alert: alert, isRead: store.isRead(alert))
                    .contentShape(Rectangle())
                    .onTapGesture {
                        store.markRead(alert)
                        if let url = alert.openURL {
                            openURL(url)
                        }
                    }
                    .listRowBackground(
                        store.isRead(alert)
                            ? Color(.systemBackground)
                            : Color.blue.opacity(0.05)
                    )
                    .listRowSeparator(.hidden)
            }
            .listStyle(.plain)

            if let updated = store.lastUpdated {
                Text("업데이트: \(formattedUpdated(updated))")
                    .font(.caption2)
                    .foregroundStyle(.tertiary)
                    .padding(.vertical, 6)
                    .frame(maxWidth: .infinity)
                    .background(.bar)
            }
        }
    }

    // MARK: - Helpers

    private func formattedUpdated(_ raw: String) -> String {
        let iso = ISO8601DateFormatter()
        iso.formatOptions = [.withInternetDateTime]
        guard let d = iso.date(from: raw) else {
            return String(raw.prefix(16)).replacingOccurrences(of: "T", with: " ")
        }
        let fmt = DateFormatter()
        fmt.locale = Locale(identifier: "ko_KR")
        fmt.timeZone = TimeZone(identifier: "Asia/Seoul")
        fmt.dateFormat = "M월 d일 HH:mm"
        return fmt.string(from: d)
    }
}

// MARK: - AlertRow

struct AlertRow: View {
    let alert: FDAAlert
    let isRead: Bool

    var body: some View {
        HStack(alignment: .top, spacing: 12) {
            // Source icon
            ZStack {
                RoundedRectangle(cornerRadius: 10)
                    .fill(alert.isDart ? Color.blue.opacity(0.12) : Color.red.opacity(0.12))
                    .frame(width: 44, height: 44)
                Image(systemName: alert.isDart ? "doc.text.fill" : "newspaper.fill")
                    .font(.system(size: 18))
                    .foregroundStyle(alert.isDart ? .blue : .red)
            }

            VStack(alignment: .leading, spacing: 5) {
                // Header row
                HStack(spacing: 6) {
                    Text(alert.isDart ? "DART" : "FDA")
                        .font(.caption2.bold())
                        .foregroundStyle(.white)
                        .padding(.horizontal, 6)
                        .padding(.vertical, 2)
                        .background(alert.isDart ? Color.blue : Color.red, in: Capsule())

                    Text(alert.companyKo)
                        .font(.subheadline.bold())

                    Spacer()

                    if !isRead {
                        Circle()
                            .fill(Color.blue)
                            .frame(width: 8, height: 8)
                    }
                }

                // Title
                Text(alert.title)
                    .font(.subheadline)
                    .foregroundStyle(isRead ? .secondary : .primary)
                    .lineLimit(3)
                    .multilineTextAlignment(.leading)

                // Footer row
                HStack(spacing: 8) {
                    Text(alert.publishedDisplayText)
                        .font(.caption)
                        .foregroundStyle(.tertiary)

                    if alert.isStrong {
                        Label("속보", systemImage: "bolt.fill")
                            .font(.caption2.bold())
                            .foregroundStyle(.orange)
                    }
                }
            }
        }
        .padding(.vertical, 6)
    }
}

// MARK: - Preview

#if DEBUG
#Preview {
    AlertsFeedView()
        .environmentObject(AlertsStore.shared)
}
#endif
