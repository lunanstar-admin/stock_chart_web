// CompanyDetailView.swift — FDA 알리미
// 기업 상세 화면: 회사 정보, 허가 목록, 배지, 날짜, FDA 링크, 알림 구독.

import SwiftUI
import SafariServices

struct CompanyDetailView: View {
    let company: Company

    @EnvironmentObject private var notificationService: NotificationService
    @Environment(\.openURL) private var openURL
    @State private var safariURL: URL?

    // MARK: - Body

    var body: some View {
        List {
            // 회사 요약 헤더
            headerSection

            // 알림 구독 설정
            notificationSection

            // 허가 목록
            if company.approvals.isEmpty {
                Section {
                    ContentUnavailableView(
                        "허가 이력 없음",
                        systemImage: "doc.text.magnifyingglass"
                    )
                }
            } else {
                approvalsSection
            }
        }
        .listStyle(.insetGrouped)
        .navigationTitle(company.nameKo)
        .navigationBarTitleDisplayMode(.large)
        .toolbar { toolbarContent }
        .sheet(item: $safariURL) { url in
            SafariView(url: url)
                .ignoresSafeArea()
        }
    }

    // MARK: - Header Section

    private var headerSection: some View {
        Section {
            HStack(spacing: 20) {
                StatView(
                    value: "\(company.totalApprovals)",
                    label: "FDA 허가",
                    valueColor: company.hasApprovals ? .blue : .secondary
                )
                Divider().frame(height: 36)
                StatView(
                    value: company.sector,
                    label: "분야",
                    isText: true
                )
                Divider().frame(height: 36)
                StatView(
                    value: company.code,
                    label: "종목코드",
                    isText: true
                )
            }
            .padding(.vertical, 4)
        } footer: {
            if let latest = company.latestApprovalDisplayText {
                Text("최근 허가일: \(latest)")
            }
        }
    }

    // MARK: - Notification Section

    private var notificationSection: some View {
        Section {
            HStack {
                VStack(alignment: .leading, spacing: 2) {
                    Text("\(company.nameKo) 알림")
                        .font(.body)
                    Text(notificationService.isSubscribed(to: company.code)
                         ? "새 FDA 허가 발생 시 알림을 받습니다"
                         : "이 기업의 알림이 꺼져 있습니다")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
                Spacer()
                Toggle("", isOn: Binding(
                    get: { notificationService.isSubscribed(to: company.code) },
                    set: { _ in
                        if !notificationService.subscribeAll {
                            notificationService.toggleSubscription(code: company.code)
                        }
                    }
                ))
                .labelsHidden()
                .disabled(notificationService.subscribeAll)
            }
        } header: {
            Text("알림 설정")
        } footer: {
            if notificationService.subscribeAll {
                Text("전체 구독 중 — 설정에서 개별 구독으로 변경할 수 있습니다.")
                    .font(.caption2)
            }
        }
    }

    // MARK: - Approvals Section

    private var approvalsSection: some View {
        let sorted = company.approvals.sorted {
            let lhs = $0.approvalDateValue ?? .distantPast
            let rhs = $1.approvalDateValue ?? .distantPast
            return lhs > rhs
        }

        return Section {
            ForEach(sorted) { approval in
                ApprovalRow(approval: approval) { url in
                    safariURL = url
                }
            }
        } header: {
            Text("허가 이력")
        } footer: {
            Text("출처: FDA Drugs@FDA (openFDA)")
                .font(.caption2)
        }
    }

    // MARK: - Toolbar

    @ToolbarContentBuilder
    private var toolbarContent: some ToolbarContent {
        ToolbarItem(placement: .navigationBarTrailing) {
            Button {
                if !notificationService.subscribeAll {
                    notificationService.toggleSubscription(code: company.code)
                }
            } label: {
                Image(systemName: notificationService.isSubscribed(to: company.code)
                      ? "bell.fill" : "bell.slash")
                .symbolRenderingMode(.hierarchical)
                .foregroundStyle(notificationService.isSubscribed(to: company.code) ? .blue : .secondary)
            }
            .disabled(notificationService.subscribeAll)
        }
    }
}

// MARK: - ApprovalRow

struct ApprovalRow: View {
    let approval: Approval
    var onOpenURL: ((URL) -> Void)? = nil

