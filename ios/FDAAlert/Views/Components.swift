// Components.swift — FDA 알리미
// 재사용 가능한 UI 컴포넌트 모음.
// AppTypeBadge, NewBadge, CompanyCard, SectionHeader, EmptyStateView, ErrorView

import SwiftUI

// MARK: - AppTypeBadge

/// NDA / BLA / ANDA 허가 유형 배지
struct AppTypeBadge: View {
    let appType: String

    private var color: Color {
        switch appType.uppercased() {
        case "NDA":  return .blue
        case "BLA":  return Color(red: 0.55, green: 0.27, blue: 0.85) // 보라
        case "ANDA": return .green
        default:     return .gray
        }
    }

    private var label: String {
        appType.uppercased()
    }

    var body: some View {
        Text(label)
            .font(.system(size: 11, weight: .semibold, design: .monospaced))
            .foregroundColor(color)
            .padding(.horizontal, 6)
            .padding(.vertical, 3)
            .background(color.opacity(0.12))
            .clipShape(RoundedRectangle(cornerRadius: 5, style: .continuous))
            .overlay(
                RoundedRectangle(cornerRadius: 5, style: .continuous)
                    .strokeBorder(color.opacity(0.3), lineWidth: 0.5)
            )
    }
}

// MARK: - NewBadge

/// 신규 허가 배지 ("NEW")
struct NewBadge: View {
    var body: some View {
        Text("NEW")
            .font(.system(size: 10, weight: .bold))
            .foregroundColor(.white)
            .padding(.horizontal, 6)
            .padding(.vertical, 2)
            .background(
                LinearGradient(
                    colors: [Color.red, Color.orange],
                    startPoint: .leading,
                    endPoint: .trailing
                )
            )
            .clipShape(Capsule())
    }
}

// MARK: - CompanyCard

/// 홈 화면 기업 카드
struct CompanyCard: View {
    let company: Company
    var showSector: Bool = true

    var body: some View {
        HStack(spacing: 12) {
            // 좌측: 회사 정보
            VStack(alignment: .leading, spacing: 4) {
                HStack(spacing: 6) {
                    Text(company.nameKo)
                        .font(.system(size: 16, weight: .semibold))
                        .foregroundStyle(.primary)

                    if company.hasNewApprovals {
                        NewBadge()
                    }
                }

                Text(company.nameEn)
                    .font(.system(size: 13))
                    .foregroundStyle(.secondary)

                if showSector {
                    HStack(spacing: 4) {
                        Image(systemName: "tag.fill")
                            .font(.system(size: 10))
                            .foregroundStyle(.tertiary)
                        Text(company.sector)
                            .font(.system(size: 12))
                            .foregroundStyle(.tertiary)
                    }
                }
            }

            Spacer()

            // 우측: 통계
            VStack(alignment: .trailing, spacing: 4) {
                HStack(spacing: 4) {
                    Image(systemName: "checkmark.seal.fill")
                        .font(.system(size: 12))
                        .foregroundStyle(company.hasApprovals ? .green : Color.secondary.opacity(0.4))
                    Text("\(company.totalApprovals)건")
                        .font(.system(size: 14, weight: .medium))
                        .foregroundStyle(company.hasApprovals ? .primary : .secondary)
                }

                if let dateText = company.latestApprovalDisplayText {
                    Text(dateText)
                        .font(.system(size: 11))
                        .foregroundStyle(.secondary)
                } else {
                    Text("허가 없음")
                        .font(.system(size: 11))
                        .foregroundStyle(.tertiary)
                }

                Text(company.code)
                    .font(.system(size: 11, design: .monospaced))
                    .foregroundStyle(.tertiary)
            }
        }
        .padding(.vertical, 4)
        .contentShape(Rectangle())
    }
}

// MARK: - SectionHeader

struct SectionHeader: View {
    let title: String
    var subtitle: String? = nil

    var body: some View {
        VStack(alignment: .leading, spacing: 2) {
            Text(title)
                .font(.system(size: 13, weight: .semibold))
                .foregroundStyle(.secondary)
                .textCase(.uppercase)

            if let sub = subtitle {
                Text(sub)
                    .font(.system(size: 11))
                    .foregroundStyle(.tertiary)
            }
        }
        .padding(.top, 4)
    }
}

// MARK: - StatPill

/// 통계 카운트 Pill (홈 요약 바에서 사용)
struct StatPill: View {
    let icon: String
    let value: String
    let label: String
    var accentColor: Color = .accentColor

    var body: some View {
        VStack(spacing: 2) {
            HStack(spacing: 4) {
                Image(systemName: icon)
                    .font(.system(size: 13, weight: .medium))
                    .foregroundStyle(accentColor)
                Text(value)
                    .font(.system(size: 15, weight: .bold))
                    .foregroundStyle(.primary)
            }
            Text(label)
                .font(.system(size: 11))
                .foregroundStyle(.secondary)
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, 10)
        .background(Color(.secondarySystemGroupedBackground))
        .clipShape(RoundedRectangle(cornerRadius: 12, style: .continuous))
    }
}

// MARK: - EmptyStateView

