# 百度千帆用量获取实现指南

## 整体架构

```
┌─────────────────────────────────────────────────────────────────────┐
│                        实现架构                                      │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│   用户浏览器登录 ──→ Cookie自动读取 ──→ 调用内部API ──→ 解析用量     │
│                                                                     │
│   console.bce.baidu.com    Cookie导入      /v2/billing/resources    │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 一、需要创建的文件

在 `Sources/CodexBarCore/Providers/` 下创建新目录 `BaiduQianfan/`，包含以下文件：

```
Sources/CodexBarCore/Providers/BaiduQianfan/
├── BaiduQianfanProviderDescriptor.swift    # Provider描述符
├── BaiduQianfanUsageFetcher.swift          # 用量获取
├── BaiduQianfanCookieImporter.swift        # Cookie导入
├── BaiduQianfanModels.swift                # 数据模型
└── BaiduQianfanSettingsReader.swift        # 配置读取（可选）
```

在 `Sources/CodexBar/Providers/BaiduQianfan/` 下创建：

```
Sources/CodexBar/Providers/BaiduQianfan/
├── BaiduQianfanProviderImplementation.swift  # Provider实现
└── BaiduQianfanSettingsStore.swift           # 设置存储
```

---

## 二、核心代码实现

### 1. 数据模型 - `BaiduQianfanModels.swift`

```swift
import Foundation

// MARK: - API 响应模型
public struct BaiduQianfanAPIResponse: Codable, Sendable {
    public let success: Bool
    public let result: BaiduQianfanResult?
    public let log_id: String?
}

public struct BaiduQianfanResult: Codable, Sendable {
    public let totalCount: Int?
    public let items: [BaiduQianfanResource]?
}

public struct BaiduQianfanResource: Codable, Sendable {
    public let resourceId: String?
    public let apiKey: String?
    public let planType: String?
    public let resourceStatus: String?
    let effectiveAt: String?
    public let expiresAt: String?
    public let quota: BaiduQianfanQuota?
    
    private enum CodingKeys: String, CodingKey {
        case resourceId, apiKey, planType, resourceStatus
        case effectiveAt, expiresAt, quota
    }
}

public struct BaiduQianfanQuota: Codable, Sendable {
    public let fiveHour: BaiduQianfanQuotaWindow?
    public let week: BaiduQianfanQuotaWindow?
    public let month: BaiduQianfanQuotaWindow?
}

public struct BaiduQianfanQuotaWindow: Codable, Sendable {
    public let used: Int?
    public let limit: Int?
    public let resetAt: String?
    
    public var percentUsed: Double {
        guard let used = used, let limit = limit, limit > 0 else { return 0 }
        return Double(used) / Double(limit) * 100
    }
}

// MARK: - 用量快照
public struct BaiduQianfanUsageSnapshot: Sendable {
    public let fiveHourPercent: Double
    public let fiveHourUsed: Int
    public let fiveHourLimit: Int
    public let fiveHourResetAt: Date?
    
    public let weekPercent: Double
    public let weekUsed: Int
    public let weekLimit: Int
    public let weekResetAt: Date?
    
    public let monthPercent: Double
    public let monthUsed: Int
    public let monthLimit: Int
    public let monthResetAt: Date?
    
    public let planType: String?
    public let rawJSON: String?
    
    public func toUsageSnapshot() -> UsageSnapshot {
        // 主进度条：月度用量
        let primary = RateWindow(
            usedPercent: monthPercent,
            windowMinutes: nil,
            resetsAt: monthResetAt,
            resetDescription: monthResetAt.map { "重置于 \($0.formatted())" }
        )
        
        // 次级进度条：周用量
        let secondary: RateWindow? = weekPercent > 0 ? RateWindow(
            usedPercent: weekPercent,
            windowMinutes: nil,
            resetsAt: weekResetAt,
            resetDescription: nil
        ) : nil
        
        // 第三进度条：5小时窗口
        let tertiary: RateWindow? = fiveHourPercent > 0 ? RateWindow(
            usedPercent: fiveHourPercent,
            windowMinutes: 300, // 5小时
            resetsAt: fiveHourResetAt,
            resetDescription: nil
        ) : nil
        
        let identity = ProviderIdentitySnapshot(
            providerID: .baiduQianfan,
            accountEmail: nil,
            accountOrganization: nil,
            loginMethod: planType.map { "百度千帆 \($0)" }
        )
        
        return UsageSnapshot(
            primary: primary,
            secondary: secondary,
            tertiary: tertiary,
            providerCost: nil,
            updatedAt: Date(),
            identity: identity
        )
    }
}