    @Environment(\.openURL) private var openURL

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            // 상단: 배지 + 날짜
            HStack(spacing: 6) {
                AppTypeBadge(type: approval.appType)
                if approval.isNew {
                    NewBadge()
                }
                Spacer()
                Text(approval.formattedDate)
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }

            // 브랜드명 / 출원번호
            Text(approval.brandName.isEmpty ? approval.appNumber : approval.brandName)
                .font(.headline)

            // 일반명
            if !approval.genericName.isEmpty {
                Text(approval.genericName)
                    .font(.subheadline)
                    .foregroundStyle(.secondary)
                    .italic()
            }

            // 제형 + 경로 + FDA 링크
            HStack(spacing: 8) {
                if !approval.dosageForm.isEmpty {
                    infoChip(approval.dosageForm.capitalized)
                }
                if !approval.route.isEmpty {
                    infoChip(approval.routeKo.isEmpty
                             ? approval.route.capitalized
                             : approval.routeKo)
                }
                Spacer()
                if !approval.fdaURL.isEmpty, let url = URL(string: approval.fdaURL) {
                    Button {
                        if let handler = onOpenURL {
                            handler(url)
                        } else {
                            openURL(url)
                        }
                    } label: {
                        Label("FDA ↗", systemImage: "arrow.up.right.square")
                            .font(.caption)
                            .labelStyle(.titleAndIcon)
                    }
                    .buttonStyle(.bordered)
                    .controlSize(.mini)
                }
            }

            // 보충 허가일
            if let supplDate = approval.latestSupplDateDisplay {
                Text("최근 보충 허가: \(supplDate)")
                    .font(.caption2)
                    .foregroundStyle(.tertiary)
            }
        }
        .padding(.vertical, 4)
    }

    private func infoChip(_ text: String) -> some View {
        Text(text)
            .font(.caption2)
            .foregroundStyle(.secondary)
            .padding(.horizontal, 6)
            .padding(.vertical, 2)
            .background(Color.secondary.opacity(0.12))
            .clipShape(Capsule())
    }
}

// MARK: - SafariView

struct SafariView: UIViewControllerRepresentable {
    let url: URL

    func makeUIViewController(context: Context) -> SFSafariViewController {
        let cfg = SFSafariViewController.Configuration()
        cfg.entersReaderIfAvailable = false
        cfg.barCollapsingEnabled = true
        let vc = SFSafariViewController(url: url, configuration: cfg)
        return vc
    }

    func updateUIViewController(_ uiViewController: SFSafariViewController, context: Context) {}
}

// SafariView URL Identifiable 확장 (sheet(item:) 용)
extension URL: @retroactive Identifiable {
    public var id: String { absoluteString }
}

// MARK: - Preview

#if DEBUG
#Preview {
    NavigationStack {
        CompanyDetailView(company: Company(
            nameKo: "셀트리온",
            nameEn: "Celltrion",
            code: "068270",
            sector: "바이오시밀러",
            approvals: [
                Approval(
                    appNumber: "BLA761298",
                    appType: "BLA",
                    brandName: "Zymfentra",
                    genericName: "infliximab-dyyb",
                    dosageForm: "SOLUTION",
                    route: "SUBCUTANEOUS",
                    approvalDate: "2023-10-19",
                    latestSupplDate: "",
                    isNew: true,
                    fdaURL: "https://www.accessdata.fda.gov/"
                ),
                Approval(
                    appNumber: "BLA125550",
                    appType: "BLA",
                    brandName: "Remsima",
                    genericName: "infliximab-abda",
                    dosageForm: "LYOPHILIZED POWDER",
                    route: "INTRAVENOUS",
                    approvalDate: "2016-04-05",
                    latestSupplDate: "2022-11-30",
                    isNew: false,
                    fdaURL: "https://www.accessdata.fda.gov/"
                )
            ],
            totalApprovals: 2,
            latestApproval: "2023-10-19",
            newCount: 1
        ))
        .environmentObject(NotificationService.shared)
    }
}
#endif
