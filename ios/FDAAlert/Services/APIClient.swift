import Foundation

enum APIClient {
    static func registerDevice(
        apnsToken: String,
        environment: String,
        subscriptions: [String] = ["all"]
    ) async throws {
        let url = URL(string: "\(Config.supabaseURL)/functions/v1/register-device")!
        var req = URLRequest(url: url)
        req.httpMethod = "POST"
        req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        req.setValue("Bearer \(Config.supabaseAnonKey)", forHTTPHeaderField: "Authorization")

        let info = Bundle.main.infoDictionary
        let appVersion = info?["CFBundleShortVersionString"] as? String ?? ""
        let osVersion = UIDevice.current.systemVersion

        let body: [String: Any] = [
            "apns_token": apnsToken,
            "environment": environment,
            "app_version": appVersion,
            "os_version": osVersion,
            "subscriptions": subscriptions,
        ]
        req.httpBody = try JSONSerialization.data(withJSONObject: body)

        let (_, response) = try await URLSession.shared.data(for: req)
        guard let http = response as? HTTPURLResponse, http.statusCode == 200 else {
            throw URLError(.badServerResponse)
        }
    }
}
