use serde::{Deserialize, Serialize};
use crate::proxy::ProxyConfig;
use super::proxy::ProxySettings;

/// 应用配置
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AppConfig {
    pub language: String,
    pub theme: String,
    pub auto_refresh: bool,
    pub refresh_interval: i32,  // 分钟
    pub auto_sync: bool,
    pub sync_interval: i32,  // 分钟
    pub default_export_path: Option<String>,
    /// API 反代服务配置
    #[serde(default)]
    pub proxy: ProxyConfig,
    /// 网络代理配置
    #[serde(default)]
    pub network_proxy: ProxySettings,
}

impl AppConfig {
    pub fn new() -> Self {
        Self {
            language: "zh-CN".to_string(),
            theme: "system".to_string(),
            auto_refresh: false,
            refresh_interval: 15,
            auto_sync: false,
            sync_interval: 5,
            default_export_path: None,
            proxy: ProxyConfig::default(),
            network_proxy: ProxySettings::default(),
        }
    }
}

impl Default for AppConfig {
    fn default() -> Self {
        Self::new()
    }
}
