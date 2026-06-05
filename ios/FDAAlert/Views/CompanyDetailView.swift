import SwiftUI

struct CompanyDetailView: View {
    let company: Company

    var body: some View {
        List {
            headerSection
            if company.approvals.isEmpty {
                Section {
                    ContentUnavailableView("허가 이력 없음", systemImage: "doc.text.magnifyingglass")
                }
            } else {
                approvalsSection
            }
        }
        .listStyle(.insetGrouped)
        .navigationTitle(company.nameKo)
        .navigationBarTitleDisplayMode(.large)
    }

    private var headerSection: some View {
        Section {
            HStack(spacing: 20) {
                statView(value: "\(company.totalApprovals)", label: "FDA 허가")
                Divider().frame(height: 36)
                statView(value: company.sector, label: "분야", isText: true)
                Divider().frame(height: 36)
                statView(value: company.code, label: "종목코드", isText: true)
            }
            .padding(.vertical, 4)
        }
    }

    private var approvalsSection: some View {
        Section {
            ForEach(company.approvals) { approval in
                ApprovalRow(approval: approval)
            }
        } header: {
            Text("허가 이력")
        } footer: {
            Text("출처: FDA Drugs@FDA (openFDA API)")
                .font(.caption2)
        }
    }

    private func statView(value: String, label: String, isText: Bool = false) -> some View {
        VStack(spacing: 2) {
            Text(value)
                .font(isText ? .subheadline : .title2)
                .bold()
                .foregroundStyle(isText ? .primary : .blue)
                .lineLimit(1)
                .minimumScaleFactor(0.7)
            Text(label).font(.caption2).foregroundStyle(.secondary)
        }
        .frame(maxWidth: .infinity)
    }
}

struct ApprovalRow: View {
    let approval: Approval
    @Environment(\.openURL) private var openURL

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack(spacing: 6) {
                AppTypeBadge(type: approval.appType)
                if approval.isNew {
                    Text("NEW").font(.system(size: 9, weight: .bold))
                        .padding(.horizontal, 5).padding(.vertical, 2)
                        .background(.blue).foregroundStyle(.white)
                        .clipShape(RoundedRectangle(cornerRadius: 4))
                }
                Spacer()
                Text(approval.formattedDate)
                    .font(.caption).foregroundStyle(.secondary)
            }

            Text(approval.brandName.isEmpty ? approval.appNumber : approval.brandName)
                .font(.headline)

            if !approval.genericName.isEmpty {
                Text(approval.genericName)
                    .font(.subheadline).foregroundStyle(.secondary)
            }

            HStack(spacing: 8) {
                if !approval.dosageForm.isEmpty {
                    infoChip(approval.dosageForm.capitalized)
                }
                if !approval.route.isEmpty {
                    infoChip(approval.route.capitalized)
                }
                Spacer()
                if !approval.fdaURL.isEmpty, let url = URL(string: approval.fdaURL) {
                    Button {
                        openURL(url)
                    } label: {
                        Label("FDA ↗", systemImage: "arrow.up.right.square")
                            .font(.caption).labelStyle(.titleAndIcon)
                    }
                    .buttonStyle(.bordered)
                    .controlSize(.mini)
                }
            }

            if !approval.latestSupplDate.isEmpty, approval.latestSupplDate != approval.approvalDate {
                Text("최근 보충 허가: \(formatDate(approval.latestSupplDate))")
                    .font(.caption2).foregroundStyle(.tertiary)
            }
        }
        .padding(.vertical, 4)
    }

    private func infoChip(_ text: String) -> some View {
        Text(text)
            .font(.caption2).foregroundStyle(.secondary)
            .padding(.horizontal, 6).padding(.vertical, 2)
            .background(.secondary.opacity(0.12))
            .clipShape(Capsule())
    }

    private func formatDate(_ d: String) -> String {
        let p = d.split(separator: "-")
        if p.count == 3 { return "\(p[0]).\(p[1]).\(p[2])" }
        return d
    }
}

// MARK: - Shared Components
struct AppTypeBadge: View {
    let type: String

    var color: Color {
        switch type {
        case "BLA": return .blue
        case "NDA": return .green
        case "ANDA": return .purple
        default: return .secondary
        }
    }

    var body: some View {
        Text(type)
            .font(.system(size: 10, weight: .bold))
            .padding(.horizontal, 6).padding(.vertical, 2)
            .background(color.opacity(0.15))
            .foregroundStyle(color)
            .clipShape(RoundedRectangle(cornerRadius: 4))
    }
}
