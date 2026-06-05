// FDAService.swift — FDA 알리미
// fda_approvals.json 을 비동기 fetch 하고 결과를 뷰 레이어에 publish.
// @MainActor ObservableObject — 모든 상태 변경이 메인 스레드에서 발생.

import Foundation
import Combine

@MainActor
final class FDAStore: ObservableObject {

    // MARK: - Singleton
    static let shared = FDAStore()

    // MARK: - Published State
    @Published private(set) var data: FDAData?
    @Published private(set) var isLoading: Bool = false
    @Published private(set) var errorMessage: String?

    /// 검색어
    @Published var searchText: String = ""

    /// 섹터 필터 ("" = 전체)
    @Published var selectedSector: String = ""

    /// 허가 있는 기업만 표시
    @Published var filterHasApprovals: Bool = false

    // MARK: - Computed

    /// 필터/검색 적용된 기업 목록
    var filteredCompanies: [Company] {
        guard let companies = data?.companies else { return [] }
        var result = companies

        if filterHasApprovals {
            result = result.filter { $0.hasApprovals }
        }

        if !selectedSector.isEmpty {
            result = result.filter { $0.sector == selectedSector }
        }

        let query = searchText.trimmingCharacters(in: .whitespaces)
        if !query.isEmpty {
            let lower = query.lowercased()
            result = result.filter {
                $0.nameKo.contains(lower) ||
                $0.nameEn.lowercased().contains(lower) ||
                $0.sector.contains(lower) ||
                $0.code.contains(lower) ||
                $0.approvals.contains {
                    $0.brandName.lowercased().contains(lower) ||
                    $0.genericName.lowercased().contains(lower)
                }
            }
        }

        return result
    }

    /// 전체 섹터 목록 (정렬)
    var allSectors: [String] {
        let sectors = Set(data?.companies.map(\.sector) ?? [])
        return sectors.sorted()
    }

    /// 신규 허가 건수 합계
    var totalNewCount: Int {
        data?.newApprovals.count ?? 0
    }

    // MARK: - Private

    private var cachedData: FDAData?
    private var cacheTimestamp: Date?
    private var loadTask: Task<Void, Never>?

    private let session: URLSession = {
        let cfg = URLSessionConfiguration.default
        cfg.timeoutIntervalForRequest = Config.requestTimeout
        cfg.timeoutIntervalForResource = Config.requestTimeout * 2
        cfg.requestCachePolicy = .reloadIgnoringLocalCacheData
        return URLSession(configuration: cfg)
    }()

    // MARK: - Init

    private init() {}

    // MARK: - Public API

    /// 데이터 로드 (캐시 유효 시 재사용)
    func load(forceRefresh: Bool = false) {
        if isLoading { return }

        if !forceRefresh,
           let cached = cachedData,
           let ts = cacheTimestamp,
           Date().timeIntervalSince(ts) < Config.cacheMaxAge {
            data = cached
            return
        }

        loadTask?.cancel()
        loadTask = Task { await fetchData() }
    }

    /// 당김 새로 고침
    func refresh() async {
        await fetchData()
    }

    /// 회사 코드로 기업 찾기
    func company(withCode code: String) -> Company? {
        data?.companies.first { $0.code == code }
    }

    // MARK: - Private

    private func fetchData() async {
        isLoading = true
        errorMessage = nil

        do {
            let (raw, response) = try await session.data(from: Config.fdaDataURL)

            if let http = response as? HTTPURLResponse, !(200...299).contains(http.statusCode) {
                errorMessage = "서버 오류 (HTTP \(http.statusCode))"
                isLoading = false
                return
            }

            let decoded = try JSONDecoder().decode(FDAData.self, from: raw)

            cachedData = decoded
            cacheTimestamp = Date()
            data = decoded

        } catch is CancellationError {
            // Task 취소 — 무시
        } catch let e as DecodingError {
            errorMessage = "데이터 파싱 오류: \(decodingErrorMessage(e))"
        } catch {
            errorMessage = "네트워크 오류: \(error.localizedDescription)"
        }

        isLoading = false
    }

    private func decodingErrorMessage(_ error: DecodingError) -> String {
        switch error {
        case .keyNotFound(let key, _):       return "필드 누락: \(key.stringValue)"
        case .typeMismatch(_, let ctx):       return "타입 불일치: \(ctx.debugDescription)"
        case .valueNotFound(_, let ctx):      return "값 없음: \(ctx.debugDescription)"
        case .dataCorrupted(let ctx):         return "데이터 손상: \(ctx.debugDescription)"
        @unknown default:                     return error.localizedDescription
        }
    }
}
