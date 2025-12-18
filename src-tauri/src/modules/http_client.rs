use std::sync::{Arc, RwLock};
use reqwest::{Client, Proxy};
use crate::models::ProxySettings;
use anyhow::{Result, Context};

/// HTTP 客户端工厂
///
/// 职责：根据代理配置构建 reqwest::Client 实例
/// 特性：
/// - 线程安全（Arc<RwLock<>>）
/// - 支持热更新配置
/// - 支持代理连接测试
#[derive(Clone)]
pub struct HttpClientFactory {
    /// 代理配置（线程安全的共享状态）
    proxy_config: Arc<RwLock<Option<ProxySettings>>>,
}

impl HttpClientFactory {
    /// 创建新的工厂实例（默认无代理）
    pub fn new() -> Self {
        Self {
            proxy_config: Arc::new(RwLock::new(None)),
        }
    }

    /// 从现有配置创建工厂实例（仅测试环境使用）
    #[cfg(test)]
    pub fn with_config(config: Option<ProxySettings>) -> Self {
        Self {
            proxy_config: Arc::new(RwLock::new(config)),
        }
    }

    /// 构建 HTTP 客户端
    ///
    /// 自动应用当前代理配置，如果代理配置无效会返回错误
    ///
    /// # 错误
    /// - 读取配置锁失败
    /// - 创建代理对象失败
    /// - 构建客户端失败
    pub fn build_client(&self) -> Result<Client> {
        let config = self.proxy_config.read()
            .map_err(|e| anyhow::anyhow!("读取代理配置锁失败: {}", e))?;

        let mut builder = Client::builder()
            .timeout(std::time::Duration::from_secs(30))
            .connect_timeout(std::time::Duration::from_secs(10));

        // 如果启用代理，则配置代理
        if let Some(proxy_settings) = &*config {
            if proxy_settings.enabled {
                tracing::info!(
                    "应用网络代理配置: {:?} {}:{}",
                    proxy_settings.proxy_type,
                    proxy_settings.host,
                    proxy_settings.port
                );
                let proxy = self.create_proxy(proxy_settings)?;
                builder = builder.proxy(proxy);
            }
        }

        builder.build()
            .context("构建 HTTP 客户端失败")
    }

    /// 创建 reqwest::Proxy 对象
    ///
    /// 根据代理类型构建不同的 Proxy 实例
    fn create_proxy(&self, settings: &ProxySettings) -> Result<Proxy> {
        let proxy_url = settings.to_proxy_url();

        // 根据代理类型创建不同的 Proxy
        let proxy = match settings.proxy_type {
            crate::models::ProxyType::Http => {
                Proxy::http(&proxy_url)
                    .context("创建 HTTP 代理失败")?
            },
            crate::models::ProxyType::Socks5 => {
                Proxy::all(&proxy_url)
                    .context("创建 SOCKS5 代理失败")?
            },
        };

        Ok(proxy)
    }

    /// 热更新代理配置（立即生效）
    ///
    /// 更新后，下次调用 `build_client()` 会使用新配置
    ///
    /// # 错误
    /// - 写入配置锁失败
    pub fn update_proxy(&self, new_config: Option<ProxySettings>) -> Result<()> {
        let mut config = self.proxy_config.write()
            .map_err(|e| anyhow::anyhow!("更新代理配置锁失败: {}", e))?;

        *config = new_config.clone();

        if let Some(proxy) = &new_config {
            if proxy.enabled {
                tracing::info!("代理配置已更新: {}:{}", proxy.host, proxy.port);
            } else {
                tracing::info!("代理已禁用");
            }
        } else {
            tracing::info!("代理配置已清除");
        }

        Ok(())
    }

    /// 获取当前代理配置（仅测试环境使用）
    #[cfg(test)]
    pub fn get_proxy_config(&self) -> Option<ProxySettings> {
        self.proxy_config.read().ok()?.clone()
    }

    /// 测试代理连接（验证可用性）
    ///
    /// 尝试通过代理访问测试 URL，验证代理是否可用
    ///
    /// # 参数
    /// - `settings`: 待测试的代理配置
    ///
    /// # 错误
    /// - 代理配置无效
    /// - 代理连接失败
    /// - 测试请求超时
    pub async fn test_proxy(&self, settings: &ProxySettings) -> Result<()> {
        // 先验证配置格式
        settings.validate()
            .map_err(|e| anyhow::anyhow!("代理配置验证失败: {}", e))?;

        // 临时构建客户端测试
        let proxy = self.create_proxy(settings)?;
        let client = Client::builder()
            .proxy(proxy)
            .timeout(std::time::Duration::from_secs(10))
            .connect_timeout(std::time::Duration::from_secs(5))
            .build()
            .context("构建测试客户端失败")?;

        // 尝试连接测试 URL（使用 Google，因为项目主要与 Google API 交互）
        let test_url = "https://www.google.com";
        tracing::info!("测试代理连接: {}", test_url);

        let response = client.get(test_url)
            .send()
            .await
            .context("代理连接测试失败：无法访问测试 URL，请检查代理服务器是否正常运行")?;

        if !response.status().is_success() {
            anyhow::bail!(
                "代理测试失败：HTTP 状态码 {}",
                response.status()
            );
        }

        tracing::info!("代理连接测试成功");
        Ok(())
    }
}

impl Default for HttpClientFactory {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::models::ProxyType;

    #[test]
    fn test_factory_creation() {
        let factory = HttpClientFactory::new();
        assert!(factory.get_proxy_config().is_none());
    }

    #[test]
    fn test_factory_with_config() {
        let proxy = ProxySettings::new(
            ProxyType::Http,
            "127.0.0.1".to_string(),
            8080,
            None,
            None,
        );
        let factory = HttpClientFactory::with_config(Some(proxy.clone()));
        assert!(factory.get_proxy_config().is_some());
    }

    #[test]
    fn test_update_proxy() {
        let factory = HttpClientFactory::new();
        let proxy = ProxySettings::new(
            ProxyType::Http,
            "127.0.0.1".to_string(),
            8080,
            None,
            None,
        );

        factory.update_proxy(Some(proxy.clone())).unwrap();
        let config = factory.get_proxy_config().unwrap();
        assert_eq!(config.host, "127.0.0.1");
        assert_eq!(config.port, 8080);
    }

    #[test]
    fn test_build_client_without_proxy() {
        let factory = HttpClientFactory::new();
        let client = factory.build_client();
        assert!(client.is_ok());
    }
}
