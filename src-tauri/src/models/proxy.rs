use serde::{Deserialize, Serialize};

/// 代理类型枚举
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
#[serde(rename_all = "lowercase")]
pub enum ProxyType {
    /// HTTP 代理
    Http,
    /// SOCKS5 代理
    Socks5,
}

/// 网络代理配置结构
///
/// 支持 HTTP 和 SOCKS5 代理，可选用户名/密码认证
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ProxySettings {
    /// 是否启用代理
    pub enabled: bool,

    /// 代理类型（HTTP 或 SOCKS5）
    pub proxy_type: ProxyType,

    /// 代理服务器地址（如：127.0.0.1）
    pub host: String,

    /// 代理服务器端口
    pub port: u16,

    /// 用户名（可选，用于需要认证的代理）
    #[serde(skip_serializing_if = "Option::is_none")]
    pub username: Option<String>,

    /// 密码（可选，用于需要认证的代理）
    #[serde(skip_serializing_if = "Option::is_none")]
    pub password: Option<String>,
}

impl Default for ProxySettings {
    fn default() -> Self {
        Self {
            enabled: false,
            proxy_type: ProxyType::Http,
            host: String::new(),
            port: 0,
            username: None,
            password: None,
        }
    }
}

impl ProxySettings {
    /// 构建代理 URL
    ///
    /// 示例：
    /// - HTTP: `http://127.0.0.1:8080`
    /// - SOCKS5: `socks5://127.0.0.1:1080`
    /// - 带认证: `http://user:pass@127.0.0.1:8080`
    pub fn to_proxy_url(&self) -> String {
        let protocol = match self.proxy_type {
            ProxyType::Http => "http",
            ProxyType::Socks5 => "socks5",
        };

        // 构建认证信息部分
        let auth = match (&self.username, &self.password) {
            (Some(user), Some(pass)) => format!("{}:{}@", user, pass),
            (Some(user), None) => format!("{}@", user),
            _ => String::new(),
        };

        format!("{}://{}{}:{}", protocol, auth, self.host, self.port)
    }

    /// 验证配置有效性
    ///
    /// 检查必填字段是否合法
    pub fn validate(&self) -> Result<(), String> {
        if self.host.is_empty() {
            return Err("代理服务器地址不能为空".to_string());
        }

        if self.port == 0 {
            return Err("代理端口号无效".to_string());
        }

        // 验证主机名格式（简单检查）
        if self.host.contains(' ') {
            return Err("代理服务器地址格式错误".to_string());
        }

        Ok(())
    }

    /// 创建新的代理配置（仅测试环境使用）
    #[cfg(test)]
    pub fn new(
        proxy_type: ProxyType,
        host: String,
        port: u16,
        username: Option<String>,
        password: Option<String>,
    ) -> Self {
        Self {
            enabled: true,
            proxy_type,
            host,
            port,
            username,
            password,
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_proxy_url_without_auth() {
        let proxy = ProxySettings::new(
            ProxyType::Http,
            "127.0.0.1".to_string(),
            8080,
            None,
            None,
        );
        assert_eq!(proxy.to_proxy_url(), "http://127.0.0.1:8080");
    }

    #[test]
    fn test_proxy_url_with_auth() {
        let proxy = ProxySettings::new(
            ProxyType::Socks5,
            "proxy.example.com".to_string(),
            1080,
            Some("user".to_string()),
            Some("pass".to_string()),
        );
        assert_eq!(proxy.to_proxy_url(), "socks5://user:pass@proxy.example.com:1080");
    }

    #[test]
    fn test_validate_empty_host() {
        let mut proxy = ProxySettings::default();
        proxy.enabled = true;
        proxy.port = 8080;
        assert!(proxy.validate().is_err());
    }

    #[test]
    fn test_validate_zero_port() {
        let mut proxy = ProxySettings::default();
        proxy.enabled = true;
        proxy.host = "127.0.0.1".to_string();
        assert!(proxy.validate().is_err());
    }
}
