// HomeView.swift — FDA 알리미
// 메인 화면: 기업 목록, 검색, 당김 새로 고침, 요약 통계.

import SwiftUI

struct HomeView: View {
    @EnvironmentObject private var store: FDAStore
    @Binding var pendingCompanyCode: String?
    @State private var selectedCompany: Company?

    // MARK: - Body

    var body: some View {
        NavigationStack {
            Group {
                if store.isLoading && store.data == nil {
                    ProgressView("불러오는 중…")
                        .frame(maxWidth: .infinity, maxHeight: .infinity)
                } else if let error = store.errorMessage, store.data == nil {
                    ContentUnavailableView {
                        Label("오류", systemImage: "exclamationmark.triangle")
                    } description: {
                        Text(error)
                    } actions: {
                        Button("다시 시도") { Task { await store.refresh() } }
                    }
                } else {
                    listContent
                }
            }
            .navigationTitle("FDA 허가 현황")
            .navigationBarTitleDisplayMode(.large)
            .searchable(text: $store.searchText, prompt: "기업명·약품명 검색")
            .refreshable { await store.refresh() }
            .toolbar {
                ToolbarItem(placement: .navigationBarTrailing) {
                    filterMenu
                }
            }
            .navigationDestination(item: $selectedCompany) { company in
                CompanyDetailView(company: company)
            }
        }
        .onChange(of: pendingCompanyCode) { _, code in
            guard let code,
                  let company = store.data?.companies.first(where: { $0.code == code })
            else { return }
            selectedCompany = company
            pendingCompanyCode = nil
        }
    }

    // MARK: - List Content

    private var listContent: some View {
        List {
            if let data = store.data {
                summarySection(data)
            }
            if let newApprovals = store.data?.newApprovals, !newApprovals.isEmpty {
                newApprovalsSection(newApprovals)
            }
            companiesSection
        }
        .listStyle(.insetGrouped)
    }

    // MARK: - Summary Section

    private func summarySection(_ data: FDAData) -> some View {
        Section {
            HStack(spacing: 20) {
                StatView(
                    value: "\(data.totalCompaniesWithApprovals)",
                    label: "허가 기업",
                    valueColor: .blue
                )
                Divider().frame(height: 36)
                StatView(
                    value: "\(data.totalApprovals)",
                    label: "총 허가 건수"
                )
                Divider().frame(height: 36)
                StatView(
                    value: data.newApprovals.isEmpty ? "-" : "\(data.newApprovals.count)",
                    label: "최근 신규",
                    valueColor: data.newApprovals.isEmpty ? .secondary : .orange
                )
            }
            .padding(.vertical, 4)
        } header: {
            Text("전체 현황")
        } footer: {
            Text("업데이트: \(data.updatedDisplayText)")
        }
    }

    // MARK: - New Approvals Section

    private func newApprovalsSection(_ approvals: [NewApproval]) -> some View {
        Section {
            ForEach(approvals) { approval in
                Button {
                    if let company = store.data?.companies.first(where: { $0.code == approval.code }) {
                        selectedCompany = company
                    }
                } label: {
                    NewApprovalRow(approval: approval)
                }
                .buttonStyle(.plain)
            }
        } header: {
            Label("최근 신규 허가", systemImage: "sparkles")
                .foregroundStyle(.orange)
        }
    }

    // MARK: - Companies Section

    private var companiesSection: some View {
        Section {
            let companies = store.filteredCompanies
            if companies.isEmpty {
                if store.searchText.isEmpty && store.selectedSector.isEmpty {
                    EmptyStateView(
                        icon: "building.2",
                        title: "기업 없음",
                        message: "등록된 기업이 없습니다."
                    )
                } else {
                    EmptyStateView(
                        icon: "magnifyingglass",
                        title: "검색 결과 없음",
                        message: "조건에 맞는 기업이 없습니다.",
                        actionLabel: "필터 초기화"
                    ) {
                        store.searchText = ""
                        store.selectedSector = ""
                    }
                }
            } else {
                ForEach(companies) { company in
                    CompanyRow(company: company)
                        .onTapGesture { selectedCompany = company }
                }
            }
        } header: {
            HStack {
                Text("기업별 허가 현황")
                Spacer()
                Text("\(store.filteredCompanies.count)개")
                    .font(.caption)
                    .foregroundStyle(.tertiary)
            }
        }
    }

    // MARK: - Filter Menu

    private var filterMenu: some View {
        Menu {
            // 섹터 필터
            Picker("분야", selection: $store.selectedSector) {
                Text("전체 분야").tag("")
                ForEach(store.allSectors, id: \.self) { sector in
                    Text(sector).tag(sector)
                }
            }

            Divider()

            // 허가 있는 기업만
            Toggle(isOn: $store.filterHasApprovals) {
                Label("허가 있는 기업만", systemImage: "checkmark.seal")
            }

            Divider()

            Button {
                Task { await store.refresh() }
            } label: {
                Label("새로 고침", systemImage: "arrow.clockwise")
            }

        } label: {
            let isFiltered = !store.selectedSector.isEmpty || store.filterHasApprovals
            Image(systemName: isFiltered
                  ? "line.3.horizontal.decrease.circle.fill"
                  : "line.3.horizontal.decrease.circle")
            .foregroundStyle(isFiltered ? .blue : .primary)
        }
    }
}

// MARK: - NewApprovalRow

private struct NewApprovalRow: View {
    let approval: NewApproval

    var body: some View {
        HStack(spacing: 10) {
            Image(systemName: "sparkle")
                .font(.system(size: 16))
                .foregroundStyle(.orange)
                .frame(width: 28)

            VStack(alignment: .leading, spacing: 3) {
                HStack(spacing: 6) {
                    AppTypeBadge(type: approval.appType)
                    NewBadge()
                    Text(approval.companyKo)
                        .font(.subheadline)
                        .bold()
                }
                Text(approval.brandName.isEmpty ? approval.appNumber : approval.brandName)
                    .font(.subheadline)
                Text(approval.genericName)
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }

            Spacer()

            Text(formatDate(approval.approvalDate))
                .font(.caption2)
                .foregroundStyle(.secondary)
        }
        .padding(.vertical, 2)
    }

    private func formatDate(_ d: String) -> String {
        let p = d.split(separator: "-")
        if p.count == 3 { return "\(p[0]).\(p[1]).\(p[2])" }
        return d
    }
}

// MARK: - Preview

#if DEBUG
#Preview {
    HomeView(pendingCompanyCode: .constant(nil))
        .environmentObject(FDAStore.shared)
        .environmentObject(NotificationService.shared)
}
#endif
