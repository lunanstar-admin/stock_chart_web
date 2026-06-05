import Foundation

// MARK: - Root
struct FDAData: Codable {
    let updated: String
    let companies: [Company]
    let newApprovals: [NewApproval]
    let totalCompanies: Int
    let totalCompaniesWithApprovals: Int
    let totalApprovals: Int

    enum CodingKeys: String, CodingKey {
        case updated, companies
        case newApprovals = "new_approvals"
        case totalCompanies = "total_companies"
        case totalCompaniesWithApprovals = "total_companies_with_approvals"
        case totalApprovals = "total_approvals"
    }
}

// MARK: - Company
struct Company: Codable, Identifiable {
    var id: String { code }
    let nameKo: String
    let nameEn: String
    let code: String
    let sector: String
    let approvals: [Approval]
    let totalApprovals: Int
    let latestApproval: String?
    let newCount: Int

    enum CodingKeys: String, CodingKey {
        case nameKo = "name_ko"
        case nameEn = "name_en"
        case code, sector, approvals
        case totalApprovals = "total_approvals"
        case latestApproval = "latest_approval"
        case newCount = "new_count"
    }
}

// MARK: - Approval
struct Approval: Codable, Identifiable {
    var id: String { appNumber }
    let appNumber: String
    let appType: String
    let brandName: String
    let genericName: String
    let dosageForm: String
    let route: String
    let approvalDate: String
    let latestSupplDate: String
    let isNew: Bool
    let fdaURL: String

    enum CodingKeys: String, CodingKey {
        case appNumber = "app_number"
        case appType = "app_type"
        case brandName = "brand_name"
        case genericName = "generic_name"
        case dosageForm = "dosage_form"
        case route
        case approvalDate = "approval_date"
        case latestSupplDate = "latest_suppl_date"
        case isNew = "is_new"
        case fdaURL = "fda_url"
    }

    var formattedDate: String {
        guard approvalDate.count >= 7 else { return approvalDate }
        let parts = approvalDate.split(separator: "-")
        if parts.count == 3 { return "\(parts[0]).\(parts[1]).\(parts[2])" }
        return approvalDate
    }
}

// MARK: - NewApproval (alert payload)
struct NewApproval: Codable {
    let companyKo: String
    let companyEn: String
    let code: String
    let appNumber: String
    let appType: String
    let brandName: String
    let genericName: String
    let approvalDate: String

    enum CodingKeys: String, CodingKey {
        case companyKo = "company_ko"
        case companyEn = "company_en"
        case code
        case appNumber = "app_number"
        case appType = "app_type"
        case brandName = "brand_name"
        case genericName = "generic_name"
        case approvalDate = "approval_date"
    }
}