// MARK: - 错误类型
public enum BaiduQianfanError: LocalizedError, Sendable {
    case notLoggedIn
    case networkError(String)
    case parseFailed(String)
    case noSessionCookie
    case apiError(String)
    
    public var errorDescription: String? {
        switch self {
        case .notLoggedIn:
            "未登录百度千帆，请在浏览器中登录 console.bce.baidu.com"
        case let .networkError(msg):
            "网络错误: \(msg)"
        case let .parseFailed(msg):
            "解析失败: \(msg)"
        case .noSessionCookie:
            "未找到登录状态，请在浏览器中登录百度智能云控制台"
        case let .apiError(msg):
            "API错误: \(msg)"
        }
    }
}
```

---

### 2. Cookie 导入 - `BaiduQianfanCookieImporter.swift`

```swift
#if os(macOS)
import Foundation
import SweetCookieKit

public enum BaiduQianfanCookieImporter {
    private static let cookieClient = BrowserCookieClient()
    
    /// 百度相关的 Cookie 域名
    private static let cookieDomains = [
        "console.bce.baidu.com",
        "bce.baidu.com",
        "qianfan.baidubce.com",
        ".baidu.com",
    ]
    
    /// 关键的会话 Cookie 名称（需要根据抓包结果确认）
    private static let sessionCookieNames: Set<String> = [
        "BIDUPSID",
        "BAIDUID",
        "BDUSS",
        "STOKEN",
        // 根据实际情况添加更多
    ]
    
    public struct SessionInfo: Sendable {
        public let cookies: [HTTPCookie]
        public let sourceLabel: String
        
        public var cookieHeader: String {
            cookies.map { "\($0.name)=\($0.value)" }.joined(separator: "; ")
        }
    }
    
    /// 从浏览器导入 Cookie
    public static func importSession(
        browserDetection: BrowserDetection,
        logger: ((String) -> Void)? = nil
    ) throws -> SessionInfo {
        let log: (String) -> Void = { msg in logger?("[baidu-qianfan] \(msg)") }
        
        let browserOrder = Browser.defaultImportOrder
        
        for browser in browserOrder {
            guard browserDetection.isCookieSourceAvailable(browser) else { continue }
            guard BrowserCookieAccessGate.shouldAttempt(browser) else { continue }
            
            do {
                let query = BrowserCookieQuery(domains: cookieDomains)
                let sources = try cookieClient.records(
                    matching: query,
                    in: browser,
                    logger: log
                )
                
                for source in sources where !source.records.isEmpty {
                    let httpCookies = BrowserCookieClient.makeHTTPCookies(
                        source.records,
                        origin: query.origin
                    )
                    
                    // 检查是否有会话 Cookie
                    let hasSession = httpCookies.contains { sessionCookieNames.contains($0.name) }
                    
                    if hasSession || !httpCookies.isEmpty {
                        log("Found \(httpCookies.count) cookies in \(source.label)")
                        return SessionInfo(cookies: httpCookies, sourceLabel: source.label)
                    }
                }
            } catch {
                BrowserCookieAccessGate.recordIfNeeded(error)
                log("\(browser.displayName) cookie import failed: \(error.localizedDescription)")
            }
        }
        
        throw BaiduQianfanError.noSessionCookie
    }
    
    /// 检查是否有可用的会话
    public static func hasSession(
        browserDetection: BrowserDetection,
        logger: ((String) -> Void)? = nil
    ) -> Bool {
        do {
            _ = try importSession(browserDetection: browserDetection, logger: logger)
            return true
        } catch {
            return false
        }
    }
}
#else
// 非 macOS 平台的空实现
public enum BaiduQianfanCookieImporter {
    public struct SessionInfo: Sendable {
        public let cookies: [HTTPCookie] = []
        public let sourceLabel: String = ""
        public var cookieHeader: String { "" }
    }
    
    public static func importSession(
        browserDetection: BrowserDetection,
        logger: ((String) -> Void)? = nil
    ) throws -> SessionInfo {
        throw BaiduQianfanError.noSessionCookie
    }
}
#endif
```

---

### 3. 用量获取 - `BaiduQianfanUsageFetcher.swift`

```swift
import Foundation

public struct BaiduQianfanUsageFetcher: Sendable {
    public let baseURL: URL
    public var timeout: TimeInterval = 15.0
    
    public init(baseURL: URL = URL(string: "https://qianfan.baidubce.com")!) {
        self.baseURL = baseURL
    }
    
