import SwiftUI

struct HomeView: View {
    @EnvironmentObject var store: FDAStore
    @Binding var pendingCompanyCode: String?
    @State private var selectedCompany: Company?

    var body: some View {
        NavigationStack {
            Group {
                if store.isLoading && store.data == nil {
                    ProgressView("불러오는 중…")
                        .frame(maxWidth: .infinity, maxHeight: .infinity)
                } else if let error = store.errorMessage {
                    ContentUnavailableView {
                        Label("오류", systemImage: "exclamationmark.triangle")
                    } description: {
                        Text(error)
                    } actions: {
                        Button("다시 시도") { Task { await store.load() } }
                    }
                } else {
                    listContent
                }
            }
            .navigationTitle("FDA 허가 현황")
            .navigationBarTitleDisplayMode(.large)
            .searchable(text: $store.searchText, prompt: "기업명·약품명 검색")
            .refreshable { await store.load() }
            .toolbar {
                ToolbarItem(placement: .navigationBarTrailing) {
                    filterMenu
                }
            }
        }
        .navigationDestination(item: $selectedCompany) { company in
            CompanyDetailView(company: company)
        }
        .onChange(of: pendingCompanyCode) { _, code in
            guard let code, let company = store.data?.companies.first(where: { $0.code == code }) else { return }
            selectedCompany = company
            pendingCompanyCode = nil
        }
    }

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

    private func summarySection(_ data: FDAData) -> some View {
        Section {
            HStack(spacing: 20) {
                statView(value: "\(data.totalCompaniesWithApprovals)", label: "허가 기업")
                Divider().frame(height: 36)
                statView(value: "\(data.totalApprovals)", label: "총 허가 건수")
                Divider().frame(height: 36)
                statView(value: data.newApprovals.count > 0 ? "\(data.newApprovals.count)" : "-",
                         label: "최근 신규",
                         valueColor: data.newApprovals.count > 0 ? .blue : .secondary)
            }
            .padding(.vertical, 4)
        } header: {
            Text("전체 현황")
        } footer: {
            if let updated = store.data?.updated {
                Text("업데이트: \(formatUpdated(updated))")
            }
        }
    }

    private func newApprovalsSection(_ approvals: [NewApproval]) -> some View {
        Section("🆕 최근 90일 신규 허가") {
            ForEach(approvals, id: \.appNumber) { a in
                HStack {
                    AppTypeBadge(type: a.appType)
                    VStack(alignment: .leading, spacing: 2) {
                        Text(a.brandName.isEmpty ? a.appNumber : a.brandName)
                            .font(.subheadline).bold()
                        Text("\(a.companyKo) · \(a.genericName)")
                            .font(.caption).foregroundStyle(.secondary)
                    }
                    Spacer()
                    Text(formatDate(a.approvalDate))
                        .font(.caption2).foregroundStyle(.secondary)
                }
            }
        }
    }

    private var companiesSection: some View {
        Section("기업별 허가 현황") {
            ForEach(store.filteredCompanies) { company in
                CompanyRow(company: company)
                    .contentShape(Rectangle())
                    .onTapGesture { selectedCompany = company }
            }
        }
    }

    private var filterMenu: some View {
        Menu {
            Picker("분야", selection: $store.selectedSector) {
                Text("전체 분야").tag("")
                ForEach(store.allSectors, id: \.self) { sector in
                    Text(sector).tag(sector)
                }
            }
        } label: {
            Image(systemName: store.selectedSector.isEmpty ? "line.3.horizontal.decrease.circle" : "line.3.horizontal.decrease.circle.fill")
        }
    }

    private func statView(value: String, label: String, valueColor: Color = .primary) -> some View {
        VStack(spacing: 2) {
            Text(value).font(.title2).bold().foregroundStyle(valueColor)
            Text(label).font(.caption2).foregroundStyle(.secondary)
        }
        .frame(maxWidth: .infinity)
    }

    private func formatUpdated(_ iso: String) -> String {
        guard iso.count >= 16 else { return iso }
        return String(iso.prefix(16)).replacingOccurrences(of: "T", with: " ")
    }

    private func formatDate(_ d: String) -> String {
        let p = d.split(separator: "-")
        if p.count == 3 { return "\(p[0]).\(p[1]).\(p[2])" }
        return d
    }
}

struct CompanyRow: View {
    let company: Company

    var body: some View {
        HStack(spacing: 12) {
            VStack(alignment: .leading, spacing: 3) {
                HStack(spacing: 6) {
                    Text(company.nameKo).font(.headline)
                    if company.newCount > 0 {
                        Text("NEW").font(.system(size: 9, weight: .bold))
                            .padding(.horizontal, 5).padding(.vertical, 2)
                            .background(.blue).foregroundStyle(.white)
                            .clipShape(RoundedRectangle(cornerRadius: 4))
                    }
                }
                HStack(spacing: 6) {
                    Text(company.nameEn).font(.caption).foregroundStyle(.secondary)
                    Text(company.sector)
                        .font(.caption2).foregroundStyle(.secondary)
                        .padding(.horizontal, 6).padding(.vertical, 1)
                        .background(.secondary.opacity(0.15))
                        .clipShape(Capsule())
                }
            }
            Spacer()
            VStack(alignment: .trailing, spacing: 2) {
                Text("\(company.totalApprovals)")
                    .font(.title3).bold()
                    .foregroundStyle(company.totalApprovals > 0 ? .blue : .secondary)
                Text("허가").font(.caption2).foregroundStyle(.secondary)
                if let latest = company.latestApproval {
                    Text(formatDate(latest)).font(.caption2).foregroundStyle(.tertiary)
                }
            }
            Image(systemName: "chevron.right")
                .font(.caption).foregroundStyle(.tertiary)
        }
        .padding(.vertical, 4)
    }

    private func formatDate(_ d: String) -> String {
        let p = d.split(separator: "-")
        if p.count == 3 { return "\(p[0]).\(p[1])" }
        return d
    }
}
