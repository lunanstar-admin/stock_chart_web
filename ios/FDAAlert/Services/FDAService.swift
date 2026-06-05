import Foundation

@MainActor
final class FDAStore: ObservableObject {
    @Published var data: FDAData?
    @Published var isLoading = false
    @Published var errorMessage: String?
    @Published var searchText = ""
    @Published var selectedType: String = ""     // "", "BLA", "NDA", "ANDA"
    @Published var selectedSector: String = ""

    var filteredCompanies: [Company] {
        guard let companies = data?.companies else { return [] }
        return companies.filter { company in
            let nameMatch = searchText.isEmpty
                || company.nameKo.contains(searchText)
                || company.nameEn.lowercased().contains(searchText.lowercased())
                || company.approvals.contains {
                    $0.brandName.lowercased().contains(searchText.lowercased())
                    || $0.genericName.lowercased().contains(searchText.lowercased())
                }
            let sectorMatch = selectedSector.isEmpty || company.sector == selectedSector
            return nameMatch && sectorMatch
        }
    }

    var allSectors: [String] {
        let sectors = Set(data?.companies.map(\.sector) ?? [])
        return sectors.sorted()
    }

    func load() async {
        isLoading = true
        errorMessage = nil
        do {
            let (raw, _) = try await URLSession.shared.data(from: Config.fdaDataURL)
            let decoded = try JSONDecoder().decode(FDAData.self, from: raw)
            data = decoded
        } catch {
            errorMessage = error.localizedDescription
        }
        isLoading = false
    }
}