    /// 使用 Cookie Header 获取用量
    public func fetch(cookieHeader: String) async throws -> BaiduQianfanUsageSnapshot {
        let url = baseURL.appendingPathComponent("/v2/billing/resources")
        var request = URLRequest(url: url)
        request.timeoutInterval = timeout
        request.httpMethod = "GET"
        request.setValue("application/json", forHTTPHeaderField: "Accept")
        request.setValue(cookieHeader, forHTTPHeaderField: "Cookie")
        
        // 可能需要的额外 Header（根据抓包结果调整）
        request.setValue("https://console.bce.baidu.com/", forHTTPHeaderField: "Referer")
        request.setValue("Mozilla/5.0", forHTTPHeaderField: "User-Agent")
        
        let (data, response) = try await URLSession.shared.data(for: request)
        
        guard let httpResponse = response as? HTTPURLResponse else {
            throw BaiduQianfanError.networkError("Invalid response")
        }
        
        switch httpResponse.statusCode {
        case 200:
            break
        case 401, 403:
            throw BaiduQianfanError.notLoggedIn
        default:
            let body = String(data: data, encoding: .utf8) ?? ""
            throw BaiduQianfanError.networkError("HTTP \(httpResponse.statusCode): \(body.prefix(200))")
        }
        
        return try parseResponse(data: data)
    }
    
    /// 解析 API 响应
    private func parseResponse(data: Data) throws -> BaiduQianfanUsageSnapshot {
        let rawJSON = String(data: data, encoding: .utf8) ?? ""
        
        let apiResponse: BaiduQianfanAPIResponse
        do {
            apiResponse = try JSONDecoder().decode(BaiduQianfanAPIResponse.self, from: data)
        } catch {
            throw BaiduQianfanError.parseFailed("JSON decode: \(error.localizedDescription)")
        }
        
        guard apiResponse.success else {
            throw BaiduQianfanError.apiError("API returned success=false")
        }
        
        guard let items = apiResponse.result?.items, let resource = items.first else {
            throw BaiduQianfanError.parseFailed("No resource data in response")
        }
        
        let quota = resource.quota
        let parser = ISO8601DateFormatter()
        parser.formatOptions = [.withInternetDateTime, .withTimeZone]
        
        func parseDate(_ string: String?) -> Date? {
            string.flatMap { parser.date(from: $0) }
        }
        
        func percent(_ window: BaiduQianfanQuotaWindow?) -> (percent: Double, used: Int, limit: Int) {
            guard let w = window, let used = w.used, let limit = w.limit else {
                return (0, 0, 0)
            }
            let pct = limit > 0 ? Double(used) / Double(limit) * 100 : 0
            return (min(100, max(0, pct)), used, limit)
        }
        
        let fiveHour = percent(quota?.fiveHour)
        let week = percent(quota?.week)
        let month = percent(quota?.month)
        
        return BaiduQianfanUsageSnapshot(
            fiveHourPercent: fiveHour.percent,
            fiveHourUsed: fiveHour.used,
            fiveHourLimit: fiveHour.limit,
            fiveHourResetAt: parseDate(quota?.fiveHour?.resetAt),
            weekPercent: week.percent,
            weekUsed: week.used,
            weekLimit: week.limit,
            weekResetAt: parseDate(quota?.week?.resetAt),
            monthPercent: month.percent,
            monthUsed: month.used,
            monthLimit: month.limit,
            monthResetAt: parseDate(quota?.month?.resetAt),
            planType: resource.planType,
            rawJSON: rawJSON
        )
    }
}
```

---

### 4. Provider 描述符 - `BaiduQianfanProviderDescriptor.swift`

```swift
import Foundation

public enum BaiduQianfanProviderDescriptor {
    public static let providerID: ProviderID = .baiduQianfan
    
    public static func createDescriptor() -> ProviderDescriptor {
        ProviderDescriptor(
            id: providerID,
            displayName: "百度千帆",
            shortName: "千帆",
            description: "百度智能云千帆大模型平台",
            category: .codingPlan,
            supportsMultipleAccounts: false,
            requiresAPIKey: false,
            requiresBrowserLogin: true,
            usageFetchStrategy: .cookieBased,
            icon: ProviderIcon.custom(name: "baidu-qianfan"),
            websiteURL: URL(string: "https://console.bce.baidu.com/qianfan")!
        )
    }
}
```

---

### 5. Provider 实现 - `BaiduQianfanProviderImplementation.swift`

```swift
#if os(macOS)
import Foundation
import SwiftUI

public final class BaiduQianfanProviderImplementation: ProviderImplementation {
    public let providerID: ProviderID = .baiduQianfan
    
    private let usageFetcher = BaiduQianfanUsageFetcher()
    private let browserDetection: BrowserDetection
    
    public init(browserDetection: BrowserDetection) {
        self.browserDetection = browserDetection
    }
    
