// Components.swift — FDA 알리미
// 재사용 가능한 UI 컴포넌트 모음.
// AppTypeBadge, NewBadge, CompanyRow, SectionHeader, EmptyStateView

import SwiftUI

// MARK: - AppTypeBadge

/// NDA / BLA / ANDA 허가 유형 배지
struct AppTypeBadge: View {
    let type: String

    private var badgeColor: Color {
        switch type.uppercased() {
        case "NDA":  return .green
        case "BLA":  return .blue
        case "ANDA": return .purple
        default:     return .secondary
        }
    }

    var body: some View {
        Text(type.uppercased())
            .font(.system(size: 10, weight: .bold, design: .monospaced))
            .foregroundStyle(badgeColor)
            .padding(.horizontal, 6)
            .padding(.vertical, 2)
            .background(badgeColor.opacity(0.15))
            .clipShape(RoundedRectangle(cornerRadius: 4, style: .continuous))
            .overlay(
                RoundedRectangle(cornerRadius: 4, style: .continuous)
                    .strokeBorder(badgeColor.opacity(0.3), lineWidth: 0.5)
            )
    }
}

// MARK: - NewBadge

/// 신규 허가 배지 ("NEW")
struct NewBadge: View {
    var body: some View {
        Text("NEW")
            .font(.system(size: 9, weight: .bold))
            .foregroundStyle(.white)
            .padding(.horizontal, 5)
            .padding(.vertical, 2)
            .background(
                LinearGradient(
                    colors: [Color.red, Color.orange],
                    startPoint: .leading,
                    endPoint: .trailing
                )
            )
            .clipShape(RoundedRectangle(cornerRadius: 4))
    }
}

// MARK: - StatView

/// 요약 통계 항목
struct StatView: View {
    let value: String
    let label: String
    var valueColor: Color = .primary
    var isText: Bool = false

    var body: some View {
        VStack(spacing: 2) {
            Text(value)
                .font(isText ? .subheadline : .title2)
                .bold()
                .foregroundStyle(valueColor)
                .lineLimit(1)
                .minimumScaleFactor(0.6)
            Text(label)
                .font(.caption2)
                .foregroundStyle(.secondary)
        }
        .frame(maxWidth: .infinity)
    }
}

// MARK: - CompanyRow

/// 홈 화면 기업 행 (리스트용)
struct CompanyRow: View {
    let company: Company

    var body: some View {
        HStack(spacing: 12) {
            VStack(alignment: .leading, spacing: 3) {
                HStack(spacing: 6) {
                    Text(company.nameKo)
                        .font(.headline)
                    if company.hasNewApprovals {
                        NewBadge()
                    }
                }
                HStack(spacing: 6) {
                    Text(company.nameEn)
                        .font(.caption)
                        .foregroundStyle(.secondary)
                    Text(company.sector)
                        .font(.caption2)
                        .foregroundStyle(.secondary)
                        .padding(.horizontal, 6)
                        .padding(.vertical, 1)
                        .background(Color.secondary.opacity(0.12))
                        .clipShape(Capsule())
                }
            }
            Spacer()
            VStack(alignment: .trailing, spacing: 2) {
                Text("\(company.totalApprovals)")
                    .font(.title3)
                    .bold()
                    .foregroundStyle(company.hasApprovals ? .blue : .secondary)
                Text("허가")
                    .font(.caption2)
                    .foregroundStyle(.secondary)
                if let latest = company.latestApproval {
                    Text(formatShortDate(latest))
                        .font(.caption2)
                        .foregroundStyle(.tertiary)
                }
            }
            Image(systemName: "chevron.right")
                .font(.caption)
                .foregroundStyle(.tertiary)
        }
        .padding(.vertical, 4)
        .contentShape(Rectangle())
    }

    private func formatShortDate(_ d: String) -> String {
        let p = d.split(separator: "-")
        if p.count == 3 { return "\(p[0]).\(p[1])" }
        return d
    }
}

// MARK: - EmptyStateView

struct EmptyStateView: View {
    let icon: String
    let title: String
    let message: String
    var actionLabel: String? = nil
    var action: (() -> Void)? = nil

    var body: some View {
        VStack(spacing: 16) {
            Image(systemName: icon)
                .font(.system(size: 48))
                .foregroundStyle(.quaternary)
            VStack(spacing: 4) {
                Text(title)
                    .font(.headline)
                Text(message)
                    .font(.subheadline)
                    .foregroundStyle(.secondary)
                    .multilineTextAlignment(.center)
            }
            if let label = actionLabel, let action {
                Button(label, action: action)
                    .buttonStyle(.bordered)
                    .controlSize(.small)
            }
        }
        .padding(32)
        .frame(maxWidth: .infinity)
    }
}

// MARK: - Previews

#if DEBUG
#Preview("AppTypeBadge") {
    HStack(spacing: 8) {
        AppTypeBadge(type: "NDA")
        AppTypeBadge(type: "BLA")
        AppTypeBadge(type: "ANDA")
    }
    .padding()
}

#Preview("CompanyRow") {
    List {
        CompanyRow(company: Company(
            nameKo: "셀트리온",
            nameEn: "Celltrion",
            code: "068270",
            sector: "바이오시밀러",
            approvals: [],
            totalApprovals: 5,
            latestApproval: "2023-10-19",
            newCount: 1
        ))
    }
    .listStyle(.insetGrouped)
}
#endif
