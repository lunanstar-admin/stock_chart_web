// AlertsStore.swift — FDA 알리미
// fda_alerts.json 을 fetch·캐시하고 읽음 상태를 관리하는 스토어.

import Foundation
import Combine

@MainActor
final class AlertsStore: ObservableObject {

    static let shared = AlertsStore()

    @Published private(set) var alerts: [FDAAlert] = []
    @Published private(set) var isLoading = false
    @Published private(set) var errorMessage: String?
    @Published private(set) var lastUpdated: String?

    var unreadCount: Int { alerts.filter { !readIDs.contains($0.id) }.count }

    private var readIDs: Set<String> = []
    private var refreshTimer: Timer?
    private let readIDsKey = "fda_alert_read_ids"

    private let session: URLSession = {
        let cfg = URLSessionConfiguration.default
        cfg.timeoutIntervalForRequest = Config.requestTimeout
        cfg.requestCachePolicy = .reloadIgnoringLocalCacheData
        return URLSession(configuration: cfg)
    }()

    private init() {
        loadReadIDs()
        scheduleAutoRefresh()
        NotificationCenter.default.addObserver(
            self,
            selector: #selector(appForegrounded),
            name: UIApplication.willEnterForegroundNotification,
            object: nil
        )
    }

    // MARK: - Public

    func load() {
        guard !isLoading else { return }
        Task { await fetchAlerts() }
    }

    func refresh() async {
        await fetchAlerts()
    }

    func markRead(_ alert: FDAAlert) {
        guard !readIDs.contains(alert.id) else { return }
        readIDs.insert(alert.id)
        saveReadIDs()
        objectWillChange.send()
    }

    func markAllRead() {
        let ids = alerts.map(\.id)
        guard !ids.isEmpty else { return }
        ids.forEach { readIDs.insert($0) }
        saveReadIDs()
        objectWillChange.send()
    }

    func isRead(_ alert: FDAAlert) -> Bool { readIDs.contains(alert.id) }

    // MARK: - Private

    private func fetchAlerts() async {
        isLoading = true
        errorMessage = nil
        defer { isLoading = false }
        do {
            let (raw, response) = try await session.data(from: Config.fdaAlertsURL)
            if let http = response as? HTTPURLResponse, !(200...299).contains(http.statusCode) {
                errorMessage = "서버 오류 (HTTP \(http.statusCode))"
                return
            }
            let decoded = try JSONDecoder().decode(AlertsData.self, from: raw)
            alerts = decoded.alerts
            lastUpdated = decoded.updated
        } catch is CancellationError {
        } catch {
            if alerts.isEmpty { errorMessage = error.localizedDescription }
        }
    }

    private func scheduleAutoRefresh() {
        refreshTimer = Timer.scheduledTimer(withTimeInterval: 15 * 60, repeats: true) { [weak self] _ in
            guard let self else { return }
            Task { @MainActor in await self.fetchAlerts() }
        }
    }

    @objc private func appForegrounded() {
        Task { await fetchAlerts() }
    }

    private func loadReadIDs() {
        let arr = UserDefaults.standard.stringArray(forKey: readIDsKey) ?? []
        readIDs = Set(arr)
    }

    private func saveReadIDs() {
        UserDefaults.standard.set(Array(readIDs), forKey: readIDsKey)
    }
}