    public func fetchUsage(
        cookieHeaderOverride: String?,
        logger: ((String) -> Void)?
    ) async throws -> UsageSnapshot {
        let log = logger ?? { _ in }
        
        let cookieHeader: String
        if let override = CookieHeaderNormalizer.normalize(cookieHeaderOverride) {
            cookieHeader = override
        } else if let cached = CookieHeaderCache.load(provider: providerID) {
            cookieHeader = cached.cookieHeader
        } else {
            let session = try BaiduQianfanCookieImporter.importSession(
                browserDetection: browserDetection,
                logger: log
            )
            cookieHeader = session.cookieHeader
            CookieHeaderCache.store(
                provider: providerID,
                cookieHeader: cookieHeader,
                sourceLabel: session.sourceLabel
            )
        }
        
        let snapshot = try await usageFetcher.fetch(cookieHeader: cookieHeader)
        return snapshot.toUsageSnapshot()
    }
    
    public func checkLoginStatus() async -> ProviderLoginStatus {
        do {
            let _ = try BaiduQianfanCookieImporter.importSession(
                browserDetection: browserDetection,
                logger: nil
            )
            return .loggedIn
        } catch {
            return .notLoggedIn
        }
    }
    
    public func logout() async {
        CookieHeaderCache.clear(provider: providerID)
    }
}
#endif
```

---

### 6. 注册 Provider

在 `Sources/CodexBarCore/Providers/Providers.swift` 中添加：

```swift
extension ProviderID {
    case baiduQianfan
}

extension ProviderDefaults {
    static let metadata: [ProviderID: ProviderMetadata] = [
        // ... 其他 providers
        .baiduQianfan: ProviderMetadata(
            browserCookieOrder: Browser.defaultImportOrder,
            displayName: "百度千帆"
        ),
    ]
}
```

---

## 三、需要根据抓包调整的部分

| 项目 | 需要确认的内容 | 如何获取 |
|------|---------------|----------|
| **API URL** | `/v2/billing/resources` 是否正确 | 抓包请求URL |
| **请求方法** | GET / POST | 抓包请求方法 |
| **请求头** | 是否需要 Referer、X-Request-ID 等 | 抓包 Headers |
| **Cookie 域名** | console.bce.baidu.com 是否足够 | 测试验证 |
| **Cookie 名称** | BIDUPSID、BAIDUID 等是否必需 | 测试验证 |

---

## 四、测试验证

```swift
// 测试代码
func testBaiduQianfanFetch() async {
    let fetcher = BaiduQianfanUsageFetcher()
    
    do {
        // 先从浏览器获取 Cookie
        let session = try BaiduQianfanCookieImporter.importSession(
            browserDetection: BrowserDetection()
        )
        
        // 获取用量
        let snapshot = try await fetcher.fetch(cookieHeader: session.cookieHeader)
        
        print("月用量: \(snapshot.monthPercent)%")
        print("周用量: \(snapshot.weekPercent)%")
        print("5小时用量: \(snapshot.fiveHourPercent)%")
        print("套餐类型: \(snapshot.planType ?? "未知")")
    } catch {
        print("错误: \(error)")
    }
}
```

---

## 五、实现步骤总结

```
1. 创建文件结构
   └── Sources/CodexBarCore/Providers/BaiduQianfan/
       └── 5个核心文件

2. 实现数据模型
   └── 解析你提供的 JSON 响应结构

3. 实现 Cookie 导入
   └── 从浏览器自动读取百度域名的 Cookie

4. 实现用量获取
   └── 调用抓包发现的内部 API

5. 注册 Provider
   └── 添加到 ProviderID 和 ProviderDefaults

6. 抓包调优
   └── 根据实际请求调整 URL、Headers、Cookie 域名

7. 测试验证
   └── 确保用量数据正确显示
```

---

## 六、API 响应示例

```json
{
  "success": true,
  "result": {
    "totalCount": 1,
    "items": [{
      "resourceId": "cp-muqxd0Mk",
      "apiKey": "bce-v3/ALTAKSP-xxx",
      "planType": "LITE",
      "resourceStatus": "Running",
      "effectiveAt": "2026-03-27T10:09:52+08:00",
      "expiresAt": "2026-04-27T10:09:52+08:00",
      "quota": {
        "fiveHour": {
          "used": 0,
          "limit": 1200,
          "resetAt": "2026-04-04T10:46:37+08:00"
        },
        "week": {
          "used": 1386,
          "limit": 9000,
          "resetAt": "2026-04-06T00:00:00+08:00"
        },
        "month": {
          "used": 1564,
          "limit": 18000,
          "resetAt": "2026-04-27T10:09:52+08:00"
        }
      },
      "autoRenew": {
        "renewTime": 1,
        "renewTimeUnit": "month"
      }
    }]
  },
  "log_id": "4209371467"
}
```
