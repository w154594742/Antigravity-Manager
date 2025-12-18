use crate::models::ProxySettings;
use crate::modules::{http_client::HttpClientFactory, config};
use tauri::State;

/// 保存网络代理设置
///
/// 执行流程：
/// 1. 验证配置有效性
/// 2. 测试代理连接（如果启用）
/// 3. 更新客户端工厂配置（立即生效）
/// 4. 持久化到配置文件
///
/// # 错误
/// - 配置验证失败
/// - 代理连接测试失败
/// - 保存配置文件失败
#[tauri::command]
pub async fn save_proxy_settings(
    settings: ProxySettings,
    factory: State<'_, HttpClientFactory>,
) -> Result<(), String> {
    tracing::info!("保存网络代理设置: enabled={}, type={:?}", settings.enabled, settings.proxy_type);

    // 1. 如果启用代理，先验证和测试
    if settings.enabled {
        // 验证配置格式
        settings.validate()
            .map_err(|e| format!("配置验证失败: {}", e))?;

        // 测试代理连接
        tracing::info!("开始测试代理连接...");
        factory.test_proxy(&settings).await
            .map_err(|e| format!("代理连接测试失败: {}", e))?;
        tracing::info!("代理连接测试成功");
    }

    // 2. 更新客户端工厂配置（立即生效）
    factory.update_proxy(if settings.enabled {
        Some(settings.clone())
    } else {
        None
    })
    .map_err(|e| format!("更新客户端工厂配置失败: {}", e))?;

    // 3. 持久化到配置文件
    let mut config = config::load_app_config()
        .map_err(|e| format!("加载配置文件失败: {}", e))?;

    config.network_proxy = settings.clone();

    config::save_app_config(&config)
        .map_err(|e| format!("保存配置文件失败: {}", e))?;

    tracing::info!("网络代理设置已保存并生效");
    Ok(())
}

/// 获取当前网络代理设置
///
/// 从配置文件读取代理配置
#[tauri::command]
pub fn get_proxy_settings() -> Result<ProxySettings, String> {
    let config = config::load_app_config()
        .map_err(|e| format!("加载配置文件失败: {}", e))?;

    Ok(config.network_proxy)
}

/// 测试代理连接（不保存配置）
///
/// 用于在保存前验证代理是否可用
///
/// # 参数
/// - `settings`: 待测试的代理配置
///
/// # 返回
/// - 成功时返回提示信息
/// - 失败时返回错误详情
#[tauri::command]
pub async fn test_proxy_connection(
    settings: ProxySettings,
    factory: State<'_, HttpClientFactory>,
) -> Result<String, String> {
    tracing::info!("测试代理连接: {}:{}", settings.host, settings.port);

    factory.test_proxy(&settings).await
        .map_err(|e| format!("测试失败: {}", e))?;

    Ok("代理连接成功！".to_string())
}
