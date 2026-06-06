// Models.swift — FDA 알리미
// Codable 데이터 모델. fda_approvals.json 스키마와 1:1 대응.

import Foundation

// MARK: - Root

/// fda_approvals.json 최상위 구조
struct FDAData: Codable {
    let updated: String
    let companies: [Company]
    let newApprovals: [NewApproval]
    let totalCompanies: Int
    let totalCompaniesWithApprovals: Int
    let totalApprovals: Int

    enum CodingKeys: String, CodingKey {
        case updated, companies
        case newApprovals             = "new_approvals"
        case totalCompanies           = "total_companies"
        case totalCompaniesWithApprovals = "total_companies_with_approvals"
        case totalApprovals           = "total_approvals"
    }

    /// 업데이트 시각을 사용자 친화적 문자열로 반환
    var updatedDisplayText: String {
        let iso = ISO8601DateFormatter()
        iso.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        let iso2 = ISO8601DateFormatter()
        iso2.formatOptions = [.withInternetDateTime]
        let date = iso.date(from: updated) ?? iso2.date(from: updated)
        guard let date else {
            // fallback: "2026-06-04T13:30:00" → "2026.06.04 13:30"
            return updated.prefix(16).replacingOccurrences(of: "T", with: " ")
        }
        let fmt = DateFormatter()
        fmt.locale = Locale(identifier: "ko_KR")
        fmt.dateFormat = "M월 d일 HH:mm 기준"
        fmt.timeZone = TimeZone(identifier: "Asia/Seoul")
        return fmt.string(from: date)
    }
}

// MARK: - Company

struct Company: Codable, Identifiable, Hashable {
    var id: String { code }

    let nameKo: String
    let nameEn: String
    /// KRX 종목코드
    let code: String
    let sector: String
    let approvals: [Approval]
    let totalApprovals: Int
    /// nullable — 허가 없는 기업은 nil
    let latestApproval: String?
    /// 신규 허가 건수 (is_new == true)
    let newCount: Int

    enum CodingKeys: String, CodingKey {
        case nameKo        = "name_ko"
        case nameEn        = "name_en"
        case code, sector, approvals
        case totalApprovals = "total_approvals"
        case latestApproval = "latest_approval"
        case newCount       = "new_count"
    }

    // MARK: Computed

    var hasApprovals: Bool { totalApprovals > 0 }
    var hasNewApprovals: Bool { newCount > 0 }

    var latestApprovalDate: Date? {
        guard let raw = latestApproval else { return nil }
        return Self.ymdFormatter.date(from: raw)
    }

    var latestApprovalDisplayText: String? {
        guard let d = latestApprovalDate else { return nil }
        return Self.displayFormatter.string(from: d)
    }

    // MARK: Hashable

    static func == (lhs: Company, rhs: Company) -> Bool { lhs.code == rhs.code }
    func hash(into hasher: inout Hasher) { hasher.combine(code) }

    // MARK: Private formatters

    private static let ymdFormatter: DateFormatter = {
        let f = DateFormatter()
        f.dateFormat = "yyyy-MM-dd"
        f.locale = Locale(identifier: "en_US_POSIX")
        return f
    }()

    private static let displayFormatter: DateFormatter = {
        let f = DateFormatter()
        f.locale = Locale(identifier: "ko_KR")
        f.dateFormat = "yyyy. M. d."
        return f
    }()
}

// MARK: - Approval

struct Approval: Codable, Identifiable, Hashable {
    var id: String { appNumber }

    let appNumber: String
    let appType: String       // "NDA" | "BLA" | "ANDA"
    let brandName: String
    let genericName: String
    let dosageForm: String
    let route: String
    let approvalDate: String
    let latestSupplDate: String
    let isNew: Bool
    let fdaURL: String

    enum CodingKeys: String, CodingKey {
        case appNumber      = "app_number"
        case appType        = "app_type"
        case brandName      = "brand_name"
        case genericName    = "generic_name"
        case dosageForm     = "dosage_form"
        case route
        case approvalDate   = "approval_date"
        case latestSupplDate = "latest_suppl_date"
        case isNew          = "is_new"
        case fdaURL         = "fda_url"
    }

    // MARK: Computed

    var approvalDateValue: Date? {
        Self.ymdFormatter.date(from: approvalDate)
    }

    var formattedDate: String {
        guard let d = approvalDateValue else { return approvalDate }
        return Self.displayFormatter.string(from: d)
    }

    var latestSupplDateDisplay: String? {
        guard !latestSupplDate.isEmpty,
              latestSupplDate != approvalDate,
              let d = Self.ymdFormatter.date(from: latestSupplDate)
        else { return nil }
        return Self.displayFormatter.string(from: d)
    }