struct EmptyStateView: View {
    let icon: String
    let title: String
    let message: String
    var action: (() -> Void)? = nil
    var actionLabel: String? = nil

    var body: some View {
        VStack(spacing: 16) {
            Image(systemName: icon)
                .font(.system(size: 48))
                .foregroundStyle(.quaternary)

            VStack(spacing: 4) {
                Text(title)
                    .font(.headline)
                    .foregroundStyle(.primary)
                Text(message)
                    .font(.subheadline)
                    .foregroundStyle(.secondary)
                    .multilineTextAlignment(.center)
            }

            if let action, let label = actionLabel {
                Button(label, action: action)
                    .buttonStyle(.bordered)
                    .controlSize(.small)
            }
        }
        .padding(32)
        .frame(maxWidth: .infinity)
    }
}

// MARK: - ErrorView

struct ErrorView: View {
    let error: AppError
    let onRetry: () -> Void

    var body: some View {
        VStack(spacing: 20) {
            Image(systemName: "exclamationmark.triangle.fill")
                .font(.system(size: 40))
                .foregroundStyle(.orange)

            VStack(spacing: 6) {
                Text("데이터를 불러오지 못했습니다")
                    .font(.headline)

                Text(error.errorDescription ?? "알 수 없는 오류")
                    .font(.subheadline)
                    .foregroundStyle(.secondary)
                    .multilineTextAlignment(.center)
                    .padding(.horizontal, 24)
            }

            Button {
                onRetry()
            } label: {
                Label("다시 시도", systemImage: "arrow.clockwise")
            }
            .buttonStyle(.bordered)
            .controlSize(.regular)
        }
        .padding(40)
        .frame(maxWidth: .infinity)
    }
}

// MARK: - LoadingView

struct LoadingView: View {
    var message: String = "데이터를 불러오는 중…"

    var body: some View {
        VStack(spacing: 16) {
            ProgressView()
                .scaleEffect(1.2)
            Text(message)
                .font(.subheadline)
                .foregroundStyle(.secondary)
        }
        .frame(maxWidth: .infinity, minHeight: 200)
    }
}

// MARK: - ApprovalRow

/// 기업 상세 화면의 허가 항목 행
struct ApprovalRow: View {
    let approval: Approval

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            // 상단: 배지 + 브랜드명
            HStack(spacing: 8) {
                AppTypeBadge(appType: approval.appType)

                if approval.isNew {
                    NewBadge()
                }

                Spacer()

                Text(approval.approvalDateDisplay)
                    .font(.system(size: 12))
                    .foregroundStyle(.secondary)
            }

            // 브랜드명
            if !approval.brandName.isEmpty {
                Text(approval.brandName)
                    .font(.system(size: 15, weight: .semibold))
                    .foregroundStyle(.primary)
            }

            // 일반명
            Text(approval.genericName)
                .font(.system(size: 13))
                .foregroundStyle(.secondary)
                .italic()

            // 제형 / 투여 경로
            HStack(spacing: 12) {
                if !approval.dosageForm.isEmpty {
                    Label(
                        approval.dosageForm.capitalized,
                        systemImage: "pills.fill"
                    )
                    .font(.system(size: 12))
                    .foregroundStyle(.tertiary)
                }

                if !approval.routeKo.isEmpty {
                    Label(
                        approval.routeKo,
                        systemImage: "syringe.fill"
                    )
                    .font(.system(size: 12))
                    .foregroundStyle(.tertiary)
                }
            }

            // 보충 허가일
            if let supplDate = approval.latestSupplDateDisplay {
                HStack(spacing: 4) {
                    Image(systemName: "arrow.triangle.2.circlepath")
                        .font(.system(size: 10))
                        .foregroundStyle(.tertiary)
                    Text("보충 허가: \(supplDate)")
                        .font(.system(size: 11))
                        .foregroundStyle(.tertiary)
                }
            }

            // 출원 번호
            Text(approval.appNumber)
                .font(.system(size: 11, design: .monospaced))
                .foregroundStyle(.quaternary)
        }
        .padding(.vertical, 4)
    }
}

// MARK: - Previews

#if DEBUG
#Preview("AppTypeBadge") {
    HStack(spacing: 8) {
        AppTypeBadge(appType: "NDA")
        AppTypeBadge(appType: "BLA")
        AppTypeBadge(appType: "ANDA")
    }
    .padding()
}

#Preview("CompanyCard") {
    let sampleApproval = Approval(
        appNumber: "BLA761298",
        appType: "BLA",
        brandName: "Zymfentra",
        genericName: "infliximab-dyyb",
        dosageForm: "SOLUTION",
        route: "SUBCUTANEOUS",
        approvalDate: "2023-10-19",
        latestSupplDate: "",
        isNew: true,
        fdaURL: "https://example.com"
    )
    let company = Company(
        nameKo: "셀트리온",
        nameEn: "Celltrion",
        code: "068270",
        sector: "바이오시밀러",
        approvals: [sampleApproval],
        totalApprovals: 5,
        latestApproval: "2023-10-19",
        newCount: 1
    )
    List {
        CompanyCard(company: company)
    }
    .listStyle(.insetGrouped)
}
#endif