    /// 투여 경로 한국어 표시
    var routeKo: String {
        switch route.uppercased() {
        case "ORAL":           return "경구"
        case "INTRAVENOUS":    return "정맥"
        case "SUBCUTANEOUS":   return "피하"
        case "INTRAMUSCULAR":  return "근육"
        case "INTRAVITREAL":   return "유리체"
        case "TOPICAL":        return "국소"
        case "INTRANASAL":     return "비강"
        case "INHALATION":     return "흡입"
        default:               return route.isEmpty ? "" : route
        }
    }

    // MARK: Hashable

    static func == (lhs: Approval, rhs: Approval) -> Bool { lhs.appNumber == rhs.appNumber }
    func hash(into hasher: inout Hasher) { hasher.combine(appNumber) }

    // MARK: Private

    private static let ymdFormatter: DateFormatter = {
        let f = DateFormatter()
        f.dateFormat = "yyyy-MM-dd"
        f.locale = Locale(identifier: "en_US_POSIX")
        return f
    }()

    private static let displayFormatter: DateFormatter = {
        let f = DateFormatter()
        f.locale = Locale(identifier: "ko_KR")
        f.dateFormat = "yyyy. M. d."
        return f
    }()
}

// MARK: - NewApproval (신규 허가 — 알림용)

struct NewApproval: Codable, Identifiable {
    var id: String { appNumber }

    let companyKo: String
    let companyEn: String
    let code: String
    let appNumber: String
    let appType: String
    let brandName: String
    let genericName: String
    let approvalDate: String

    enum CodingKeys: String, CodingKey {
        case companyKo  = "company_ko"
        case companyEn  = "company_en"
        case code
        case appNumber  = "app_number"
        case appType    = "app_type"
        case brandName  = "brand_name"
        case genericName = "generic_name"
        case approvalDate = "approval_date"
    }
}

// MARK: - AlertsData

struct AlertsData: Codable {
    let updated: String
    let total: Int
    let newCount: Int
    let alerts: [FDAAlert]

    enum CodingKeys: String, CodingKey {
        case updated, total, alerts
        case newCount = "new_count"
    }
}

struct FDAAlert: Codable, Identifiable {
    let id: String
    let source: String
    let companyKo: String
    let companyEn: String
    let code: String
    let title: String
    let url: String
    let published: String
    let tier: String
    let matchedKeyword: String?
    let flrNm: String?

    enum CodingKeys: String, CodingKey {
        case id, source, code, title, url, published, tier
        case companyKo      = "company_ko"
        case companyEn      = "company_en"
        case matchedKeyword = "matched_keyword"
        case flrNm          = "flr_nm"
    }

    var isDart: Bool { source == "DART" }
    var isStrong: Bool { tier == "strong" }
    var openURL: URL? { URL(string: url) }

    var publishedDate: Date? {
        let iso = ISO8601DateFormatter()
        iso.formatOptions = [.withInternetDateTime]
        if let d = iso.date(from: published) { return d }
        let fmt = DateFormatter()
        fmt.dateFormat = "yyyy-MM-dd"
        fmt.locale = Locale(identifier: "en_US_POSIX")
        return fmt.date(from: published)
    }

    var publishedDisplayText: String {
        guard let d = publishedDate else { return published }
        let fmt = DateFormatter()
        fmt.locale = Locale(identifier: "ko_KR")
        fmt.timeZone = TimeZone(identifier: "Asia/Seoul")
        let hours = Calendar.current.dateComponents([.hour], from: d, to: Date()).hour ?? 999
        fmt.dateFormat = hours < 24 ? "HH:mm" : (hours < 168 ? "M/d HH:mm" : "M월 d일")
        return fmt.string(from: d)
    }
}

// MARK: - DeepLink

/// 푸시 알림 tap → 앱 내 특정 화면으로 이동
struct DeepLink: Equatable {
    enum Destination: Equatable {
        case company(code: String)
        case home
    }
    let destination: Destination

    /// notification userInfo 에서 딥링크 파싱
    static func from(userInfo: [AnyHashable: Any]) -> DeepLink? {
        if let code = userInfo["company_code"] as? String, !code.isEmpty {
            return DeepLink(destination: .company(code: code))
        }
        return nil
    }

    /// URL 스킴에서 딥링크 파싱 — fdaalert://company/068270
    static func from(url: URL) -> DeepLink? {
        guard url.scheme == Config.urlScheme else { return nil }
        let host = url.host ?? ""
        let components = url.pathComponents.filter { $0 != "/" }
        switch host {
        case "company":
            if let code = components.first {
                return DeepLink(destination: .company(code: code))
            }
        default:
            break
        }
        return nil
    }
}
